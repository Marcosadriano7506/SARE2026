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
)


DEMO_CLASS_CODE = "DEMO5A"


def create_demo_dataset():
    if os.getenv("ALLOW_HOMOLOGATION_BOOTSTRAP", "false").lower() != "true":
        raise RuntimeError("Dados de demonstração só podem ser criados em homologação.")

    existing = ClassRoom.query.filter_by(access_code=DEMO_CLASS_CODE).first()
    if existing is not None:
        return existing, False

    evaluation = Evaluation.query.filter_by(name="SARE DEMO 2026.2").first()
    if evaluation is None:
        evaluation = Evaluation(
            name="SARE DEMO 2026.2",
            school_year=2026,
            edition="DEMO",
            is_active=True,
        )
        db.session.add(evaluation)

    school = School.query.filter_by(name="Escola Municipal Demonstração").first()
    if school is None:
        school = School(name="Escola Municipal Demonstração")
        db.session.add(school)

    db.session.flush()

    classroom = ClassRoom(
        school=school,
        evaluation=evaluation,
        grade=5,
        name="5º Ano A — Demonstração",
        access_code=DEMO_CLASS_CODE,
    )
    classroom.students = [
        Student(name="Ana Souza", external_id="DEMO001"),
        Student(name="Bruno Lima", external_id="DEMO002"),
        Student(name="Carla Santos", external_id="DEMO003"),
        Student(name="Diego Alves", external_id="DEMO004"),
        Student(name="Elisa Rocha", external_id="DEMO005"),
    ]
    db.session.add(classroom)

    for subject, prefix, title in (
        (SubjectArea.PORTUGUESE, "LP", "Língua Portuguesa — 5º Ano"),
        (SubjectArea.MATHEMATICS, "MA", "Matemática — 5º Ano"),
    ):
        test = Test(
            evaluation=evaluation,
            grade=5,
            subject=subject,
            title=title,
        )
        db.session.add(test)
        for number, correct in enumerate(["A", "B", "C", "D", "A"], start=1):
            code = f"{prefix}{number:02d}"
            skill = Skill.query.filter_by(code=code, grade=5, subject=subject).first()
            if skill is None:
                skill = Skill(
                    code=code,
                    description=f"Habilidade de demonstração {code}",
                    grade=5,
                    subject=subject,
                )
                db.session.add(skill)
            test.questions.append(
                Question(
                    number=number,
                    skill=skill,
                    correct_option=correct,
                )
            )

    db.session.commit()
    return classroom, True
