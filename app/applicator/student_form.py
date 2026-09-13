from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import RadioField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional


class StudentApplicationForm(FlaskForm):
    presence = RadioField(
        "Situação",
        choices=[("PRESENT", "Presente"), ("ABSENT", "Ausente")],
        validators=[DataRequired()],
    )
    self_declaration = SelectField(
        "Autodeclaração",
        choices=[
            ("", "Não informado"),
            ("PRETO", "Preto"),
            ("PARDO", "Pardo"),
            ("AMARELO", "Amarelo"),
            ("INDIGENA", "Indígena"),
            ("BRANCO", "Branco"),
        ],
        validators=[Optional()],
    )
    discursive = FileField(
        "Foto da discursiva",
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png", "webp"], "Envie uma imagem JPG, PNG ou WEBP."),
        ],
    )
    submit = SubmitField("Salvar estudante")
