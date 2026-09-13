from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    COORDINATOR = "COORDINATOR"
    APPLICATOR = "APPLICATOR"


class ApplicationStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    FINALIZED = "FINALIZED"
    REOPENED = "REOPENED"
    INCONSISTENT = "INCONSISTENT"


class StudentPresence(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


class RaceDeclaration(str, Enum):
    PRETO = "PRETO"
    PARDO = "PARDO"
    AMARELO = "AMARELO"
    INDIGENA = "INDIGENA"
    BRANCO = "BRANCO"


class SubjectArea(str, Enum):
    PORTUGUESE = "PORTUGUESE"
    MATHEMATICS = "MATHEMATICS"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    job_title = db.Column(db.String(160), nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole, name="user_role"), nullable=False, index=True)
    is_active_user = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    @property
    def is_active(self):
        return self.is_active_user

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password, method="scrypt")

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


class School(db.Model):
    __tablename__ = "schools"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    external_code = db.Column(db.String(80))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    classes = db.relationship("ClassRoom", back_populates="school")


class Evaluation(db.Model):
    __tablename__ = "evaluations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    school_year = db.Column(db.Integer, nullable=False)
    edition = db.Column(db.String(50))
    starts_on = db.Column(db.Date)
    ends_on = db.Column(db.Date)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    classes = db.relationship("ClassRoom", back_populates="evaluation")
    tests = db.relationship("Test", back_populates="evaluation")


class ClassRoom(db.Model):
    __tablename__ = "classes"
    __table_args__ = (
        db.UniqueConstraint(
            "evaluation_id", "school_id", "grade", "name", name="uq_class_identity"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False, index=True)
    evaluation_id = db.Column(
        db.Integer, db.ForeignKey("evaluations.id"), nullable=False, index=True
    )
    grade = db.Column(db.SmallInteger, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    access_code = db.Column(db.String(32), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    school = db.relationship("School", back_populates="classes")
    evaluation = db.relationship("Evaluation", back_populates="classes")
    students = db.relationship(
        "Student", back_populates="classroom", cascade="all, delete-orphan"
    )
    application = db.relationship(
        "ClassApplication",
        back_populates="classroom",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Student(db.Model):
    __tablename__ = "students"
    __table_args__ = (
        db.UniqueConstraint("class_id", "external_id", name="uq_student_external_in_class"),
    )

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False, index=True)
    external_id = db.Column(db.String(100))
    name = db.Column(db.String(220), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    classroom = db.relationship("ClassRoom", back_populates="students")
    records = db.relationship(
        "StudentRecord", back_populates="student", cascade="all, delete-orphan"
    )


class Test(db.Model):
    __tablename__ = "tests"
    __table_args__ = (
        db.UniqueConstraint(
            "evaluation_id", "grade", "subject", name="uq_test_evaluation_grade_subject"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    evaluation_id = db.Column(
        db.Integer, db.ForeignKey("evaluations.id"), nullable=False, index=True
    )
    grade = db.Column(db.SmallInteger, nullable=False)
    subject = db.Column(db.Enum(SubjectArea, name="subject_area"), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    evaluation = db.relationship("Evaluation", back_populates="tests")
    questions = db.relationship(
        "Question", back_populates="test", cascade="all, delete-orphan"
    )


class Skill(db.Model):
    __tablename__ = "skills"
    __table_args__ = (
        db.UniqueConstraint("code", "grade", "subject", name="uq_skill_code_grade_subject"),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text)
    subject = db.Column(db.Enum(SubjectArea, name="subject_area"), nullable=False)
    grade = db.Column(db.SmallInteger, nullable=False)

    questions = db.relationship("Question", back_populates="skill")


class Question(db.Model):
    __tablename__ = "questions"
    __table_args__ = (
        db.UniqueConstraint("test_id", "number", name="uq_question_test_number"),
    )

    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey("tests.id"), nullable=False, index=True)
    number = db.Column(db.Integer, nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), index=True)
    correct_option = db.Column(db.String(1), nullable=False)

    test = db.relationship("Test", back_populates="questions")
    skill = db.relationship("Skill", back_populates="questions")
    answers = db.relationship("Answer", back_populates="question")


class ClassApplication(db.Model):
    __tablename__ = "class_applications"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(
        db.Integer, db.ForeignKey("classes.id"), unique=True, nullable=False
    )
    applicator_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    status = db.Column(
        db.Enum(ApplicationStatus, name="application_status"),
        nullable=False,
        default=ApplicationStatus.NOT_STARTED,
        index=True,
    )
    started_at = db.Column(db.DateTime(timezone=True))
    finalized_at = db.Column(db.DateTime(timezone=True))
    reopened_at = db.Column(db.DateTime(timezone=True))
    finalized_by = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    reopened_by = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    receipt_code = db.Column(db.String(64), unique=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    classroom = db.relationship("ClassRoom", back_populates="application")
    applicator = db.relationship("User", foreign_keys=[applicator_id])
    records = db.relationship(
        "StudentRecord", back_populates="class_application", cascade="all, delete-orphan"
    )


class StudentRecord(db.Model):
    __tablename__ = "student_records"
    __table_args__ = (
        db.UniqueConstraint(
            "class_application_id", "student_id", name="uq_record_application_student"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    class_application_id = db.Column(
        db.Integer,
        db.ForeignKey("class_applications.id"),
        nullable=False,
        index=True,
    )
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False, index=True
    )
    presence = db.Column(
        db.Enum(StudentPresence, name="student_presence"), nullable=False, index=True
    )
    self_declaration = db.Column(db.Enum(RaceDeclaration, name="race_declaration"))
    saved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    saved_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    class_application = db.relationship("ClassApplication", back_populates="records")
    student = db.relationship("Student", back_populates="records")
    saver = db.relationship("User", foreign_keys=[saved_by])
    answers = db.relationship(
        "Answer", back_populates="student_record", cascade="all, delete-orphan"
    )
    discursive = db.relationship(
        "DiscursiveUpload",
        back_populates="student_record",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Answer(db.Model):
    __tablename__ = "answers"
    __table_args__ = (
        db.UniqueConstraint(
            "student_record_id", "question_id", name="uq_answer_record_question"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_record_id = db.Column(
        db.Integer, db.ForeignKey("student_records.id"), nullable=False, index=True
    )
    question_id = db.Column(
        db.Integer, db.ForeignKey("questions.id"), nullable=False, index=True
    )
    selected_option = db.Column(db.String(1))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    student_record = db.relationship("StudentRecord", back_populates="answers")
    question = db.relationship("Question", back_populates="answers")

    @property
    def is_correct(self) -> bool | None:
        if self.selected_option is None:
            return None
        return self.selected_option == self.question.correct_option


class DiscursiveUpload(db.Model):
    __tablename__ = "discursive_uploads"

    id = db.Column(db.Integer, primary_key=True)
    student_record_id = db.Column(
        db.Integer,
        db.ForeignKey("student_records.id"),
        unique=True,
        nullable=False,
    )
    storage_provider = db.Column(db.String(40), nullable=False, default="GOOGLE_DRIVE")
    storage_file_id = db.Column(db.String(255), nullable=False)
    storage_folder_id = db.Column(db.String(255))
    original_filename = db.Column(db.String(255))
    stored_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(120))
    file_size_bytes = db.Column(db.BigInteger)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    student_record = db.relationship("StudentRecord", back_populates="discursive")
    uploader = db.relationship("User", foreign_keys=[uploaded_by])


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    action = db.Column(db.String(120), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.String(120))
    details = db.Column("metadata", db.JSON, nullable=False, default=dict)
    ip_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    user = db.relationship("User")


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
