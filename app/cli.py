import os
from pathlib import Path

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import User, UserRole
from app.services.backup import BackupRestoreError, restore_structured_backup
from app.services.load_fixture import create_load_fixture, delete_load_fixture


@click.command("create-admin")
@click.option("--name", prompt=True, help="Nome do administrador.")
@click.option("--username", prompt=True, help="Login do administrador.")
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="Senha do administrador.",
)
@with_appcontext
def create_admin(name: str, username: str, password: str):
    username = username.strip()
    if User.query.filter_by(username=username).first():
        raise click.ClickException("Já existe um usuário com esse login.")

    user = User(
        name=name.strip(),
        username=username,
        role=UserRole.ADMIN,
        is_active_user=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Administrador '{username}' criado com sucesso.")


@click.command("init-homologation")
@with_appcontext
def init_homologation():
    """Inicializa somente o ambiente temporário de homologação."""
    if os.getenv("ALLOW_HOMOLOGATION_BOOTSTRAP", "false").lower() != "true":
        raise click.ClickException("Bootstrap de homologação não autorizado.")

    db.create_all()

    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    name = os.getenv("BOOTSTRAP_ADMIN_NAME", "Administrador SARE").strip()

    if not username or not password:
        raise click.ClickException("Credenciais de bootstrap não configuradas.")

    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(
            name=name,
            username=username,
            role=UserRole.ADMIN,
            is_active_user=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrador de homologação '{username}' criado.")
    else:
        click.echo("Administrador de homologação já existe.")


@click.command("restore-backup")
@click.argument("backup_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--confirm",
    required=True,
    help="Digite RESTAURAR para confirmar a substituição integral dos dados.",
)
@with_appcontext
def restore_backup(backup_path: Path, confirm: str):
    """Restaura um backup estruturado. Uso exclusivo de contingência técnica."""
    if confirm != "RESTAURAR":
        raise click.ClickException(
            "Confirmação inválida. Use --confirm RESTAURAR somente após validar o arquivo."
        )

    try:
        counts = restore_structured_backup(backup_path.read_bytes())
    except BackupRestoreError as exc:
        raise click.ClickException(str(exc)) from exc

    total = sum(counts.values())
    click.echo(
        f"Restauração concluída com sucesso: {total} registros em {len(counts)} tabelas."
    )


@click.command("create-load-fixture")
@click.option("--users", default=100, show_default=True, type=click.IntRange(1, 250))
@click.option("--students-per-class", default=30, show_default=True, type=click.IntRange(1, 60))
@with_appcontext
def create_load_fixture_command(users: int, students_per_class: int):
    """Cria usuários/turmas sintéticos para teste de carga em homologação."""
    try:
        result = create_load_fixture(
            user_count=users,
            students_per_class=students_per_class,
        )
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(
        "Fixture criado: "
        f"{result['total_users']} usuários alvo, "
        f"{result['classes_created']} turmas novas e "
        f"{result['students_created']} estudantes novos."
    )


@click.command("delete-load-fixture")
@click.option(
    "--confirm",
    required=True,
    help="Digite REMOVER para confirmar a remoção dos dados sintéticos.",
)
@with_appcontext
def delete_load_fixture_command(confirm: str):
    """Remove o fixture sintético de carga."""
    if confirm != "REMOVER":
        raise click.ClickException("Use --confirm REMOVER para confirmar.")
    try:
        result = delete_load_fixture()
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(
        "Fixture removido: "
        f"{result['users_deleted']} usuários e "
        f"{result['classes_deleted']} turmas."
    )


def register_cli(app):
    app.cli.add_command(create_admin)
    app.cli.add_command(init_homologation)
    app.cli.add_command(restore_backup)
    app.cli.add_command(create_load_fixture_command)
    app.cli.add_command(delete_load_fixture_command)
