from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.auth.permissions import roles_required
from app.extensions import db
from app.models import Evaluation, User, UserRole
from app.services.system_status import calculate_system_status
from app.services.load_fixture import LOAD_EVALUATION_NAME, create_load_fixture, delete_load_fixture
from app.services.audit import record_audit
from app.storage.factory import get_storage_service


system_admin_bp = Blueprint(
    "system_admin",
    __name__,
    url_prefix="/admin/ambiente",
)


@system_admin_bp.get("/")
@login_required
@roles_required(UserRole.ADMIN)
def index():
    status = calculate_system_status(current_app)
    load_evaluation = Evaluation.query.filter_by(name=LOAD_EVALUATION_NAME).first()
    load_stats = {
        "users": User.query.filter(User.username.like("load%")).count(),
        "classes": len(load_evaluation.classes) if load_evaluation else 0,
        "students": (
            sum(len(classroom.students) for classroom in load_evaluation.classes)
            if load_evaluation else 0
        ),
    }
    return render_template(
        "admin/system_status.html",
        status=status,
        load_stats=load_stats,
    )


@system_admin_bp.post("/testar-drive")
@login_required
@roles_required(UserRole.ADMIN)
def test_drive_write():
    try:
        storage = get_storage_service("GOOGLE_DRIVE")
        message = storage.smoke_test_write_delete()
        record_audit(
            user_id=current_user.id,
            action="GOOGLE_DRIVE_SMOKE_TEST",
            entity_type="SYSTEM",
            entity_id=None,
            details={"result": "success"},
        )
        db.session.commit()
        flash(message, "success")
    except Exception as exc:
        current_app.logger.exception("Falha no smoke test do Google Drive.")
        flash(f"Falha no teste do Google Drive: {exc.__class__.__name__}", "error")

    return redirect(url_for("system_admin.index"))


@system_admin_bp.post("/carga/criar")
@login_required
@roles_required(UserRole.ADMIN)
def create_load_data():
    if not current_app.config.get("ALLOW_HOMOLOGATION_BOOTSTRAP", False):
        return ("Fixture de carga só é permitido em homologação.", 409)

    if (request.form.get("confirm") or "").strip().upper() != "CRIAR":
        flash("Digite CRIAR para confirmar o fixture sintético.", "error")
        return redirect(url_for("system_admin.index"))

    try:
        users = int(request.form.get("users", "20"))
        students_per_class = int(request.form.get("students_per_class", "30"))
        result = create_load_fixture(
            user_count=users,
            students_per_class=students_per_class,
        )
        record_audit(
            user_id=current_user.id,
            action="LOAD_FIXTURE_CREATED",
            entity_type="SYSTEM",
            entity_id=None,
            details=result,
        )
        db.session.commit()
        flash(
            f"Fixture pronto: {result['total_users']} aplicadores sintéticos, "
            f"{result['students_per_class']} estudantes por turma.",
            "success",
        )
    except (ValueError, RuntimeError) as exc:
        db.session.rollback()
        flash(str(exc), "error")

    return redirect(url_for("system_admin.index"))


@system_admin_bp.post("/carga/remover")
@login_required
@roles_required(UserRole.ADMIN)
def remove_load_data():
    if not current_app.config.get("ALLOW_HOMOLOGATION_BOOTSTRAP", False):
        return ("Fixture de carga só é permitido em homologação.", 409)

    if (request.form.get("confirm") or "").strip().upper() != "REMOVER":
        flash("Digite REMOVER para confirmar a limpeza.", "error")
        return redirect(url_for("system_admin.index"))

    try:
        result = delete_load_fixture()
        record_audit(
            user_id=current_user.id,
            action="LOAD_FIXTURE_REMOVED",
            entity_type="SYSTEM",
            entity_id=None,
            details=result,
        )
        db.session.commit()
        flash("Fixture sintético removido com sucesso.", "success")
    except RuntimeError as exc:
        db.session.rollback()
        flash(str(exc), "error")

    return redirect(url_for("system_admin.index"))
