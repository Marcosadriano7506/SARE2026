from io import BytesIO
from types import SimpleNamespace

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from openpyxl import Workbook
from flask_login import current_user, login_required

from app.auth.permissions import roles_required
from app.coordinator.application_forms import ApplicationAssignmentForm, ReopenClassForm
from app.coordinator.evaluation_forms import AnswerKeyImportForm, EvaluationForm, RosterImportForm
from app.coordinator.forms import ApplicatorForm, ApplicatorPasswordResetForm
from app.extensions import db
from app.models import (
    ApplicationStatus,
    ClassApplication,
    ClassRoom,
    Evaluation,
    School,
    Student,
    User,
    UserRole,
    utcnow,
)
from app.services.absence_report import generate_absence_report_pdf
from app.services.analytics import calculate_evaluation_analytics
from app.services.class_codes_pdf import generate_class_codes_pdf
from app.services.answer_key_import import (
    AnswerKeyImportError,
    import_answer_key,
    parse_answer_key_xlsx,
)
from app.services.application_rules import summarize_application
from app.services.audit import record_audit
from app.services.demo_data import DEMO_CLASS_CODE, create_demo_dataset
from app.services.results_pdf import generate_results_pdf
from app.services.results_workbook import build_results_workbook
from app.services.roster_import import (
    RosterImportError,
    import_roster,
    parse_roster_xlsx,
)

coordinator_bp = Blueprint("coordinator", __name__, url_prefix="/coordenacao")


@coordinator_bp.get("/")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def dashboard():
    applicators = (
        User.query.filter_by(role=UserRole.APPLICATOR)
        .order_by(User.is_active_user.desc(), User.name.asc())
        .all()
    )
    evaluations = Evaluation.query.order_by(
        Evaluation.school_year.desc(), Evaluation.created_at.desc()
    ).all()

    status_counts = {
        status.value: ClassApplication.query.filter_by(status=status).count()
        for status in ApplicationStatus
    }
    metrics = {
        "evaluations": Evaluation.query.count(),
        "schools": School.query.count(),
        "classes": ClassRoom.query.count(),
        "students": Student.query.count(),
        "applicators": len(applicators),
        "finalized": status_counts.get(ApplicationStatus.FINALIZED.value, 0),
        "in_progress": status_counts.get(ApplicationStatus.IN_PROGRESS.value, 0),
    }

    return render_template(
        "coordinator/dashboard.html",
        applicators=applicators,
        evaluations=evaluations,
        metrics=metrics,
        demo_class_code=DEMO_CLASS_CODE,
    )


@coordinator_bp.route("/aplicadores/novo", methods=["GET", "POST"])
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def create_applicator():
    form = ApplicatorForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first():
            form.username.errors.append("Já existe um usuário com esse login.")
            return render_template("coordinator/applicator_form.html", form=form), 409

        applicator = User(
            name=form.name.data.strip(),
            job_title=form.job_title.data.strip(),
            username=username,
            role=UserRole.APPLICATOR,
            is_active_user=True,
        )
        applicator.set_password(form.password.data)
        db.session.add(applicator)
        db.session.flush()

        record_audit(
            user_id=current_user.id,
            action="APPLICATOR_CREATED",
            entity_type="USER",
            entity_id=applicator.id,
            details={"role": UserRole.APPLICATOR.value},
        )
        db.session.commit()

        flash("Aplicador cadastrado com sucesso.", "success")
        return redirect(url_for("coordinator.dashboard"))

    return render_template("coordinator/applicator_form.html", form=form)


@coordinator_bp.route("/avaliacoes/nova", methods=["GET", "POST"])
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def create_evaluation():
    form = EvaluationForm()
    if form.validate_on_submit():
        evaluation = Evaluation(
            name=form.name.data.strip(),
            school_year=form.school_year.data,
            edition=(form.edition.data or "").strip() or None,
            starts_on=form.starts_on.data,
            ends_on=form.ends_on.data,
            is_active=True,
        )
        db.session.add(evaluation)
        db.session.flush()
        record_audit(
            user_id=current_user.id,
            action="EVALUATION_CREATED",
            entity_type="EVALUATION",
            entity_id=evaluation.id,
            details={
                "name": evaluation.name,
                "school_year": evaluation.school_year,
                "edition": evaluation.edition,
                "starts_on": evaluation.starts_on.isoformat() if evaluation.starts_on else None,
                "ends_on": evaluation.ends_on.isoformat() if evaluation.ends_on else None,
            },
        )
        db.session.commit()
        flash("Avaliação criada com sucesso.", "success")
        return redirect(url_for("coordinator.dashboard"))

    return render_template("coordinator/evaluation_form.html", form=form)


@coordinator_bp.route("/base/importar", methods=["GET", "POST"])
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def import_base():
    form = RosterImportForm()
    evaluations = Evaluation.query.filter_by(is_active=True).order_by(
        Evaluation.school_year.desc(), Evaluation.name.asc()
    ).all()
    form.evaluation_id.choices = [
        (item.id, f"{item.name} ({item.school_year})") for item in evaluations
    ]

    if form.validate_on_submit():
        evaluation = db.session.get(Evaluation, form.evaluation_id.data)
        if evaluation is None:
            form.evaluation_id.errors.append("Avaliação não encontrada.")
            return render_template("coordinator/import_roster.html", form=form), 404

        content = form.file.data.read()
        try:
            rows = parse_roster_xlsx(content)
            result = import_roster(evaluation, rows)
            record_audit(
                user_id=current_user.id,
                action="ROSTER_IMPORTED",
                entity_type="EVALUATION",
                entity_id=evaluation.id,
                details={
                    "rows": result.rows_processed,
                    "schools_created": result.schools_created,
                    "classes_created": result.classes_created,
                    "students_created": result.students_created,
                },
            )
            db.session.commit()
        except RosterImportError as exc:
            db.session.rollback()
            return render_template(
                "coordinator/import_roster.html",
                form=form,
                import_errors=exc.errors,
            ), 422
        except Exception:
            db.session.rollback()
            raise

        flash(
            (
                f"Base importada: {result.students_created} estudantes novos, "
                f"{result.classes_created} turmas e {result.schools_created} escolas."
            ),
            "success",
        )
        return redirect(url_for("coordinator.dashboard"))

    return render_template("coordinator/import_roster.html", form=form)


@coordinator_bp.post("/demo/criar")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def create_demo():
    try:
        classroom, created = create_demo_dataset()
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("coordinator.dashboard"))

    record_audit(
        user_id=current_user.id,
        action="DEMO_DATASET_CREATED" if created else "DEMO_DATASET_REUSED",
        entity_type="CLASS",
        entity_id=classroom.id,
        details={"access_code": classroom.access_code},
    )
    db.session.commit()

    if created:
        flash(
            f"Base de demonstração criada. Código da turma: {classroom.access_code}",
            "success",
        )
    else:
        flash(
            f"A base de demonstração já existe. Código da turma: {classroom.access_code}",
            "success",
        )
    return redirect(url_for("coordinator.dashboard"))


@coordinator_bp.get("/base/modelo.xlsx")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def download_roster_template():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "BASE"
    sheet.append(["ESCOLA", "ANO", "TURMA", "ALUNO", "MATRÍCULA"])
    sheet.append(["Escola Exemplo", 5, "5º Ano A", "Aluno Exemplo", "000001"])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1:E2"
    widths = {"A": 34, "B": 10, "C": 20, "D": 34, "E": 18}
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="modelo_importacao_sare.xlsx",
    )




@coordinator_bp.get("/avaliacoes/<int:evaluation_id>/codigos.pdf")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def export_class_codes_pdf(evaluation_id: int):
    evaluation = db.session.get(Evaluation, evaluation_id)
    if evaluation is None:
        return ("Avaliação não encontrada.", 404)

    pdf = generate_class_codes_pdf(evaluation)
    return send_file(
        BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"codigos_turmas_{evaluation.school_year}_{evaluation.id}.pdf",
    )


@coordinator_bp.route("/gabarito/importar", methods=["GET", "POST"])
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def import_answer_key():
    form = AnswerKeyImportForm()
    evaluations = Evaluation.query.filter_by(is_active=True).order_by(
        Evaluation.school_year.desc(), Evaluation.name.asc()
    ).all()
    form.evaluation_id.choices = [
        (item.id, f"{item.name} ({item.school_year})") for item in evaluations
    ]

    if form.validate_on_submit():
        evaluation = db.session.get(Evaluation, form.evaluation_id.data)
        if evaluation is None:
            form.evaluation_id.errors.append("Avaliação não encontrada.")
            return render_template("coordinator/import_answer_key.html", form=form), 404

        try:
            rows = parse_answer_key_xlsx(form.file.data.read())
            result = import_answer_key(evaluation, rows)
            record_audit(
                user_id=current_user.id,
                action="ANSWER_KEY_IMPORTED",
                entity_type="EVALUATION",
                entity_id=evaluation.id,
                details={
                    "rows": result.rows_processed,
                    "tests_created": result.tests_created,
                    "skills_created": result.skills_created,
                    "questions_created": result.questions_created,
                    "questions_updated": result.questions_updated,
                },
            )
            db.session.commit()
        except AnswerKeyImportError as exc:
            db.session.rollback()
            return render_template(
                "coordinator/import_answer_key.html",
                form=form,
                import_errors=exc.errors,
            ), 422
        except Exception:
            db.session.rollback()
            raise

        flash(
            (
                f"Gabarito importado: {result.questions_created} questões novas e "
                f"{result.questions_updated} atualizadas."
            ),
            "success",
        )
        return redirect(url_for("coordinator.dashboard"))

    return render_template("coordinator/import_answer_key.html", form=form)


@coordinator_bp.get("/gabarito/modelo.xlsx")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def download_answer_key_template():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "GABARITO"
    sheet.append(
        ["ANO", "COMPONENTE", "QUESTÃO", "HABILIDADE", "GABARITO", "DESCRIÇÃO DA HABILIDADE"]
    )
    sheet.append([5, "LP", 1, "D01", "A", "Habilidade de exemplo"])
    sheet.append([5, "MATEMÁTICA", 1, "D02", "B", "Habilidade de exemplo"])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1:F3"
    widths = {"A": 10, "B": 22, "C": 12, "D": 16, "E": 12, "F": 50}
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="modelo_gabarito_sare.xlsx",
    )


STATUS_LABELS = {
    "NOT_STARTED": "Não iniciada",
    "IN_PROGRESS": "Em andamento",
    "FINALIZED": "Finalizada",
    "REOPENED": "Reaberta",
    "INCONSISTENT": "Inconsistência",
}


@coordinator_bp.get("/aplicacoes")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def applications():
    evaluation_id = request.args.get("evaluation_id", type=int)
    school_id = request.args.get("school_id", type=int)
    status_filter = (request.args.get("status") or "").strip().upper()

    query = ClassRoom.query.join(School, ClassRoom.school_id == School.id)
    if evaluation_id:
        query = query.filter(ClassRoom.evaluation_id == evaluation_id)
    if school_id:
        query = query.filter(ClassRoom.school_id == school_id)

    classrooms = query.order_by(
        School.name.asc(),
        ClassRoom.grade.asc(),
        ClassRoom.name.asc(),
    ).all()

    rows = []
    counts = {
        "NOT_STARTED": 0,
        "IN_PROGRESS": 0,
        "FINALIZED": 0,
        "REOPENED": 0,
        "INCONSISTENT": 0,
    }
    for classroom in classrooms:
        application = classroom.application
        status = application.status.value if application else "NOT_STARTED"
        counts[status] = counts.get(status, 0) + 1

        if status_filter and status != status_filter:
            continue

        rows.append(
            SimpleNamespace(
                classroom=classroom,
                application=application,
                applicator=application.applicator if application else None,
                status=status,
                status_label=STATUS_LABELS[status],
            )
        )

    evaluations = Evaluation.query.order_by(
        Evaluation.school_year.desc(),
        Evaluation.name.asc(),
    ).all()
    schools = School.query.order_by(School.name.asc()).all()

    return render_template(
        "coordinator/applications.html",
        rows=rows,
        counts=counts,
        evaluations=evaluations,
        schools=schools,
        selected_evaluation_id=evaluation_id,
        selected_school_id=school_id,
        selected_status=status_filter,
        status_labels=STATUS_LABELS,
    )


@coordinator_bp.get("/turmas/<int:class_id>")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def class_detail(class_id: int):
    classroom = db.session.get(ClassRoom, class_id)
    if classroom is None:
        return ("Turma não encontrada.", 404)

    application = classroom.application
    if application is None:
        summary = SimpleNamespace(
            total_students=len(classroom.students),
            present_students=0,
            absent_students=0,
            pending_students=len(classroom.students),
            confirmed_discursives=0,
        )
        status = "NOT_STARTED"
    else:
        summary = summarize_application(application)
        status = application.status.value

    assignment_form = ApplicationAssignmentForm()
    active_applicators = (
        User.query.filter_by(role=UserRole.APPLICATOR, is_active_user=True)
        .order_by(User.name.asc())
        .all()
    )
    assignment_form.applicator_id.choices = [(0, "Liberar turma para outro aplicador")] + [
        (item.id, f"{item.name} · {item.username}") for item in active_applicators
    ]
    if application and application.applicator_id:
        assignment_form.applicator_id.data = application.applicator_id

    return render_template(
        "coordinator/class_detail.html",
        classroom=classroom,
        application=application,
        summary=summary,
        status=status,
        status_label=STATUS_LABELS[status],
        reopen_form=ReopenClassForm(),
        assignment_form=assignment_form,
    )


@coordinator_bp.post("/turmas/<int:class_id>/responsavel")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def assign_class_applicator(class_id: int):
    classroom = db.session.get(ClassRoom, class_id)
    if classroom is None:
        return ("Turma não encontrada.", 404)

    application = classroom.application
    if application is None or application.status == ApplicationStatus.FINALIZED:
        flash("Esta turma não pode ter o responsável alterado neste momento.", "error")
        return redirect(url_for("coordinator.class_detail", class_id=classroom.id))

    active_applicators = (
        User.query.filter_by(role=UserRole.APPLICATOR, is_active_user=True)
        .order_by(User.name.asc())
        .all()
    )
    form = ApplicationAssignmentForm()
    form.applicator_id.choices = [(0, "Liberar turma para outro aplicador")] + [
        (item.id, f"{item.name} · {item.username}") for item in active_applicators
    ]

    if not form.validate_on_submit():
        flash("Confira o aplicador e informe o motivo da alteração.", "error")
        return redirect(url_for("coordinator.class_detail", class_id=classroom.id))

    previous_applicator_id = application.applicator_id
    selected_id = form.applicator_id.data
    if selected_id:
        selected = db.session.get(User, selected_id)
        if (
            selected is None
            or selected.role != UserRole.APPLICATOR
            or not selected.is_active_user
        ):
            flash("Aplicador selecionado não está disponível.", "error")
            return redirect(url_for("coordinator.class_detail", class_id=classroom.id))
        application.applicator_id = selected.id
    else:
        application.applicator_id = None

    record_audit(
        user_id=current_user.id,
        action="CLASS_APPLICATION_REASSIGNED",
        entity_type="CLASS_APPLICATION",
        entity_id=application.id,
        details={
            "previous_applicator_id": previous_applicator_id,
            "new_applicator_id": application.applicator_id,
            "reason": form.reason.data.strip(),
        },
    )
    db.session.commit()

    flash(
        "Responsável pela turma atualizado."
        if application.applicator_id
        else "Turma liberada para outro aplicador assumir.",
        "success",
    )
    return redirect(url_for("coordinator.class_detail", class_id=classroom.id))


@coordinator_bp.post("/turmas/<int:class_id>/reabrir")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def reopen_class(class_id: int):
    classroom = db.session.get(ClassRoom, class_id)
    if classroom is None:
        return ("Turma não encontrada.", 404)

    application = classroom.application
    if application is None or application.status != ApplicationStatus.FINALIZED:
        flash("Somente turmas finalizadas podem ser reabertas.", "error")
        return redirect(url_for("coordinator.class_detail", class_id=classroom.id))

    form = ReopenClassForm()
    if not form.validate_on_submit():
        summary = summarize_application(application)
        assignment_form = ApplicationAssignmentForm()
        active_applicators = (
            User.query.filter_by(role=UserRole.APPLICATOR, is_active_user=True)
            .order_by(User.name.asc())
            .all()
        )
        assignment_form.applicator_id.choices = [(0, "Liberar turma para outro aplicador")] + [
            (item.id, f"{item.name} · {item.username}") for item in active_applicators
        ]
        return render_template(
            "coordinator/class_detail.html",
            classroom=classroom,
            application=application,
            summary=summary,
            status=application.status.value,
            status_label=STATUS_LABELS[application.status.value],
            reopen_form=form,
            assignment_form=assignment_form,
        ), 422

    previous_receipt = application.receipt_code
    application.status = ApplicationStatus.REOPENED
    application.reopened_at = utcnow()
    application.reopened_by = current_user.id
    application.finalized_at = None
    application.finalized_by = None
    application.receipt_code = None

    record_audit(
        user_id=current_user.id,
        action="CLASS_APPLICATION_REOPENED",
        entity_type="CLASS_APPLICATION",
        entity_id=application.id,
        details={
            "reason": form.reason.data.strip(),
            "previous_receipt_code": previous_receipt,
        },
    )
    db.session.commit()
    flash("Turma reaberta com sucesso.", "success")
    return redirect(url_for("coordinator.class_detail", class_id=classroom.id))


@coordinator_bp.get("/resultados/<int:evaluation_id>")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def results(evaluation_id: int):
    evaluation = db.session.get(Evaluation, evaluation_id)
    if evaluation is None:
        return ("Avaliação não encontrada.", 404)
    analytics = calculate_evaluation_analytics(evaluation)
    return render_template("coordinator/results.html", analytics=analytics)


@coordinator_bp.get("/resultados/<int:evaluation_id>/excel")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def export_results_excel(evaluation_id: int):
    evaluation = db.session.get(Evaluation, evaluation_id)
    if evaluation is None:
        return ("Avaliação não encontrada.", 404)

    output = BytesIO(build_results_workbook(evaluation))
    filename = f"resultados_sare_{evaluation.school_year}_{evaluation.id}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@coordinator_bp.get("/resultados/<int:evaluation_id>/relatorio.pdf")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def export_results_pdf(evaluation_id: int):
    evaluation = db.session.get(Evaluation, evaluation_id)
    if evaluation is None:
        return ("Avaliação não encontrada.", 404)

    analytics = calculate_evaluation_analytics(evaluation)
    pdf = generate_results_pdf(evaluation, analytics)
    return send_file(
        BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"relatorio_resultados_{evaluation.school_year}_{evaluation.id}.pdf",
    )


@coordinator_bp.get("/resultados/<int:evaluation_id>/ausentes.pdf")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def export_absences_pdf(evaluation_id: int):
    evaluation = db.session.get(Evaluation, evaluation_id)
    if evaluation is None:
        return ("Avaliação não encontrada.", 404)

    analytics = calculate_evaluation_analytics(evaluation)
    pdf = generate_absence_report_pdf(evaluation, analytics.absences)
    return send_file(
        BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"ausentes_{evaluation.school_year}_{evaluation.id}.pdf",
    )
