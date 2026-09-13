from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import BinaryIO

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from werkzeug.utils import secure_filename

from .base import StoredFile


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
TOKEN_URI = "https://oauth2.googleapis.com/token"
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


def oauth_environment_configured() -> bool:
    return all(
        os.getenv(key, "").strip()
        for key in (
            "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "GOOGLE_OAUTH_REFRESH_TOKEN",
        )
    )


def service_account_environment_configured() -> bool:
    return bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip())


def build_google_credentials():
    if oauth_environment_configured():
        return OAuthCredentials(
            token=None,
            refresh_token=os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN", "").strip(),
            token_uri=TOKEN_URI,
            client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip(),
            client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip(),
            scopes=[DRIVE_FILE_SCOPE],
        )

    raw_credentials = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw_credentials:
        try:
            info = json.loads(raw_credentials)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON inválido.") from exc

        return service_account.Credentials.from_service_account_info(
            info, scopes=[DRIVE_SCOPE]
        )

    raise RuntimeError(
        "Credenciais do Google Drive não configuradas. "
        "Use OAuth ou service account."
    )


def build_drive_service(credentials=None):
    return build(
        "drive",
        "v3",
        credentials=credentials or build_google_credentials(),
        cache_discovery=False,
    )


def _find_folder(service, name: str, parent_id: str | None = None) -> str | None:
    escaped_name = _escape_query(_folder_name(name))
    query_parts = [
        f"name = '{escaped_name}'",
        f"mimeType = '{FOLDER_MIME}'",
        "trashed = false",
    ]
    if parent_id:
        query_parts.append(f"'{_escape_query(parent_id)}' in parents")
    else:
        query_parts.append("'root' in parents")

    response = (
        service.files()
        .list(
            q=" and ".join(query_parts),
            spaces="drive",
            fields="files(id,name)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = response.get("files", [])
    return files[0]["id"] if files else None


def _create_folder(service, name: str, parent_id: str | None = None) -> str:
    body = {
        "name": _folder_name(name),
        "mimeType": FOLDER_MIME,
    }
    if parent_id:
        body["parents"] = [parent_id]

    created = (
        service.files()
        .create(
            body=body,
            fields="id",
            supportsAllDrives=True,
        )
        .execute()
    )
    return created["id"]


def ensure_oauth_root_folders(credentials) -> tuple[str, str]:
    """Cria/reutiliza SARE/DISCURSIVAS no Meu Drive do usuário OAuth.

    Com o escopo drive.file o aplicativo enxerga e gerencia apenas arquivos
    criados/abertos pelo próprio aplicativo. Por isso a pasta raiz deve ser
    criada pelo SARE durante a autorização inicial.
    """
    service = build_drive_service(credentials)

    sare_folder_id = _find_folder(service, "SARE")
    if sare_folder_id is None:
        sare_folder_id = _create_folder(service, "SARE")

    discursivas_id = _find_folder(service, "DISCURSIVAS", sare_folder_id)
    if discursivas_id is None:
        discursivas_id = _create_folder(service, "DISCURSIVAS", sare_folder_id)

    return sare_folder_id, discursivas_id


class GoogleDriveStorage:
    provider = "GOOGLE_DRIVE"

    def __init__(self):
        root_folder_id = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "").strip()
        if not root_folder_id:
            raise RuntimeError("GOOGLE_DRIVE_ROOT_FOLDER_ID não configurado.")

        self.service = build_drive_service()
        self.root_folder_id = root_folder_id

    def _find_or_create_folder(self, name: str, parent_id: str) -> str:
        existing = _find_folder(self.service, name, parent_id)
        if existing:
            return existing
        return _create_folder(self.service, name, parent_id)

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

    def check_connection(self) -> str:
        folder = (
            self.service.files()
            .get(
                fileId=self.root_folder_id,
                fields="id,name,mimeType",
                supportsAllDrives=True,
            )
            .execute()
        )
        if folder.get("mimeType") != FOLDER_MIME:
            raise RuntimeError("GOOGLE_DRIVE_ROOT_FOLDER_ID não aponta para uma pasta.")
        return f"Pasta raiz do Drive acessível: {folder.get('name', 'SARE')}."
