from __future__ import annotations

from dataclasses import dataclass, field

from app.models import (
    ApplicationStatus,
    Evaluation,
    StudentPresence,
    SubjectArea,
)
from app.services.scoring import proficiency_level


def _pct(correct: int, total: int) -> float:
    return round((correct / total * 100), 2) if total else 0.0


@dataclass
class StudentMetric:
    student_id: int
    student_name: str
    school_name: str
    class_name: str
    grade: int
    total_correct: int
    total_items: int
    lp_correct: int
    lp_items: int
    math_correct: int
    math_items: int

    @property
    def total_percent(self) -> float:
        return _pct(self.total_correct, self.total_items)

    @property
    def lp_percent(self) -> float:
        return _pct(self.lp_correct, self.lp_items)

    @property
    def math_percent(self) -> float:
        return _pct(self.math_correct, self.math_items)

    @property
    def level(self) -> str:
        return proficiency_level(self.total_percent)


@dataclass
class AggregateMetric:
    name: str
    correct: int = 0
    items: int = 0
    present_students: int = 0

    @property
    def percent(self) -> float:
        return _pct(self.correct, self.items)


@dataclass
class SkillMetric:
    code: str
    subject: str
    grade: int
    correct: int = 0
    opportunities: int = 0

    @property
    def percent(self) -> float:
        return _pct(self.correct, self.opportunities)


@dataclass
class EvaluationAnalytics:
    evaluation: Evaluation
    finalized_classes: int = 0
    present_students: int = 0
    absent_students: int = 0
    total_correct: int = 0
    total_items: int = 0
    lp_correct: int = 0
    lp_items: int = 0
    math_correct: int = 0
    math_items: int = 0
    students: list[StudentMetric] = field(default_factory=list)
    schools: list[AggregateMetric] = field(default_factory=list)
    classes: list[AggregateMetric] = field(default_factory=list)
    skills: list[SkillMetric] = field(default_factory=list)

    @property
    def total_percent(self) -> float:
        return _pct(self.total_correct, self.total_items)

    @property
    def lp_percent(self) -> float:
        return _pct(self.lp_correct, self.lp_items)

    @property
    def math_percent(self) -> float:
        return _pct(self.math_correct, self.math_items)

    @property
    def proficiency_counts(self) -> dict[str, int]:
        result = {"DEFASAGEM": 0, "INTERMEDIARIO": 0, "AVANCADO": 0}
        for student in self.students:
            result[student.level] += 1
        return result


def calculate_evaluation_analytics(evaluation: Evaluation) -> EvaluationAnalytics:
    analytics = EvaluationAnalytics(evaluation=evaluation)

    questions_by_grade: dict[int, list] = {}
    for test in evaluation.tests:
        questions_by_grade.setdefault(test.grade, []).extend(test.questions)

    school_map: dict[str, AggregateMetric] = {}
    class_map: dict[str, AggregateMetric] = {}
    skill_map: dict[tuple[str, str, int], SkillMetric] = {}

    for classroom in evaluation.classes:
        application = classroom.application
        if application is None or application.status != ApplicationStatus.FINALIZED:
            continue

        analytics.finalized_classes += 1
        questions = questions_by_grade.get(classroom.grade, [])
        question_subject = {
            question.id: question.test.subject for question in questions
        }
        answer_keys = {question.id: question.correct_option for question in questions}

        school_metric = school_map.setdefault(
            classroom.school.name,
            AggregateMetric(name=classroom.school.name),
        )
        class_label = f"{classroom.school.name} — {classroom.name}"
        class_metric = class_map.setdefault(
            class_label,
            AggregateMetric(name=class_label),
        )

        for record in application.records:
            if record.presence == StudentPresence.ABSENT:
                analytics.absent_students += 1
                continue

            analytics.present_students += 1
            school_metric.present_students += 1
            class_metric.present_students += 1

            answers = {answer.question_id: answer.selected_option for answer in record.answers}
            total_correct = lp_correct = math_correct = 0
            lp_items = math_items = 0

            for question in questions:
                selected = answers.get(question.id)
                correct = int(selected is not None and selected == answer_keys[question.id])
                subject = question_subject[question.id]

                if subject == SubjectArea.PORTUGUESE:
                    lp_items += 1
                    lp_correct += correct
                    analytics.lp_items += 1
                    analytics.lp_correct += correct
                else:
                    math_items += 1
                    math_correct += correct
                    analytics.math_items += 1
                    analytics.math_correct += correct

                if question.skill is not None:
                    key = (
                        question.skill.code,
                        subject.value,
                        classroom.grade,
                    )
                    skill_metric = skill_map.setdefault(
                        key,
                        SkillMetric(
                            code=question.skill.code,
                            subject=subject.value,
                            grade=classroom.grade,
                        ),
                    )
                    skill_metric.opportunities += 1
                    skill_metric.correct += correct

            total_items = len(questions)
            total_correct = lp_correct + math_correct

            analytics.total_items += total_items
            analytics.total_correct += total_correct

            school_metric.items += total_items
            school_metric.correct += total_correct
            class_metric.items += total_items
            class_metric.correct += total_correct

            analytics.students.append(
                StudentMetric(
                    student_id=record.student.id,
                    student_name=record.student.name,
                    school_name=classroom.school.name,
                    class_name=classroom.name,
                    grade=classroom.grade,
                    total_correct=total_correct,
                    total_items=total_items,
                    lp_correct=lp_correct,
                    lp_items=lp_items,
                    math_correct=math_correct,
                    math_items=math_items,
                )
            )

    analytics.students.sort(
        key=lambda item: (-item.total_percent, item.student_name)
    )
    analytics.schools = sorted(
        school_map.values(), key=lambda item: (-item.percent, item.name)
    )
    analytics.classes = sorted(
        class_map.values(), key=lambda item: (-item.percent, item.name)
    )
    analytics.skills = sorted(
        skill_map.values(),
        key=lambda item: (item.grade, item.subject, item.code),
    )
    return analytics
