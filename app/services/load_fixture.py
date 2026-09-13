from __future__ import annotations

import os

from app.extensions import db
from app.models import (
    ClassRoom,
    Evaluation,
    Question,
    School,
    Skill,
    Student,
    SubjectArea,
    Test,
    User,
    UserRole,
)


LOAD_EVALUATION_NAME = "SARE LOAD TEST"
LOAD_LP_SKILL = "LOAD-LP-01"
LOAD_MATH_SKILL = "LOAD-MAT-01"


def _ensure_load_tests(evaluation: Evaluation) -> None:
    specs = (
        (
            SubjectArea.PORTUGUESE,
            "LP 5º — Carga",
            LOAD_LP_SKILL,
            "A",
        ),
        (
            SubjectArea.MATHEMATICS,
            "MAT 5º — Carga",
            LOAD_MATH_SKILL,
            "B",
        ),
    )

    for subject, title, skill_code, correct_option in specs:
        skill = Skill.query.filter_by(
            code=skill_code,
            grade=5,
            subject=subject,
        ).first()
        if skill is None:
            skill = Skill(
                code=skill_code,
                grade=5,
                subject=subject,
            )
            db.session.add(skill)
            db.session.flush()

        test = Test.query.filter_by(
            evaluation_id=evaluation.id,
            grade=5,
            subject=subject,
        ).first()
        if test is None:
            test = Test(
                evaluation=evaluation,
                grade=5,
                subject=subject,
                title=title,
            )
            db.session.add(test)
            db.session.flush()

        if not test.questions:
            db.session.add(
                Question(
                    test=test,
                    number=1,
                    skill=skill,
                    correct_option=correct_option,
                )
            )
            db.session.flush()


def create_load_fixture(
    *,
    user_count: int = 100,
    students_per_class: int = 30,
    password: str | None = None,
) -> dict[str, int]:
    if os.getenv("ALLOW_HOMOLOGATION_BOOTSTRAP", "false").lower() != "true":
        raise RuntimeError("Fixture de carga só pode ser criado em homologação.")

    if user_count < 1 or user_count > 250:
        raise ValueError("user_count deve estar entre 1 e 250.")
    if students_per_class < 1 or students_per_class > 60:
        raise ValueError("students_per_class deve estar entre 1 e 60.")

    password = password or os.getenv("LOAD_TEST_PASSWORD", "")
    if len(password) < 8:
        raise ValueError("Defina LOAD_TEST_PASSWORD com pelo menos 8 caracteres.")

    evaluation = Evaluation.query.filter_by(name=LOAD_EVALUATION_NAME).first()
    if evaluation is None:
        evaluation = Evaluation(
            name=LOAD_EVALUATION_NAME,
            school_year=2026,
            edition="LOAD",
            is_active=True,
        )
        db.session.add(evaluation)
        db.session.flush()

    _ensure_load_tests(evaluation)

    created_users = 0
    created_schools = 0
    created_classes = 0
    created_students = 0

    school_cache: dict[int, School] = {}

    for index in range(1, user_count + 1):
        username = f"load{index:03d}"
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(
                name=f"Aplicador Carga {index:03d}",
                job_title="Teste de carga",
                username=username,
                role=UserRole.APPLICATOR,
                is_active_user=True,
            )
            user.set_password(password)
            db.session.add(user)
            created_users += 1

        school_number = ((index - 1) % 25) + 1
        school = school_cache.get(school_number)
        if school is None:
            school_name = f"Escola Sintética {school_number:02d}"
            school = School.query.filter_by(name=school_name).first()
            if school is None:
                school = School(name=school_name)
                db.session.add(school)
                db.session.flush()
                created_schools += 1
            school_cache[school_number] = school

        class_code = f"LOAD{index:04d}"
        classroom = ClassRoom.query.filter_by(access_code=class_code).first()
        if classroom is None:
            classroom = ClassRoom(
                school=school,
                evaluation=evaluation,
                grade=5,
                name=f"5º Ano LOAD {index:03d}",
                access_code=class_code,
            )
            db.session.add(classroom)
            db.session.flush()
            created_classes += 1

        existing_students = len(classroom.students)
        for student_number in range(existing_students + 1, students_per_class + 1):
            db.session.add(
                Student(
                    classroom=classroom,
                    external_id=f"L{index:03d}-{student_number:03d}",
                    name=f"Estudante Sintético {index:03d}-{student_number:03d}",
                )
            )
            created_students += 1

    db.session.commit()

    return {
        "users_created": created_users,
        "schools_created": created_schools,
        "classes_created": created_classes,
        "students_created": created_students,
        "total_users": user_count,
        "students_per_class": students_per_class,
    }


def delete_load_fixture() -> dict[str, int]:
    if os.getenv("ALLOW_HOMOLOGATION_BOOTSTRAP", "false").lower() != "true":
        raise RuntimeError("Fixture de carga só pode ser removido em homologação.")

    evaluation = Evaluation.query.filter_by(name=LOAD_EVALUATION_NAME).first()
    classes_deleted = 0
    if evaluation is not None:
        load_classes = list(evaluation.classes)
        classes_deleted = len(load_classes)
        for classroom in load_classes:
            db.session.delete(classroom)
        db.session.flush()
        db.session.delete(evaluation)
        db.session.flush()

    users = User.query.filter(
        User.role == UserRole.APPLICATOR,
        User.username.like("load%"),
    ).all()
    users_deleted = len(users)
    for user in users:
        db.session.delete(user)

    db.session.flush()

    synthetic_schools = School.query.filter(
        School.name.like("Escola Sintética %")
    ).all()
    schools_deleted = 0
    for school in synthetic_schools:
        if not school.classes:
            db.session.delete(school)
            schools_deleted += 1

    synthetic_skills = Skill.query.filter(
        Skill.code.in_([LOAD_LP_SKILL, LOAD_MATH_SKILL])
    ).all()
    skills_deleted = len(synthetic_skills)
    for skill in synthetic_skills:
        db.session.delete(skill)

    db.session.commit()
    return {
        "users_deleted": users_deleted,
        "classes_deleted": classes_deleted,
        "schools_deleted": schools_deleted,
        "skills_deleted": skills_deleted,
    }
