from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.auth.permissions import roles_required
from app.coordinator.forms import ApplicatorForm
from app.extensions import db
from app.models import User, UserRole
from app.services.audit import record_audit

coordinator_bp = Blueprint("coordinator", __name__, url_prefix="/coordenacao")


@coordinator_bp.get("/")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def dashboard():
    applicators = (
        User.query.filter_by(role=UserRole.APPLICATOR)
        .order_by(User.is_active_user.desc(), User.name.asc())
        .all()
    )
    return render_template("coordinator/dashboard.html", applicators=applicators)


@coordinator_bp.route("/aplicadores/novo", methods=["GET", "POST"])
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def create_applicator():
    form = ApplicatorForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first():
            form.username.errors.append("Já existe um usuário com esse login.")
            return render_template("coordinator/applicator_form.html", form=form), 409

        applicator = User(
            name=form.name.data.strip(),
            job_title=form.job_title.data.strip(),
            username=username,
            role=UserRole.APPLICATOR,
            is_active_user=True,
        )
        applicator.set_password(form.password.data)
        db.session.add(applicator)
        db.session.flush()

        record_audit(
            user_id=current_user.id,
            action="APPLICATOR_CREATED",
            entity_type="USER",
            entity_id=applicator.id,
            details={"role": UserRole.APPLICATOR.value},
        )
        db.session.commit()

        flash("Aplicador cadastrado com sucesso.", "success")
        return redirect(url_for("coordinator.dashboard"))

    return render_template("coordinator/applicator_form.html", form=form)
