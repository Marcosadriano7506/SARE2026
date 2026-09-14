from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


PAGE_WIDTH, PAGE_HEIGHT = A4


def _bar(pdf, *, x, y, label, value, max_width=90 * mm):
    value = max(0.0, min(float(value), 100.0))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(x, y + 3, label)
    bar_x = x + 42 * mm
    bar_width = max_width * (value / 100)
    pdf.setFillGray(0.92)
    pdf.rect(bar_x, y, max_width, 7, fill=1, stroke=0)
    pdf.setFillGray(0.25)
    pdf.rect(bar_x, y, bar_width, 7, fill=1, stroke=0)
    pdf.setFillGray(0)
    pdf.drawRightString(bar_x + max_width + 12 * mm, y + 2, f"{value:.1f}%")


def _section_title(pdf, y, title):
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(18 * mm, y, title)
    return y - 6 * mm


def _new_page(pdf, evaluation_name):
    pdf.showPage()
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(18 * mm, PAGE_HEIGHT - 18 * mm, "SARE — Relatório Geral de Resultados")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(18 * mm, PAGE_HEIGHT - 24 * mm, evaluation_name)
    return PAGE_HEIGHT - 34 * mm


def generate_results_pdf(evaluation, analytics) -> bytes:
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(18 * mm, PAGE_HEIGHT - 18 * mm, "SARE — Relatório Geral de Resultados")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(18 * mm, PAGE_HEIGHT - 25 * mm, f"Avaliação: {evaluation.name}")

    y = PAGE_HEIGHT - 38 * mm
    y = _section_title(pdf, y, "Visão geral")

    pdf.setFont("Helvetica", 9)
    overview = [
        ("Turmas finalizadas", analytics.finalized_classes),
        ("Estudantes presentes", analytics.present_students),
        ("Estudantes ausentes", analytics.absent_students),
    ]
    for label, value in overview:
        pdf.drawString(20 * mm, y, f"{label}:")
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawRightString(75 * mm, y, str(value))
        pdf.setFont("Helvetica", 9)
        y -= 5 * mm

    y -= 3 * mm
    y = _section_title(pdf, y, "Desempenho")
    _bar(pdf, x=20 * mm, y=y, label="Geral", value=analytics.total_percent)
    y -= 8 * mm
    _bar(pdf, x=20 * mm, y=y, label="Língua Portuguesa", value=analytics.lp_percent)
    y -= 8 * mm
    _bar(pdf, x=20 * mm, y=y, label="Matemática", value=analytics.math_percent)
    y -= 12 * mm

    y = _section_title(pdf, y, "Proficiência")
    levels = analytics.proficiency_counts
    total_students = max(analytics.present_students, 1)
    for key, label in [
        ("DEFASAGEM", "Defasagem"),
        ("INTERMEDIARIO", "Intermediário"),
        ("AVANCADO", "Avançado"),
    ]:
        count = levels.get(key, 0)
        percent = count / total_students * 100
        _bar(pdf, x=20 * mm, y=y, label=label, value=percent)
        pdf.setFont("Helvetica", 7)
        pdf.drawString(166 * mm, y + 1, f"({count})")
        y -= 8 * mm

    y -= 5 * mm
    y = _section_title(pdf, y, "Ranking de escolas")
    pdf.setFont("Helvetica", 8)
    for idx, item in enumerate(analytics.schools[:10], start=1):
        pdf.drawString(20 * mm, y, f"{idx}. {item.name[:62]}")
        pdf.drawRightString(190 * mm, y, f"{item.percent:.2f}%")
        y -= 5 * mm
        if y < 28 * mm:
            y = _new_page(pdf, evaluation.name)

    y -= 4 * mm
    y = _section_title(pdf, y, "Ranking de turmas")
    pdf.setFont("Helvetica", 8)
    for idx, item in enumerate(analytics.classes[:15], start=1):
        pdf.drawString(20 * mm, y, f"{idx}. {item.name[:62]}")
        pdf.drawRightString(190 * mm, y, f"{item.percent:.2f}%")
        y -= 5 * mm
        if y < 28 * mm:
            y = _new_page(pdf, evaluation.name)

    critical_skills = sorted(
        analytics.skills,
        key=lambda item: (item.percent, item.grade, item.code),
    )

    y -= 4 * mm
    if y < 55 * mm:
        y = _new_page(pdf, evaluation.name)

    y = _section_title(pdf, y, "Habilidades com menor desempenho")
    pdf.setFont("Helvetica", 8)
    for item in critical_skills[:20]:
        component = "LP" if item.subject == "PORTUGUESE" else "MAT"
        label = f"{item.grade}º · {component} · {item.code}"
        pdf.drawString(20 * mm, y, label)
        pdf.drawRightString(190 * mm, y, f"{item.percent:.2f}%")
        y -= 5 * mm
        if y < 28 * mm:
            y = _new_page(pdf, evaluation.name)

    pdf.setFont("Helvetica-Oblique", 7)
    pdf.drawString(
        18 * mm,
        12 * mm,
        "Relatório gerado automaticamente pelo Sistema de Aplicação e Resultados do SARE.",
    )
    pdf.save()
    return output.getvalue()
