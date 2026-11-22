"""Extensões Flask partilhadas pela aplicação."""

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Faça login para continuar."
login_manager.login_message_category = "warning"
# "strong" remove a sessão se o X-Forwarded-For variar entre requisições no proxy.
login_manager.session_protection = "basic"

csrf = CSRFProtect()
