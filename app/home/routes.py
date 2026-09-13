from flask import Blueprint, redirect, url_for
from flask_login import current_user, login_required

from app.models import UserRole

home_bp = Blueprint("home", __name__)


@home_bp.get("/")
@login_required
def index():
    if current_user.role in (UserRole.ADMIN, UserRole.COORDINATOR):
        return redirect(url_for("coordinator.dashboard"))
    if current_user.role == UserRole.APPLICATOR:
        return redirect(url_for("applicator.dashboard"))
    return redirect(url_for("auth.login"))
