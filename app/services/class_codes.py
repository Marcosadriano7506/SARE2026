from __future__ import annotations

import secrets

from app.models import ClassRoom


CLASS_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CLASS_CODE_LENGTH = 12


def generate_class_code() -> str:
    for _ in range(20):
        code = "".join(
            secrets.choice(CLASS_CODE_ALPHABET)
            for _ in range(CLASS_CODE_LENGTH)
        )
        if ClassRoom.query.filter_by(access_code=code).first() is None:
            return code
    raise RuntimeError("Não foi possível gerar um código de turma único.")
