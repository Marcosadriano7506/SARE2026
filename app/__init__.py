from flask import Flask
from .config import Config
from .extensions import db, migrate, login_manager, csrf
from .routes.health import health_bp


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"

    app.register_blueprint(health_bp)

    return app
