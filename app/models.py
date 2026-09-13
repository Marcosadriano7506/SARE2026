from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    COORDINATOR = "COORDINATOR"
    APPLICATOR = "APPLICATOR"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    job_title = db.Column(db.String(160), nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole, name="user_role"), nullable=False, index=True)
    is_active_user = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    @property
    def is_active(self):
        return self.is_active_user

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password, method="scrypt")

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
