from datetime import datetime, timezone
from io import BytesIO

from flask import Blueprint, current_app, flash, redirect, send_file, url_for
from flask_login import current_user, login_required

from app.auth.permissions import roles_required
from app.extensions import db
from app.models import UserRole
from app.services.audit import record_audit
from app.services.backup import generate_structured_backup
from app.storage.factory import get_storage_service


backup_admin_bp = Blueprint(
    "backup_admin",
    __name__,
    url_prefix="/admin/backup",
)


@backup_admin_bp.get("/download")
@login_required
@roles_required(UserRole.ADMIN)
def download():
    payload = generate_structured_backup()

    record_audit(
        user_id=current_user.id,
        action="STRUCTURED_BACKUP_DOWNLOADED",
        entity_type="SYSTEM",
        entity_id=None,
        details={"size_bytes": len(payload)},
    )
    db.session.commit()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return send_file(
        BytesIO(payload),
        mimetype="application/gzip",
        as_attachment=True,
        download_name=f"sare_backup_{stamp}.json.gz",
    )


@backup_admin_bp.post("/drive")
@login_required
@roles_required(UserRole.ADMIN)
def upload_to_drive():
    payload = generate_structured_backup()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"sare_backup_{stamp}.json.gz"

    try:
        storage = get_storage_service("GOOGLE_DRIVE")
        if not hasattr(storage, "upload_system_backup"):
            # NormalizingStorage delega atributos conhecidos via composição;
            # o método de backup pertence ao backend interno.
            backend = getattr(storage, "backend", None) or getattr(storage, "_backend", None)
        else:
            backend = storage

        target = backend or storage
        stored = target.upload_system_backup(content=payload, filename=filename)
    except Exception as exc:
        current_app.logger.exception("Falha ao enviar backup estruturado para o Google Drive.")
        flash(
            f"Não foi possível enviar o backup ao Drive ({exc.__class__.__name__}). "
            "O backup local continua disponível para download.",
            "error",
        )
        return redirect(url_for("admin.dashboard"))

    record_audit(
        user_id=current_user.id,
        action="STRUCTURED_BACKUP_UPLOADED_TO_DRIVE",
        entity_type="SYSTEM",
        entity_id=stored.file_id,
        details={
            "size_bytes": len(payload),
            "filename": stored.stored_filename,
            "folder_id": stored.folder_id,
        },
    )
    db.session.commit()
    flash(
        f"Backup enviado ao Google Drive com sucesso: {stored.stored_filename}",
        "success",
    )
    return redirect(url_for("admin.dashboard"))
