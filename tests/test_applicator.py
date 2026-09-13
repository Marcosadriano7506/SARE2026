from app.extensions import db
from app.models import (
    ApplicationStatus,
    ClassApplication,
    ClassRoom,
    Evaluation,
    School,
    Student,
    User,
    UserRole,
)


def setup_applicator_scenario(app):
    with app.app_context():
        user = User(name="Aplicador", username="app1", role=UserRole.APPLICATOR)
        user.set_password("secret123")
        evaluation = Evaluation(name="SARE 2026.2", school_year=2026)
        school = School(name="Escola Teste")
        classroom = ClassRoom(
            school=school,
            evaluation=evaluation,
            grade=5,
            name="5º Ano A",
            access_code="ABC123",
        )
        classroom.students = [Student(name="Ana"), Student(name="Bruno")]
        db.session.add_all([user, evaluation, school, classroom])
        db.session.commit()
        return user.id, classroom.id


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_valid_class_code_starts_application(app, client):
    user_id, classroom_id = setup_applicator_scenario(app)
    login_as(client, user_id)

    response = client.post(
        "/aplicador/",
        data={"code": "abc123"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        application = ClassApplication.query.filter_by(class_id=classroom_id).one()
        assert application.applicator_id == user_id
        assert application.status == ApplicationStatus.IN_PROGRESS


def test_invalid_class_code_is_rejected(app, client):
    user_id, _ = setup_applicator_scenario(app)
    login_as(client, user_id)

    response = client.post("/aplicador/", data={"code": "INVALIDO"})
    assert response.status_code == 404
    assert b"Código de turma" in response.data


def test_other_applicator_cannot_take_in_progress_class(app, client):
    first_id, classroom_id = setup_applicator_scenario(app)
    with app.app_context():
        second = User(name="Outro", username="app2", role=UserRole.APPLICATOR)
        second.set_password("secret123")
        db.session.add(second)
        db.session.flush()
        second_id = second.id
        application = ClassApplication(
            class_id=classroom_id,
            applicator_id=first_id,
            status=ApplicationStatus.IN_PROGRESS,
        )
        db.session.add(application)
        db.session.commit()

    login_as(client, second_id)
    response = client.post("/aplicador/", data={"code": "ABC123"})
    assert response.status_code == 409
