import pytest

from app import create_app


class UnsafeProductionConfig:
    TESTING = True
    SECRET_KEY = "short"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


def test_production_runtime_refuses_unsafe_configuration(monkeypatch):
    monkeypatch.setenv("SARE_ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOW_HOMOLOGATION_BOOTSTRAP", "false")
    monkeypatch.setenv("STORAGE_PROVIDER", "LOCAL_HOMOLOGATION")
    monkeypatch.delenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("EXPECTED_DB_SCHEMA", raising=False)

    with pytest.raises(RuntimeError) as exc:
        create_app(UnsafeProductionConfig)

    message = str(exc.value)
    assert "SARE produção bloqueada" in message
    assert "SECRET_KEY" in message
    assert "SESSION_COOKIE_SECURE" in message
    assert "GOOGLE_DRIVE" in message
    assert "PostgreSQL" in message


def test_non_production_runtime_does_not_apply_production_guard(monkeypatch):
    monkeypatch.setenv("SARE_ENVIRONMENT", "development")
    app = create_app(UnsafeProductionConfig)
    assert app is not None
