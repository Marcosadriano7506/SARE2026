from app.models import (
    Answer,
    ApplicationStatus,
    ClassApplication,
    ClassRoom,
    DiscursiveUpload,
    Question,
    Student,
    StudentPresence,
    StudentRecord,
)
from app.services.application_rules import can_finalize_application, validate_student_record
from app.services.scoring import answer_binary_score, proficiency_level


def test_absent_student_does_not_require_discursive():
    record = StudentRecord(presence=StudentPresence.ABSENT)
    valid, message = validate_student_record(record)
    assert valid is True
    assert message is None


def test_present_student_requires_discursive():
    record = StudentRecord(presence=StudentPresence.PRESENT)
    valid, message = validate_student_record(record)
    assert valid is False
    assert "discursiva" in message.lower()


def test_present_student_accepts_discursive_confirmation():
    record = StudentRecord(presence=StudentPresence.PRESENT)
    record.discursive = DiscursiveUpload(
        storage_file_id="file-1",
        stored_filename="aluno_1.jpg",
        uploaded_by=1,
    )
    valid, message = validate_student_record(record)
    assert valid is True
    assert message is None


def test_blank_answer_remains_none():
    question = Question(correct_option="B", number=1)
    answer = Answer(selected_option=None, question=question)
    assert answer_binary_score(answer) is None


def test_correct_and_wrong_answers_are_scored():
    question = Question(correct_option="B", number=1)
    assert answer_binary_score(Answer(selected_option="B", question=question)) == 1
    assert answer_binary_score(Answer(selected_option="A", question=question)) == 0


def test_proficiency_boundaries():
    assert proficiency_level(0) == "DEFASAGEM"
    assert proficiency_level(40) == "DEFASAGEM"
    assert proficiency_level(40.01) == "INTERMEDIARIO"
    assert proficiency_level(70) == "INTERMEDIARIO"
    assert proficiency_level(70.01) == "AVANCADO"
    assert proficiency_level(100) == "AVANCADO"


def test_finalization_fails_with_pending_student():
    classroom = ClassRoom(name="5º A", grade=5, access_code="ABC", school_id=1, evaluation_id=1)
    classroom.students = [
        Student(name="Ana"),
        Student(name="Bruno"),
    ]

    application = ClassApplication(status=ApplicationStatus.IN_PROGRESS)
    application.classroom = classroom
    application.records = [
        StudentRecord(student=classroom.students[0], presence=StudentPresence.ABSENT)
    ]

    allowed, summary, message = can_finalize_application(application)
    assert allowed is False
    assert summary.pending_students == 1
    assert "presença" in message.lower()


def test_finalization_fails_when_present_student_has_no_discursive():
    classroom = ClassRoom(name="5º A", grade=5, access_code="ABC", school_id=1, evaluation_id=1)
    student = Student(name="Ana")
    classroom.students = [student]

    application = ClassApplication(status=ApplicationStatus.IN_PROGRESS)
    application.classroom = classroom
    application.records = [
        StudentRecord(student=student, presence=StudentPresence.PRESENT)
    ]

    allowed, summary, message = can_finalize_application(application)
    assert allowed is False
    assert summary.pending_students == 0
    assert "foto" in message.lower()
