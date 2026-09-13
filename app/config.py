import os


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "sqlite:///sare_dev.db")
    if value.startswith("postgres://"):
        value = value.replace("postgres://", "postgresql+psycopg://", 1)
    elif value.startswith("postgresql://") and "+psycopg" not in value:
        value = value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "10")) * 1024 * 1024
