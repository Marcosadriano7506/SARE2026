from datetime import date

from app.extensions import db
from app.models import (
    Evaluation,
    Question,
    School,
    Skill,
    Student,
    SubjectArea,
    Test,
    ClassRoom,
    User,
    UserRole,
)
from app.services.evaluation_readiness import calculate_evaluation_readiness


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


def build_ready_evaluation():
    evaluation = Evaluation(
        name="SARE PRONTO",
        school_year=2026,
        is_active=False,
    )
    school = School(name="Escola Pronta")
    classroom = ClassRoom(
        school=school,
        evaluation=evaluation,
        grade=5,
        name="5º A",
        access_code="READY5",
    )
    classroom.students = [Student(name="Aluno 1")]

    lp_skill = Skill(code="D01", grade=5, subject=SubjectArea.PORTUGUESE)
    math_skill = Skill(code="D02", grade=5, subject=SubjectArea.MATHEMATICS)
    lp_test = Test(
        evaluation=evaluation,
        grade=5,
        subject=SubjectArea.PORTUGUESE,
        title="LP 5º",
    )
    math_test = Test(
        evaluation=evaluation,
        grade=5,
        subject=SubjectArea.MATHEMATICS,
        title="MAT 5º",
    )
    lp_test.questions = [Question(number=1, skill=lp_skill, correct_option="A")]
    math_test.questions = [Question(number=1, skill=math_skill, correct_option="B")]

    db.session.add_all(
        [evaluation, school, classroom, lp_skill, math_skill, lp_test, math_test]
    )
    return evaluation


def test_readiness_detects_missing_base_and_tests(app):
    with app.app_context():
        evaluation = Evaluation(name="SARE VAZIO", school_year=2026)
        db.session.add(evaluation)
        db.session.commit()

        readiness = calculate_evaluation_readiness(evaluation)
        assert readiness.ready is False
        assert any("Nenhuma turma" in issue for issue in readiness.issues)


def test_ready_evaluation_can_be_activated(app, client):
    coordinator_id = create_user(app, UserRole.COORDINATOR, "coord-ready")
    with app.app_context():
        evaluation = build_ready_evaluation()
        db.session.commit()
        evaluation_id = evaluation.id

    login_as(client, coordinator_id)
    response = client.post(
        f"/coordenacao/avaliacoes/{evaluation_id}/status",
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        evaluation = db.session.get(Evaluation, evaluation_id)
        assert evaluation.is_active is True


def test_unready_evaluation_cannot_be_activated(app, client):
    coordinator_id = create_user(app, UserRole.COORDINATOR, "coord-unready")
    with app.app_context():
        evaluation = Evaluation(
            name="SARE INCOMPLETO",
            school_year=2026,
            is_active=False,
        )
        db.session.add(evaluation)
        db.session.commit()
        evaluation_id = evaluation.id

    login_as(client, coordinator_id)
    response = client.post(
        f"/coordenacao/avaliacoes/{evaluation_id}/status",
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        evaluation = db.session.get(Evaluation, evaluation_id)
        assert evaluation.is_active is False


def test_evaluation_settings_validate_date_order(app, client):
    coordinator_id = create_user(app, UserRole.COORDINATOR, "coord-dates")
    with app.app_context():
        evaluation = Evaluation(name="SARE DATAS", school_year=2026)
        db.session.add(evaluation)
        db.session.commit()
        evaluation_id = evaluation.id

    login_as(client, coordinator_id)
    response = client.post(
        f"/coordenacao/avaliacoes/{evaluation_id}",
        data={
            "name": "SARE DATAS",
            "school_year": 2026,
            "edition": "2026.2",
            "starts_on": date(2026, 10, 10).isoformat(),
            "ends_on": date(2026, 10, 9).isoformat(),
        },
    )
    assert response.status_code == 200
    assert "data final".encode("utf-8") in response.data.lower()
