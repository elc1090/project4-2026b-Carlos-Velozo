"""Formulários do painel administrativo (farmácias e medicamentos)."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, FloatField, PasswordField, StringField, SubmitField
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)

from auth.forms import EmailValido
from extensions import db
from models import Farmacia, Medicamento, User


def _limpar(valor):
    """Remove espaços nas pontas de campos de texto."""
    return valor.strip() if isinstance(valor, str) else valor


class UrlImagem:
    """Aceita apenas URL http(s) ou caminho relativo iniciado por `/`."""

    def __call__(self, form, field):
        valor = (field.data or "").strip()
        if not valor:
            return
        if valor.startswith(("/", "http://", "https://")):
            return
        raise ValidationError("Informe uma URL http(s) ou um caminho iniciado por /.")


class ConteudoImagem:
    """Confere os bytes iniciais para rejeitar arquivos que não são imagens."""

    ASSINATURAS = (
        b"\x89PNG\r\n\x1a\n",
        b"\xff\xd8\xff",
    )

    def __call__(self, form, field):
        arquivo = field.data
        if not arquivo or not getattr(arquivo, "filename", ""):
            return

        posicao = arquivo.stream.tell()
        cabecalho = arquivo.stream.read(12)
        arquivo.stream.seek(posicao)

        valido = cabecalho.startswith(self.ASSINATURAS) or (
            cabecalho[:4] == b"RIFF" and cabecalho[8:12] == b"WEBP"
        )
        if not valido:
            raise ValidationError(
                "O arquivo enviado não é uma imagem PNG, JPG ou WEBP válida."
            )


class FarmaciaForm(FlaskForm):
    nome = StringField(
        "Nome da farmácia",
        filters=[_limpar],
        validators=[
            DataRequired(message="Informe o nome da farmácia."),
            Length(max=255),
        ],
    )
    endereco = StringField(
        "Endereço",
        filters=[_limpar],
        validators=[
            DataRequired(message="Informe o endereço."),
            Length(max=255),
        ],
    )
    bairro = StringField(
        "Bairro",
        filters=[_limpar],
        validators=[Optional(), Length(max=120)],
    )
    lat = FloatField(
        "Latitude",
        validators=[
            InputRequired(message="Selecione um ponto no mapa."),
            NumberRange(min=-90, max=90, message="A latitude deve ficar entre -90 e 90."),
        ],
    )
    lng = FloatField(
        "Longitude",
        validators=[
            InputRequired(message="Selecione um ponto no mapa."),
            NumberRange(
                min=-180,
                max=180,
                message="A longitude deve ficar entre -180 e 180.",
            ),
        ],
    )
    imagem_url = StringField(
        "URL da imagem",
        filters=[_limpar],
        validators=[Optional(), Length(max=500), UrlImagem()],
    )
    imagem = FileField(
        "Foto da farmácia",
        validators=[
            FileAllowed(
                ["png", "jpg", "jpeg", "webp"],
                "Envie uma imagem PNG, JPG ou WEBP.",
            ),
            ConteudoImagem(),
        ],
    )
    remover_imagem = BooleanField("Remover foto atual")
    telefone = StringField(
        "Telefone",
        filters=[_limpar],
        validators=[Optional(), Length(max=40)],
    )
    horario = StringField(
        "Horário de atendimento",
        filters=[_limpar],
        validators=[Optional(), Length(max=120)],
    )
    ativo = BooleanField("Farmácia ativa", default=True)
    submit = SubmitField("Salvar farmácia")

    def __init__(self, *args, farmacia_id: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.farmacia_id = farmacia_id

    def validate_nome(self, campo):
        consulta = Farmacia.query.filter(
            db.func.lower(Farmacia.nome) == (campo.data or "").lower()
        )
        if self.farmacia_id is not None:
            consulta = consulta.filter(Farmacia.id != self.farmacia_id)
        if consulta.first() is not None:
            raise ValidationError("Já existe uma farmácia com este nome.")


class MedicamentoForm(FlaskForm):
    nome = StringField(
        "Nome do medicamento",
        filters=[_limpar],
        validators=[
            DataRequired(message="Informe o nome do medicamento."),
            Length(max=255),
        ],
    )
    apresentacao = StringField(
        "Apresentação",
        filters=[_limpar],
        validators=[Optional(), Length(max=120)],
    )
    ativo = BooleanField("Medicamento ativo", default=True)
    submit = SubmitField("Salvar medicamento")

    def __init__(self, *args, medicamento_id: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.medicamento_id = medicamento_id

    def validate_nome(self, campo):
        consulta = Medicamento.query.filter(
            db.func.lower(Medicamento.nome) == (campo.data or "").lower()
        )
        if self.medicamento_id is not None:
            consulta = consulta.filter(Medicamento.id != self.medicamento_id)
        if consulta.first() is not None:
            raise ValidationError("Já existe um medicamento com este nome.")


class AdministradorForm(FlaskForm):
    nome = StringField(
        "Nome",
        filters=[_limpar],
        validators=[Optional(), Length(max=120)],
    )
    email = StringField(
        "E-mail",
        filters=[_limpar],
        validators=[
            DataRequired(message="Informe o e-mail."),
            EmailValido(),
            Length(max=255),
        ],
    )
    senha = PasswordField(
        "Senha inicial",
        validators=[Optional(), Length(min=8, max=128,
                    message="A senha deve ter entre 8 e 128 caracteres.")],
    )
    submit = SubmitField("Adicionar administrador")

    def validate_email(self, campo):
        email = (campo.data or "").strip().lower()
        usuario = (
            db.session.query(User)
            .filter(db.func.lower(User.email) == email)
            .first()
        )
        if usuario is not None and usuario.is_admin:
            raise ValidationError("Este e-mail já é administrador.")
