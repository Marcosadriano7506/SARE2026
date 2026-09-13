from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from types import SimpleNamespace
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError


ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_PIXELS = 30_000_000
MAX_OUTPUT_EDGE = 1800
JPEG_QUALITY = 82


class ImageValidationError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedImage:
    stream: BytesIO
    filename: str
    mime_type: str
    size_bytes: int
    width: int
    height: int


def _open_verified_image(file_storage):
    stream = file_storage.stream
    try:
        stream.seek(0)
        image = Image.open(stream)
        image_format = (image.format or "").upper()
        width, height = image.size

        if image_format not in ALLOWED_IMAGE_FORMATS:
            image.close()
            raise ImageValidationError(
                "Formato de imagem inválido. Use JPG, PNG ou WEBP."
            )
        if width <= 0 or height <= 0:
            image.close()
            raise ImageValidationError("A imagem enviada é inválida.")
        if width * height > MAX_IMAGE_PIXELS:
            image.close()
            raise ImageValidationError(
                "A imagem é grande demais. Reduza a resolução e tente novamente."
            )

        image.verify()
        stream.seek(0)
        return Image.open(stream)
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageValidationError(
            "O arquivo enviado não é uma imagem válida."
        ) from exc
    finally:
        stream.seek(0)


def validate_uploaded_image(file_storage) -> None:
    if file_storage is None:
        return
    image = _open_verified_image(file_storage)
    image.close()
    file_storage.stream.seek(0)


def normalize_uploaded_image(file_storage) -> NormalizedImage:
    """Valida, corrige orientação, remove EXIF/GPS e reduz a foto para JPEG."""
    if file_storage is None:
        raise ImageValidationError("Nenhuma imagem foi enviada.")

    image = _open_verified_image(file_storage)
    try:
        image = ImageOps.exif_transpose(image)

        if image.mode not in {"RGB", "L"}:
            if "A" in image.getbands():
                background = Image.new("RGB", image.size, "white")
                alpha = image.getchannel("A")
                background.paste(image.convert("RGB"), mask=alpha)
                image = background
            else:
                image = image.convert("RGB")
        elif image.mode == "L":
            image = image.convert("RGB")

        image.thumbnail((MAX_OUTPUT_EDGE, MAX_OUTPUT_EDGE), Image.Resampling.LANCZOS)

        output = BytesIO()
        image.save(
            output,
            format="JPEG",
            quality=JPEG_QUALITY,
            optimize=True,
            progressive=True,
        )
        size_bytes = output.tell()
        output.seek(0)

        return NormalizedImage(
            stream=output,
            filename="discursiva.jpg",
            mime_type="image/jpeg",
            size_bytes=size_bytes,
            width=image.width,
            height=image.height,
        )
    except (OSError, ValueError) as exc:
        raise ImageValidationError(
            "Não foi possível processar a imagem enviada."
        ) from exc
    finally:
        image.close()
        file_storage.stream.seek(0)


def normalize_image_stream(stream: BinaryIO) -> NormalizedImage:
    """Versão genérica para os provedores de storage."""
    return normalize_uploaded_image(SimpleNamespace(stream=stream))
