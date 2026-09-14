from flask import Blueprint
from flask_login import login_user

from app.auth.permissions import roles_required
from app.extensions import db
from app.models import User, UserRole


def install_test_routes(app):
    bp = Blueprint("permission_tests", __name__)

    @bp.get("/admin-only")
    @roles_required(UserRole.ADMIN)
    def admin_only():
        return "ok"

    app.register_blueprint(bp)


def create_user(app, role):
    with app.app_context():
        user = User(name="Teste", username=f"user-{role.value}", role=role)
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()
        return user.id


def login_as(client, app, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_admin_can_access_role_protected_route(app, client):
    install_test_routes(app)
    user_id = create_user(app, UserRole.ADMIN)
    login_as(client, app, user_id)
    response = client.get("/admin-only")
    assert response.status_code == 200


def test_applicator_cannot_access_admin_route(app, client):
    install_test_routes(app)
    user_id = create_user(app, UserRole.APPLICATOR)
    login_as(client, app, user_id)
    response = client.get("/admin-only")
    assert response.status_code == 403
