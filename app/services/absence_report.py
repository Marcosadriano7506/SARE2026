from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate_absence_report_pdf(evaluation, absences) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    def header():
        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawString(42, height - 46, "SARE — Relatório de Estudantes Ausentes")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(42, height - 62, f"Avaliação: {evaluation.name}")
        return height - 86

    y = header()
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(42, y, "ANO")
    pdf.drawString(78, y, "ESCOLA")
    pdf.drawString(275, y, "TURMA")
    pdf.drawString(390, y, "ESTUDANTE")
    y -= 14

    pdf.setFont("Helvetica", 8)
    for item in absences:
        if y < 52:
            pdf.showPage()
            y = header()
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(42, y, "ANO")
            pdf.drawString(78, y, "ESCOLA")
            pdf.drawString(275, y, "TURMA")
            pdf.drawString(390, y, "ESTUDANTE")
            y -= 14
            pdf.setFont("Helvetica", 8)

        pdf.drawString(42, y, f"{item.grade}º")
        pdf.drawString(78, y, item.school_name[:38])
        pdf.drawString(275, y, item.class_name[:20])
        pdf.drawString(390, y, item.student_name[:30])
        y -= 13

    if not absences:
        pdf.drawString(42, y, "Nenhum estudante ausente em turmas finalizadas.")

    pdf.setFont("Helvetica-Oblique", 7)
    pdf.drawString(
        42,
        30,
        "Relatório administrativo gerado automaticamente pelo Sistema SARE.",
    )
    pdf.save()
    return buffer.getvalue()
