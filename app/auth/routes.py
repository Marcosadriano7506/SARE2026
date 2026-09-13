from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import OperationalError

from app.auth.forms import LoginForm
from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _find_user_with_retry(username: str):
    try:
        return User.query.filter_by(username=username).first()
    except OperationalError:
        db.session.rollback()
        db.engine.dispose()
        return User.query.filter_by(username=username).first()


def _is_safe_next_url(target: str | None) -> bool:
    if not target:
        return False
    host_url = request.host_url
    reference = urlparse(host_url)
    test = urlparse(urljoin(host_url, target))
    return test.scheme in ("http", "https") and reference.netloc == test.netloc


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home.index"))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        # Uma conexão SSL pode ser encerrada pelo pooler entre o checkout
        # e a primeira consulta. Fazemos um único retry limpo para evitar
        # transformar uma falha transitória em erro 500 de login.
        user = _find_user_with_retry(username)
        if not user or not user.is_active or not user.check_password(form.password.data):
            flash("Login ou senha inválidos.", "error")
            return render_template("auth/login.html", form=form), 401

        session.permanent = True
        login_user(user)
        next_url = request.args.get("next")
        if _is_safe_next_url(next_url):
            return redirect(next_url)
        return redirect(url_for("home.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
