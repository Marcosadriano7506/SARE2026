from types import SimpleNamespace

from app.services.results_pdf import generate_results_pdf


def test_results_pdf_is_valid_and_does_not_need_student_images():
    evaluation = SimpleNamespace(name="SARE TESTE", school_year=2026)

    analytics = SimpleNamespace(
        finalized_classes=2,
        present_students=20,
        absent_students=2,
        total_percent=68.5,
        lp_percent=72.0,
        math_percent=65.0,
        proficiency_counts={
            "DEFASAGEM": 4,
            "INTERMEDIARIO": 10,
            "AVANCADO": 6,
        },
        schools=[
            SimpleNamespace(name="Escola A", percent=75.0),
            SimpleNamespace(name="Escola B", percent=62.0),
        ],
        classes=[
            SimpleNamespace(name="Escola A — 5º A", percent=78.0),
            SimpleNamespace(name="Escola B — 5º B", percent=60.0),
        ],
        skills=[
            SimpleNamespace(code="D01", subject="PORTUGUESE", grade=5, percent=35.0),
            SimpleNamespace(code="D02", subject="MATHEMATICS", grade=5, percent=50.0),
        ],
    )

    pdf = generate_results_pdf(evaluation, analytics)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 700
