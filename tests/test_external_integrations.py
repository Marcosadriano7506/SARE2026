from app import _check_external_integrations


class FakeStorage:
    def check_connection(self):
        return "ok"


def test_google_drive_startup_check_is_non_fatal(app, monkeypatch):
    monkeypatch.setenv("STORAGE_PROVIDER", "GOOGLE_DRIVE")

    import app.storage.factory as factory

    monkeypatch.setattr(factory, "get_storage_service", lambda provider_name=None: FakeStorage())

    _check_external_integrations(app)


def test_non_drive_provider_skips_external_check(app, monkeypatch):
    monkeypatch.setenv("STORAGE_PROVIDER", "LOCAL_HOMOLOGATION")
    _check_external_integrations(app)
