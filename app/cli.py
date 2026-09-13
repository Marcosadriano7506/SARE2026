import click
from flask import current_app
from flask.cli import with_appcontext

from app.extensions import db
from app.models import User, UserRole


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


def register_cli(app):
    app.cli.add_command(create_admin)
