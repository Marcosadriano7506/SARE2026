from app.extensions import db
from app.models import (
    ApplicationStatus,
    AuditLog,
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


def test_coordinator_can_reopen_finalized_class(app, client):
    coordinator_id = create_user(app, UserRole.COORDINATOR, "coord-reopen")
    applicator_id = create_user(app, UserRole.APPLICATOR, "app-reopen")

    with app.app_context():
        evaluation = Evaluation(name="SARE TESTE", school_year=2026)
        school = School(name="Escola Teste Reabertura")
        classroom = ClassRoom(
            school=school,
            evaluation=evaluation,
            grade=5,
            name="5º A",
            access_code="REOPEN1",
        )
        application = ClassApplication(
            classroom=classroom,
            applicator_id=applicator_id,
            status=ApplicationStatus.FINALIZED,
            finalized_by=applicator_id,
            receipt_code="SARE-OLD",
        )
        db.session.add_all([evaluation, school, classroom, application])
        db.session.commit()
        classroom_id = classroom.id

    login_as(client, coordinator_id)
    response = client.post(
        f"/coordenacao/turmas/{classroom_id}/reabrir",
        data={"reason": "Correção de lançamento da turma."},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        application = ClassApplication.query.filter_by(class_id=classroom_id).one()
        assert application.status == ApplicationStatus.REOPENED
        assert application.receipt_code is None
        assert application.reopened_by == coordinator_id
        log = AuditLog.query.filter_by(action="CLASS_APPLICATION_REOPENED").one()
        assert log.details["reason"] == "Correção de lançamento da turma."


def test_coordinator_can_deactivate_and_reactivate_applicator(app, client):
    coordinator_id = create_user(app, UserRole.COORDINATOR, "coord-status")
    applicator_id = create_user(app, UserRole.APPLICATOR, "app-status")
    login_as(client, coordinator_id)

    response = client.post(
        f"/coordenacao/aplicadores/{applicator_id}/status",
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        user = db.session.get(User, applicator_id)
        assert user.is_active_user is False
        assert AuditLog.query.filter_by(action="APPLICATOR_STATUS_CHANGED").count() == 1

    response = client.post(
        f"/coordenacao/aplicadores/{applicator_id}/status",
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        user = db.session.get(User, applicator_id)
        assert user.is_active_user is True


def test_coordinator_can_reset_applicator_password(app, client):
    coordinator_id = create_user(app, UserRole.COORDINATOR, "coord-password")
    applicator_id = create_user(app, UserRole.APPLICATOR, "app-password")
    login_as(client, coordinator_id)

    response = client.post(
        f"/coordenacao/aplicadores/{applicator_id}/senha",
        data={
            "password": "novaSenha123",
            "password_confirmation": "novaSenha123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        user = db.session.get(User, applicator_id)
        assert user.check_password("novaSenha123")
        assert AuditLog.query.filter_by(action="APPLICATOR_PASSWORD_RESET").count() == 1


def test_coordinator_can_reassign_and_release_in_progress_class(app, client):
    coordinator_id = create_user(app, UserRole.COORDINATOR, "coord-assign")
    first_id = create_user(app, UserRole.APPLICATOR, "app-first")
    second_id = create_user(app, UserRole.APPLICATOR, "app-second")

    with app.app_context():
        evaluation = Evaluation(name="SARE ASSIGN", school_year=2026)
        school = School(name="Escola Assign")
        classroom = ClassRoom(
            school=school,
            evaluation=evaluation,
            grade=5,
            name="5º A",
            access_code="ASSIGN5",
        )
        application = ClassApplication(
            classroom=classroom,
            applicator_id=first_id,
            status=ApplicationStatus.IN_PROGRESS,
        )
        db.session.add_all([evaluation, school, classroom, application])
        db.session.commit()
        classroom_id = classroom.id

    login_as(client, coordinator_id)

    response = client.post(
        f"/coordenacao/turmas/{classroom_id}/responsavel",
        data={
            "applicator_id": second_id,
            "reason": "Substituição do aplicador responsável.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        application = ClassApplication.query.filter_by(class_id=classroom_id).one()
        assert application.applicator_id == second_id
        log = AuditLog.query.filter_by(action="CLASS_APPLICATION_REASSIGNED").one()
        assert log.details["previous_applicator_id"] == first_id
        assert log.details["new_applicator_id"] == second_id

    response = client.post(
        f"/coordenacao/turmas/{classroom_id}/responsavel",
        data={
            "applicator_id": 0,
            "reason": "Liberar turma para nova designação.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        application = ClassApplication.query.filter_by(class_id=classroom_id).one()
        assert application.applicator_id is None
