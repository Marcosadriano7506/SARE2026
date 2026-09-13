from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import BinaryIO

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from werkzeug.utils import secure_filename

from .base import StoredFile


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER_MIME = "application/vnd.google-apps.folder"


def _folder_name(value: str) -> str:
    value = re.sub(r"[\x00-\x1f\x7f]+", " ", value or "")
    value = " ".join(value.split()).strip()
    return value[:180] or "Sem nome"


def _file_name(student_name: str, student_id: int, original_filename: str) -> str:
    extension = Path(secure_filename(original_filename)).suffix.lower() or ".jpg"
    base = secure_filename(student_name).strip("._") or "estudante"
    return f"{base}__{student_id}{extension}"


def _escape_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class GoogleDriveStorage:
    provider = "GOOGLE_DRIVE"

    def __init__(self):
        raw_credentials = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        root_folder_id = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "").strip()
        if not raw_credentials or not root_folder_id:
            raise RuntimeError(
                "Credenciais do Google Drive ou pasta raiz não configuradas."
            )

        try:
            info = json.loads(raw_credentials)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON inválido.") from exc

        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=[DRIVE_SCOPE]
        )
        self.service = build(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )
        self.root_folder_id = root_folder_id

    def _find_or_create_folder(self, name: str, parent_id: str) -> str:
        name = _folder_name(name)
        escaped_name = _escape_query(name)
        escaped_parent = _escape_query(parent_id)
        query = (
            f"name = '{escaped_name}' and "
            f"mimeType = '{FOLDER_MIME}' and "
            f"'{escaped_parent}' in parents and trashed = false"
        )
        response = (
            self.service.files()
            .list(
                q=query,
                spaces="drive",
                fields="files(id,name)",
                pageSize=10,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        files = response.get("files", [])
        if files:
            return files[0]["id"]

        created = (
            self.service.files()
            .create(
                body={
                    "name": name,
                    "mimeType": FOLDER_MIME,
                    "parents": [parent_id],
                },
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )
        return created["id"]

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
        evaluation_folder = self._find_or_create_folder(
            evaluation_name, self.root_folder_id
        )
        school_folder = self._find_or_create_folder(
            school_name, evaluation_folder
        )
        class_folder = self._find_or_create_folder(class_name, school_folder)

        stored_filename = _file_name(
            student_name, student_id, original_filename
        )
        stream.seek(0)
        media = MediaIoBaseUpload(
            stream,
            mimetype=mime_type or "image/jpeg",
            resumable=False,
        )
        created = (
            self.service.files()
            .create(
                body={
                    "name": stored_filename,
                    "parents": [class_folder],
                },
                media_body=media,
                fields="id,size,mimeType",
                supportsAllDrives=True,
            )
            .execute()
        )

        size = created.get("size")
        return StoredFile(
            provider=self.provider,
            file_id=created["id"],
            folder_id=class_folder,
            stored_filename=stored_filename,
            mime_type=created.get("mimeType") or mime_type,
            size_bytes=int(size) if size is not None else None,
        )

    def delete(self, file_id: str) -> None:
        if not file_id:
            return
        self.service.files().delete(
            fileId=file_id,
            supportsAllDrives=True,
        ).execute()
