from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length


class CoordinatorForm(FlaskForm):
    name = StringField("Nome", validators=[DataRequired(), Length(max=160)])
    job_title = StringField("Função", validators=[DataRequired(), Length(max=160)])
    username = StringField("Login", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField(
        "Senha",
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    submit = SubmitField("Cadastrar coordenador")
