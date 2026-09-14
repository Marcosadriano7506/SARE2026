import re

from app.services.class_codes import generate_class_code


def test_generated_class_code_has_exactly_four_digits(app):
    with app.app_context():
        code = generate_class_code()

    assert re.fullmatch(r"\d{4}", code)
    assert 1000 <= int(code) <= 9999
