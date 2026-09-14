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
from app.services.operational_readiness import calculate_operational_audit


def _ready_evaluation_with_two_classes():
    evaluation = Evaluation(name="SARE AUDIT", school_year=2026, is_active=False)
    school = School(name="Escola Audit")
    class_a = ClassRoom(
        school=school,
        evaluation=evaluation,
        grade=5,
        name="5º A",
        access_code="AUDITA",
    )
    class_b = ClassRoom(
        school=school,
        evaluation=evaluation,
        grade=5,
        name="5º B",
        access_code="AUDITB",
    )
    class_a.students = [Student(name="Ana", external_id="001")]
    class_b.students = [Student(name="Bruno", external_id="002")]

    lp_skill = Skill(code="D01", grade=5, subject=SubjectArea.PORTUGUESE)
    math_skill = Skill(code="D02", grade=5, subject=SubjectArea.MATHEMATICS)
    lp_test = Test(
        evaluation=evaluation,
        grade=5,
        subject=SubjectArea.PORTUGUESE,
        title="LP",
    )
    math_test = Test(
        evaluation=evaluation,
        grade=5,
        subject=SubjectArea.MATHEMATICS,
        title="MAT",
    )
    lp_test.questions = [Question(number=1, skill=lp_skill, correct_option="A")]
    math_test.questions = [Question(number=1, skill=math_skill, correct_option="B")]

    db.session.add_all([
        evaluation,
        school,
        class_a,
        class_b,
        lp_skill,
        math_skill,
        lp_test,
        math_test,
    ])
    db.session.flush()
    return evaluation, class_a, class_b


def test_operational_audit_approves_clean_base(app):
    with app.app_context():
        evaluation, _, _ = _ready_evaluation_with_two_classes()
        db.session.commit()

        audit = calculate_operational_audit(evaluation)

        assert audit.ready is True
        assert audit.students == 2
        assert audit.duplicate_registration_groups == 0


def test_operational_audit_blocks_duplicate_registration_across_classes(app):
    with app.app_context():
        evaluation, _, class_b = _ready_evaluation_with_two_classes()
        class_b.students[0].external_id = "001"
        db.session.commit()

        audit = calculate_operational_audit(evaluation)

        assert audit.ready is False
        assert audit.duplicate_registration_groups == 1
        assert any("matrícula" in item.lower() for item in audit.blockers)


def test_operational_audit_warns_missing_registration_without_blocking(app):
    with app.app_context():
        evaluation, class_a, _ = _ready_evaluation_with_two_classes()
        class_a.students[0].external_id = None
        db.session.commit()

        audit = calculate_operational_audit(evaluation)

        assert audit.ready is True
        assert audit.students_without_registration == 1
        assert any("sem matrícula" in item.lower() for item in audit.warnings)
