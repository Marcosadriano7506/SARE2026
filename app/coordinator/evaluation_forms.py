from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import DateField, IntegerField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class EvaluationBaseForm(FlaskForm):
    name = StringField("Nome da avaliação", validators=[DataRequired(), Length(max=180)])
    school_year = IntegerField(
        "Ano letivo", validators=[DataRequired(), NumberRange(min=2020, max=2200)]
    )
    edition = StringField("Edição", validators=[Optional(), Length(max=50)])
    starts_on = DateField("Início da aplicação", validators=[Optional()])
    ends_on = DateField("Fim da aplicação", validators=[Optional()])

    def validate(self, extra_validators=None):
        valid = super().validate(extra_validators=extra_validators)
        if self.starts_on.data and self.ends_on.data and self.ends_on.data < self.starts_on.data:
            self.ends_on.errors.append("A data final não pode ser anterior à data inicial.")
            valid = False
        return valid


class EvaluationForm(EvaluationBaseForm):
    submit = SubmitField("Criar avaliação")


class EvaluationSettingsForm(EvaluationBaseForm):
    submit = SubmitField("Salvar configurações")


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


class AnswerKeyImportForm(FlaskForm):
    evaluation_id = SelectField("Avaliação", coerce=int, validators=[DataRequired()])
    file = FileField(
        "Planilha de gabarito",
        validators=[
            FileRequired(),
            FileAllowed(["xlsx"], "Envie uma planilha .xlsx."),
        ],
    )
    submit = SubmitField("Importar gabarito")
