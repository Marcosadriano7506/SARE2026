from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp


class ClassCodeForm(FlaskForm):
    code = StringField(
        "Código da turma",
        validators=[
            DataRequired(),
            Length(min=4, max=4, message="O código deve ter 4 dígitos."),
            Regexp(r"^\d{4}$", message="Digite somente os 4 números do código."),
        ],
        render_kw={
            "inputmode": "numeric",
            "pattern": "[0-9]{4}",
            "maxlength": "4",
            "autocomplete": "off",
        },
    )
    submit = SubmitField("Abrir turma")
