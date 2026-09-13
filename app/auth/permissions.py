from functools import wraps

from flask import abort
from flask_login import current_user

from app.models import UserRole


def roles_required(*allowed_roles: UserRole):
    allowed = set(allowed_roles)

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in allowed:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
