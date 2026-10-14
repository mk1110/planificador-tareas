"""Protección CSRF ligera, sin dependencias adicionales.

Genera un token por sesión y lo valida en cada petición con método de escritura
(POST / PUT / PATCH / DELETE). El token viaja en el formulario (campo
``csrf_token``) o en la cabecera ``X-CSRF-Token`` para las llamadas ``fetch``.
"""

from __future__ import annotations

import secrets

from flask import abort, request, session

CSRF_SESSION_KEY = "_csrf_token"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def generate_csrf_token() -> str:
    """Devuelve (creando si hace falta) el token CSRF de la sesión actual."""
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def validate_csrf_token() -> bool:
    """Compara en tiempo constante el token recibido con el de la sesión."""
    expected = session.get(CSRF_SESSION_KEY, "")
    provided = request.headers.get(CSRF_HEADER) or request.form.get("csrf_token", "")
    if not expected or not provided:
        return False
    return secrets.compare_digest(expected, provided)


def register_csrf_protection(app) -> None:
    @app.before_request
    def _csrf_protect():
        if request.method in SAFE_METHODS:
            return None
        if not validate_csrf_token():
            abort(400, description="Token CSRF inválido o ausente. Recarga la página.")
        return None

    @app.context_processor
    def _inject_csrf_token():
        return {"csrf_token": generate_csrf_token}