from __future__ import annotations

from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def receipt_payload(application, summary) -> dict:
    classroom = application.classroom
    return {
        "evaluation": classroom.evaluation.name,
        "school": classroom.school.name,
        "class_name": classroom.name,
        "grade": classroom.grade,
        "applicator": application.applicator.name if application.applicator else "",
        "job_title": application.applicator.job_title if application.applicator else "",
        "total_students": summary.total_students,
        "present_students": summary.present_students,
        "absent_students": summary.absent_students,
        "completed_records": summary.completed_records,
        "confirmed_discursives": summary.confirmed_discursives,
        "started_at": application.started_at,
        "finalized_at": application.finalized_at,
        "class_code": classroom.access_code,
        "receipt_code": application.receipt_code,
        "status": "FINALIZADA",
    }


def _draw_qr(pdf, value: str, x: float, y: float, size: float = 86) -> None:
    qr = QrCodeWidget(value)
    bounds = qr.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    drawing = Drawing(
        size,
        size,
        transform=[size / width, 0, 0, size / height, 0, 0],
    )
    drawing.add(qr)
    renderPDF.draw(drawing, pdf, x, y)


def generate_receipt_pdf(application, summary, verification_url: str | None = None) -> bytes:
    payload = receipt_payload(application, summary)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 56
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(48, y, "SARE — Comprovante de Finalização")
    y -= 28

    pdf.setFont("Helvetica", 10)
    lines = [
        f"Avaliação: {payload['evaluation']}",
        f"Escola: {payload['school']}",
        f"Turma: {payload['class_name']} — {payload['grade']}º ano",
        f"Aplicador: {payload['applicator']}",
        f"Função: {payload['job_title'] or 'Não informada'}",
        "",
        f"Total de estudantes: {payload['total_students']}",
        f"Presentes: {payload['present_students']}",
        f"Ausentes: {payload['absent_students']}",
        f"Registros concluídos: {payload['completed_records']}",
        f"Discursivas confirmadas: {payload['confirmed_discursives']}",
        "",
        f"Início: {payload['started_at'].strftime('%d/%m/%Y %H:%M') if payload['started_at'] else '-'}",
        f"Finalização: {payload['finalized_at'].strftime('%d/%m/%Y %H:%M') if payload['finalized_at'] else '-'}",
        f"Código da turma: {payload['class_code']}",
        f"Código do comprovante: {payload['receipt_code']}",
        "",
        "Status: FINALIZADA COM SUCESSO",
    ]

    for line in lines:
        if not line:
            y -= 8
            continue
        pdf.drawString(48, y, line)
        y -= 17

    if verification_url:
        _draw_qr(pdf, verification_url, width - 138, 76, 86)
        pdf.setFont("Helvetica", 7)
        pdf.drawCentredString(width - 95, 65, "Escaneie para validar")

    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawString(
        48,
        42,
        "Documento gerado automaticamente pelo Sistema de Aplicação e Resultados do SARE.",
    )
    pdf.save()
    return buffer.getvalue()
