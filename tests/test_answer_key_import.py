from io import BytesIO

import pytest
from openpyxl import Workbook

from app.extensions import db
from app.models import Evaluation, Question, Skill, Test
from app.services.answer_key_import import (
    AnswerKeyImportError,
    import_answer_key,
    parse_answer_key_xlsx,
)


def workbook_bytes(headers, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_parse_answer_key_accepts_lp_and_math():
    content = workbook_bytes(
        ["ANO", "COMPONENTE", "QUESTÃO", "HABILIDADE", "GABARITO"],
        [
            [5, "LP", 1, "D01", "A"],
            [5, "Matemática", 1, "D02", "B"],
        ],
    )
    rows = parse_answer_key_xlsx(content)
    assert len(rows) == 2
    assert rows[0].correct_option == "A"
    assert rows[1].correct_option == "B"


def test_parse_answer_key_rejects_invalid_option():
    content = workbook_bytes(
        ["ANO", "COMPONENTE", "QUESTÃO", "HABILIDADE", "GABARITO"],
        [[5, "LP", 1, "D01", "E"]],
    )
    with pytest.raises(AnswerKeyImportError) as exc:
        parse_answer_key_xlsx(content)
    assert "A, B, C ou D" in str(exc.value)


def test_import_answer_key_creates_and_updates_questions(app):
    content = workbook_bytes(
        [
            "ANO",
            "COMPONENTE",
            "QUESTÃO",
            "HABILIDADE",
            "GABARITO",
            "DESCRIÇÃO DA HABILIDADE",
            "O QUE SE ESPERA",
        ],
        [
            [5, "LP", 1, "D01", "A", "Leitura", "Reconhecer informações no texto."],
            [5, "LP", 2, "D02", "B", "Inferência", "Inferir informação implícita."],
        ],
    )
    rows = parse_answer_key_xlsx(content)

    with app.app_context():
        evaluation = Evaluation(name="SARE TESTE GAB", school_year=2026)
        db.session.add(evaluation)
        db.session.commit()

        result = import_answer_key(evaluation, rows)
        db.session.commit()
        assert result.tests_created == 1
        assert result.skills_created == 2
        assert result.questions_created == 2
        assert Test.query.count() == 1
        assert Skill.query.count() == 2
        assert Question.query.count() == 2
        skill = Skill.query.filter_by(code="D01").one()
        assert skill.description == "Leitura"
        assert skill.expected_outcome == "Reconhecer informações no texto."

        updated_rows = parse_answer_key_xlsx(
            workbook_bytes(
                ["ANO", "COMPONENTE", "QUESTÃO", "HABILIDADE", "GABARITO"],
                [[5, "LP", 1, "D01", "D"]],
            )
        )
        updated = import_answer_key(evaluation, updated_rows)
        db.session.commit()
        assert updated.questions_updated == 1
        assert Question.query.filter_by(number=1).one().correct_option == "D"
