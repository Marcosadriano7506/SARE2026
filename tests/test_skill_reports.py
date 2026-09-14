from io import BytesIO
from zipfile import ZipFile

from app.extensions import db
from app.models import (
    Answer,
    ApplicationStatus,
    ClassApplication,
    ClassRoom,
    Evaluation,
    Question,
    School,
    Skill,
    Student,
    StudentPresence,
    StudentRecord,
    SubjectArea,
    Test,
    User,
    UserRole,
)
from app.services.skill_reports import (
    build_skill_reports_zip,
    calculate_skill_report_data,
    generate_skill_report_pdf,
)


def _scenario(app):
    with app.app_context():
        applicator = User(
            name="Aplicador",
            username="skill-report-app",
            role=UserRole.APPLICATOR,
        )
        applicator.set_password("secret123")

        evaluation = Evaluation(name="SARE HABILIDADES", school_year=2026)
        school = School(name="Escola Modelo")
        classroom = ClassRoom(
            school=school,
            evaluation=evaluation,
            grade=2,
            name="2º Ano A",
            access_code="2481",
        )
        skill = Skill(
            code="EF01LP01",
            grade=2,
            subject=SubjectArea.PORTUGUESE,
            description="Reconhecer a direção convencional da leitura e da escrita.",
            expected_outcome="Compreender a leitura da esquerda para a direita.",
        )
        test = Test(
            evaluation=evaluation,
            grade=2,
            subject=SubjectArea.PORTUGUESE,
            title="Língua Portuguesa — 2º Ano",
        )
        q1 = Question(
            test=test,
            number=1,
            skill=skill,
            correct_option="A",
        )
        q2 = Question(
            test=test,
            number=2,
            skill=skill,
            correct_option="B",
        )
        student = Student(classroom=classroom, name="Estudante Teste")
        application = ClassApplication(
            classroom=classroom,
            applicator=applicator,
            status=ApplicationStatus.FINALIZED,
        )

        db.session.add_all([
            applicator,
            evaluation,
            school,
            classroom,
            skill,
            test,
            q1,
            q2,
            student,
            application,
        ])
        db.session.flush()

        record = StudentRecord(
            class_application=application,
            student=student,
            presence=StudentPresence.PRESENT,
            saved_by=applicator.id,
        )
        record.answers = [
            Answer(question=q1, selected_option="A"),
            Answer(question=q2, selected_option="D"),
        ]
        db.session.add(record)
        db.session.commit()
        return evaluation.id, school.id, classroom.id


def test_skill_report_calculates_network_school_and_class(app):
    evaluation_id, school_id, class_id = _scenario(app)

    with app.app_context():
        evaluation = db.session.get(Evaluation, evaluation_id)
        data = calculate_skill_report_data(evaluation)

        network = next(iter(data.network.values()))
        school = next(iter(data.schools.values()))
        classroom = next(iter(data.classes.values()))

        assert network.correct == 1
        assert network.opportunities == 2
        assert network.percent == 50.0
        assert network.item_count == 2
        assert school.correct == 1
        assert school.percent == 50.0
        assert classroom.correct == 1
        assert classroom.percent == 50.0

        pdf = generate_skill_report_pdf(
            evaluation,
            data,
            scope_type="class",
            class_id=class_id,
        )
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 1000


def test_skill_report_zip_contains_network_school_and_class(app):
    evaluation_id, _, _ = _scenario(app)

    with app.app_context():
        evaluation = db.session.get(Evaluation, evaluation_id)
        package = build_skill_reports_zip(evaluation)

    with ZipFile(BytesIO(package)) as archive:
        names = archive.namelist()
        assert "00_REDE/relatorio_habilidades_rede.pdf" in names
        assert any(name.endswith("/relatorio_habilidades_escola.pdf") for name in names)
        assert any("/TURMAS/" in name and name.endswith(".pdf") for name in names)
        assert "LEIA-ME.txt" in names
