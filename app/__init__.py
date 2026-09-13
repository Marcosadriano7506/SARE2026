from flask import Flask

from .config import Config
from .extensions import csrf, db, login_manager, migrate
from .routes.health import health_bp


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

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(applicator_bp)
    app.register_blueprint(coordinator_bp)
    app.register_blueprint(home_bp)
    register_cli(app)

    return app
