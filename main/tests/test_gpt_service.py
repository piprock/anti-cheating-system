import json
import pytest

from main.services import GPTService

class DummyResp:
    class choice_message:
        def __init__(self, content):
            self.content = content
    class choice:
        def __init__(self, content):
            self.message = DummyResp.choice_message(content)
    def __init__(self, content):
        self.choices = [DummyResp.choice(content)]

class DummyClient:
    def __init__(self, payload):
        self.payload = payload
    class chat:
        class completions:
            @staticmethod
            def create(**kwargs):
                # Return JSON of score or summary depending on prompt
                messages = kwargs.get('messages', [])
                last = messages[-1]['content'] if messages else ''
                if 'Оціни' in last or 'score' in last or 'Поверни' in last:
                    return DummyResp(json.dumps({"score": 88, "feedback": "Добре."}))
                elif 'Проаналізуй' in last:
                    return DummyResp(json.dumps({"summary": "Короткий підсумок.", "plagiarism_score": 12}))
                else:
                    return DummyResp('Звичайна відповідь')

@pytest.fixture
def gpt_service(monkeypatch):
    service = GPTService()
    # monkeypatch internal client
    monkeypatch.setattr(service, 'client', DummyClient({}))
    return service

@pytest.mark.django_db
def test_score_answer_json(gpt_service):
    score, feedback = gpt_service.score_answer('Що таке Python?', 'Це мова програмування.')
    assert score == 88
    assert feedback.startswith('Добре')

@pytest.mark.django_db
def test_summarize_exam_json(gpt_service):
    summary, overall, plag = gpt_service.summarize_exam([
        {"question": "Q1", "answer": "A1", "accuracy_score": 80},
        {"question": "Q2", "answer": "A2", "accuracy_score": 100},
    ])
    assert summary.startswith('Короткий')
    assert overall == 90
    assert plag == 12

@pytest.mark.django_db
def test_chat_history_accumulates(gpt_service):
    reply1 = gpt_service.chat('Привіт', session_id='sess1')
    reply2 = gpt_service.chat('Ще раз', session_id='sess1')
    assert isinstance(reply1, str)
    assert isinstance(reply2, str)
    # Ensure two user messages stored
    from main.cache_utils import cache_get_chat_history
    hist = cache_get_chat_history('sess1')
    assert len(hist) >= 4  # user+assistant pairs

@pytest.mark.django_db
def test_score_answer_fallback(monkeypatch, gpt_service):
    def fail(*a, **k):
        raise RuntimeError('boom')
    monkeypatch.setattr(gpt_service, '_chat_completion_json', fail)
    score, feedback = gpt_service.score_answer('Q', 'A')
    assert score == 0
    assert 'Не вдалося' in feedback
