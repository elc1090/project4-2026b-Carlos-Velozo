"""Histórico de buscas por cliente."""

import uuid

from flask import session
from flask_login import current_user
from sqlalchemy import func

from extensions import db
from models import HistoricoBusca

_CHAVE_SESSAO = "_historico_cliente_id"


def cliente_id_atual() -> str:
    """Devolve o identificador estável do dono do histórico atual."""
    if current_user.is_authenticated:
        return f"u:{current_user.id}"

    identificador = session.get(_CHAVE_SESSAO)
    if not identificador:
        identificador = f"s:{uuid.uuid4().hex}"
        session[_CHAVE_SESSAO] = identificador
    return identificador


def historico_recente(limite: int = 5) -> list[HistoricoBusca]:
    """Últimas buscas do cliente atual, da mais nova para a mais antiga."""
    return (
        HistoricoBusca.query.filter_by(cliente_id=cliente_id_atual())
        .order_by(HistoricoBusca.id.desc())
        .limit(limite)
        .all()
    )


def _ranking_termos(cliente_id: str | None, limite: int):
    """Consulta base do ranking; `cliente_id=None` agrega todos os clientes."""
    consulta = db.session.query(
        func.lower(HistoricoBusca.termo_busca).label("termo"),
        func.count(HistoricoBusca.id).label("total"),
    )
    if cliente_id is not None:
        consulta = consulta.filter(HistoricoBusca.cliente_id == cliente_id)
    else:
        # Registros legados sem dono ficam de fora do ranking.
        consulta = consulta.filter(HistoricoBusca.cliente_id.is_not(None))
    return (
        consulta.group_by(func.lower(HistoricoBusca.termo_busca))
        .order_by(
            func.count(HistoricoBusca.id).desc(),
            func.lower(HistoricoBusca.termo_busca),
        )
        .limit(limite)
        .all()
    )


def termos_mais_pesquisados(limite: int = 5):
    """Ranking de termos buscados apenas pelo cliente atual."""
    return _ranking_termos(cliente_id_atual(), limite)


def termos_mais_pesquisados_geral(limite: int = 5):
    """Ranking global para o dashboard, sem identificar clientes."""
    return _ranking_termos(None, limite)
