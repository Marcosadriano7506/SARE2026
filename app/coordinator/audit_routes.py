from flask import Blueprint, render_template
from flask_login import login_required

from app.auth.permissions import roles_required
from app.models import AuditLog, UserRole


audit_bp = Blueprint(
    "audit",
    __name__,
    url_prefix="/coordenacao/auditoria",
)


ACTION_LABELS = {
    "APPLICATOR_CREATED": "Aplicador cadastrado",
    "APPLICATOR_STATUS_CHANGED": "Status do aplicador alterado",
    "APPLICATOR_UPDATED": "Dados do aplicador atualizados",
    "APPLICATOR_PASSWORD_RESET": "Senha do aplicador redefinida",
    "COORDINATOR_CREATED": "Coordenador cadastrado",
    "COORDINATOR_STATUS_CHANGED": "Status do coordenador alterado",
    "EVALUATION_CREATED": "Avaliação criada",
    "EVALUATION_SETTINGS_UPDATED": "Configurações da avaliação atualizadas",
    "EVALUATION_STATUS_CHANGED": "Status da avaliação alterado",
    "ROSTER_IMPORTED": "Base de estudantes importada",
    "ANSWER_KEY_IMPORTED": "Gabarito importado",
    "CLASS_APPLICATION_STARTED": "Aplicação iniciada",
    "CLASS_APPLICATION_RESUMED": "Aplicação retomada",
    "STUDENT_RECORD_OPENED": "Registro de estudante aberto",
    "STUDENT_RECORD_SAVED": "Registro de estudante salvo",
    "DISCUSSIVE_UPLOADED": "Discursiva enviada",
    "DISCUSSIVE_REMOVED": "Discursiva removida",
    "CLASS_APPLICATION_FINALIZED": "Turma finalizada",
    "CLASS_APPLICATION_REOPENED": "Turma reaberta",
    "CLASS_APPLICATION_REASSIGNED": "Responsável da turma alterado",
    "CLASS_CODE_REGENERATED": "Código da turma regenerado",
    "DEMO_DATASET_CREATED": "Base DEMO criada",
    "DEMO_DATASET_REUSED": "Base DEMO reutilizada",
}


@audit_bp.get("/")
@login_required
@roles_required(UserRole.ADMIN, UserRole.COORDINATOR)
def index():
    logs = (
        AuditLog.query
        .order_by(AuditLog.created_at.desc())
        .limit(250)
        .all()
    )
    return render_template(
        "coordinator/audit.html",
        logs=logs,
        action_labels=ACTION_LABELS,
    )
