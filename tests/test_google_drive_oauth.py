from google.oauth2.credentials import Credentials as OAuthCredentials

from app.extensions import db
from app.models import User, UserRole
from app.storage.google_drive import (
    DRIVE_FILE_SCOPE,
    GoogleDriveStorage,
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


def test_oauth_state_is_signed_and_bound_to_user(app):
    from app.admin.google_drive_oauth import _make_oauth_state, _validate_oauth_state

    with app.test_request_context("/"):
        token = _make_oauth_state(123)
        assert _validate_oauth_state(token) == 123

        parts = token.split(".")
        signature = parts[-1]
        replacement = "A" if signature[0] != "A" else "B"
        parts[-1] = replacement + signature[1:]
        tampered = ".".join(parts)
        assert _validate_oauth_state(tampered) is None



class _FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _FakeFilesForRoot:
    def __init__(self, *, existing_id=None):
        self.existing_id = existing_id
        self.created_names = []

    def list(self, **kwargs):
        files = (
            [{"id": self.existing_id, "name": "SARE - PRODUÇÃO"}]
            if self.existing_id
            else []
        )
        return _FakeRequest({"files": files})

    def create(self, *, body, fields, supportsAllDrives):
        self.created_names.append(body["name"])
        return _FakeRequest({"id": "created-production-root"})


class _FakeDriveForRoot:
    def __init__(self, *, existing_id=None):
        self.files_api = _FakeFilesForRoot(existing_id=existing_id)

    def files(self):
        return self.files_api


def test_drive_root_can_be_created_by_name_with_app_credentials():
    storage = GoogleDriveStorage.__new__(GoogleDriveStorage)
    storage.service = _FakeDriveForRoot()

    folder_id = storage._resolve_root_folder(
        root_folder_id="",
        root_folder_name="SARE - PRODUÇÃO",
    )

    assert folder_id == "created-production-root"
    assert storage.service.files_api.created_names == ["SARE - PRODUÇÃO"]


def test_drive_root_by_name_reuses_existing_folder():
    storage = GoogleDriveStorage.__new__(GoogleDriveStorage)
    storage.service = _FakeDriveForRoot(existing_id="existing-production-root")

    folder_id = storage._resolve_root_folder(
        root_folder_id="",
        root_folder_name="SARE - PRODUÇÃO",
    )

    assert folder_id == "existing-production-root"
    assert storage.service.files_api.created_names == []
