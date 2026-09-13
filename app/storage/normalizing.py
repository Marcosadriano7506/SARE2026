from __future__ import annotations

from app.services.image_validation import normalize_image_stream


class NormalizingStorage:
    """Decorator that normalizes every discursive image before persistence."""

    def __init__(self, backend):
        self.backend = backend
        self.provider = backend.provider

    def upload_discursive(self, **kwargs):
        normalized = normalize_image_stream(kwargs["stream"])
        kwargs = dict(kwargs)
        kwargs["stream"] = normalized.stream
        kwargs["original_filename"] = normalized.filename
        kwargs["mime_type"] = normalized.mime_type
        return self.backend.upload_discursive(**kwargs)

    def delete(self, file_id: str) -> None:
        return self.backend.delete(file_id)

    def check_connection(self) -> str:
        return self.backend.check_connection()
