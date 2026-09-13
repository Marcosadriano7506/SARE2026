from app.extensions import db
from app.models import (
    Answer,
    ApplicationStatus,
    ClassApplication,
    ClassRoom,
    Evaluation,
    Question,
    School,
    Student,
    StudentPresence,
    StudentRecord,
    SubjectArea,
    Test,
    User,
    UserRole,
)
from app.services.analytics import calculate_evaluation_analytics


def test_network_result_is_weighted_by_items_not_class_average(app):
    with app.app_context():
        applicator = User(name="Aplicador", username="analytics-app", role=UserRole.APPLICATOR)
        applicator.set_password("secret123")
        evaluation = Evaluation(name="SARE ANALYTICS", school_year=2026)
        school = School(name="Escola Analytics")
        test = Test(
            evaluation=evaluation,
            grade=5,
            subject=SubjectArea.PORTUGUESE,
            title="LP",
        )
        q1 = Question(test=test, number=1, correct_option="A")
        q2 = Question(test=test, number=2, correct_option="B")

        class_a = ClassRoom(
            school=school,
            evaluation=evaluation,
            grade=5,
            name="5º A",
            access_code="ANA001",
        )
        class_b = ClassRoom(
            school=school,
            evaluation=evaluation,
            grade=5,
            name="5º B",
            access_code="ANA002",
        )

        student_a = Student(classroom=class_a, name="Aluno A")
        students_b = [
            Student(classroom=class_b, name=f"Aluno B{i}") for i in range(1, 4)
        ]

        app_a = ClassApplication(
            classroom=class_a,
            applicator=applicator,
            status=ApplicationStatus.FINALIZED,
        )
        app_b = ClassApplication(
            classroom=class_b,
            applicator=applicator,
            status=ApplicationStatus.FINALIZED,
        )
        db.session.add_all([
            applicator, evaluation, school, test, q1, q2,
            class_a, class_b, student_a, *students_b, app_a, app_b
        ])
        db.session.flush()

        record_a = StudentRecord(
            class_application=app_a,
            student=student_a,
            presence=StudentPresence.PRESENT,
            saved_by=applicator.id,
        )
        record_a.answers = [
            Answer(question=q1, selected_option="A"),
            Answer(question=q2, selected_option="B"),
        ]
        db.session.add(record_a)

        for student in students_b:
            record = StudentRecord(
                class_application=app_b,
                student=student,
                presence=StudentPresence.PRESENT,
                saved_by=applicator.id,
            )
            record.answers = [
                Answer(question=q1, selected_option="C"),
                Answer(question=q2, selected_option="D"),
            ]
            db.session.add(record)

        db.session.commit()

        analytics = calculate_evaluation_analytics(evaluation)
        assert analytics.present_students == 4
        assert analytics.total_correct == 2
        assert analytics.total_items == 8
        assert analytics.total_percent == 25.0
        assert analytics.lp_percent == 25.0
        assert len(analytics.students) == 4
        assert len(analytics.questions) == 2
        assert analytics.questions[0].opportunities == 4
        assert analytics.questions[0].percent == 25.0
