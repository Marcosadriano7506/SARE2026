from flask import Blueprint, current_app, render_template
from flask_login import login_required

from app.auth.permissions import roles_required
from app.models import UserRole
from app.services.system_status import calculate_system_status


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
    return render_template("admin/system_status.html", status=status)
