from google.oauth2.credentials import Credentials as OAuthCredentials

from app.extensions import db
from app.models import User, UserRole
from app.storage.google_drive import (
    DRIVE_FILE_SCOPE,
    build_google_credentials,
    oauth_environment_configured,
)


def create_user(app, role, username):
    with app.app_context():
        user = User(name="Usuário", username=username, role=role)
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()
        return user.id


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_oauth_credentials_are_built_from_environment(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REFRESH_TOKEN", "refresh-token")
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)

    assert oauth_environment_configured() is True

    credentials = build_google_credentials()
    assert isinstance(credentials, OAuthCredentials)
    assert credentials.refresh_token == "refresh-token"
    assert credentials.client_id == "client-id"
    assert DRIVE_FILE_SCOPE in credentials.scopes


def test_admin_can_open_google_drive_setup(app, client, monkeypatch):
    admin_id = create_user(app, UserRole.ADMIN, "admin-drive")
    login_as(client, admin_id)

    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "https://example.test/admin/google-drive/oauth/callback",
    )

    response = client.get("/admin/google-drive/")
    assert response.status_code == 200
    assert b"Conectar Google Drive" in response.data
    assert b"https://example.test/admin/google-drive/oauth/callback" in response.data


def test_coordinator_cannot_open_google_drive_setup(app, client):
    coordinator_id = create_user(app, UserRole.COORDINATOR, "coord-drive")
    login_as(client, coordinator_id)

    response = client.get("/admin/google-drive/")
    assert response.status_code == 403
