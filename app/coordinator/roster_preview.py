from __future__ import annotations

import secrets
import time
from collections import Counter
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.auth.permissions import roles_required
from app.coordinator.evaluation_forms import RosterImportForm
from app.extensions import db
from app.models import Evaluation, UserRole
from app.services.audit import record_audit
from app.services.evaluation_lock import evaluation_setup_lock_message
from app.services.roster_import import (
    RosterImportError,
    import_roster,
    parse_roster_xlsx,
)


roster_preview_bp = Blueprint(
    "roster_preview",
    __name__,
    url_prefix="/coordenacao/base-preview",
)

PREVIEW_DIR = Path("/tmp/sare_roster_previews")
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


def _preview_summary(rows):
    schools = sorted({row.school for row in rows})
    classes = sorted({(row.school, row.grade, row.class_name) for row in rows})
    grades = Counter(row.grade for row in rows)

    duplicate_keys = Counter()
    for row in rows:
        if row.external_id:
            identity = (row.school.upper(), row.grade, row.class_name.upper(), "ID", row.external_id)
        else:
            identity = (row.school.upper(), row.grade, row.class_name.upper(), "NAME", row.student.upper())
        duplicate_keys[identity] += 1

    duplicates = sum(count - 1 for count in duplicate_keys.values() if count > 1)
    duplicate_groups = sum(1 for count in duplicate_keys.values() if count > 1)

    external_ids = Counter(
        row.external_id.strip().upper()
        for row in rows
        if row.external_id and row.external_id.strip()
    )
    duplicate_registration_groups = {
        key: count for key, count in external_ids.items() if count > 1
    }
    duplicate_registration_rows = sum(
        count - 1 for count in duplicate_registration_groups.values()
    )
    missing_registration = sum(
        1 for row in rows if not (row.external_id or "").strip()
    )

    class_sizes = Counter((row.school, row.grade, row.class_name) for row in rows)
    smallest_classes = sorted(
        (
            {
                "school": school,
                "grade": grade,
                "class_name": class_name,
                "students": count,
            }
            for (school, grade, class_name), count in class_sizes.items()
        ),
        key=lambda item: (item["students"], item["school"], item["class_name"]),
    )[:10]

    return {
        "students": len(rows),
        "schools": len(schools),
        "classes": len(classes),
        "grades": dict(sorted(grades.items())),
        "duplicate_rows": duplicates,
        "duplicate_groups": duplicate_groups,
        "duplicate_registration_rows": duplicate_registration_rows,
        "duplicate_registration_groups": len(duplicate_registration_groups),
        "duplicate_registration_examples": list(sorted(duplicate_registration_groups))[:10],
        "missing_registration": missing_registration,
        "smallest_classes": smallest_classes,
        "sample": rows[:25],
    }


def _form_with_choices():
    form = RosterImportForm()
    evaluations = Evaluation.query.order_by(
        Evaluation.school_year.desc(), Evaluation.name.asc()
    ).all()
    form.evaluation_id.choices = [
        (item.id, f"{item.name} ({item.school_year})") for item in evaluations
    ]
    return form


@roster_preview_bp.route("/", methods=["GET", "POST"])
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def index():
    _cleanup_old_previews()
    form = _form_with_choices()

    if form.validate_on_submit():
        evaluation = db.session.get(Evaluation, form.evaluation_id.data)
        if evaluation is None:
            form.evaluation_id.errors.append("Avaliação não encontrada.")
            return render_template("coordinator/import_roster_preview.html", form=form), 404

        lock_message = evaluation_setup_lock_message(evaluation)
        if lock_message:
            flash(lock_message, "error")
            return redirect(url_for("coordinator.dashboard"))

        content = form.file.data.read()
        try:
            rows = parse_roster_xlsx(content)
        except RosterImportError as exc:
            return render_template(
                "coordinator/import_roster_preview.html",
                form=form,
                import_errors=exc.errors,
            ), 422

        token = secrets.token_urlsafe(24)
        path = PREVIEW_DIR / f"{token}.xlsx"
        path.write_bytes(content)
        session["roster_preview"] = {
            "token": token,
            "evaluation_id": evaluation.id,
            "user_id": current_user.id,
        }

        return render_template(
            "coordinator/roster_preview_confirmation.html",
            evaluation=evaluation,
            token=token,
            summary=_preview_summary(rows),
        )

    return render_template("coordinator/import_roster_preview.html", form=form)


@roster_preview_bp.post("/<token>/confirmar")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def confirm(token: str):
    preview = session.get("roster_preview") or {}
    if (
        preview.get("token") != token
        or preview.get("user_id") != current_user.id
    ):
        flash("A prévia expirou ou pertence a outra sessão. Envie a planilha novamente.", "error")
        return redirect(url_for("roster_preview.index"))

    evaluation = db.session.get(Evaluation, preview.get("evaluation_id"))
    if evaluation is None:
        flash("Avaliação não encontrada.", "error")
        return redirect(url_for("roster_preview.index"))

    lock_message = evaluation_setup_lock_message(evaluation)
    if lock_message:
        flash(lock_message, "error")
        return redirect(url_for("coordinator.dashboard"))

    path = PREVIEW_DIR / f"{token}.xlsx"
    if not path.exists():
        session.pop("roster_preview", None)
        flash("A prévia expirou. Envie a planilha novamente.", "error")
        return redirect(url_for("roster_preview.index"))

    try:
        rows = parse_roster_xlsx(path.read_bytes())
        result = import_roster(evaluation, rows)
        record_audit(
            user_id=current_user.id,
            action="ROSTER_IMPORTED",
            entity_type="EVALUATION",
            entity_id=evaluation.id,
            details={
                "rows": result.rows_processed,
                "schools_created": result.schools_created,
                "classes_created": result.classes_created,
                "students_created": result.students_created,
                "via_preview": True,
            },
        )
        db.session.commit()
    except RosterImportError as exc:
        db.session.rollback()
        flash("A planilha deixou de ser válida: " + "; ".join(exc.errors[:3]), "error")
        return redirect(url_for("roster_preview.index"))
    except Exception:
        db.session.rollback()
        raise
    finally:
        path.unlink(missing_ok=True)
        session.pop("roster_preview", None)

    flash(
        f"Base importada: {result.students_created} estudantes novos, "
        f"{result.classes_created} turmas e {result.schools_created} escolas.",
        "success",
    )
    return redirect(url_for("evaluation_management.detail", evaluation_id=evaluation.id))


@roster_preview_bp.post("/<token>/cancelar")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def cancel(token: str):
    preview = session.get("roster_preview") or {}
    if preview.get("token") == token and preview.get("user_id") == current_user.id:
        (PREVIEW_DIR / f"{token}.xlsx").unlink(missing_ok=True)
        session.pop("roster_preview", None)
    flash("Importação cancelada. Nenhum dado foi gravado.", "success")
    return redirect(url_for("roster_preview.index"))
