from flask_wtf import FlaskForm
from wtforms import SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class ReopenClassForm(FlaskForm):
    reason = TextAreaField(
        "Motivo da reabertura",
        validators=[DataRequired(), Length(min=5, max=500)],
    )
    submit = SubmitField("Reabrir turma")
