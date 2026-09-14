from flask import Blueprint, current_app, render_template, send_from_directory

from app.models import ApplicationStatus, ClassApplication

public_bp = Blueprint("public", __name__)


@public_bp.get("/sobre")
def about():
    return render_template("public/about.html")


@public_bp.get("/privacidade")
def privacy():
    return render_template("public/privacy.html")


@public_bp.get("/termos")
def terms():
    return render_template("public/terms.html")


@public_bp.get("/sw.js")
def service_worker():
    response = send_from_directory(
        current_app.static_folder,
        "sw.js",
        mimetype="application/javascript",
    )
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@public_bp.get("/verificar/<receipt_code>")
def verify_receipt(receipt_code: str):
    application = ClassApplication.query.filter_by(receipt_code=receipt_code).first()
    valid = bool(
        application is not None
        and application.status == ApplicationStatus.FINALIZED
        and application.receipt_code
    )
    return (
        render_template(
            "public/verify_receipt.html",
            valid=valid,
            application=application if valid else None,
            receipt_code=receipt_code,
        ),
        200 if valid else 404,
    )
