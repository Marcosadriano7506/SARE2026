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


def test_coordinator_can_create_applicator(app, client):
    coordinator_id = create_user(app, UserRole.COORDINATOR, "coord")
    login_as(client, coordinator_id)

    response = client.post(
        "/coordenacao/aplicadores/novo",
        data={
            "name": "Aplicador Um",
            "job_title": "Professor",
            "username": "aplicador1",
            "password": "senha123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        user = User.query.filter_by(username="aplicador1").one()
        assert user.role == UserRole.APPLICATOR
        assert user.check_password("senha123")
        assert AuditLog.query.filter_by(action="APPLICATOR_CREATED").count() == 1


def test_applicator_cannot_open_coordinator_panel(app, client):
    applicator_id = create_user(app, UserRole.APPLICATOR, "app")
    login_as(client, applicator_id)
    response = client.get("/coordenacao/")
    assert response.status_code == 403
