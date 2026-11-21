"""Formulários de autenticação."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import (
    DataRequired,
    EqualTo,
    Length,
    Optional,
    ValidationError,
)

from extensions import db
from models import User
from utils import email_valido


def _limpar(valor):
    return valor.strip() if isinstance(valor, str) else valor


class EmailValido:
    """Valida o formato do email sem rejeitar domínios internos (.local)."""

    def __init__(self, message: str = "E-mail inválido."):
        self.message = message

    def __call__(self, form, field):
        if not email_valido(field.data):
            raise ValidationError(self.message)


class LoginForm(FlaskForm):
    email = StringField(
        "E-mail",
        filters=[_limpar],
        validators=[
            DataRequired(message="Informe seu e-mail."),
            EmailValido(),
            Length(max=255),
        ],
    )
    senha = PasswordField(
        "Senha",
        validators=[
            DataRequired(message="Informe sua senha."),
            Length(max=128),
        ],
    )
    lembrar = BooleanField("Lembrar de mim")
    submit = SubmitField("Entrar")


class RegisterForm(FlaskForm):
    nome = StringField(
        "Nome",
        filters=[_limpar],
        validators=[Optional(), Length(max=120)],
    )
    email = StringField(
        "E-mail",
        filters=[_limpar],
        validators=[
            DataRequired(message="Informe seu e-mail."),
            EmailValido(),
            Length(max=255),
        ],
    )
    senha = PasswordField(
        "Senha",
        validators=[
            DataRequired(message="Informe uma senha."),
            Length(
                min=8,
                max=128,
                message="A senha deve ter entre 8 e 128 caracteres.",
            ),
        ],
    )
    confirmar_senha = PasswordField(
        "Confirmar senha",
        validators=[
            DataRequired(message="Confirme a senha."),
            EqualTo("senha", message="As senhas não coincidem."),
        ],
    )
    submit = SubmitField("Criar conta")

    def validate_email(self, campo):
        email = (campo.data or "").strip().lower()
        existente = (
            db.session.query(User)
            .filter(db.func.lower(User.email) == email)
            .first()
        )
        if existente is not None:
            raise ValidationError("Já existe uma conta com este e-mail.")
