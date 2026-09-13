from app.extensions import db
from app.models import (
    ApplicationStatus,
    ClassApplication,
    ClassRoom,
    Evaluation,
    Question,
    School,
    Skill,
    Student,
    SubjectArea,
    Test,
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
        lp_test.questions = [
            Question(number=1, skill=lp_skill, correct_option="A")
        ]
        math_test.questions = [
            Question(number=1, skill=math_skill, correct_option="B")
        ]

        db.session.add_all(
            [user, evaluation, school, classroom, lp_skill, math_skill, lp_test, math_test]
        )
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
    assert "Código de turma".encode("utf-8") in response.data


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


def test_same_applicator_can_resume_class_without_student_context(app, client):
    user_id, classroom_id = setup_applicator_scenario(app)
    with app.app_context():
        application = ClassApplication(
            class_id=classroom_id,
            applicator_id=user_id,
            status=ApplicationStatus.IN_PROGRESS,
        )
        db.session.add(application)
        db.session.commit()
        application_id = application.id

    login_as(client, user_id)
    response = client.post(
        "/aplicador/",
        data={"code": "ABC123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"/aplicador/turma/{application_id}"
    )


def test_absent_student_save_marks_redirect_for_local_draft_cleanup(app, client):
    user_id, classroom_id = setup_applicator_scenario(app)
    with app.app_context():
        application = ClassApplication(
            class_id=classroom_id,
            applicator_id=user_id,
            status=ApplicationStatus.IN_PROGRESS,
        )
        db.session.add(application)
        db.session.flush()
        application_id = application.id
        student_id = Student.query.filter_by(class_id=classroom_id).first().id
        db.session.commit()

    login_as(client, user_id)
    response = client.post(
        f"/aplicador/turma/{application_id}/aluno/{student_id}",
        data={
            "presence": "ABSENT",
            "self_declaration": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert (
        response.headers["Location"]
        .endswith(f"/aplicador/turma/{application_id}?saved={student_id}")
    )


def test_inactive_evaluation_blocks_class_code(app, client):
    user_id, classroom_id = setup_applicator_scenario(app)
    with app.app_context():
        classroom = db.session.get(ClassRoom, classroom_id)
        classroom.evaluation.is_active = False
        db.session.commit()

    login_as(client, user_id)
    response = client.post("/aplicador/", data={"code": "ABC123"})
    assert response.status_code == 409
    assert "desativada".encode("utf-8") in response.data.lower()


def test_future_evaluation_window_blocks_class_code(app, client):
    from datetime import date, timedelta

    user_id, classroom_id = setup_applicator_scenario(app)
    with app.app_context():
        classroom = db.session.get(ClassRoom, classroom_id)
        classroom.evaluation.starts_on = date.today() + timedelta(days=2)
        db.session.commit()

    login_as(client, user_id)
    response = client.post("/aplicador/", data={"code": "ABC123"})
    assert response.status_code == 409
    assert "disponível".encode("utf-8") in response.data.lower()


def test_missing_subject_test_blocks_class_code(app, client):
    user_id, classroom_id = setup_applicator_scenario(app)
    with app.app_context():
        classroom = db.session.get(ClassRoom, classroom_id)
        math_test = Test.query.filter_by(
            evaluation_id=classroom.evaluation_id,
            grade=5,
            subject=SubjectArea.MATHEMATICS,
        ).one()
        db.session.delete(math_test)
        db.session.commit()

    login_as(client, user_id)
    response = client.post("/aplicador/", data={"code": "ABC123"})
    assert response.status_code == 409
    assert "gabarito".encode("utf-8") in response.data.lower()
