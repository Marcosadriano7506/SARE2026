from app.models import ClassRoom, Evaluation, Student, Test, User
from app.services.evaluation_readiness import calculate_evaluation_readiness
from app.services.load_fixture import create_load_fixture, delete_load_fixture


def test_load_fixture_is_idempotent_and_removable(app, monkeypatch):
    monkeypatch.setenv("ALLOW_HOMOLOGATION_BOOTSTRAP", "true")
    monkeypatch.setenv("LOAD_TEST_PASSWORD", "LoadTest123!")

    with app.app_context():
        result = create_load_fixture(user_count=3, students_per_class=4)
        assert result["users_created"] == 3
        assert result["classes_created"] == 3
        assert result["students_created"] == 12
        assert User.query.filter(User.username.like("load%")).count() == 3
        assert ClassRoom.query.filter(ClassRoom.access_code.like("LOAD%")).count() == 3
        assert Student.query.filter(Student.external_id.like("L%")).count() == 12

        evaluation = Evaluation.query.filter_by(name="SARE LOAD TEST").one()
        readiness = calculate_evaluation_readiness(evaluation)
        assert readiness.ready is True
        assert readiness.tests == 2
        assert readiness.questions == 2
        assert Test.query.filter_by(evaluation_id=evaluation.id).count() == 2

        second = create_load_fixture(user_count=3, students_per_class=4)
        assert second["users_created"] == 0
        assert second["classes_created"] == 0
        assert second["students_created"] == 0

        deleted = delete_load_fixture()
        assert deleted["users_deleted"] == 3
        assert deleted["classes_deleted"] == 3
        assert User.query.filter(User.username.like("load%")).count() == 0
        assert ClassRoom.query.filter(ClassRoom.access_code.like("LOAD%")).count() == 0
