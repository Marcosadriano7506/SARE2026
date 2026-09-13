from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import IntegerField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Length


class EvaluationForm(FlaskForm):
    name = StringField("Nome da avaliação", validators=[DataRequired(), Length(max=180)])
    school_year = IntegerField(
        "Ano letivo", validators=[DataRequired(), NumberRange(min=2020, max=2200)]
    )
    edition = StringField("Edição", validators=[Optional(), Length(max=50)])
    submit = SubmitField("Criar avaliação")


class RosterImportForm(FlaskForm):
    evaluation_id = SelectField("Avaliação", coerce=int, validators=[DataRequired()])
    file = FileField(
        "Planilha de estudantes",
        validators=[
            FileRequired(),
            FileAllowed(["xlsx"], "Envie uma planilha .xlsx."),
        ],
    )
    submit = SubmitField("Importar base")
