from __future__ import annotations

from dataclasses import dataclass

from app.models import ApplicationStatus, StudentPresence, StudentRecord


@dataclass(frozen=True)
class CompletionSummary:
    total_students: int
    completed_records: int
    present_students: int
    absent_students: int
    confirmed_discursives: int

    @property
    def pending_students(self) -> int:
        return max(self.total_students - self.completed_records, 0)

    @property
    def is_complete(self) -> bool:
        return (
            self.pending_students == 0
            and self.confirmed_discursives == self.present_students
        )


def validate_student_record(record: StudentRecord) -> tuple[bool, str | None]:
    if record.presence == StudentPresence.ABSENT:
        return True, None

    if record.presence == StudentPresence.PRESENT and record.discursive is None:
        return False, "Estudante presente precisa ter a foto da discursiva confirmada."

    return True, None


def summarize_application(application) -> CompletionSummary:
    classroom = application.classroom
    total_students = len(classroom.students) if classroom else 0
    records = list(application.records or [])

    present = sum(1 for record in records if record.presence == StudentPresence.PRESENT)
    absent = sum(1 for record in records if record.presence == StudentPresence.ABSENT)
    confirmed = sum(
        1
        for record in records
        if record.presence == StudentPresence.PRESENT and record.discursive is not None
    )

    return CompletionSummary(
        total_students=total_students,
        completed_records=len(records),
        present_students=present,
        absent_students=absent,
        confirmed_discursives=confirmed,
    )


def can_finalize_application(application) -> tuple[bool, CompletionSummary, str | None]:
    if application.status == ApplicationStatus.FINALIZED:
        summary = summarize_application(application)
        return False, summary, "A turma já está finalizada."

    summary = summarize_application(application)

    if summary.pending_students:
        return (
            False,
            summary,
            f"Existem {summary.pending_students} estudante(s) sem registro de presença.",
        )

    missing_discursives = summary.present_students - summary.confirmed_discursives
    if missing_discursives:
        return (
            False,
            summary,
            f"Existem {missing_discursives} estudante(s) presente(s) sem foto confirmada.",
        )

    return True, summary, None
