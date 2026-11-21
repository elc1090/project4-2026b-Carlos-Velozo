"""Configuração da aplicação."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(nome: str, padrao: bool = False) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "on", "sim"}


def normalizar_database_url(url: str | None) -> str:
    """Converte postgres:// e usa SQLite se DATABASE_URL estiver vazia."""
    if not url or not url.strip():
        return f"sqlite:///{(BASE_DIR / 'mapeiasus_dev.db').as_posix()}"

    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    # Driver explícito para o SQLAlchemy 2.1.
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-troque-esta-chave-antes-de-publicar")

    # Banco de dados
    SQLALCHEMY_DATABASE_URI = normalizar_database_url(os.getenv("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # Cria tabelas em falta no arranque.
    AUTO_CREATE_TABLES = _env_bool("AUTO_CREATE_TABLES", True)

    # true exige login; false mantém a busca pública.
    REQUIRE_LOGIN = _env_bool("REQUIRE_LOGIN", False)

    # Cadastro público por e-mail e senha.
    ALLOW_REGISTRATION = _env_bool("ALLOW_REGISTRATION", True)

    # Upload de imagens das farmácias.
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER") or str(
        BASE_DIR / "static" / "uploads"
    )
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB por requisição

    # Autenticação
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    ADMIN_EMAILS = [
        email.strip().lower()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    ]
    # Admin inicial criado no primeiro deploy.
    ADMIN_BOOTSTRAP_EMAIL = os.getenv("ADMIN_BOOTSTRAP_EMAIL", "").strip().lower()
    ADMIN_BOOTSTRAP_PASSWORD = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "")

    # Sessão / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    # Fallback se o proxy não enviar X-Forwarded-Proto.
    PREFERRED_URL_SCHEME = "https" if SESSION_COOKIE_SECURE else "http"
