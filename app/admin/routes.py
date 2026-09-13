from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.admin.forms import CoordinatorForm
from app.auth.permissions import roles_required
from app.extensions import db
from app.models import User, UserRole
from app.services.audit import record_audit


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/")
@login_required
@roles_required(UserRole.ADMIN)
def dashboard():
    coordinators = (
        User.query.filter_by(role=UserRole.COORDINATOR)
        .order_by(User.is_active_user.desc(), User.name.asc())
        .all()
    )
    return render_template("admin/dashboard.html", coordinators=coordinators)


@admin_bp.route("/coordenadores/novo", methods=["GET", "POST"])
@login_required
@roles_required(UserRole.ADMIN)
def create_coordinator():
    form = CoordinatorForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first():
            form.username.errors.append("Já existe um usuário com esse login.")
            return render_template("admin/coordinator_form.html", form=form), 409

        coordinator = User(
            name=form.name.data.strip(),
            job_title=form.job_title.data.strip(),
            username=username,
            role=UserRole.COORDINATOR,
            is_active_user=True,
        )
        coordinator.set_password(form.password.data)
        db.session.add(coordinator)
        db.session.flush()

        record_audit(
            user_id=current_user.id,
            action="COORDINATOR_CREATED",
            entity_type="USER",
            entity_id=coordinator.id,
            details={"role": UserRole.COORDINATOR.value},
        )
        db.session.commit()

        flash("Coordenador cadastrado com sucesso.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/coordinator_form.html", form=form)


@admin_bp.post("/coordenadores/<int:user_id>/status")
@login_required
@roles_required(UserRole.ADMIN)
def toggle_coordinator_status(user_id: int):
    coordinator = db.session.get(User, user_id)
    if coordinator is None or coordinator.role != UserRole.COORDINATOR:
        return ("Coordenador não encontrado.", 404)

    coordinator.is_active_user = not coordinator.is_active_user
    record_audit(
        user_id=current_user.id,
        action="COORDINATOR_STATUS_CHANGED",
        entity_type="USER",
        entity_id=coordinator.id,
        details={"active": coordinator.is_active_user},
    )
    db.session.commit()
    flash("Status do coordenador atualizado.", "success")
    return redirect(url_for("admin.dashboard"))
