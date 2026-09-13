import secrets
from io import BytesIO

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
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
from app.services.application_rules import can_finalize_application, summarize_application
from app.services.audit import record_audit
from app.services.evaluation_readiness import classroom_is_ready, evaluation_window_status
from app.services.image_validation import ImageValidationError, validate_uploaded_image
from app.services.receipt import generate_receipt_pdf
from app.storage.factory import get_storage_service

applicator_bp = Blueprint("applicator", __name__, url_prefix="/aplicador")


def _application_window_or_redirect(application):
    window_open, window_message = evaluation_window_status(application.classroom.evaluation)
    if window_open:
        return None
    flash(window_message or "Esta avaliação não está disponível para aplicação.", "error")
    return redirect(url_for("applicator.dashboard"))


@applicator_bp.route("/", methods=["GET", "POST"])
@login_required
@roles_required(UserRole.APPLICATOR)
def dashboard():
    form = ClassCodeForm()
    if request.method == "GET":
        code_from_qr = (request.args.get("code") or "").strip().upper()
        if code_from_qr:
            form.code.data = code_from_qr

    if form.validate_on_submit():
        code = form.code.data.strip().upper()
        classroom = ClassRoom.query.filter_by(access_code=code).with_for_update().first()

        if classroom is None:
            form.code.errors.append("Código de turma não encontrado.")
            return render_template("applicator/dashboard.html", form=form), 404

        window_open, window_message = evaluation_window_status(classroom.evaluation)
        if not window_open:
            flash(window_message or "Esta avaliação não está disponível para aplicação.", "error")
            return render_template("applicator/dashboard.html", form=form), 409

        classroom_ready, classroom_message = classroom_is_ready(classroom)
        if not classroom_ready:
            flash(classroom_message or "Esta turma ainda não está pronta para aplicação.", "error")
            return render_template("applicator/dashboard.html", form=form), 409

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
            return redirect(
                url_for("applicator.classroom", application_id=application.id)
            )

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

    blocked = _application_window_or_redirect(application)
    if blocked is not None and application.status != ApplicationStatus.FINALIZED:
        return blocked

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

    can_finalize, summary, finalize_reason = can_finalize_application(application)

    return render_template(
        "applicator/classroom.html",
        application=application,
        rows=rows,
        can_finalize=can_finalize,
        summary=summary,
        finalize_reason=finalize_reason,
        saved_student_id=request.args.get("saved", type=int),
    )


@applicator_bp.post("/turma/<int:application_id>/finalizar")
@login_required
@roles_required(UserRole.APPLICATOR)
def finalize_classroom(application_id: int):
    application = (
        ClassApplication.query
        .filter_by(id=application_id)
        .with_for_update()
        .first()
    )
    if application is None:
        abort(404)
    if application.applicator_id != current_user.id:
        abort(403)

    # Finalização é idempotente: reenvios/duplo clique retornam à mesma
    # tela final sem criar novo recibo ou novo evento de auditoria.
    if application.status == ApplicationStatus.FINALIZED:
        return redirect(
            url_for("applicator.finalized", application_id=application.id)
        )

    blocked = _application_window_or_redirect(application)
    if blocked is not None:
        return blocked

    allowed, summary, reason = can_finalize_application(application)
    if not allowed:
        flash(reason or "A turma ainda não pode ser finalizada.", "error")
        return redirect(url_for("applicator.classroom", application_id=application.id))

    application.status = ApplicationStatus.FINALIZED
    application.finalized_at = utcnow()
    application.finalized_by = current_user.id
    if not application.receipt_code:
        application.receipt_code = f"SARE-{secrets.token_hex(6).upper()}"

    record_audit(
        user_id=current_user.id,
        action="CLASS_APPLICATION_FINALIZED",
        entity_type="CLASS_APPLICATION",
        entity_id=application.id,
        details={
            "total_students": summary.total_students,
            "present_students": summary.present_students,
            "absent_students": summary.absent_students,
        },
    )
    db.session.commit()
    return redirect(url_for("applicator.finalized", application_id=application.id))


@applicator_bp.get("/turma/<int:application_id>/finalizada")
@login_required
@roles_required(UserRole.APPLICATOR)
def finalized(application_id: int):
    application = db.session.get(ClassApplication, application_id)
    if application is None:
        abort(404)
    if application.applicator_id != current_user.id:
        abort(403)
    if application.status != ApplicationStatus.FINALIZED:
        abort(409)

    summary = summarize_application(application)
    return render_template(
        "applicator/finalized.html",
        application=application,
        summary=summary,
    )


@applicator_bp.get("/turma/<int:application_id>/comprovante")
@login_required
@roles_required(UserRole.APPLICATOR)
def receipt(application_id: int):
    application = db.session.get(ClassApplication, application_id)
    if application is None:
        abort(404)
    if application.applicator_id != current_user.id:
        abort(403)
    if application.status != ApplicationStatus.FINALIZED:
        abort(409)

    summary = summarize_application(application)
    verification_url = url_for(
        "public.verify_receipt",
        receipt_code=application.receipt_code,
        _external=True,
    )
    pdf = generate_receipt_pdf(application, summary, verification_url)
    filename = f"comprovante_{application.classroom.access_code}.pdf"
    return send_file(
        BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


def _application_and_student(application_id: int, student_id: int):
    if request.method == "POST":
        # Serializa gravações da mesma turma. Isso protege contra duplo envio
        # quase simultâneo (duplo toque, Enter repetido ou reenvio do browser).
        application = (
            ClassApplication.query
            .filter_by(id=application_id)
            .with_for_update()
            .first()
        )
    else:
        application = db.session.get(ClassApplication, application_id)

    if application is None:
        abort(404)
    if application.applicator_id != current_user.id:
        abort(403)
    if application.status == ApplicationStatus.FINALIZED:
        abort(409)

    blocked = _application_window_or_redirect(application)
    if blocked is not None:
        abort(409, description="A avaliação não está disponível para edição.")

    student = db.session.get(Student, student_id)
    if student is None or student.class_id != application.class_id:
        abort(404)
    return application, student


def _safe_delete_discursive(upload) -> None:
    if upload is None or not upload.storage_file_id:
        return
    try:
        get_storage_service(upload.storage_provider).delete(upload.storage_file_id)
    except Exception:
        current_app.logger.exception("Falha ao remover arquivo discursivo antigo.")


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

    previous_presence = record.presence.value if record is not None else None
    previous_declaration = (
        record.self_declaration.value
        if record is not None and record.self_declaration is not None
        else None
    )
    previous_had_discursive = bool(record is not None and record.discursive is not None)

    if request.method == "GET":
        record_audit(
            user_id=current_user.id,
            action="STUDENT_RECORD_OPENED",
            entity_type="STUDENT",
            entity_id=student.id,
            details={
                "application_id": application.id,
                "existing_record": record is not None,
            },
        )
        db.session.commit()

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
        elif photo:
            try:
                validate_uploaded_image(photo)
            except ImageValidationError as exc:
                form.discursive.errors.append(str(exc))

        if not form.discursive.errors:
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
                    _safe_delete_discursive(record.discursive)
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
                        old_provider = record.discursive.storage_provider
                        old_file_id = record.discursive.storage_file_id
                        if not (
                            old_provider == stored.provider
                            and old_file_id == stored.file_id
                        ):
                            _safe_delete_discursive(record.discursive)
                        record.discursive.storage_provider = stored.provider
                        record.discursive.storage_file_id = stored.file_id
                        record.discursive.storage_folder_id = stored.folder_id
                        record.discursive.original_filename = photo.filename
                        record.discursive.stored_filename = stored.stored_filename
                        record.discursive.mime_type = stored.mime_type
                        record.discursive.file_size_bytes = stored.size_bytes
                        record.discursive.uploaded_by = current_user.id
                        record.discursive.uploaded_at = utcnow()

            if presence == StudentPresence.PRESENT:
                new_answers = {}
                for question in questions:
                    raw_value = request.form.get(f"q_{question.id}")
                    new_answers[question.id] = (
                        raw_value if raw_value in {"A", "B", "C", "D"} else None
                    )
            else:
                new_answers = {question.id: None for question in questions}

            changed_questions = [
                f"{question.test.subject.value}:Q{question.number}"
                for question in questions
                if existing_answers.get(question.id) != new_answers.get(question.id)
            ]
            new_declaration = (
                record.self_declaration.value
                if record.self_declaration is not None
                else None
            )

            record_audit(
                user_id=current_user.id,
                action="STUDENT_RECORD_SAVED",
                entity_type="STUDENT_RECORD",
                entity_id=record.id,
                details={
                    "presence_before": previous_presence,
                    "presence_after": presence.value,
                    "questions_changed": changed_questions,
                    "self_declaration_changed": previous_declaration != new_declaration,
                    "discursive_changed": bool(photo) or (
                        previous_had_discursive
                        and presence == StudentPresence.ABSENT
                    ),
                },
            )

            if photo and record.discursive is not None:
                record_audit(
                    user_id=current_user.id,
                    action="DISCUSSIVE_UPLOADED",
                    entity_type="STUDENT_RECORD",
                    entity_id=record.id,
                    details={
                        "storage_provider": record.discursive.storage_provider,
                        "size_bytes": record.discursive.file_size_bytes,
                        "replaced_existing": previous_had_discursive,
                    },
                )
            elif previous_had_discursive and presence == StudentPresence.ABSENT:
                record_audit(
                    user_id=current_user.id,
                    action="DISCUSSIVE_REMOVED",
                    entity_type="STUDENT_RECORD",
                    entity_id=record.id,
                    details={"reason": "STUDENT_MARKED_ABSENT"},
                )

            db.session.commit()
            flash("Estudante salvo com sucesso.", "success")
            return redirect(
                url_for(
                    "applicator.classroom",
                    application_id=application.id,
                    saved=student.id,
                )
            )

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
