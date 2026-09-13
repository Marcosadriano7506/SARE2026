from app.extensions import db
from app.models import ClassRoom, Evaluation, School
from app.services.class_codes_pdf import generate_class_codes_pdf


def test_class_codes_pdf_contains_valid_pdf_for_evaluation(app):
    with app.app_context():
        evaluation = Evaluation(name="SARE CÓDIGOS", school_year=2026)
        school = School(name="Escola Teste")
        classroom = ClassRoom(
            school=school,
            evaluation=evaluation,
            grade=5,
            name="5º Ano A",
            access_code="ABC12345",
        )
        db.session.add_all([evaluation, school, classroom])
        db.session.commit()

        pdf = generate_class_codes_pdf(evaluation)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 700
