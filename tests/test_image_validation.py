from io import BytesIO

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.services.image_validation import ImageValidationError, validate_uploaded_image


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
