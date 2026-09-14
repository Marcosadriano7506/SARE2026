import os
import re
from datetime import timedelta


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "sqlite:///sare_dev.db")
    if value.startswith("postgres://"):
        value = value.replace("postgres://", "postgresql+psycopg://", 1)
    elif value.startswith("postgresql://") and "+psycopg" not in value:
        value = value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def _database_schema() -> str:
    schema = os.getenv("DB_SCHEMA", "").strip()
    if not schema:
        return ""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
        raise RuntimeError("DB_SCHEMA contém caracteres inválidos.")
    return schema


def _engine_options(database_url: str) -> dict:
    options = {
        "pool_pre_ping": True,
        "pool_recycle": 240,
    }
    if database_url.startswith("postgresql+"):
        options.update(
            {
                "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
                "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "2")),
                "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "15")),
                "pool_use_lifo": True,
            }
        )
        schema = _database_schema()
        if schema:
            options["connect_args"] = {
                "options": f"-csearch_path={schema}",
            }
    return options


_DATABASE_URL = _database_url()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(_DATABASE_URL)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv("SESSION_LIFETIME_HOURS", "8")))
    SESSION_REFRESH_EACH_REQUEST = True
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "10")) * 1024 * 1024
