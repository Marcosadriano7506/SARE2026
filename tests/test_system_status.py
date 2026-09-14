from app.services.system_status import calculate_system_status


def _login_admin(app, client, username="admin-system"):
    from app.extensions import db
    from app.models import User, UserRole

    with app.app_context():
        admin = User(name="Admin", username=username, role=UserRole.ADMIN)
        admin.set_password("secret123")
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id

    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["_fresh"] = True

    return admin_id


def test_non_persistent_test_environment_is_not_production_ready(app):
    with app.app_context():
        status = calculate_system_status(app)

    assert status.database_ok is True
    assert status.database_persistent is False
    assert status.production_environment is False
    assert status.production_ready is False


def test_admin_can_run_google_drive_smoke_test(app, client, monkeypatch):
    from app.extensions import db
    from app.models import AuditLog

    class FakeStorage:
        def smoke_test_write_delete(self):
            return "Gravação e exclusão no Google Drive confirmadas."

    _login_admin(app, client, "admin-smoke")

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


def test_synthetic_load_routes_do_not_exist_in_official_runtime(app, client):
    _login_admin(app, client, "admin-no-load")

    assert client.post("/admin/ambiente/carga/criar").status_code == 404
    assert client.post("/admin/ambiente/carga/remover").status_code == 404


def test_system_status_page_has_no_homologation_controls(app, client):
    _login_admin(app, client, "admin-status-page")

    response = client.get("/admin/ambiente/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Homologação" not in body
    assert "fixture" not in body.lower()
    assert "carga/criar" not in body
    assert "Status do Sistema" in body
