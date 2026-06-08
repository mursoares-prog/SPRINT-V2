"""Cria/atualiza o arquivo de usuários (auth_users.json).

Uso:
  python seed_auth.py                      # cria defaults se o arquivo não existir
  python seed_auth.py <usuario> <senha> <admin|projetista>   # adiciona/atualiza um usuário

Rodar a partir da pasta backend/ (com a venv ativa).
"""
import json
import sys
from pathlib import Path

from app.auth import hash_password, users_path

DEFAULTS = [
    ("teste", "teste123", "admin"),            # continuidade do login atual + papel admin
    ("projetista", "projetista123", "projetista"),  # exemplo de projetista
]


def main() -> None:
    path = users_path()
    users = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    if len(sys.argv) == 4:
        username, password, role = sys.argv[1], sys.argv[2], sys.argv[3]
        if role not in ("admin", "projetista"):
            sys.exit("papel deve ser 'admin' ou 'projetista'")
        users[username] = {"passwordHash": hash_password(password), "role": role}
        print(f"Usuário '{username}' ({role}) gravado.")
    elif not users:
        for username, password, role in DEFAULTS:
            users[username] = {"passwordHash": hash_password(password), "role": role}
        print(f"Criados {len(DEFAULTS)} usuários padrão: " + ", ".join(f"{u}/{p} ({r})" for u, p, r in DEFAULTS))
    else:
        print("Arquivo já existe e nenhum usuário informado — nada a fazer.")
        return

    path.write_text(json.dumps(users, indent=2) + "\n", encoding="utf-8")
    print(f"-> {path}")


if __name__ == "__main__":
    main()
