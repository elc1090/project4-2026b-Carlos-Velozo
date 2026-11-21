"""Rotas públicas: página inicial, busca de medicamentos e histórico."""

from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, send_from_directory
from flask_login import current_user
from werkzeug.utils import secure_filename

from admin.uploads import EXTENSOES_PERMITIDAS, pasta_uploads
from extensions import db
from historico import cliente_id_atual, historico_recente
from models import Farmacia, FarmaciaMedicamento, HistoricoBusca, Medicamento
from utils import remover_acentos

bp = Blueprint("public", __name__)


def _para_float(valor):
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/health")
def health():
    """Health check."""
    return jsonify({"status": "ok"})


@bp.get("/uploads/farmacias/<nome>")
def foto_farmacia(nome):
    """Serve as fotos enviadas pelo painel."""
    nome_seguro = secure_filename(nome)
    if (
        nome_seguro != nome
        or Path(nome).suffix.lower() not in EXTENSOES_PERMITIDAS
    ):
        return jsonify({"error": "Imagem não encontrada."}), 404
    return send_from_directory(pasta_uploads(), nome_seguro)


@bp.get("/api/buscar")
def buscar():
    """Farmácias ativas onde o medicamento pesquisado está disponível."""
    termo = (request.args.get("medicamento") or "").strip()
    if not termo:
        return jsonify([])

    termo_norm = remover_acentos(termo)

    farmacias = (
        db.session.query(Farmacia)
        .join(FarmaciaMedicamento, FarmaciaMedicamento.farmacia_id == Farmacia.id)
        .join(Medicamento, Medicamento.id == FarmaciaMedicamento.medicamento_id)
        .filter(
            Medicamento.nome_busca.like(f"%{termo_norm}%"),
            Medicamento.ativo.is_(True),
            Farmacia.ativo.is_(True),
            FarmaciaMedicamento.disponivel.is_(True),
        )
        .order_by(Farmacia.nome)
        .distinct()
        .all()
    )

    return jsonify([farmacia.to_public_dict() for farmacia in farmacias])


@bp.get("/api/sugestoes")
def sugestoes():
    """Sugestões para o autocomplete do campo de busca."""
    termo = (request.args.get("q") or "").strip()
    if not termo:
        return jsonify([])

    termo_norm = remover_acentos(termo)

    nomes = (
        db.session.query(Medicamento.nome)
        .filter(
            Medicamento.nome_busca.like(f"%{termo_norm}%"),
            Medicamento.ativo.is_(True),
        )
        .distinct()
        .order_by(Medicamento.nome)
        .limit(8)
        .all()
    )

    return jsonify([nome for (nome,) in nomes])


@bp.post("/api/historico")
def salvar_historico():
    """Registra a pesquisa para o painel de 'Pesquisas Recentes'."""
    data = request.get_json(silent=True) or {}
    termo = (data.get("termo") or "").strip()

    if not termo:
        return jsonify({"error": "Termo de busca vazio"}), 400

    registro = HistoricoBusca(
        termo_busca=termo[:255],
        lat_usuario=_para_float(data.get("lat")),
        lng_usuario=_para_float(data.get("lng")),
        user_id=current_user.id if current_user.is_authenticated else None,
        cliente_id=cliente_id_atual(),
    )
    db.session.add(registro)
    db.session.commit()

    return jsonify({"status": "sucesso", "mensagem": "Busca registrada no histórico"})


@bp.get("/api/historico")
def obter_historico():
    """Devolve somente as últimas buscas do cliente autenticado."""
    registros = historico_recente(5)
    return jsonify([registro.to_public_dict() for registro in registros])
