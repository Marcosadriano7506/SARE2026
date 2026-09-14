import hashlib
import hmac

from flask import current_app, request

from app.extensions import db
from app.models import AuditLog


def _hashed_ip() -> str | None:
    if not request:
        return None
    raw_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    raw_ip = raw_ip.split(",")[0].strip()
    if not raw_ip:
        return None
    key = current_app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(key, raw_ip.encode("utf-8"), hashlib.sha256).hexdigest()


def record_audit(
    *,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    details: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=details or {},
        ip_hash=_hashed_ip(),
    )
    db.session.add(log)
    return log
