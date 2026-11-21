"""Upload e remoção das fotos das farmácias."""

from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename

EXTENSOES_PERMITIDAS = {".png", ".jpg", ".jpeg", ".webp"}
# Rota própria para servir fotos fora da pasta do código.
PREFIXO_URL = "/uploads/farmacias/"
PREFIXO_ANTIGO = "/static/uploads/farmacias/"


def pasta_uploads() -> Path:
    """Diretório das fotos, configurável por `UPLOAD_FOLDER`."""
    return Path(current_app.config["UPLOAD_FOLDER"]) / "farmacias"


def _pasta_destino() -> Path:
    pasta = pasta_uploads()
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def guardar_imagem(arquivo) -> str:
    """Guarda o upload com nome único e devolve a URL pública relativa."""
    extensao = Path(secure_filename(arquivo.filename)).suffix.lower()
    if extensao not in EXTENSOES_PERMITIDAS:
        raise ValueError("Formato de imagem não suportado.")

    nome = f"{uuid4().hex}{extensao}"
    destino = _pasta_destino() / nome
    arquivo.save(destino)
    return f"{PREFIXO_URL}{nome}"


def remover_imagem(url: str | None) -> None:
    """Remove apenas ficheiros geridos por este módulo."""
    prefixo = next(
        (p for p in (PREFIXO_URL, PREFIXO_ANTIGO) if url and url.startswith(p)),
        None,
    )
    if prefixo is None:
        return

    nome = secure_filename(url[len(prefixo):])
    if not nome:
        return

    caminho = _pasta_destino() / nome
    try:
        caminho.unlink(missing_ok=True)
    except OSError:
        # Falha ao apagar não impede a operação.
        pass
