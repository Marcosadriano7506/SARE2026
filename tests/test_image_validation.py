from io import BytesIO

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.services.image_validation import (
    ImageValidationError,
    MAX_OUTPUT_EDGE,
    normalize_uploaded_image,
    validate_uploaded_image,
)


def test_valid_png_is_accepted_and_stream_is_rewound():
    buffer = BytesIO()
    Image.new("RGB", (32, 24)).save(buffer, format="PNG")
    buffer.seek(0)

    upload = FileStorage(
        stream=buffer,
        filename="discursiva.png",
        content_type="image/png",
    )
    validate_uploaded_image(upload)

    assert upload.stream.tell() == 0


def test_fake_jpg_is_rejected():
    upload = FileStorage(
        stream=BytesIO(b"not-an-image"),
        filename="discursiva.jpg",
        content_type="image/jpeg",
    )

    with pytest.raises(ImageValidationError):
        validate_uploaded_image(upload)


def test_normalization_converts_large_png_to_jpeg_without_metadata():
    buffer = BytesIO()
    Image.new("RGBA", (3200, 2400), (255, 0, 0, 120)).save(buffer, format="PNG")
    buffer.seek(0)
    upload = FileStorage(
        stream=buffer,
        filename="discursiva.png",
        content_type="image/png",
    )

    normalized = normalize_uploaded_image(upload)

    assert normalized.filename == "discursiva.jpg"
    assert normalized.mime_type == "image/jpeg"
    assert max(normalized.width, normalized.height) <= MAX_OUTPUT_EDGE
    assert normalized.size_bytes > 0

    with Image.open(normalized.stream) as result:
        assert result.format == "JPEG"
        assert result.mode == "RGB"
        assert not result.getexif()
