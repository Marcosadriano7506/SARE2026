from io import BytesIO

import pytest
from openpyxl import Workbook

from app.extensions import db
from app.models import Evaluation, Student
from app.services.roster_import import (
    RosterImportError,
    import_roster,
    parse_roster_xlsx,
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


def test_parse_roster_accepts_portuguese_headers():
    content = workbook_bytes(
        ["ESCOLA", "ANO", "TURMA", "ALUNO", "MATRÍCULA"],
        [["Escola A", "5º ano", "5º A", "Ana Souza", "123"]],
    )
    rows = parse_roster_xlsx(content)
    assert len(rows) == 1
    assert rows[0].grade == 5
    assert rows[0].external_id == "123"


def test_parse_roster_rejects_invalid_grade():
    content = workbook_bytes(
        ["ESCOLA", "ANO", "TURMA", "ALUNO"],
        [["Escola A", "1º ano", "1º A", "Ana Souza"]],
    )
    with pytest.raises(RosterImportError) as exc:
        parse_roster_xlsx(content)
    assert "entre 2 e 9" in str(exc.value)


def test_import_roster_creates_school_class_and_students(app):
    content = workbook_bytes(
        ["ESCOLA", "ANO", "TURMA", "ALUNO", "MATRÍCULA"],
        [
            ["Escola A", 5, "5º A", "Ana Souza", "123"],
            ["Escola A", 5, "5º A", "Bruno Lima", "124"],
        ],
    )
    rows = parse_roster_xlsx(content)

    with app.app_context():
        evaluation = Evaluation(name="SARE TESTE", school_year=2026)
        db.session.add(evaluation)
        db.session.commit()

        result = import_roster(evaluation, rows)
        db.session.commit()

        assert result.schools_created == 1
        assert result.classes_created == 1
        assert result.students_created == 2
        assert Student.query.count() == 2
