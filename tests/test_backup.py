import gzip
import json

from app.extensions import db
from app.models import User, UserRole
from app.services.backup import generate_structured_backup


def test_structured_backup_contains_application_tables(app):
    with app.app_context():
        user = User(name="Admin", username="backup-admin", role=UserRole.ADMIN)
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()

        payload = generate_structured_backup()

    decoded = json.loads(gzip.decompress(payload).decode("utf-8"))
    assert decoded["format"] == "SARE_STRUCTURED_BACKUP"
    assert decoded["version"] == 1
    assert "users" in decoded["tables"]
    assert "evaluations" in decoded["tables"]
    assert any(row["username"] == "backup-admin" for row in decoded["tables"]["users"])


def test_only_admin_can_download_backup(app, client):
    with app.app_context():
        coordinator = User(
            name="Coord",
            username="backup-coord",
            role=UserRole.COORDINATOR,
        )
        coordinator.set_password("secret123")
        db.session.add(coordinator)
        db.session.commit()
        coordinator_id = coordinator.id

    with client.session_transaction() as session:
        session["_user_id"] = str(coordinator_id)
        session["_fresh"] = True

    response = client.get("/admin/backup/download")
    assert response.status_code == 403
