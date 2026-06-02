import pytest
from main.services import ExamService

@pytest.fixture
def exam_service():
    return ExamService()

@pytest.mark.django_db
def test_start_exam_initializes_state(exam_service):
    questions = ["ПІБ студента", "Що таке змінна?", "Поясніть рекурсію"]
    state = exam_service.start_exam('survey1', questions)
    assert state['index'] == 0
    assert state['questions'] == questions
    assert state['qa_log'] == []

@pytest.mark.django_db
def test_record_first_answer_sets_fullname_and_score(exam_service):
    state = exam_service.start_exam('survey2', ["ПІБ", "Q2"])
    # first answer manually passed with score 100
    exam_service.record_answer(state, "Іван Петренко", 100, "ПІБ збережено.")
    assert state['qa_log'][0]['accuracy_score'] == 100
    assert state['index'] == 1

@pytest.mark.django_db
def test_build_session_payload_excludes_first(exam_service):
    state = exam_service.start_exam('survey3', ["ПІБ", "Q2", "Q3"])
    exam_service.record_answer(state, "Степан Прізвищенко", 100, "ok")
    exam_service.record_answer(state, "Ans2", 80, "fb2")
    exam_service.record_answer(state, "Ans3", 60, "fb3")
    payload = exam_service.build_session_payload(state, "Summary", 70, 10)
    assert len(payload['answers']) == 2
    assert all(a['question'] != 'ПІБ' for a in payload['answers'])

@pytest.mark.django_db
def test_compute_grade_penalties(exam_service):
    # High accuracy baseline
    assert exam_service.compute_grade(95, 0, 0) == 5
    # plagiarism penalty
    assert exam_service.compute_grade(95, 30, 0) == 4
    # gaze penalty
    assert exam_service.compute_grade(95, 0, 40) == 4
    # both penalties
    assert exam_service.compute_grade(95, 30, 40) == 3
    # low accuracy clamps
    assert exam_service.compute_grade(10, 0, 0) == 1

@pytest.mark.django_db
def test_average_accuracy(exam_service):
    qa_log = [
        {"accuracy_score": 50},
        {"accuracy_score": 100},
        {"accuracy_score": 75},
    ]
    assert exam_service.calculate_average_accuracy(qa_log) == 75
