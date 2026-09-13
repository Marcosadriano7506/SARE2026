from __future__ import annotations

import gzip
import json
from datetime import date, datetime
from enum import Enum
from io import BytesIO

from sqlalchemy import select

from app.extensions import db


BACKUP_FORMAT_VERSION = 1


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
