from app.models import Evaluation


def evaluation_has_started_applications(evaluation: Evaluation) -> bool:
    return any(classroom.application is not None for classroom in evaluation.classes)


def evaluation_setup_lock_message(evaluation: Evaluation) -> str | None:
    if evaluation_has_started_applications(evaluation):
        return (
            "A configuração desta avaliação foi bloqueada porque pelo menos uma turma "
            "já iniciou a aplicação. Base de estudantes e gabarito não podem mais ser "
            "alterados."
        )
    return None
