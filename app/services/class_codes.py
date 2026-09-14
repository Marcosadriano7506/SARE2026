from __future__ import annotations

import secrets

from app.models import ClassRoom


CLASS_CODE_MIN = 1000
CLASS_CODE_MAX = 9999
CLASS_CODE_ATTEMPTS = 100


def generate_class_code() -> str:
    for _ in range(CLASS_CODE_ATTEMPTS):
        code = str(
            CLASS_CODE_MIN
            + secrets.randbelow(CLASS_CODE_MAX - CLASS_CODE_MIN + 1)
        )
        if ClassRoom.query.filter_by(access_code=code).first() is None:
            return code
    raise RuntimeError("Não foi possível gerar um código de turma único de 4 dígitos.")
