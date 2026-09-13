from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import Evaluation, SubjectArea


BAHIA_TZ = ZoneInfo("America/Bahia")


@dataclass
class EvaluationReadiness:
    ready: bool
    issues: list[str] = field(default_factory=list)
    classes: int = 0
    students: int = 0
    grades: list[int] = field(default_factory=list)
    tests: int = 0
    questions: int = 0


def local_today():
    return datetime.now(BAHIA_TZ).date()


def evaluation_window_status(evaluation: Evaluation) -> tuple[bool, str | None]:
    if not evaluation.is_active:
        return False, "Esta avaliação está desativada pela coordenação."

    today = local_today()
    if evaluation.starts_on and today < evaluation.starts_on:
        return (
            False,
            f"A aplicação estará disponível a partir de {evaluation.starts_on.strftime('%d/%m/%Y')}.",
        )
    if evaluation.ends_on and today > evaluation.ends_on:
        return (
            False,
            f"O período de aplicação terminou em {evaluation.ends_on.strftime('%d/%m/%Y')}.",
        )
    return True, None


def calculate_evaluation_readiness(evaluation: Evaluation) -> EvaluationReadiness:
    issues: list[str] = []
    classrooms = list(evaluation.classes)
    grades = sorted({item.grade for item in classrooms})
    students = sum(len(item.students) for item in classrooms)
    tests = list(evaluation.tests)
    questions = sum(len(test.questions) for test in tests)

    if not classrooms:
        issues.append("Nenhuma turma foi importada.")
    if classrooms and students == 0:
        issues.append("As turmas não possuem estudantes.")

    for classroom in classrooms:
        if not classroom.students:
            issues.append(
                f"{classroom.school.name} — {classroom.name} não possui estudantes."
            )

    tests_by_grade_subject = {
        (test.grade, test.subject): test
        for test in tests
    }
    for grade in grades:
        for subject, label in (
            (SubjectArea.PORTUGUESE, "Língua Portuguesa"),
            (SubjectArea.MATHEMATICS, "Matemática"),
        ):
            test = tests_by_grade_subject.get((grade, subject))
            if test is None:
                issues.append(f"{grade}º ano sem prova de {label}.")
            elif not test.questions:
                issues.append(f"{grade}º ano sem questões cadastradas em {label}.")

    return EvaluationReadiness(
        ready=not issues,
        issues=issues,
        classes=len(classrooms),
        students=students,
        grades=grades,
        tests=len(tests),
        questions=questions,
    )


def classroom_is_ready(classroom) -> tuple[bool, str | None]:
    if not classroom.students:
        return False, "Esta turma ainda não possui estudantes cadastrados."

    tests = [
        test
        for test in classroom.evaluation.tests
        if test.grade == classroom.grade
    ]
    tests_by_subject = {test.subject: test for test in tests}
    for subject, label in (
        (SubjectArea.PORTUGUESE, "Língua Portuguesa"),
        (SubjectArea.MATHEMATICS, "Matemática"),
    ):
        test = tests_by_subject.get(subject)
        if test is None or not test.questions:
            return False, f"O gabarito de {label} do {classroom.grade}º ano não está pronto."

    return True, None
