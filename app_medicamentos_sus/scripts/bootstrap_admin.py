"""Cria o admin inicial com ADMIN_BOOTSTRAP_EMAIL e ADMIN_BOOTSTRAP_PASSWORD.

Uso: python scripts/bootstrap_admin.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models import User  # noqa: E402
from utils import email_valido  # noqa: E402


def run() -> None:
    app = create_app()
    email = (app.config.get("ADMIN_BOOTSTRAP_EMAIL") or "").strip().lower()
    senha = app.config.get("ADMIN_BOOTSTRAP_PASSWORD") or ""

    if not email and not senha:
        print("Bootstrap ignorado: ADMIN_BOOTSTRAP_EMAIL/PASSWORD não definidos.")
        return
    if not email_valido(email):
        raise SystemExit("ADMIN_BOOTSTRAP_EMAIL inválido.")
    if len(senha) < 8:
        raise SystemExit("ADMIN_BOOTSTRAP_PASSWORD deve ter pelo menos 8 caracteres.")

    with app.app_context():
        usuario = (
            db.session.query(User)
            .filter(db.func.lower(User.email) == email)
            .first()
        )
        if usuario is None:
            usuario = User(email=email, role="admin", ativo=True)
            db.session.add(usuario)
        usuario.role = "admin"
        usuario.ativo = True
        usuario.definir_senha(senha)
        db.session.commit()
        print(f"Administrador pronto: {email}")


if __name__ == "__main__":
    run()
