from io import BytesIO

from openpyxl import Workbook

from app.extensions import db
from app.models import Evaluation, Student, User, UserRole


def _xlsx_bytes():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["ESCOLA", "ANO", "TURMA", "ALUNO", "MATRÍCULA"])
    sheet.append(["Escola A", 5, "5º A", "Ana", "001"])
    sheet.append(["Escola A", 5, "5º A", "Bruno", "002"])
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def _setup_coordinator(app):
    with app.app_context():
        user = User(name="Coord", username="preview-coord", role=UserRole.COORDINATOR)
        user.set_password("secret123")
        evaluation = Evaluation(name="SARE PREVIEW", school_year=2026, is_active=False)
        db.session.add_all([user, evaluation])
        db.session.commit()
        return user.id, evaluation.id


def _login(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_preview_does_not_write_students_before_confirmation(app, client):
    user_id, evaluation_id = _setup_coordinator(app)
    _login(client, user_id)

    response = client.post(
        "/coordenacao/base-preview/",
        data={
            "evaluation_id": str(evaluation_id),
            "file": (_xlsx_bytes(), "base.xlsx"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert "Primeiras 2 linhas válidas".encode("utf-8") in response.data

    with app.app_context():
        assert Student.query.count() == 0

    with client.session_transaction() as session:
        token = session["roster_preview"]["token"]

    response = client.post(
        f"/coordenacao/base-preview/{token}/confirmar",
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        assert Student.query.count() == 2


def test_preview_reports_duplicate_rows_without_writing(app, client):
    user_id, evaluation_id = _setup_coordinator(app)
    _login(client, user_id)

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["ESCOLA", "ANO", "TURMA", "ALUNO", "MATRÍCULA"])
    sheet.append(["Escola A", 5, "5º A", "Ana", "001"])
    sheet.append(["Escola A", 5, "5º A", "Ana", "001"])
    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    response = client.post(
        "/coordenacao/base-preview/",
        data={
            "evaluation_id": str(evaluation_id),
            "file": (output, "duplicados.xlsx"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert "Duplicidades aparentes".encode("utf-8") in response.data
    assert "possíveis duplicidades".encode("utf-8") in response.data

    with app.app_context():
        assert Student.query.count() == 0
