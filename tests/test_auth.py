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


def test_login_marks_session_permanent(client, app):
    create_user(app, username="permanent", password="secret")
    response = client.post(
        "/auth/login",
        data={"username": "permanent", "password": "secret"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with client.session_transaction() as session:
        assert session.permanent is True


def test_disabled_user_is_logged_out_on_next_request(client, app):
    user_id = create_user(app, username="disable-me", password="secret")
    response = client.post(
        "/auth/login",
        data={"username": "disable-me", "password": "secret"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        user = db.session.get(User, user_id)
        user.is_active_user = False
        db.session.commit()

    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
