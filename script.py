import subprocess, re, json, psycopg2, requests
from psycopg2 import sql

con_params = {
    'host': 'localhost',
    'port': '5432',
    'dbname': 'stat',
    'user': 'grafana_user',
    'password': 'grafana_password'
}

try:
  con = psycopg2.connect(**con_params)
  print("Connexion réussie")
except Exception as e:
  print(f"Erreur de connexion : {e}")

response = requests.get("http://localhost:3000/api/datasources").json()

FILE_CHANGED = r"^ +([^ ]+) * \| +([0-9]+) [\+]*[-]*$"
ALL_CHANGES = r"^ ([0-9]+) file[s]? changed, (([0-9]+) insertion[s]?\(\+\), )?(([0-9]+) deletion[s]?\(-\))?$"
AUTHOR = r"Author: [^<]+<([^@]+)@[^>]+>$"
DATASOURCE_UID = response[0]['uid']

class Repo:
  def __init__(this, url) -> None:
    this.url = url
    this.name = re.split(r"\/", url)[-1]
    this.path = "/tmp/" + this.name
    this.clone()
    cur = con.cursor()
    drop_table = sql.SQL('''
    DROP TABLE IF EXISTS {}
    ''').format(sql.Identifier(this.name))
    create_table_query = sql.SQL('''
    CREATE TABLE IF NOT EXISTS {} (
        id SERIAL PRIMARY KEY,
        sha VARCHAR(255) NOT NULL,
        file_edited INT NOT NULL,
        addition INT NOT NULL,
        deletion INT NOT NULL,
        author VARCHAR(255) NOT NULL,
        date TIMESTAMP,
        detail JSONB
    );
    ''').format(sql.Identifier(this.name))

    cur.execute(drop_table)
    cur.execute(create_table_query)
    con.commit()
    this.listCommit()
    for commit in this.commits: commit.insert(this.name, cur)
    con.commit()
    this.createDashboard()
  
  def createDashboard(this):
    subprocess.run(["cp", "./dashboard.json", "dashboard/" + this.name + ".json"])
    subprocess.run(["sed", "-i", "s/UID_DATASOURCE/" + DATASOURCE_UID + "/g", "dashboard/" + this.name + ".json"])
    subprocess.run(["sed", "-i", "s/APPLICATION_NAME/" + this.name + "/g", "dashboard/" + this.name + ".json"])
    with open("dashboard/" + this.name + ".json", 'r') as file:
      file_content = file.read()
    headers = {
      'Content-Type': 'application/json'
    }
    requests.post("http://localhost:3000/api/dashboards/db", headers=headers, data=file_content)
  
  def clone(this):
    subprocess.run(["git", "clone", this.url, this.path])
    print(this.url, " cloned")
  
  def listCommit(this):
    commits = subprocess.run(["git", "log", '--format="%H"'], capture_output=True, cwd=this.path)
    commits = commits.stdout.decode().split("\n")
    commits = list(map(lambda commit: commit.replace('"', ''), commits))
    commits.pop()
    this.commits = list(map(lambda commit: this.Commit(commit, this.path), commits))

  class Commit:
    def __init__(this, sha, path) -> None:
      this.data = {}
      this.data["sha"] = sha
      this.path = path
      this.data["files"] = []
      this.data["total"] = {
          "files changed": 0,
          "addition": 0,
          "deletion": 0
        }
      this.analysis()

    def analysis(this):
      content = subprocess.run(["git", "show", "--stat", this.data["sha"]], capture_output=True, cwd=this.path).stdout.decode()
      try:
        this.data["files"] = list(map(lambda el: {"file": el[0], "modifications": el[1]}, re.findall(FILE_CHANGED, content, re.MULTILINE)))
        total = re.search(ALL_CHANGES, content, re.MULTILINE)
        this.data["total"] = {
          "files changed": total.group(1),
          "addition": total.group(3) if total.group(3) is not None else 0,
          "deletion": total.group(5) if total.group(5) is not None else 0
        }
      except:
        pass
      try:
        this.data["author"] = re.search(AUTHOR, content, re.MULTILINE).group(1)
      except:
        this.data["author"] = "None"
      this.data["timeStamp"] = subprocess.run(["git", "show", "-s", "--format=%ci", this.data["sha"]], capture_output=True, cwd=this.path).stdout.decode()[:-1].split(" ")[0]
    
    def insert(this, table_name, cur):
      insert_query = sql.SQL('''
      INSERT INTO {} (sha, file_edited, addition, deletion, author, date, detail)
      VALUES (%s, %s, %s, %s, %s, %s, %s);
      ''').format(sql.Identifier(table_name))
      cur.execute(insert_query, (
        this.data["sha"],
        this.data["total"]["files changed"],
        this.data["total"]["addition"],
        this.data["total"]["deletion"],
        this.data["author"],
        this.data["timeStamp"],
        json.dumps(this.data["files"])
      ))
  
    def toString(this):
      return json.dumps(this.data)
      

repos = [
  "repo.git"
]

for repo in repos: Repo(repo)
con.close()