from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import text

from app.extensions import db
from app.storage.factory import get_storage_service
from app.storage.google_drive import (
    oauth_environment_configured,
    service_account_environment_configured,
)


@dataclass
class SystemStatus:
    database_ok: bool
    database_backend: str
    database_persistent: bool
    database_schema: str | None
    expected_schema: str | None
    schema_ok: bool
    storage_provider: str
    storage_configured: bool
    storage_ok: bool
    session_cookie_secure: bool
    production_environment: bool
    production_ready: bool
    database_message: str
    storage_message: str


def calculate_system_status(app) -> SystemStatus:
    backend = db.engine.url.get_backend_name()
    database_ok = False
    database_schema = None
    database_message = ""
    try:
        db.session.execute(text("SELECT 1"))
        database_ok = True
        if backend == "postgresql":
            database_schema = db.session.execute(
                text("SELECT current_schema()")
            ).scalar()
        database_message = "Conexão com o banco confirmada."
    except Exception as exc:
        db.session.rollback()
        database_message = f"Falha de conexão: {exc.__class__.__name__}"

    database_persistent = backend == "postgresql"
    expected_schema = os.getenv("EXPECTED_DB_SCHEMA", "").strip() or None
    schema_ok = (
        database_schema == expected_schema
        if expected_schema
        else database_schema is not None
    )

    provider = os.getenv("STORAGE_PROVIDER", "").upper()
    root_configured = bool(
        os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "").strip()
        or os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_NAME", "").strip()
    )
    storage_configured = (
        provider == "GOOGLE_DRIVE"
        and root_configured
        and (
            oauth_environment_configured()
            or service_account_environment_configured()
        )
    )

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
        storage_message = "Credenciais ou pasta raiz do Drive não configuradas."

    cookie_secure = bool(app.config.get("SESSION_COOKIE_SECURE"))
    production_environment = (
        os.getenv("SARE_ENVIRONMENT", "").strip().lower() == "production"
    )

    production_ready = all(
        [
            production_environment,
            database_ok,
            database_persistent,
            schema_ok,
            provider == "GOOGLE_DRIVE",
            storage_configured,
            storage_ok,
            cookie_secure,
        ]
    )

    return SystemStatus(
        database_ok=database_ok,
        database_backend=backend,
        database_persistent=database_persistent,
        database_schema=database_schema,
        expected_schema=expected_schema,
        schema_ok=schema_ok,
        storage_provider=provider,
        storage_configured=storage_configured,
        storage_ok=storage_ok,
        session_cookie_secure=cookie_secure,
        production_environment=production_environment,
        production_ready=production_ready,
        database_message=database_message,
        storage_message=storage_message,
    )
