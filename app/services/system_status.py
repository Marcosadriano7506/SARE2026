from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import text

from app.extensions import db
from app.storage.factory import get_storage_service


@dataclass
class SystemStatus:
    database_ok: bool
    database_backend: str
    database_persistent: bool
    storage_provider: str
    storage_configured: bool
    storage_ok: bool
    session_cookie_secure: bool
    homologation: bool
    production_ready: bool
    database_message: str
    storage_message: str


def calculate_system_status(app) -> SystemStatus:
    backend = db.engine.url.get_backend_name()
    database_ok = False
    database_message = ""
    try:
        db.session.execute(text("SELECT 1"))
        database_ok = True
        database_message = "Conexão com o banco confirmada."
    except Exception as exc:
        db.session.rollback()
        database_message = f"Falha de conexão: {exc.__class__.__name__}"

    database_persistent = backend != "sqlite"

    provider = os.getenv("STORAGE_PROVIDER", "LOCAL_HOMOLOGATION").upper()
    if provider == "GOOGLE_DRIVE":
        storage_configured = bool(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
            and os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "").strip()
        )
    else:
        storage_configured = provider == "LOCAL_HOMOLOGATION"

    storage_ok = False
    storage_message = ""
    if storage_configured:
        try:
            storage = get_storage_service(provider)
            details = storage.check_connection()
            storage_ok = True
            storage_message = details or "Armazenamento disponível."
        except Exception as exc:
            storage_message = f"Falha no armazenamento: {exc.__class__.__name__}"
    else:
        storage_message = "Credenciais/pasta raiz ainda não configuradas."

    homologation = (
        os.getenv("ALLOW_HOMOLOGATION_BOOTSTRAP", "false").lower() == "true"
    )
    cookie_secure = bool(app.config.get("SESSION_COOKIE_SECURE"))

    production_ready = all(
        [
            database_ok,
            database_persistent,
            provider == "GOOGLE_DRIVE",
            storage_configured,
            storage_ok,
            cookie_secure,
            not homologation,
        ]
    )

    return SystemStatus(
        database_ok=database_ok,
        database_backend=backend,
        database_persistent=database_persistent,
        storage_provider=provider,
        storage_configured=storage_configured,
        storage_ok=storage_ok,
        session_cookie_secure=cookie_secure,
        homologation=homologation,
        production_ready=production_ready,
        database_message=database_message,
        storage_message=storage_message,
    )
