from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from app.models import (
    ApplicationStatus,
    ClassApplication,
    ClassRoom,
    Evaluation,
    Student,
    StudentRecord,
    User,
    UserRole,
    utcnow,
)
from app.services.evaluation_readiness import calculate_evaluation_readiness


@dataclass
class OperationalAudit:
    ready: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    students: int = 0
    schools: int = 0
    classes: int = 0
    students_with_registration: int = 0
    students_without_registration: int = 0
    duplicate_registration_groups: int = 0
    duplicate_name_groups: int = 0
    active_applicators: int = 0


@dataclass
class LiveApplicationSnapshot:
    schools_expected: int
    schools_started: int
    classes_expected: int
    classes_started: int
    classes_finalized: int
    classes_in_progress: int
    students_expected: int
    student_records: int
    discursives: int
    stale_classes: int
    last_activity_at: object | None
    completion_percent: float


def calculate_operational_audit(evaluation: Evaluation) -> OperationalAudit:
    blockers: list[str] = []
    warnings: list[str] = []

    base = calculate_evaluation_readiness(evaluation)
    blockers.extend(base.issues)

    classrooms = list(evaluation.classes)
    students = [student for classroom in classrooms for student in classroom.students]
    schools = {classroom.school_id for classroom in classrooms}

    registration_groups: dict[str, list[Student]] = defaultdict(list)
    missing_registration = 0
    for student in students:
        external = (student.external_id or "").strip()
        if external:
            registration_groups[external.upper()].append(student)
        else:
            missing_registration += 1

    duplicate_registration = {
        key: group for key, group in registration_groups.items() if len(group) > 1
    }
    if duplicate_registration:
        examples = ", ".join(list(sorted(duplicate_registration))[:5])
        blockers.append(
            f"{len(duplicate_registration)} matrícula(s) aparecem em mais de uma linha/turma"
            + (f" (ex.: {examples})." if examples else ".")
        )

    duplicate_names = 0
    for classroom in classrooms:
        names = Counter(
            " ".join(student.name.upper().split())
            for student in classroom.students
        )
        duplicate_names += sum(1 for count in names.values() if count > 1)

    if duplicate_names:
        warnings.append(
            f"{duplicate_names} grupo(s) de nomes idênticos aparecem na mesma turma. "
            "Confira se são homônimos ou duplicidades."
        )

    if missing_registration:
        warnings.append(
            f"{missing_registration} estudante(s) estão sem matrícula/ID externo. "
            "O sistema funciona, mas a identificação administrativa fica menos segura."
        )

    active_applicators = User.query.filter_by(
        role=UserRole.APPLICATOR,
        is_active_user=True,
    ).count()
    if active_applicators == 0:
        warnings.append("Nenhum aplicador ativo está cadastrado ainda.")
    elif active_applicators < 2:
        warnings.append("Existe apenas 1 aplicador ativo cadastrado.")

    return OperationalAudit(
        ready=not blockers,
        blockers=blockers,
        warnings=warnings,
        students=len(students),
        schools=len(schools),
        classes=len(classrooms),
        students_with_registration=len(students) - missing_registration,
        students_without_registration=missing_registration,
        duplicate_registration_groups=len(duplicate_registration),
        duplicate_name_groups=duplicate_names,
        active_applicators=active_applicators,
    )


def calculate_live_snapshot(evaluation: Evaluation, *, stale_minutes: int = 30) -> LiveApplicationSnapshot:
    classrooms = list(evaluation.classes)
    applications = [
        classroom.application
        for classroom in classrooms
        if classroom.application is not None
    ]

    schools_expected = {classroom.school_id for classroom in classrooms}
    schools_started = {
        application.classroom.school_id
        for application in applications
    }

    student_records = sum(len(application.records) for application in applications)
    discursives = sum(
        1
        for application in applications
        for record in application.records
        if record.discursive is not None
    )

    last_activity_at = None
    stale_classes = 0
    stale_cutoff = utcnow() - timedelta(minutes=stale_minutes)

    for application in applications:
        activity_candidates = [
            application.started_at,
            application.updated_at,
            application.finalized_at,
            application.reopened_at,
        ]
        activity_candidates.extend(record.updated_at for record in application.records)
        activity_candidates.extend(record.saved_at for record in application.records)
        activity = max((item for item in activity_candidates if item is not None), default=None)

        if activity is not None:
            if last_activity_at is None or activity > last_activity_at:
                last_activity_at = activity

        if (
            application.status in {ApplicationStatus.IN_PROGRESS, ApplicationStatus.REOPENED}
            and activity is not None
            and activity < stale_cutoff
        ):
            stale_classes += 1

    classes_started = len(applications)
    classes_finalized = sum(
        1 for application in applications
        if application.status == ApplicationStatus.FINALIZED
    )
    classes_in_progress = sum(
        1 for application in applications
        if application.status in {ApplicationStatus.IN_PROGRESS, ApplicationStatus.REOPENED}
    )
    students_expected = sum(len(classroom.students) for classroom in classrooms)

    completion_percent = (
        (student_records / students_expected) * 100
        if students_expected
        else 0.0
    )

    return LiveApplicationSnapshot(
        schools_expected=len(schools_expected),
        schools_started=len(schools_started),
        classes_expected=len(classrooms),
        classes_started=classes_started,
        classes_finalized=classes_finalized,
        classes_in_progress=classes_in_progress,
        students_expected=students_expected,
        student_records=student_records,
        discursives=discursives,
        stale_classes=stale_classes,
        last_activity_at=last_activity_at,
        completion_percent=completion_percent,
    )
