from __future__ import annotations

import secrets
import time
from collections import Counter
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required

from app.auth.permissions import roles_required
from app.coordinator.evaluation_forms import AnswerKeyImportForm
from app.extensions import db
from app.models import Evaluation, SubjectArea, UserRole
from app.services.answer_key_import import (
    AnswerKeyImportError,
    import_answer_key,
    parse_answer_key_xlsx,
)
from app.services.audit import record_audit
from app.services.evaluation_lock import evaluation_setup_lock_message


answer_key_preview_bp = Blueprint(
    "answer_key_preview",
    __name__,
    url_prefix="/coordenacao/gabarito-preview",
)

PREVIEW_DIR = Path("/tmp/sare_answer_key_previews")
PREVIEW_TTL_SECONDS = 2 * 60 * 60


def _cleanup_old_previews() -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - PREVIEW_TTL_SECONDS
    for path in PREVIEW_DIR.glob("*.xlsx"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            continue


def _form_with_choices():
    form = AnswerKeyImportForm()
    evaluations = Evaluation.query.order_by(
        Evaluation.school_year.desc(), Evaluation.name.asc()
    ).all()
    form.evaluation_id.choices = [
        (item.id, f"{item.name} ({item.school_year})") for item in evaluations
    ]
    return form


def _preview_summary(rows):
    by_grade = Counter(row.grade for row in rows)
    by_subject = Counter(
        "Língua Portuguesa"
        if row.subject == SubjectArea.PORTUGUESE
        else "Matemática"
        for row in rows
    )
    skills = {(row.grade, row.subject.value, row.skill_code) for row in rows}
    answer_distribution = Counter(row.correct_option for row in rows)
    return {
        "questions": len(rows),
        "grades": dict(sorted(by_grade.items())),
        "subjects": dict(sorted(by_subject.items())),
        "skills": len(skills),
        "answers": dict(sorted(answer_distribution.items())),
        "sample": rows[:30],
    }


@answer_key_preview_bp.route("/", methods=["GET", "POST"])
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def index():
    _cleanup_old_previews()
    form = _form_with_choices()

    if form.validate_on_submit():
        evaluation = db.session.get(Evaluation, form.evaluation_id.data)
        if evaluation is None:
            form.evaluation_id.errors.append("Avaliação não encontrada.")
            return render_template("coordinator/import_answer_key_preview.html", form=form), 404

        lock_message = evaluation_setup_lock_message(evaluation)
        if lock_message:
            flash(lock_message, "error")
            return redirect(url_for("coordinator.dashboard"))

        content = form.file.data.read()
        try:
            rows = parse_answer_key_xlsx(content)
        except AnswerKeyImportError as exc:
            return render_template(
                "coordinator/import_answer_key_preview.html",
                form=form,
                import_errors=exc.errors,
            ), 422

        token = secrets.token_urlsafe(24)
        (PREVIEW_DIR / f"{token}.xlsx").write_bytes(content)
        session["answer_key_preview"] = {
            "token": token,
            "evaluation_id": evaluation.id,
            "user_id": current_user.id,
        }
        return render_template(
            "coordinator/answer_key_preview_confirmation.html",
            evaluation=evaluation,
            token=token,
            summary=_preview_summary(rows),
        )

    return render_template("coordinator/import_answer_key_preview.html", form=form)


@answer_key_preview_bp.post("/<token>/confirmar")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def confirm(token: str):
    preview = session.get("answer_key_preview") or {}
    if preview.get("token") != token or preview.get("user_id") != current_user.id:
        flash("A prévia expirou ou pertence a outra sessão. Envie o gabarito novamente.", "error")
        return redirect(url_for("answer_key_preview.index"))

    evaluation = db.session.get(Evaluation, preview.get("evaluation_id"))
    if evaluation is None:
        flash("Avaliação não encontrada.", "error")
        return redirect(url_for("answer_key_preview.index"))

    lock_message = evaluation_setup_lock_message(evaluation)
    if lock_message:
        flash(lock_message, "error")
        return redirect(url_for("coordinator.dashboard"))

    path = PREVIEW_DIR / f"{token}.xlsx"
    if not path.exists():
        session.pop("answer_key_preview", None)
        flash("A prévia expirou. Envie o gabarito novamente.", "error")
        return redirect(url_for("answer_key_preview.index"))

    try:
        rows = parse_answer_key_xlsx(path.read_bytes())
        result = import_answer_key(evaluation, rows)
        record_audit(
            user_id=current_user.id,
            action="ANSWER_KEY_IMPORTED",
            entity_type="EVALUATION",
            entity_id=evaluation.id,
            details={
                "rows": result.rows_processed,
                "tests_created": result.tests_created,
                "skills_created": result.skills_created,
                "questions_created": result.questions_created,
                "questions_updated": result.questions_updated,
                "via_preview": True,
            },
        )
        db.session.commit()
    except AnswerKeyImportError as exc:
        db.session.rollback()
        flash("O gabarito deixou de ser válido: " + "; ".join(exc.errors[:3]), "error")
        return redirect(url_for("answer_key_preview.index"))
    except Exception:
        db.session.rollback()
        raise
    finally:
        path.unlink(missing_ok=True)
        session.pop("answer_key_preview", None)

    flash(
        f"Gabarito importado: {result.questions_created} questões novas e "
        f"{result.questions_updated} atualizadas.",
        "success",
    )
    return redirect(url_for("evaluation_management.detail", evaluation_id=evaluation.id))


@answer_key_preview_bp.post("/<token>/cancelar")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def cancel(token: str):
    preview = session.get("answer_key_preview") or {}
    if preview.get("token") == token and preview.get("user_id") == current_user.id:
        (PREVIEW_DIR / f"{token}.xlsx").unlink(missing_ok=True)
        session.pop("answer_key_preview", None)
    flash("Importação do gabarito cancelada. Nenhum dado foi gravado.", "success")
    return redirect(url_for("answer_key_preview.index"))
