from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class StoredFile:
    provider: str
    file_id: str
    folder_id: str | None
    stored_filename: str
    mime_type: str | None
    size_bytes: int | None


class StorageService(Protocol):
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
    ) -> StoredFile: ...

    def delete(self, file_id: str) -> None: ...

    def check_connection(self) -> str: ...
