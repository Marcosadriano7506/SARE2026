from app.extensions import db
from app.models import User, UserRole


def create_user(app, username="admin", password="secret"):
    with app.app_context():
        user = User(name="Administrador", username=username, role=UserRole.ADMIN)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def test_login_success(client, app):
    create_user(app)
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_login_rejects_invalid_password(client, app):
    create_user(app)
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401


def test_protected_home_redirects_anonymous(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
