from flask import Blueprint, jsonify
from sqlalchemy import text
from app.extensions import db

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    db_status = "ok"
    status_code = 200
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db.session.rollback()
        db_status = "unavailable"
        status_code = 503

    return jsonify({
        "status": "ok" if status_code == 200 else "degraded",
        "database": db_status,
    }), status_code
