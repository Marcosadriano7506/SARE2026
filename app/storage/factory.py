import os

from .google_drive import GoogleDriveStorage
from .local_homologation import LocalHomologationStorage


def get_storage_service(provider_name: str | None = None):
    provider = (
        provider_name or os.getenv("STORAGE_PROVIDER", "LOCAL_HOMOLOGATION")
    ).upper()

    if provider == "LOCAL_HOMOLOGATION":
        if os.getenv("ALLOW_HOMOLOGATION_BOOTSTRAP", "false").lower() != "true":
            raise RuntimeError("Storage local só é permitido em homologação.")
        return LocalHomologationStorage()

    if provider == "GOOGLE_DRIVE":
        return GoogleDriveStorage()

    raise RuntimeError(f"Storage provider desconhecido: {provider}")
