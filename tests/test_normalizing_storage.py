from app.storage.normalizing import NormalizingStorage


class FakeBackend:
    provider = "GOOGLE_DRIVE"

    def smoke_test_write_delete(self):
        return "ok"


def test_normalizing_storage_forwards_smoke_test():
    storage = NormalizingStorage(FakeBackend())
    assert storage.smoke_test_write_delete() == "ok"
