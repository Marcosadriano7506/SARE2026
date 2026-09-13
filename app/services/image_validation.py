from __future__ import annotations

from PIL import Image, UnidentifiedImageError


ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_PIXELS = 30_000_000


class ImageValidationError(ValueError):
    pass


def validate_uploaded_image(file_storage) -> None:
    if file_storage is None:
        return

    stream = file_storage.stream
    try:
        stream.seek(0)
        with Image.open(stream) as image:
            image_format = (image.format or "").upper()
            width, height = image.size

            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise ImageValidationError(
                    "Formato de imagem inválido. Use JPG, PNG ou WEBP."
                )
            if width <= 0 or height <= 0:
                raise ImageValidationError("A imagem enviada é inválida.")
            if width * height > MAX_IMAGE_PIXELS:
                raise ImageValidationError(
                    "A imagem é grande demais. Reduza a resolução e tente novamente."
                )

            image.verify()
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageValidationError(
            "O arquivo enviado não é uma imagem válida."
        ) from exc
    finally:
        stream.seek(0)
