from __future__ import annotations

import os

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import login_required
from google_auth_oauthlib.flow import Flow

from app.auth.permissions import roles_required
from app.models import UserRole
from app.storage.google_drive import (
    DRIVE_FILE_SCOPE,
    ensure_oauth_root_folders,
)


google_drive_oauth_bp = Blueprint(
    "google_drive_oauth",
    __name__,
    url_prefix="/admin/google-drive",
)


def _oauth_client_config():
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "GOOGLE_OAUTH_CLIENT_ID e GOOGLE_OAUTH_CLIENT_SECRET não configurados."
        )

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def _redirect_uri() -> str:
    configured = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    if configured:
        return configured
    return url_for(
        "google_drive_oauth.callback",
        _external=True,
        _scheme="https",
    )


@google_drive_oauth_bp.get("/")
@login_required
@roles_required(UserRole.ADMIN)
def index():
    configured = bool(
        os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
        and os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    )
    return render_template(
        "admin/google_drive_oauth.html",
        configured=configured,
        redirect_uri=_redirect_uri(),
    )


@google_drive_oauth_bp.post("/start")
@login_required
@roles_required(UserRole.ADMIN)
def start():
    try:
        flow = Flow.from_client_config(
            _oauth_client_config(),
            scopes=[DRIVE_FILE_SCOPE],
        )
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("google_drive_oauth.index"))

    flow.redirect_uri = _redirect_uri()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    session["google_drive_oauth_state"] = state
    return redirect(authorization_url)


@google_drive_oauth_bp.get("/oauth/callback")
@login_required
@roles_required(UserRole.ADMIN)
def callback():
    if request.args.get("error"):
        flash(
            f"Google não autorizou o acesso: {request.args.get('error')}",
            "error",
        )
        return redirect(url_for("google_drive_oauth.index"))

    expected_state = session.pop("google_drive_oauth_state", None)
    received_state = request.args.get("state")
    if not expected_state or received_state != expected_state:
        return ("Estado OAuth inválido ou expirado.", 400)

    flow = Flow.from_client_config(
        _oauth_client_config(),
        scopes=[DRIVE_FILE_SCOPE],
        state=expected_state,
    )
    redirect_uri = _redirect_uri()
    flow.redirect_uri = redirect_uri

    query = request.query_string.decode("utf-8")
    authorization_response = f"{redirect_uri}?{query}"
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    refresh_token = credentials.refresh_token
    if not refresh_token:
        return (
            "O Google não retornou refresh token. "
            "Tente novamente usando o botão Conectar Google Drive.",
            409,
        )

    _sare_folder_id, discursivas_folder_id = ensure_oauth_root_folders(
        credentials
    )

    return render_template(
        "admin/google_drive_oauth_result.html",
        refresh_token=refresh_token,
        root_folder_id=discursivas_folder_id,
    )
