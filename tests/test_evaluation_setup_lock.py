from io import BytesIO

from app.extensions import db
from app.models import (
    ApplicationStatus,
    ClassApplication,
    ClassRoom,
    Evaluation,
    School,
    User,
    UserRole,
)


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


def build_started_evaluation(app):
    with app.app_context():
        applicator = User(
            name="Aplicador",
            username="lock-app",
            role=UserRole.APPLICATOR,
        )
        applicator.set_password("secret123")
        evaluation = Evaluation(
            name="SARE LOCK",
            school_year=2026,
            is_active=True,
        )
        school = School(name="Escola Lock")
        classroom = ClassRoom(
            school=school,
            evaluation=evaluation,
            grade=5,
            name="5º A",
            access_code="LOCKABCDE234",
        )
        application = ClassApplication(
            classroom=classroom,
            applicator=applicator,
            status=ApplicationStatus.IN_PROGRESS,
        )
        db.session.add_all([applicator, evaluation, school, classroom, application])
        db.session.commit()
        return evaluation.id


def test_roster_import_is_blocked_after_application_starts(app, client):
    coordinator_id = create_user(app, UserRole.COORDINATOR, "coord-lock-roster")
    evaluation_id = build_started_evaluation(app)
    login_as(client, coordinator_id)

    response = client.post(
        "/coordenacao/base/importar",
        data={
            "evaluation_id": evaluation_id,
            "file": (BytesIO(b"placeholder"), "base.xlsx"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_answer_key_import_is_blocked_after_application_starts(app, client):
    coordinator_id = create_user(app, UserRole.COORDINATOR, "coord-lock-key")
    evaluation_id = build_started_evaluation(app)
    login_as(client, coordinator_id)

    response = client.post(
        "/coordenacao/gabarito/importar",
        data={
            "evaluation_id": evaluation_id,
            "file": (BytesIO(b"placeholder"), "gabarito.xlsx"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302
