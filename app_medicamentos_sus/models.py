"""Modelos SQLAlchemy do MapeiaSUS."""

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


def utcnow() -> datetime:
    """Data/hora UTC sem timezone, compatível com SQLite e PostgreSQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(120))
    senha_hash = db.Column(db.String(255))
    google_sub = db.Column(db.String(255), unique=True)
    role = db.Column(db.String(20), nullable=False, default="user")
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=utcnow)

    @property
    def is_active(self) -> bool:  # usado pelo Flask-Login
        return bool(self.ativo)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def definir_senha(self, senha: str) -> None:
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha: str) -> bool:
        return bool(self.senha_hash) and check_password_hash(self.senha_hash, senha)

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"


class Farmacia(db.Model):
    __tablename__ = "farmacias"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), unique=True, nullable=False)
    endereco = db.Column(db.String(255), nullable=False)
    bairro = db.Column(db.String(120))
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    imagem_url = db.Column(db.String(500))
    telefone = db.Column(db.String(40))
    horario = db.Column(db.String(120))
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=utcnow)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    criado_por = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    vinculos = db.relationship(
        "FarmaciaMedicamento",
        back_populates="farmacia",
        cascade="all, delete-orphan",
    )

    def to_public_dict(self) -> dict:
        """Formato consumido por `static/js/main.js`."""
        return {
            "id": self.id,
            "nome": self.nome,
            "endereco": self.endereco,
            "bairro": self.bairro,
            "lat": self.lat,
            "lng": self.lng,
            "imagem": self.imagem_url,
        }

    def __repr__(self) -> str:
        return f"<Farmacia {self.nome}>"


class Medicamento(db.Model):
    __tablename__ = "medicamentos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), unique=True, nullable=False)
    nome_busca = db.Column(db.String(255), nullable=False, index=True)
    apresentacao = db.Column(db.String(120))
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=utcnow)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    vinculos = db.relationship(
        "FarmaciaMedicamento",
        back_populates="medicamento",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Medicamento {self.nome}>"


class FarmaciaMedicamento(db.Model):
    __tablename__ = "farmacia_medicamento"

    farmacia_id = db.Column(
        db.Integer,
        db.ForeignKey("farmacias.id", ondelete="CASCADE"),
        primary_key=True,
    )
    medicamento_id = db.Column(
        db.Integer,
        db.ForeignKey("medicamentos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    disponivel = db.Column(db.Boolean, nullable=False, default=True)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    atualizado_por = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    farmacia = db.relationship("Farmacia", back_populates="vinculos")
    medicamento = db.relationship("Medicamento", back_populates="vinculos")

    def __repr__(self) -> str:
        return f"<FarmaciaMedicamento {self.farmacia_id}:{self.medicamento_id}>"


class HistoricoBusca(db.Model):
    __tablename__ = "historico_buscas"

    id = db.Column(db.Integer, primary_key=True)
    termo_busca = db.Column(db.String(255), nullable=False)
    data_hora = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    # "u:<id>" para contas, "s:<uuid>" para visitantes.
    cliente_id = db.Column(db.String(64), index=True)
    lat_usuario = db.Column(db.Float)
    lng_usuario = db.Column(db.Float)

    def to_public_dict(self) -> dict:
        # Formato de data esperado por main.js.
        return {
            "termo_busca": self.termo_busca,
            "data_hora": self.data_hora.strftime("%Y-%m-%d %H:%M:%S")
            if self.data_hora
            else None,
        }

    def __repr__(self) -> str:
        return f"<HistoricoBusca {self.termo_busca!r}>"
