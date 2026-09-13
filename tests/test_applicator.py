from app.extensions import db
from app.models import (
    ApplicationStatus,
    AuditLog,
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


def test_qr_deep_link_prefills_class_code(app, client):
    user_id, _ = setup_applicator_scenario(app)
    login_as(client, user_id)

    response = client.get("/aplicador/?code=abc123")
    assert response.status_code == 200
    assert b'value="ABC123"' in response.data


def test_opening_student_is_recorded_in_audit(app, client):
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
    response = client.get(
        f"/aplicador/turma/{application_id}/aluno/{student_id}"
    )
    assert response.status_code == 200

    with app.app_context():
        log = AuditLog.query.filter_by(action="STUDENT_RECORD_OPENED").one()
        assert log.entity_type == "STUDENT"
        assert log.entity_id == str(student_id)
        assert log.details["application_id"] == application_id


def test_replacing_discursive_deletes_previous_file_and_absence_deletes_current(
    app, client, monkeypatch
):
    from io import BytesIO

    from app.models import DiscursiveUpload, StudentRecord
    from app.storage.base import StoredFile

    class FakeStorage:
        provider = "GOOGLE_DRIVE"

        def __init__(self):
            self.uploaded = []
            self.deleted = []

        def upload_discursive(self, **kwargs):
            file_id = f"file-{len(self.uploaded) + 1}"
            stored = StoredFile(
                provider=self.provider,
                file_id=file_id,
                folder_id="folder-1",
                stored_filename=f"student-{len(self.uploaded) + 1}.jpg",
                mime_type="image/jpeg",
                size_bytes=1234,
            )
            self.uploaded.append(stored)
            return stored

        def delete(self, file_id):
            self.deleted.append(file_id)

    fake_storage = FakeStorage()

    import app.applicator.routes as applicator_routes

    monkeypatch.setattr(
        applicator_routes,
        "get_storage_service",
        lambda provider_name=None: fake_storage,
    )
    monkeypatch.setattr(
        applicator_routes,
        "validate_uploaded_image",
        lambda photo: None,
    )

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
        question_ids = [
            item.id
            for item in Question.query.join(Test, Question.test_id == Test.id)
            .filter(Test.grade == 5)
            .order_by(Question.id.asc())
            .all()
        ]
        db.session.commit()

    login_as(client, user_id)

    first_data = {
        "presence": "PRESENT",
        "self_declaration": "PARDO",
        "discursive": (BytesIO(b"first-image"), "first.jpg"),
    }
    for question_id in question_ids:
        first_data[f"q_{question_id}"] = "A"

    first = client.post(
        f"/aplicador/turma/{application_id}/aluno/{student_id}",
        data=first_data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert first.status_code == 302
    assert [item.file_id for item in fake_storage.uploaded] == ["file-1"]
    assert fake_storage.deleted == []

    second_data = {
        "presence": "PRESENT",
        "self_declaration": "PARDO",
        "discursive": (BytesIO(b"second-image"), "second.jpg"),
    }
    for question_id in question_ids:
        second_data[f"q_{question_id}"] = "B"

    second = client.post(
        f"/aplicador/turma/{application_id}/aluno/{student_id}",
        data=second_data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert second.status_code == 302
    assert [item.file_id for item in fake_storage.uploaded] == ["file-1", "file-2"]
    assert fake_storage.deleted == ["file-1"]

    with app.app_context():
        record = StudentRecord.query.filter_by(
            class_application_id=application_id,
            student_id=student_id,
        ).one()
        assert record.discursive is not None
        assert record.discursive.storage_file_id == "file-2"
        assert DiscursiveUpload.query.count() == 1

    absent = client.post(
        f"/aplicador/turma/{application_id}/aluno/{student_id}",
        data={
            "presence": "ABSENT",
            "self_declaration": "",
        },
        follow_redirects=False,
    )
    assert absent.status_code == 302
    assert fake_storage.deleted == ["file-1", "file-2"]

    with app.app_context():
        record = StudentRecord.query.filter_by(
            class_application_id=application_id,
            student_id=student_id,
        ).one()
        assert record.presence.value == "ABSENT"
        assert record.discursive is None
        assert DiscursiveUpload.query.count() == 0

        actions = [
            log.action
            for log in AuditLog.query.order_by(AuditLog.id.asc()).all()
        ]
        assert "DISCUSSIVE_UPLOADED" in actions
        assert "DISCUSSIVE_REMOVED" in actions


def test_classroom_finalization_is_idempotent(app, client):
    from app.models import StudentPresence, StudentRecord

    user_id, classroom_id = setup_applicator_scenario(app)

    with app.app_context():
        application = ClassApplication(
            class_id=classroom_id,
            applicator_id=user_id,
            status=ApplicationStatus.IN_PROGRESS,
        )
        db.session.add(application)
        db.session.flush()

        students = Student.query.filter_by(class_id=classroom_id).all()
        for student in students:
            db.session.add(
                StudentRecord(
                    class_application=application,
                    student=student,
                    presence=StudentPresence.ABSENT,
                    saved_by=user_id,
                )
            )
        db.session.commit()
        application_id = application.id

    login_as(client, user_id)

    first = client.post(
        f"/aplicador/turma/{application_id}/finalizar",
        follow_redirects=False,
    )
    assert first.status_code == 302

    with app.app_context():
        application = db.session.get(ClassApplication, application_id)
        first_receipt = application.receipt_code
        assert application.status == ApplicationStatus.FINALIZED
        assert first_receipt
        assert AuditLog.query.filter_by(
            action="CLASS_APPLICATION_FINALIZED"
        ).count() == 1

    second = client.post(
        f"/aplicador/turma/{application_id}/finalizar",
        follow_redirects=False,
    )
    assert second.status_code == 302
    assert second.headers["Location"].endswith(
        f"/aplicador/turma/{application_id}/finalizada"
    )

    with app.app_context():
        application = db.session.get(ClassApplication, application_id)
        assert application.receipt_code == first_receipt
        assert AuditLog.query.filter_by(
            action="CLASS_APPLICATION_FINALIZED"
        ).count() == 1
