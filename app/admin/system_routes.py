from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.auth.permissions import roles_required
from app.extensions import db
from app.models import UserRole
from app.services.audit import record_audit
from app.services.system_status import calculate_system_status
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
    return render_template(
        "admin/system_status.html",
        status=status,
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
