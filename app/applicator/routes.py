from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.applicator.forms import ClassCodeForm
from app.auth.permissions import roles_required
from app.extensions import db
from app.models import (
    ApplicationStatus,
    ClassApplication,
    ClassRoom,
    StudentPresence,
    UserRole,
    utcnow,
)
from app.services.audit import record_audit

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
