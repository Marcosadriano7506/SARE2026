from types import SimpleNamespace

from app.extensions import db
from app.models import AuditLog, User, UserRole


def _admin(app):
    with app.app_context():
        user = User(name="Admin Backup", username="admin-backup-drive", role=UserRole.ADMIN)
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()
        return user.id


def _login(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_admin_can_send_structured_backup_to_drive(app, client, monkeypatch):
    admin_id = _admin(app)
    _login(client, admin_id)

    captured = {}

    class FakeBackend:
        def upload_system_backup(self, *, content, filename):
            captured["content"] = content
            captured["filename"] = filename
            return SimpleNamespace(
                file_id="drive-backup-1",
                folder_id="backup-folder",
                stored_filename=filename,
            )

    class FakeStorage:
        backend = FakeBackend()

    monkeypatch.setattr(
        "app.admin.backup_routes.get_storage_service",
        lambda provider_name=None: FakeStorage(),
    )

    response = client.post("/admin/backup/drive", follow_redirects=False)

    assert response.status_code == 302
    assert captured["content"][:2] == b"\x1f\x8b"
    assert captured["filename"].startswith("sare_backup_")
    assert captured["filename"].endswith(".json.gz")

    with app.app_context():
        assert AuditLog.query.filter_by(
            action="STRUCTURED_BACKUP_UPLOADED_TO_DRIVE"
        ).count() == 1
