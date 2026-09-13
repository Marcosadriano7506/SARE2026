import gzip
import json

from app.extensions import db
from app.models import Evaluation, User, UserRole
from app.services.backup import generate_structured_backup, restore_structured_backup


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


def test_structured_backup_can_restore_database_round_trip(app):
    with app.app_context():
        admin = User(name="Admin Original", username="restore-admin", role=UserRole.ADMIN)
        admin.set_password("secret123")
        evaluation = Evaluation(
            name="SARE RESTORE",
            school_year=2026,
            edition="2026.2",
            is_active=False,
        )
        db.session.add_all([admin, evaluation])
        db.session.commit()

        payload = generate_structured_backup()

        evaluation.name = "ALTERADO"
        extra = Evaluation(name="EXTRA", school_year=2027, is_active=False)
        db.session.add(extra)
        db.session.commit()
        db.session.expunge_all()

        counts = restore_structured_backup(payload)
        db.session.expire_all()

        restored = Evaluation.query.order_by(Evaluation.id).all()
        assert counts["evaluations"] == 1
        assert [item.name for item in restored] == ["SARE RESTORE"]
        assert User.query.filter_by(username="restore-admin").one().name == "Admin Original"
