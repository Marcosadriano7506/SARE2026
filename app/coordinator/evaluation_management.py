from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.auth.permissions import roles_required
from app.coordinator.evaluation_forms import EvaluationSettingsForm
from app.extensions import db
from app.models import Evaluation, UserRole
from app.services.audit import record_audit
from app.services.evaluation_readiness import (
    calculate_evaluation_readiness,
    evaluation_window_status,
)
from app.services.operational_readiness import calculate_operational_audit


evaluation_management_bp = Blueprint(
    "evaluation_management",
    __name__,
    url_prefix="/coordenacao/avaliacoes",
)


@evaluation_management_bp.route("/<int:evaluation_id>", methods=["GET", "POST"])
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def detail(evaluation_id: int):
    evaluation = db.session.get(Evaluation, evaluation_id)
    if evaluation is None:
        return ("Avaliação não encontrada.", 404)

    form = EvaluationSettingsForm(obj=evaluation)
    if form.validate_on_submit():
        evaluation.name = form.name.data.strip()
        evaluation.school_year = form.school_year.data
        evaluation.edition = (form.edition.data or "").strip() or None
        evaluation.starts_on = form.starts_on.data
        evaluation.ends_on = form.ends_on.data

        record_audit(
            user_id=current_user.id,
            action="EVALUATION_SETTINGS_UPDATED",
            entity_type="EVALUATION",
            entity_id=evaluation.id,
            details={
                "name": evaluation.name,
                "school_year": evaluation.school_year,
                "edition": evaluation.edition,
                "starts_on": evaluation.starts_on.isoformat() if evaluation.starts_on else None,
                "ends_on": evaluation.ends_on.isoformat() if evaluation.ends_on else None,
            },
        )
        db.session.commit()
        flash("Configurações da avaliação atualizadas.", "success")
        return redirect(
            url_for("evaluation_management.detail", evaluation_id=evaluation.id)
        )

    readiness = calculate_evaluation_readiness(evaluation)
    operational_audit = calculate_operational_audit(evaluation)
    window_open, window_message = evaluation_window_status(evaluation)
    return render_template(
        "coordinator/evaluation_detail.html",
        evaluation=evaluation,
        form=form,
        readiness=readiness,
        operational_audit=operational_audit,
        window_open=window_open,
        window_message=window_message,
    )


@evaluation_management_bp.post("/<int:evaluation_id>/status")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def toggle_status(evaluation_id: int):
    evaluation = db.session.get(Evaluation, evaluation_id)
    if evaluation is None:
        return ("Avaliação não encontrada.", 404)

    if not evaluation.is_active:
        readiness = calculate_evaluation_readiness(evaluation)
        if not readiness.ready:
            flash(
                "A avaliação não pode ser ativada enquanto houver pendências de preparação.",
                "error",
            )
            return redirect(
                url_for("evaluation_management.detail", evaluation_id=evaluation.id)
            )

    evaluation.is_active = not evaluation.is_active
    record_audit(
        user_id=current_user.id,
        action="EVALUATION_STATUS_CHANGED",
        entity_type="EVALUATION",
        entity_id=evaluation.id,
        details={"active": evaluation.is_active},
    )
    db.session.commit()

    flash(
        "Avaliação ativada para aplicação."
        if evaluation.is_active
        else "Avaliação desativada. Novos acessos por código foram bloqueados.",
        "success",
    )
    return redirect(
        url_for("evaluation_management.detail", evaluation_id=evaluation.id)
    )
