from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.models import UserRole

home_bp = Blueprint("home", __name__)


@home_bp.get("/")
@login_required
def index():
    if current_user.role in (UserRole.ADMIN, UserRole.COORDINATOR):
        return redirect(url_for("coordinator.dashboard"))
    return render_template("home/index.html")
