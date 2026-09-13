from datetime import datetime, timezone
from io import BytesIO

from flask import Blueprint, send_file
from flask_login import current_user, login_required

from app.auth.permissions import roles_required
from app.extensions import db
from app.models import UserRole
from app.services.audit import record_audit
from app.services.backup import generate_structured_backup


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
