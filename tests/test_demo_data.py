from app.models import ClassRoom, Question, Student, Test
from app.services.demo_data import DEMO_CLASS_CODE, create_demo_dataset


def test_demo_dataset_is_idempotent(app, monkeypatch):
    monkeypatch.setenv("ALLOW_HOMOLOGATION_BOOTSTRAP", "true")

    with app.app_context():
        classroom, created = create_demo_dataset()
        assert created is True
        assert classroom.access_code == DEMO_CLASS_CODE
        assert Student.query.count() == 5
        assert Test.query.count() == 2
        assert Question.query.count() == 10

        classroom_again, created_again = create_demo_dataset()
        assert created_again is False
        assert classroom_again.id == classroom.id
        assert ClassRoom.query.count() == 1
