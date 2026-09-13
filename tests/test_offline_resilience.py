from pathlib import Path


def test_student_draft_preserves_answers_and_image_in_indexeddb():
    content = Path("app/static/js/student_draft.js").read_text(encoding="utf-8")

    assert "indexedDB" in content
    assert "student_submissions" in content
    assert "queueSubmission" in content
    assert "syncPending" in content
    assert "pending.image" in content
    assert "Sem conexão" in content


def test_student_submit_queues_when_offline_or_network_fails():
    content = Path("app/static/js/student_submit.js").read_text(encoding="utf-8")

    assert "!navigator.onLine" in content
    assert "queueSubmission" in content
    assert "fetch(" in content
    assert "A conexão falhou durante o envio" in content


def test_service_worker_caches_offline_assets_and_official_logo():
    content = Path("app/static/sw.js").read_text(encoding="utf-8")

    assert "sare-shell-v4" in content
    assert "/static/js/student_draft.js" in content
    assert "/static/js/student_submit.js" in content
    assert "/static/icons/sare-logo-original.png" in content


def test_student_form_declares_existing_discursive_for_offline_queue():
    content = Path("app/templates/applicator/student.html").read_text(encoding="utf-8")

    assert "data-has-discursive" in content
    assert "respostas e foto ficam preservadas" in content
