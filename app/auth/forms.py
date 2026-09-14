from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length


class LoginForm(FlaskForm):
    username = StringField("Login", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Senha", validators=[DataRequired(), Length(max=128)])
    submit = SubmitField("Entrar")



class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        "Senha atual",
        validators=[DataRequired(), Length(max=128)],
    )
    new_password = PasswordField(
        "Nova senha",
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    confirm_password = PasswordField(
        "Confirmar nova senha",
        validators=[
            DataRequired(),
            EqualTo("new_password", message="As senhas não coincidem."),
        ],
    )
    submit = SubmitField("Alterar senha")
