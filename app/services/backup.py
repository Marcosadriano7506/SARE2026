from __future__ import annotations

import gzip
import json
from datetime import date, datetime
from enum import Enum
from io import BytesIO

from sqlalchemy import Date, DateTime, select

from app.extensions import db


BACKUP_FORMAT_VERSION = 1


class BackupRestoreError(ValueError):
    pass


def _json_value(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def generate_structured_backup() -> bytes:
    """Exports every application table as a gzip-compressed JSON snapshot."""
    payload = {
        "format": "SARE_STRUCTURED_BACKUP",
        "version": BACKUP_FORMAT_VERSION,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "tables": {},
    }

    for table in sorted(db.metadata.tables.values(), key=lambda item: item.name):
        result = db.session.execute(select(table)).mappings().all()
        payload["tables"][table.name] = [
            {key: _json_value(value) for key, value in row.items()}
            for row in result
        ]

    raw = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    output = BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", compresslevel=6) as zipped:
        zipped.write(raw)
    return output.getvalue()


def _decode_backup(content: bytes) -> dict:
    try:
        raw = gzip.decompress(content)
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupRestoreError("Arquivo de backup inválido ou corrompido.") from exc

    if payload.get("format") != "SARE_STRUCTURED_BACKUP":
        raise BackupRestoreError("Formato de backup não reconhecido.")
    if payload.get("version") != BACKUP_FORMAT_VERSION:
        raise BackupRestoreError("Versão de backup incompatível com esta aplicação.")
    if not isinstance(payload.get("tables"), dict):
        raise BackupRestoreError("Backup sem conjunto de tabelas válido.")
    return payload


def _coerce_row(table, row: dict) -> dict:
    result = {}
    for column in table.columns:
        if column.name not in row:
            continue
        value = row[column.name]
        if value is None:
            result[column.name] = None
        elif isinstance(column.type, DateTime):
            result[column.name] = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif isinstance(column.type, Date):
            result[column.name] = date.fromisoformat(value)
        else:
            result[column.name] = value
    return result


def restore_structured_backup(content: bytes) -> dict[str, int]:
    """Replaces application data transactionally from a trusted backup file."""
    payload = _decode_backup(content)
    tables_payload = payload["tables"]
    known_tables = {table.name: table for table in db.metadata.sorted_tables}

    unknown = sorted(set(tables_payload) - set(known_tables))
    if unknown:
        raise BackupRestoreError(
            "Backup contém tabelas desconhecidas: " + ", ".join(unknown)
        )

    counts: dict[str, int] = {}
    try:
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())

        for table in db.metadata.sorted_tables:
            rows = tables_payload.get(table.name, [])
            if not isinstance(rows, list):
                raise BackupRestoreError(
                    f"Conteúdo inválido para a tabela {table.name}."
                )
            normalized = [_coerce_row(table, row) for row in rows]
            if normalized:
                db.session.execute(table.insert(), normalized)
            counts[table.name] = len(normalized)

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return counts
