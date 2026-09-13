from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.applicator.forms import ClassCodeForm
from app.applicator.student_form import StudentApplicationForm
from app.auth.permissions import roles_required
from app.extensions import db
from app.models import (
    Answer,
    ApplicationStatus,
    ClassApplication,
    ClassRoom,
    DiscursiveUpload,
    Question,
    RaceDeclaration,
    Student,
    StudentPresence,
    Test,
    UserRole,
    utcnow,
)
from app.services.audit import record_audit
from app.storage.factory import get_storage_service

applicator_bp = Blueprint("applicator", __name__, url_prefix="/aplicador")


@applicator_bp.route("/", methods=["GET", "POST"])
@login_required
@roles_required(UserRole.APPLICATOR)
def dashboard():
    form = ClassCodeForm()
    if form.validate_on_submit():
        code = form.code.data.strip().upper()
        classroom = ClassRoom.query.filter_by(access_code=code).first()

        if classroom is None:
            form.code.errors.append("Código de turma não encontrado.")
            return render_template("applicator/dashboard.html", form=form), 404

        application = classroom.application

        if application and application.status == ApplicationStatus.FINALIZED:
            flash("Esta turma já foi finalizada.", "error")
            return render_template("applicator/dashboard.html", form=form), 409

        if application and application.applicator_id not in (None, current_user.id):
            flash("Esta turma já está em andamento com outro aplicador.", "error")
            return render_template("applicator/dashboard.html", form=form), 409

        if application is None:
            application = ClassApplication(
                classroom=classroom,
                applicator_id=current_user.id,
                status=ApplicationStatus.IN_PROGRESS,
                started_at=utcnow(),
            )
            db.session.add(application)
            db.session.flush()
            action = "CLASS_APPLICATION_STARTED"
        else:
            previous_status = application.status
            application.applicator_id = current_user.id
            if application.started_at is None:
                application.started_at = utcnow()
            application.status = ApplicationStatus.IN_PROGRESS
            action = "CLASS_APPLICATION_RESUMED"
            record_audit(
                user_id=current_user.id,
                action=action,
                entity_type="CLASS_APPLICATION",
                entity_id=application.id,
                details={"previous_status": previous_status.value},
            )
            db.session.commit()
            return redirect(url_for("applicator.classroom", application_id=application.id))

        record_audit(
            user_id=current_user.id,
            action=action,
            entity_type="CLASS_APPLICATION",
            entity_id=application.id,
            details={"class_id": classroom.id},
        )
        db.session.commit()
        return redirect(url_for("applicator.classroom", application_id=application.id))

    return render_template("applicator/dashboard.html", form=form)


@applicator_bp.get("/turma/<int:application_id>")
@login_required
@roles_required(UserRole.APPLICATOR)
def classroom(application_id: int):
    application = db.session.get(ClassApplication, application_id)
    if application is None:
        abort(404)
    if application.applicator_id != current_user.id:
        abort(403)

    records_by_student = {record.student_id: record for record in application.records}
    rows = []
    for student in sorted(application.classroom.students, key=lambda item: item.name):
        record = records_by_student.get(student.id)
        if record is None:
            status = "PENDING"
        elif record.presence == StudentPresence.ABSENT:
            status = "ABSENT"
        else:
            status = "COMPLETED"
        rows.append((student, status))

    return render_template(
        "applicator/classroom.html",
        application=application,
        rows=rows,
    )


def _application_and_student(application_id: int, student_id: int):
    application = db.session.get(ClassApplication, application_id)
    if application is None:
        abort(404)
    if application.applicator_id != current_user.id:
        abort(403)
    if application.status == ApplicationStatus.FINALIZED:
        abort(409)

    student = db.session.get(Student, student_id)
    if student is None or student.class_id != application.class_id:
        abort(404)
    return application, student


def _questions_for(application: ClassApplication):
    return (
        Question.query.join(Test, Question.test_id == Test.id)
        .filter(
            Test.evaluation_id == application.classroom.evaluation_id,
            Test.grade == application.classroom.grade,
        )
        .order_by(Test.subject.asc(), Question.number.asc())
        .all()
    )


@applicator_bp.route(
    "/turma/<int:application_id>/aluno/<int:student_id>",
    methods=["GET", "POST"],
)
@login_required
@roles_required(UserRole.APPLICATOR)
def student(application_id: int, student_id: int):
    application, student = _application_and_student(application_id, student_id)
    form = StudentApplicationForm()
    questions = _questions_for(application)
    record = next(
        (item for item in application.records if item.student_id == student.id),
        None,
    )

    if request.method == "GET" and record is not None:
        form.presence.data = record.presence.value
        form.self_declaration.data = (
            record.self_declaration.value if record.self_declaration else ""
        )

    existing_answers = {}
    if record is not None:
        existing_answers = {
            answer.question_id: answer.selected_option for answer in record.answers
        }

    if form.validate_on_submit():
        presence = StudentPresence(form.presence.data)
        photo = form.discursive.data

        if presence == StudentPresence.PRESENT and record is not None and record.discursive:
            photo_required = False
        else:
            photo_required = presence == StudentPresence.PRESENT

        if photo_required and not photo:
            form.discursive.errors.append(
                "A foto da discursiva é obrigatória para estudante presente."
            )
        else:
            if record is None:
                from app.models import StudentRecord

                record = StudentRecord(
                    class_application=application,
                    student=student,
                    presence=presence,
                    saved_by=current_user.id,
                )
                db.session.add(record)
                db.session.flush()
            else:
                record.presence = presence
                record.saved_by = current_user.id
                record.updated_at = utcnow()

            if presence == StudentPresence.ABSENT:
                record.self_declaration = None
                for answer in list(record.answers):
                    db.session.delete(answer)
                if record.discursive is not None:
                    db.session.delete(record.discursive)
            else:
                record.self_declaration = (
                    RaceDeclaration(form.self_declaration.data)
                    if form.self_declaration.data
                    else None
                )

                answers_by_question = {
                    answer.question_id: answer for answer in record.answers
                }
                for question in questions:
                    raw_value = request.form.get(f"q_{question.id}")
                    selected = raw_value if raw_value in {"A", "B", "C", "D"} else None
                    answer = answers_by_question.get(question.id)
                    if answer is None:
                        answer = Answer(
                            student_record=record,
                            question=question,
                            selected_option=selected,
                        )
                        db.session.add(answer)
                    else:
                        answer.selected_option = selected
                        answer.updated_at = utcnow()

                if photo:
                    storage = get_storage_service()
                    stored = storage.upload_discursive(
                        evaluation_name=application.classroom.evaluation.name,
                        school_name=application.classroom.school.name,
                        class_name=application.classroom.name,
                        student_name=student.name,
                        student_id=student.id,
                        stream=photo.stream,
                        original_filename=photo.filename or "discursiva.jpg",
                        mime_type=photo.mimetype,
                    )
                    if record.discursive is None:
                        record.discursive = DiscursiveUpload(
                            storage_provider=stored.provider,
                            storage_file_id=stored.file_id,
                            storage_folder_id=stored.folder_id,
                            original_filename=photo.filename,
                            stored_filename=stored.stored_filename,
                            mime_type=stored.mime_type,
                            file_size_bytes=stored.size_bytes,
                            uploaded_by=current_user.id,
                        )
                    else:
                        record.discursive.storage_provider = stored.provider
                        record.discursive.storage_file_id = stored.file_id
                        record.discursive.storage_folder_id = stored.folder_id
                        record.discursive.original_filename = photo.filename
                        record.discursive.stored_filename = stored.stored_filename
                        record.discursive.mime_type = stored.mime_type
                        record.discursive.file_size_bytes = stored.size_bytes
                        record.discursive.uploaded_by = current_user.id
                        record.discursive.uploaded_at = utcnow()

            record_audit(
                user_id=current_user.id,
                action="STUDENT_RECORD_SAVED",
                entity_type="STUDENT_RECORD",
                entity_id=record.id,
                details={"presence": presence.value},
            )
            db.session.commit()
            flash("Estudante salvo com sucesso.", "success")
            return redirect(url_for("applicator.classroom", application_id=application.id))

    groups = []
    for subject, label in (("PORTUGUESE", "Língua Portuguesa"), ("MATHEMATICS", "Matemática")):
        subject_questions = [q for q in questions if q.test.subject.value == subject]
        if subject_questions:
            groups.append({"label": label, "questions": subject_questions})

    return render_template(
        "applicator/student.html",
        application=application,
        student=student,
        record=record,
        form=form,
        question_groups=groups,
        existing_answers=existing_answers,
    )
