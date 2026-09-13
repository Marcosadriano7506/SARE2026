import os
from contextlib import contextmanager

from flask import Flask, redirect, request, session, url_for
from flask_login import logout_user
from sqlalchemy.exc import IntegrityError

from .config import Config
from .extensions import csrf, db, login_manager, migrate
from .routes.health import health_bp


@contextmanager
def _bootstrap_lock():
    lock_path = "/tmp/sare-homologation-bootstrap.lock"
    lock_file = open(lock_path, "w")
    try:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()


def _ensure_bootstrap_user(*, username, password, name, role, job_title=None):
    from .models import User

    if not username or not password:
        return None

    user = User.query.filter_by(username=username).first()
    if user is not None:
        return user

    user = User(
        name=name,
        job_title=job_title,
        username=username,
        role=role,
        is_active_user=True,
    )
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return User.query.filter_by(username=username).first()
    return user


def _bootstrap_homologation(app):
    if os.getenv("ALLOW_HOMOLOGATION_BOOTSTRAP", "false").lower() != "true":
        return

    from .models import UserRole

    with app.app_context(), _bootstrap_lock():
        db.create_all()

        admin = _ensure_bootstrap_user(
            username=os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip(),
            password=os.getenv("BOOTSTRAP_ADMIN_PASSWORD", ""),
            name=os.getenv("BOOTSTRAP_ADMIN_NAME", "Administrador SARE").strip(),
            role=UserRole.ADMIN,
        )
        if admin is None:
            app.logger.warning("Bootstrap de administrador sem credenciais completas.")

        applicator = _ensure_bootstrap_user(
            username=os.getenv("BOOTSTRAP_APPLICATOR_USERNAME", "").strip(),
            password=os.getenv("BOOTSTRAP_APPLICATOR_PASSWORD", ""),
            name=os.getenv("BOOTSTRAP_APPLICATOR_NAME", "Aplicador DEMO").strip(),
            role=UserRole.APPLICATOR,
            job_title=os.getenv("BOOTSTRAP_APPLICATOR_JOB_TITLE", "Professor").strip(),
        )

        if (
            os.getenv("AUTO_CREATE_DEMO_DATA", "false").lower() == "true"
            and applicator is not None
        ):
            from .services.demo_data import create_demo_dataset

            create_demo_dataset()


def _check_external_integrations(app):
    provider = os.getenv("STORAGE_PROVIDER", "LOCAL_HOMOLOGATION").upper()
    with app.app_context():
        database_backend = db.engine.url.get_backend_name()

    oauth_client = bool(os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip())
    oauth_secret = bool(os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip())
    oauth_refresh = bool(os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN", "").strip())
    drive_root = bool(os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "").strip())

    app.logger.warning(
        "SARE runtime config: database=%s storage=%s "
        "oauth_client=%s oauth_secret=%s oauth_refresh=%s drive_root=%s",
        database_backend,
        provider,
        oauth_client,
        oauth_secret,
        oauth_refresh,
        drive_root,
    )

    if provider != "GOOGLE_DRIVE":
        return

    try:
        from .storage.factory import get_storage_service

        storage = get_storage_service("GOOGLE_DRIVE")
        message = storage.check_connection()
        app.logger.warning("SARE storage check: Google Drive OK — %s", message)
    except Exception:
        app.logger.exception("SARE storage check: Google Drive FAILED")


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"

    from . import models  # noqa: F401
    from .admin.backup_routes import backup_admin_bp
    from .admin.routes import admin_bp
    from .admin.google_drive_oauth import google_drive_oauth_bp
    from .admin.system_routes import system_admin_bp
    from .applicator.routes import applicator_bp
    from .auth.routes import auth_bp
    from .cli import register_cli
    from .coordinator.answer_key_preview import answer_key_preview_bp
    from .coordinator.applicator_management import applicator_management_bp
    from .coordinator.audit_routes import audit_bp
    from .coordinator.evaluation_management import evaluation_management_bp
    from .coordinator.roster_preview import roster_preview_bp
    from .coordinator.routes import coordinator_bp
    from .home.routes import home_bp
    from .routes.public import public_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(google_drive_oauth_bp)
    app.register_blueprint(system_admin_bp)
    app.register_blueprint(backup_admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(applicator_bp)
    app.register_blueprint(coordinator_bp)
    app.register_blueprint(applicator_management_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(evaluation_management_bp)
    app.register_blueprint(roster_preview_bp)
    app.register_blueprint(answer_key_preview_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(public_bp)
    register_cli(app)

    @app.before_request
    def enforce_active_user():
        raw_user_id = session.get("_user_id")
        if not raw_user_id:
            return None

        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            logout_user()
            if request.endpoint != "auth.login":
                return redirect(url_for("auth.login"))
            return None

        session_user = db.session.get(models.User, user_id, populate_existing=True)
        if session_user is None or not session_user.is_active_user:
            logout_user()
            if request.endpoint != "auth.login":
                return redirect(url_for("auth.login"))
        return None

    @app.after_request
    def security_response_headers(response):
        if not request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.context_processor
    def inject_environment_flags():
        return {
            "is_homologation": os.getenv(
                "ALLOW_HOMOLOGATION_BOOTSTRAP", "false"
            ).lower() == "true"
        }

    _bootstrap_homologation(app)
    _check_external_integrations(app)

    return app
