from app.extensions import db
from app.models import AuditLog, User, UserRole


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


def test_admin_can_create_coordinator(app, client):
    admin_id = create_user(app, UserRole.ADMIN, "admin-test")
    login_as(client, admin_id)

    response = client.post(
        "/admin/coordenadores/novo",
        data={
            "name": "Coordenadora",
            "job_title": "Coordenação Pedagógica",
            "username": "coord-nova",
            "password": "senha123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        coordinator = User.query.filter_by(username="coord-nova").one()
        assert coordinator.role == UserRole.COORDINATOR
        assert coordinator.check_password("senha123")
        assert AuditLog.query.filter_by(action="COORDINATOR_CREATED").count() == 1


def test_coordinator_cannot_access_admin_area(app, client):
    coordinator_id = create_user(app, UserRole.COORDINATOR, "coord-no-admin")
    login_as(client, coordinator_id)

    response = client.get("/admin/")
    assert response.status_code == 403


def test_admin_can_toggle_coordinator_status(app, client):
    admin_id = create_user(app, UserRole.ADMIN, "admin-toggle")
    coordinator_id = create_user(app, UserRole.COORDINATOR, "coord-toggle")
    login_as(client, admin_id)

    response = client.post(
        f"/admin/coordenadores/{coordinator_id}/status",
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        coordinator = db.session.get(User, coordinator_id)
        assert coordinator.is_active_user is False
        assert AuditLog.query.filter_by(action="COORDINATOR_STATUS_CHANGED").count() == 1
