from io import BytesIO

from openpyxl import Workbook

from app.extensions import db
from app.models import Evaluation, Question, User, UserRole


def _xlsx_bytes():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["ANO", "COMPONENTE", "QUESTÃO", "HABILIDADE", "GABARITO", "DESCRIÇÃO DA HABILIDADE"])
    sheet.append([5, "LP", 1, "D01", "A", "Localizar informação explícita"])
    sheet.append([5, "MATEMÁTICA", 1, "D02", "B", "Resolver problema"])
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def _setup(app):
    with app.app_context():
        user = User(name="Coord", username="key-preview", role=UserRole.COORDINATOR)
        user.set_password("secret123")
        evaluation = Evaluation(name="SARE KEY PREVIEW", school_year=2026, is_active=False)
        db.session.add_all([user, evaluation])
        db.session.commit()
        return user.id, evaluation.id


def _login(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_answer_key_preview_does_not_write_before_confirmation(app, client):
    user_id, evaluation_id = _setup(app)
    _login(client, user_id)

    response = client.post(
        "/coordenacao/gabarito-preview/",
        data={
            "evaluation_id": str(evaluation_id),
            "file": (_xlsx_bytes(), "gabarito.xlsx"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert "Primeiras 2 questões".encode("utf-8") in response.data
    with app.app_context():
        assert Question.query.count() == 0

    with client.session_transaction() as session:
        token = session["answer_key_preview"]["token"]

    response = client.post(
        f"/coordenacao/gabarito-preview/{token}/confirmar",
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        assert Question.query.count() == 2
