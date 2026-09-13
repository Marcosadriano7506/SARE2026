from app.services.system_status import calculate_system_status


def test_homologation_environment_is_not_marked_production_ready(app):
    with app.app_context():
        status = calculate_system_status(app)

    assert status.database_ok is True
    assert status.homologation is True
    assert status.production_ready is False
    assert status.storage_provider == "LOCAL_HOMOLOGATION"
