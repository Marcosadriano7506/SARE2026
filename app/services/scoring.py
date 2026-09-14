from __future__ import annotations

from app.models import Answer


def answer_binary_score(answer: Answer) -> int | None:
    """Retorna 1 para acerto, 0 para erro e None para questão em branco."""
    if answer.selected_option is None:
        return None
    return 1 if answer.selected_option == answer.question.correct_option else 0


def proficiency_level(percent: float) -> str:
    if percent < 0 or percent > 100:
        raise ValueError("Percentual deve estar entre 0 e 100.")
    if percent <= 40:
        return "DEFASAGEM"
    if percent <= 70:
        return "INTERMEDIARIO"
    return "AVANCADO"
