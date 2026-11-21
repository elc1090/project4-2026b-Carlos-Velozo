"""Verificação de ID tokens do Google Identity Services."""

from flask import current_app, has_app_context
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

ISSUERS_VALIDOS = frozenset({"accounts.google.com", "https://accounts.google.com"})

# Tolera relógios locais alguns segundos atrás do Google.
TOLERANCIA_RELOGIO_SEGUNDOS = 60


def verificar_credencial_google(credential: str, client_id: str) -> dict | None:
    """Valida o ID token e devolve os dados, ou None se inválido."""
    if not credential or not client_id:
        return None

    def falhar(motivo: str) -> None:
        if has_app_context():
            current_app.logger.warning("Google ID token rejeitado: %s", motivo)

    try:
        info = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            audience=client_id,
            clock_skew_in_seconds=TOLERANCIA_RELOGIO_SEGUNDOS,
        )
    except (GoogleAuthError, TypeError, ValueError) as erro:
        falhar(f"verificação falhou ({type(erro).__name__}: {erro})")
        return None

    if info.get("iss") not in ISSUERS_VALIDOS:
        falhar("emissor inválido")
        return None
    if info.get("email_verified") not in (True, "true"):
        falhar("e-mail não verificado")
        return None
    if not info.get("sub") or not info.get("email"):
        falhar("sub/e-mail ausente")
        return None

    return info
