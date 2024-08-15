{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    pkgs.python39
    pkgs.python39Packages.psycopg2
    pkgs.python39Packages.requests
  ];

  # Vous pouvez aussi ajouter d'autres dépendances Python ici
  # buildInputs = [ pkgs.python39Packages.requests pkgs.python39Packages.numpy ];
}
