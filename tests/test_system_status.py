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


def test_admin_can_create_load_fixture_only_in_homologation(app, client, monkeypatch):
    from app.extensions import db
    from app.models import AuditLog, User, UserRole
    import app.admin.system_routes as system_routes

    with app.app_context():
        admin = User(name="Admin", username="admin-load", role=UserRole.ADMIN)
        admin.set_password("secret123")
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id

    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["_fresh"] = True

    called = {}

    def fake_create_load_fixture(*, user_count, students_per_class):
        called["user_count"] = user_count
        called["students_per_class"] = students_per_class
        return {
            "users_created": user_count,
            "schools_created": 1,
            "classes_created": user_count,
            "students_created": user_count * students_per_class,
            "total_users": user_count,
            "students_per_class": students_per_class,
        }

    monkeypatch.setenv("ALLOW_HOMOLOGATION_BOOTSTRAP", "true")
    monkeypatch.setattr(
        system_routes,
        "create_load_fixture",
        fake_create_load_fixture,
    )

    response = client.post(
        "/admin/ambiente/carga/criar",
        data={
            "users": "20",
            "students_per_class": "30",
            "confirm": "CRIAR",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert called == {"user_count": 20, "students_per_class": 30}

    with app.app_context():
        assert AuditLog.query.filter_by(action="LOAD_FIXTURE_CREATED").count() == 1


def test_load_fixture_route_is_blocked_outside_homologation(app, client, monkeypatch):
    from app.extensions import db
    from app.models import User, UserRole

    with app.app_context():
        admin = User(name="Admin", username="admin-load-prod", role=UserRole.ADMIN)
        admin.set_password("secret123")
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id

    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["_fresh"] = True

    monkeypatch.setenv("ALLOW_HOMOLOGATION_BOOTSTRAP", "false")

    response = client.post(
        "/admin/ambiente/carga/criar",
        data={
            "users": "20",
            "students_per_class": "30",
            "confirm": "CRIAR",
        },
        follow_redirects=False,
    )
    assert response.status_code == 409
