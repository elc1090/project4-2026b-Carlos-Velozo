"""Funções utilitárias partilhadas entre rotas e scripts."""

import re
import unicodedata

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def remover_acentos(texto: str | None) -> str:
    """Normaliza texto para busca: sem acentos, minúsculo e sem espaços extra."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sem_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(sem_acentos.lower().split())


def email_valido(email: str | None) -> bool:
    """Validação simples de email (aceita domínios internos como .local)."""
    return bool(_EMAIL_RE.match((email or "").strip()))
