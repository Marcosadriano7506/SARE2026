from app.services.system_status import calculate_system_status


def test_non_persistent_test_environment_is_not_production_ready(app):
    with app.app_context():
        status = calculate_system_status(app)

    assert status.database_ok is True
    assert status.database_persistent is False
    assert status.production_ready is False
    assert status.storage_provider == "LOCAL_HOMOLOGATION"


def test_admin_can_run_google_drive_smoke_test(app, client, monkeypatch):
    from app.extensions import db
    from app.models import AuditLog, User, UserRole

    class FakeStorage:
        def smoke_test_write_delete(self):
            return "Gravação e exclusão no Google Drive confirmadas."

    with app.app_context():
        admin = User(name="Admin", username="admin-smoke", role=UserRole.ADMIN)
        admin.set_password("secret123")
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id

    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["_fresh"] = True

    import app.admin.system_routes as system_routes
    monkeypatch.setattr(
        system_routes,
        "get_storage_service",
        lambda provider_name=None: FakeStorage(),
    )

    response = client.post(
        "/admin/ambiente/testar-drive",
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        assert AuditLog.query.filter_by(
            action="GOOGLE_DRIVE_SMOKE_TEST"
        ).count() == 1
