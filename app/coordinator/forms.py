from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length


class ApplicatorForm(FlaskForm):
    name = StringField("Nome", validators=[DataRequired(), Length(max=160)])
    job_title = StringField(
        "Função na Secretaria", validators=[DataRequired(), Length(max=160)]
    )
    username = StringField("Login", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Senha", validators=[DataRequired(), Length(min=8, max=128)])
    submit = SubmitField("Cadastrar aplicador")


class ApplicatorPasswordResetForm(FlaskForm):
    password = PasswordField(
        "Nova senha",
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    password_confirmation = PasswordField(
        "Confirmar nova senha",
        validators=[
            DataRequired(),
            EqualTo("password", message="As senhas precisam ser iguais."),
        ],
    )
    submit = SubmitField("Redefinir senha")
