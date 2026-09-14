from types import SimpleNamespace

from app.services.receipt import generate_receipt_pdf, receipt_payload


def fake_application():
    return SimpleNamespace(
        classroom=SimpleNamespace(
            evaluation=SimpleNamespace(name="SARE 2026.2"),
            school=SimpleNamespace(name="Escola Teste"),
            name="5º Ano A",
            grade=5,
            access_code="ABC123",
        ),
        applicator=SimpleNamespace(name="João", job_title="Professor"),
        started_at=None,
        finalized_at=None,
        receipt_code="SARE-TESTE",
    )


def fake_summary():
    return SimpleNamespace(
        total_students=30,
        present_students=28,
        absent_students=2,
        completed_records=30,
        confirmed_discursives=28,
    )


def test_receipt_payload_contains_only_administrative_summary():
    payload = receipt_payload(fake_application(), fake_summary())
    assert payload["present_students"] == 28
    forbidden = {"answers", "self_declaration", "score", "correct_option", "image"}
    assert forbidden.isdisjoint(payload.keys())


def test_receipt_pdf_is_valid_pdf_bytes():
    pdf = generate_receipt_pdf(fake_application(), fake_summary())
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500
