from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.auth.permissions import roles_required
from app.coordinator.forms import ApplicatorEditForm, ApplicatorPasswordResetForm
from app.extensions import db
from app.models import User, UserRole
from app.services.audit import record_audit


applicator_management_bp = Blueprint(
    "applicator_management",
    __name__,
    url_prefix="/coordenacao/aplicadores",
)


@applicator_management_bp.get("/")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def index():
    users = (
        User.query.filter_by(role=UserRole.APPLICATOR)
        .order_by(User.is_active_user.desc(), User.name.asc())
        .all()
    )
    return render_template(
        "coordinator/applicators.html",
        applicators=users,
        password_form=ApplicatorPasswordResetForm(),
    )


@applicator_management_bp.route("/<int:user_id>/editar", methods=["GET", "POST"])
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def edit(user_id: int):
    user = db.session.get(User, user_id)
    if user is None or user.role != UserRole.APPLICATOR:
        return ("Aplicador não encontrado.", 404)

    form = ApplicatorEditForm(obj=user)
    if form.validate_on_submit():
        username = form.username.data.strip()
        duplicate = (
            User.query.filter(User.username == username, User.id != user.id).first()
        )
        if duplicate is not None:
            form.username.errors.append("Já existe um usuário com esse login.")
            return render_template(
                "coordinator/applicator_edit.html",
                form=form,
                applicator=user,
            ), 409

        previous = {
            "name": user.name,
            "job_title": user.job_title,
            "username": user.username,
        }

        user.name = form.name.data.strip()
        user.job_title = form.job_title.data.strip()
        user.username = username

        record_audit(
            user_id=current_user.id,
            action="APPLICATOR_UPDATED",
            entity_type="USER",
            entity_id=user.id,
            details={
                "previous": previous,
                "current": {
                    "name": user.name,
                    "job_title": user.job_title,
                    "username": user.username,
                },
            },
        )
        db.session.commit()
        flash("Dados do aplicador atualizados com sucesso.", "success")
        return redirect(url_for("applicator_management.index"))

    return render_template(
        "coordinator/applicator_edit.html",
        form=form,
        applicator=user,
    )


@applicator_management_bp.post("/<int:user_id>/status")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def toggle_status(user_id: int):
    user = db.session.get(User, user_id)
    if user is None or user.role != UserRole.APPLICATOR:
        return ("Aplicador não encontrado.", 404)

    user.is_active_user = not user.is_active_user
    record_audit(
        user_id=current_user.id,
        action="APPLICATOR_STATUS_CHANGED",
        entity_type="USER",
        entity_id=user.id,
        details={"active": user.is_active_user},
    )
    db.session.commit()

    flash(
        "Aplicador ativado com sucesso."
        if user.is_active_user
        else "Aplicador desativado com sucesso.",
        "success",
    )
    return redirect(url_for("applicator_management.index"))


@applicator_management_bp.post("/<int:user_id>/senha")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def reset_password(user_id: int):
    user = db.session.get(User, user_id)
    if user is None or user.role != UserRole.APPLICATOR:
        return ("Aplicador não encontrado.", 404)

    form = ApplicatorPasswordResetForm()
    if not form.validate_on_submit():
        users = (
            User.query.filter_by(role=UserRole.APPLICATOR)
            .order_by(User.is_active_user.desc(), User.name.asc())
            .all()
        )
        return render_template(
            "coordinator/applicators.html",
            applicators=users,
            password_form=form,
            password_target_id=user.id,
        ), 422

    user.set_password(form.password.data)
    record_audit(
        user_id=current_user.id,
        action="APPLICATOR_PASSWORD_RESET",
        entity_type="USER",
        entity_id=user.id,
        details={},
    )
    db.session.commit()
    flash(f"Senha de {user.name} redefinida com sucesso.", "success")
    return redirect(url_for("applicator_management.index"))
