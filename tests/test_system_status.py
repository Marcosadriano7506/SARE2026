from app.services.system_status import calculate_system_status


def test_non_persistent_test_environment_is_not_production_ready(app):
    with app.app_context():
        status = calculate_system_status(app)

    assert status.database_ok is True
    assert status.database_persistent is False
    assert status.production_ready is False
    assert status.storage_provider == "LOCAL_HOMOLOGATION"
