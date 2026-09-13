from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length


class ClassCodeForm(FlaskForm):
    code = StringField(
        "Código da turma",
        validators=[DataRequired(), Length(min=3, max=32)],
    )
    submit = SubmitField("Abrir turma")
