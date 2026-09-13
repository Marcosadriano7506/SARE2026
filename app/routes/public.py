from flask import Blueprint, render_template

from app.models import ApplicationStatus, ClassApplication

public_bp = Blueprint("public", __name__)


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
