import os
from contextlib import contextmanager

from flask import Flask
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


def _bootstrap_homologation(app):
    if os.getenv("ALLOW_HOMOLOGATION_BOOTSTRAP", "false").lower() != "true":
        return

    from .models import User, UserRole

    with app.app_context(), _bootstrap_lock():
        db.create_all()

        username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        name = os.getenv("BOOTSTRAP_ADMIN_NAME", "Administrador SARE").strip()

        if not username or not password:
            app.logger.warning("Bootstrap habilitado sem credenciais configuradas.")
            return

        if User.query.filter_by(username=username).first() is not None:
            return

        user = User(
            name=name,
            username=username,
            role=UserRole.ADMIN,
            is_active_user=True,
        )
        user.set_password(password)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"

    from . import models  # noqa: F401
    from .applicator.routes import applicator_bp
    from .auth.routes import auth_bp
    from .cli import register_cli
    from .coordinator.routes import coordinator_bp
    from .home.routes import home_bp
    from .routes.public import public_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(applicator_bp)
    app.register_blueprint(coordinator_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(public_bp)
    register_cli(app)

    _bootstrap_homologation(app)

    return app
