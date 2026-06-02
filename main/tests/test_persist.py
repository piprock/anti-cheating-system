import pytest
from django.utils import timezone

from main.services import ExamService, GazeService
from main.persist import persist_session_from_payload
from main.models import Survey, InterviewSession, Answer

@pytest.mark.django_db
def test_persist_session_basic():
    Survey.objects.create(key='surveyX', control_questions=["ПІБ", "Q1"], title='S')
    # Prepare gaze session state
    gaze = GazeService().init_session('surveyX')
    gaze['frames'] = 100
    gaze['not_looking'] = 10  # 10%
    GazeService().save_session('surveyX', gaze)

    payload = {
        "student": {"first_name": "Іван", "last_name": "Петренко"},
        "answers": [
            {"question": "Q1", "answer": "A1", "accuracy_score": 90, "feedback": "Добре"},
        ],
        "summary": {"dialogue_result": "Резюме", "overall_accuracy": 90, "plagiarism_score": 5},
    }

    saved = persist_session_from_payload('surveyX', payload)
    assert 'session_id' in saved
    session = InterviewSession.objects.get(id=saved['session_id'])
    assert session.grade_5 == 5  # high accuracy, low plag, low gaze
    assert session.gaze_not_looking_pct == pytest.approx(10.0, rel=0.2)
    assert session.overall_accuracy == 90
    assert session.plagiarism_score == 5
    assert session.answers.count() == 1

@pytest.mark.django_db
def test_persist_session_penalties():
    Survey.objects.create(key='surveyY', control_questions=["ПІБ", "Q1"], title='S')
    gaze = GazeService().init_session('surveyY')
    gaze['frames'] = 100
    gaze['not_looking'] = 60  # 60%
    GazeService().save_session('surveyY', gaze)

    payload = {
        "student": {"first_name": "Аліна", "last_name": "Козак"},
        "answers": [
            {"question": "Q1", "answer": "A1", "accuracy_score": 95, "feedback": "Добре"},
        ],
        "summary": {"dialogue_result": "Резюме", "overall_accuracy": 95, "plagiarism_score": 30},
    }
    saved = persist_session_from_payload('surveyY', payload)
    session = InterviewSession.objects.get(id=saved['session_id'])
    # Base 5, plagiarism penalty ->4, gaze penalty ->3
    assert session.grade_5 == 3

