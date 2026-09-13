from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length


class ReopenClassForm(FlaskForm):
    reason = TextAreaField(
        "Motivo da reabertura",
        validators=[DataRequired(), Length(min=5, max=500)],
    )
    submit = SubmitField("Reabrir turma")


class ApplicationAssignmentForm(FlaskForm):
    applicator_id = SelectField(
        "Aplicador responsável",
        coerce=int,
        validators=[InputRequired()],
    )
    reason = TextAreaField(
        "Motivo da alteração",
        validators=[DataRequired(), Length(min=5, max=500)],
    )
    submit = SubmitField("Atualizar responsável")
