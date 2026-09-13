from __future__ import annotations

from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


PAGE_WIDTH, PAGE_HEIGHT = A4


def _draw_qr(pdf, value: str, x: float, y: float, size: float = 32 * mm):
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


def generate_class_codes_pdf(evaluation, applicator_url: str | None = None) -> bytes:
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)

    classrooms = sorted(
        evaluation.classes,
        key=lambda item: (item.school.name, item.grade, item.name),
    )

    cards_per_page = 4
    card_height = 62 * mm
    card_width = PAGE_WIDTH - 30 * mm
    left = 15 * mm
    top = PAGE_HEIGHT - 14 * mm

    for index, classroom in enumerate(classrooms):
        slot = index % cards_per_page
        if index and slot == 0:
            pdf.showPage()

        y_top = top - slot * card_height
        y_bottom = y_top - 55 * mm

        pdf.roundRect(
            left,
            y_bottom,
            card_width,
            51 * mm,
            4 * mm,
            stroke=1,
            fill=0,
        )

        text_x = left + 7 * mm
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(text_x, y_top - 10 * mm, "SARE — Código da Turma")

        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(text_x, y_top - 18 * mm, classroom.school.name[:70])

        pdf.setFont("Helvetica", 9)
        pdf.drawString(
            text_x,
            y_top - 25 * mm,
            f"{classroom.grade}º ano · {classroom.name}",
        )

        pdf.setFont("Helvetica", 8)
        pdf.drawString(
            text_x,
            y_top - 32 * mm,
            f"Avaliação: {evaluation.name}",
        )

        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawString(
            text_x,
            y_top - 43 * mm,
            classroom.access_code,
        )

        pdf.setFont("Helvetica-Oblique", 7)
        pdf.drawString(
            text_x,
            y_top - 49 * mm,
            "O aplicador deve estar autenticado antes de usar este código.",
        )

        qr_size = 34 * mm
        qr_value = (
            f"{applicator_url}?code={classroom.access_code}"
            if applicator_url
            else classroom.access_code
        )
        _draw_qr(
            pdf,
            qr_value,
            left + card_width - qr_size - 7 * mm,
            y_bottom + 8 * mm,
            qr_size,
        )

    if not classrooms:
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(20 * mm, PAGE_HEIGHT - 30 * mm, "SARE — Códigos das Turmas")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(
            20 * mm,
            PAGE_HEIGHT - 42 * mm,
            "Nenhuma turma cadastrada nesta avaliação.",
        )

    pdf.save()
    return output.getvalue()
