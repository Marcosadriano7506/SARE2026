from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from xml.sax.saxutils import escape

from app.models import ApplicationStatus, StudentPresence, SubjectArea


BLUE = HexColor("#0A55B8")
DARK_BLUE = HexColor("#07357E")
LIGHT_BLUE = HexColor("#EAF3FF")
RED = HexColor("#FF3B30")
LIGHT_RED = HexColor("#FFF0EE")
TEXT = HexColor("#1F2937")
MUTED = HexColor("#667085")
BORDER = HexColor("#D8E2F0")
GREEN = HexColor("#18864B")
WHITE = colors.white
PAGE_WIDTH, PAGE_HEIGHT = A4


@dataclass
class SkillPerformance:
    skill_id: int
    code: str
    description: str | None
    expected_outcome: str | None
    grade: int
    subject: SubjectArea
    item_count: int = 0
    correct: int = 0
    opportunities: int = 0

    @property
    def percent(self) -> float:
        if not self.opportunities:
            return 0.0
        return round(self.correct / self.opportunities * 100, 2)


@dataclass(frozen=True)
class SchoolScope:
    id: int
    name: str


@dataclass(frozen=True)
class ClassScope:
    id: int
    school_id: int
    school_name: str
    name: str
    grade: int


@dataclass
class SkillReportData:
    network: dict[tuple[int, SubjectArea, int], SkillPerformance] = field(default_factory=dict)
    schools: dict[tuple[int, int, SubjectArea, int], SkillPerformance] = field(default_factory=dict)
    classes: dict[tuple[int, int, SubjectArea, int], SkillPerformance] = field(default_factory=dict)
    school_scopes: list[SchoolScope] = field(default_factory=list)
    class_scopes: list[ClassScope] = field(default_factory=list)


def _clone_metric(skill, *, item_count: int) -> SkillPerformance:
    return SkillPerformance(
        skill_id=skill.id,
        code=skill.code,
        description=skill.description,
        expected_outcome=skill.expected_outcome,
        grade=skill.grade,
        subject=skill.subject,
        item_count=item_count,
    )


def calculate_skill_report_data(evaluation) -> SkillReportData:
    data = SkillReportData()

    questions_by_grade: dict[int, list] = {}
    item_counts: dict[tuple[int, SubjectArea, int], int] = {}
    skill_objects: dict[tuple[int, SubjectArea, int], object] = {}

    for test in evaluation.tests:
        for question in test.questions:
            if question.skill is None:
                continue
            key = (test.grade, test.subject, question.skill.id)
            questions_by_grade.setdefault(test.grade, []).append(question)
            item_counts[key] = item_counts.get(key, 0) + 1
            skill_objects[key] = question.skill

    for key, skill in skill_objects.items():
        data.network[key] = _clone_metric(skill, item_count=item_counts[key])

    finalized_classes = []
    for classroom in evaluation.classes:
        application = classroom.application
        if application is None or application.status != ApplicationStatus.FINALIZED:
            continue
        finalized_classes.append(classroom)

    school_seen: dict[int, SchoolScope] = {}
    class_seen: list[ClassScope] = []

    for classroom in finalized_classes:
        school_seen[classroom.school.id] = SchoolScope(
            id=classroom.school.id,
            name=classroom.school.name,
        )
        class_seen.append(
            ClassScope(
                id=classroom.id,
                school_id=classroom.school.id,
                school_name=classroom.school.name,
                name=classroom.name,
                grade=classroom.grade,
            )
        )

        relevant_keys = [
            key for key in skill_objects
            if key[0] == classroom.grade
        ]
        for key in relevant_keys:
            skill = skill_objects[key]
            school_key = (classroom.school.id, *key)
            class_key = (classroom.id, *key)
            data.schools.setdefault(
                school_key,
                _clone_metric(skill, item_count=item_counts[key]),
            )
            data.classes.setdefault(
                class_key,
                _clone_metric(skill, item_count=item_counts[key]),
            )

        questions = [
            question
            for question in questions_by_grade.get(classroom.grade, [])
            if question.skill is not None
        ]

        for record in classroom.application.records:
            if record.presence != StudentPresence.PRESENT:
                continue

            answers = {
                answer.question_id: answer.selected_option
                for answer in record.answers
            }

            for question in questions:
                key = (classroom.grade, question.test.subject, question.skill.id)
                school_key = (classroom.school.id, *key)
                class_key = (classroom.id, *key)

                selected = answers.get(question.id)
                correct = int(
                    selected is not None
                    and selected == question.correct_option
                )

                network_metric = data.network[key]
                school_metric = data.schools[school_key]
                class_metric = data.classes[class_key]

                for metric in (network_metric, school_metric, class_metric):
                    metric.opportunities += 1
                    metric.correct += correct

    data.school_scopes = sorted(
        school_seen.values(),
        key=lambda item: item.name.casefold(),
    )
    data.class_scopes = sorted(
        class_seen,
        key=lambda item: (
            item.school_name.casefold(),
            item.grade,
            item.name.casefold(),
        ),
    )
    return data


def _subject_label(subject: SubjectArea) -> str:
    return (
        "LÍNGUA PORTUGUESA"
        if subject == SubjectArea.PORTUGUESE
        else "MATEMÁTICA"
    )


def _scope_metrics(
    data: SkillReportData,
    *,
    scope_type: str,
    school_id: int | None = None,
    class_id: int | None = None,
) -> list[tuple[SkillPerformance, SkillPerformance | None, SkillPerformance | None]]:
    rows = []
    keys = sorted(
        data.network,
        key=lambda key: (
            key[0],
            0 if key[1] == SubjectArea.PORTUGUESE else 1,
            data.network[key].code,
        ),
    )

    class_scope = next(
        (item for item in data.class_scopes if item.id == class_id),
        None,
    )
    if class_scope is not None:
        school_id = class_scope.school_id

    for key in keys:
        network_metric = data.network[key]

        if scope_type == "school":
            school_metric = data.schools.get((school_id, *key))
            if school_metric is None:
                continue
            rows.append((network_metric, school_metric, None))
        elif scope_type == "class":
            class_metric = data.classes.get((class_id, *key))
            if class_metric is None:
                continue
            school_metric = data.schools.get((school_id, *key))
            rows.append((network_metric, school_metric, class_metric))
        else:
            rows.append((network_metric, None, None))

    return rows


def _styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "SARETitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=19,
            textColor=DARK_BLUE,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "SARESubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=MUTED,
        ),
        "section": ParagraphStyle(
            "SARESection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            textColor=DARK_BLUE,
            spaceBefore=5,
            spaceAfter=6,
        ),
        "skill_code": ParagraphStyle(
            "SARESkillCode",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=BLUE,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "SAREBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=TEXT,
        ),
        "label": ParagraphStyle(
            "SARELabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=TEXT,
        ),
        "note": ParagraphStyle(
            "SARENote",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9,
            textColor=MUTED,
        ),
        "empty": ParagraphStyle(
            "SAREEmpty",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def _header_flowables(evaluation, title: str, context: str):
    styles = _styles()
    logo_path = (
        Path(__file__).resolve().parent.parent
        / "static"
        / "icons"
        / "sare-logo-original.png"
    )
    left = [
        Paragraph(escape(title), styles["title"]),
        Paragraph(escape(context), styles["subtitle"]),
        Paragraph(
            escape(
                f"Avaliação: {evaluation.name} · Ano letivo: {evaluation.school_year}"
            ),
            styles["subtitle"],
        ),
    ]
    logo = Image(str(logo_path), width=42 * mm, height=21 * mm)
    table = Table([[left, logo]], colWidths=[135 * mm, 42 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, BLUE),
            ]
        )
    )
    return [table, Spacer(1, 4 * mm)]


def _metric_table(
    network: SkillPerformance,
    school: SkillPerformance | None,
    classroom: SkillPerformance | None,
):
    rows = [
        [
            Paragraph("<b>Escopo</b>", _styles()["body"]),
            Paragraph("<b>Quantidade de acertos</b>", _styles()["body"]),
            Paragraph("<b>Percentual de acertos</b>", _styles()["body"]),
        ],
        ["Rede", str(network.correct), f"{network.percent:.2f}%"],
    ]
    if school is not None:
        rows.append(["Escola", str(school.correct), f"{school.percent:.2f}%"])
    if classroom is not None:
        rows.append(["Turma", str(classroom.correct), f"{classroom.percent:.2f}%"])

    table = Table(rows, colWidths=[54 * mm, 62 * mm, 58 * mm], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), DARK_BLUE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if classroom is not None:
        style.append(("BACKGROUND", (0, -1), (-1, -1), LIGHT_RED))
    table.setStyle(TableStyle(style))
    return table


def _skill_card(
    index: int,
    network: SkillPerformance,
    school: SkillPerformance | None,
    classroom: SkillPerformance | None,
):
    styles = _styles()
    description = network.description or "Descrição não informada no gabarito da avaliação."
    expected = (
        network.expected_outcome
        or "Resultado esperado não informado no gabarito da avaliação."
    )

    content = [
        Paragraph(
            f"{index}. ({escape(network.code)})",
            styles["skill_code"],
        ),
        Paragraph(
            f"<b>Habilidade:</b> {escape(description)}",
            styles["body"],
        ),
        Spacer(1, 1.5 * mm),
        Paragraph("<b>O que se espera:</b>", styles["label"]),
        Paragraph(escape(expected), styles["body"]),
        Spacer(1, 2.2 * mm),
        _metric_table(network, school, classroom),
        Spacer(1, 1.5 * mm),
        Paragraph(
            (
                f"Itens vinculados à habilidade nesta avaliação: {network.item_count}. "
                "Percentual = acertos ÷ oportunidades de resposta × 100."
            ),
            styles["note"],
        ),
        Spacer(1, 4 * mm),
    ]
    return KeepTogether(content)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.line(16 * mm, 14 * mm, PAGE_WIDTH - 16 * mm, 14 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(16 * mm, 9 * mm, "SARE · Sistema de Avaliação Riachense de Educação")
    canvas.drawRightString(
        PAGE_WIDTH - 16 * mm,
        9 * mm,
        f"Página {doc.page}",
    )
    canvas.restoreState()


def generate_skill_report_pdf(
    evaluation,
    data: SkillReportData,
    *,
    scope_type: str,
    school_id: int | None = None,
    class_id: int | None = None,
) -> bytes:
    if scope_type not in {"network", "school", "class"}:
        raise ValueError("Escopo inválido para relatório de habilidades.")

    school_scope = next(
        (item for item in data.school_scopes if item.id == school_id),
        None,
    )
    class_scope = next(
        (item for item in data.class_scopes if item.id == class_id),
        None,
    )
    if class_scope is not None:
        school_scope = next(
            (item for item in data.school_scopes if item.id == class_scope.school_id),
            None,
        )

    if scope_type == "network":
        title = "DADOS DE CADA HABILIDADE — REDE"
        context = "Consolidado das turmas finalizadas da Rede Municipal."
    elif scope_type == "school":
        if school_scope is None:
            raise ValueError("Escola não encontrada nos resultados finalizados.")
        title = f"DADOS DE CADA HABILIDADE — {school_scope.name}"
        context = "Comparativo Rede × Escola."
    else:
        if class_scope is None:
            raise ValueError("Turma não encontrada nos resultados finalizados.")
        title = f"DADOS DE CADA HABILIDADE — {class_scope.name}"
        context = (
            f"{class_scope.school_name} · {class_scope.grade}º ano · "
            "Comparativo Rede × Escola × Turma."
        )

    metric_rows = _scope_metrics(
        data,
        scope_type=scope_type,
        school_id=school_scope.id if school_scope else school_id,
        class_id=class_scope.id if class_scope else class_id,
    )

    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=19 * mm,
        title=title,
        author="SARE",
    )
    styles = _styles()
    story = _header_flowables(evaluation, title, context)

    if not metric_rows:
        story.extend(
            [
                Spacer(1, 12 * mm),
                Paragraph(
                    "Ainda não existem turmas finalizadas com dados para este relatório.",
                    styles["empty"],
                ),
            ]
        )
    else:
        current_group = None
        item_index = 0
        for network, school, classroom in metric_rows:
            group = (network.grade, network.subject)
            if group != current_group:
                if current_group is not None:
                    story.append(PageBreak())
                    story.extend(_header_flowables(evaluation, title, context))
                current_group = group
                item_index = 0
                story.append(
                    Paragraph(
                        f"{network.grade}º ANO · {_subject_label(network.subject)}",
                        styles["section"],
                    )
                )
                story.append(
                    Paragraph(
                        "Somente turmas finalizadas integram os cálculos.",
                        styles["note"],
                    )
                )
                story.append(Spacer(1, 3 * mm))

            item_index += 1
            story.append(
                _skill_card(
                    item_index,
                    network,
                    school,
                    classroom,
                )
            )

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    output.seek(0)
    return output.getvalue()


def _safe_filename(value: str, *, fallback: str = "relatorio") -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized).strip("._-")
    return (normalized[:100] or fallback)


def build_skill_reports_zip(evaluation) -> bytes:
    data = calculate_skill_report_data(evaluation)
    output = BytesIO()

    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "00_REDE/relatorio_habilidades_rede.pdf",
            generate_skill_report_pdf(
                evaluation,
                data,
                scope_type="network",
            ),
        )

        for school in data.school_scopes:
            school_dir = f"ESCOLAS/{_safe_filename(school.name)}"
            archive.writestr(
                f"{school_dir}/relatorio_habilidades_escola.pdf",
                generate_skill_report_pdf(
                    evaluation,
                    data,
                    scope_type="school",
                    school_id=school.id,
                ),
            )

            school_classes = [
                classroom
                for classroom in data.class_scopes
                if classroom.school_id == school.id
            ]
            for classroom in school_classes:
                class_name = (
                    f"{classroom.grade}_ano_"
                    f"{_safe_filename(classroom.name, fallback='turma')}"
                )
                archive.writestr(
                    f"{school_dir}/TURMAS/{class_name}.pdf",
                    generate_skill_report_pdf(
                        evaluation,
                        data,
                        scope_type="class",
                        class_id=classroom.id,
                    ),
                )

        archive.writestr(
            "LEIA-ME.txt",
            (
                "SARE — Pacote de relatórios por habilidades\n\n"
                "Conteúdo:\n"
                "- 00_REDE: consolidado da rede;\n"
                "- ESCOLAS: um relatório por escola;\n"
                "- ESCOLAS/<escola>/TURMAS: um relatório por turma finalizada.\n\n"
                "Os cálculos consideram somente turmas finalizadas.\n"
                "Percentual de acertos = quantidade de acertos / oportunidades de resposta x 100.\n"
                "Quando uma habilidade está vinculada a mais de uma questão, todas as oportunidades são consideradas.\n"
            ),
        )

    output.seek(0)
    return output.getvalue()
