from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import BinaryIO

from werkzeug.utils import secure_filename

from .base import StoredFile


def _slug(value: str) -> str:
    value = secure_filename(value).lower()
    value = re.sub(r"[^a-z0-9_.-]+", "-", value).strip("-")
    return value or "item"


class LocalHomologationStorage:
    provider = "LOCAL_HOMOLOGATION"

    def __init__(self, root: str = "/tmp/sare_uploads"):
        self.root = Path(root)

    def upload_discursive(
        self,
        *,
        evaluation_name: str,
        school_name: str,
        class_name: str,
        student_name: str,
        student_id: int,
        stream: BinaryIO,
        original_filename: str,
        mime_type: str | None,
    ) -> StoredFile:
        folder = (
            self.root
            / _slug(evaluation_name)
            / _slug(school_name)
            / _slug(class_name)
        )
        folder.mkdir(parents=True, exist_ok=True)

        extension = Path(secure_filename(original_filename)).suffix.lower() or ".jpg"
        stored_filename = f"{_slug(student_name)}__{student_id}{extension}"
        path = folder / stored_filename

        size = 0
        with path.open("wb") as target:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                target.write(chunk)

        return StoredFile(
            provider=self.provider,
            file_id=str(uuid.uuid4()),
            folder_id=str(folder),
            stored_filename=stored_filename,
            mime_type=mime_type,
            size_bytes=size,
        )
