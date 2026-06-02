"""
GPT utilities: conversation helper and strict JSON-based scoring/summary.

- chat_with_gpt: per-session chat history stored in Django cache (via cache_utils)
- ai_score: returns (score:int, feedback:str) parsed from strict JSON
- ai_summary: returns (summary:str, overall:int, plagiarism:int) using strict JSON

Refactor highlights:
- Uses response_format={"type": "json_object"} for strict JSON outputs
- Standardized JSON schemas for scoring and summary
- Exponential backoff retry with robust exception handling
"""
from __future__ import annotations

from typing import List, Dict, Tuple, Any
import json
import os
import time

from .cache_utils import cache_get_chat_history, cache_append_chat_message

import openai


def _client() -> openai.OpenAI:
    return openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _retry_sleep(attempt: int, base: float = 0.5, factor: float = 2.0, cap: float = 8.0) -> None:
    """Sleep with exponential backoff. attempt is 0-based."""
    delay = min(cap, base * (factor ** attempt))
    time.sleep(delay)


def _chat_completion_json(messages: List[Dict[str, str]], temperature: float = 0.1, max_retries: int = 3) -> Dict[str, Any]:
    """
    Call OpenAI Chat Completions with strict JSON response_format and parse the result.
    Returns parsed JSON dict. Raises last exception after retries.
    """
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            client = _client()
            resp = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = (resp.choices[0].message.content or "").strip()
            return json.loads(content)
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                _retry_sleep(attempt)
            else:
                raise
    # Unreachable, but for type checkers
    if last_err:
        raise last_err
    raise RuntimeError("Unknown error in _chat_completion_json")


def chat_with_gpt(prompt: str, session_id: str, check: bool = False) -> str:
    """Free-form chat with per-session memory stored in cache."""
    system = (
        "Тобі учень надіслав свою лабораторну роботу. Перевір на граматичні помилки і на скільки чітко розкрита мета роботи. "
        "Висловлюйся дуже стисло. В кінці оціни роботу по 5тибальній шкалі. Будь менш ввічливим, намагайся завалити студента, щоб не було оцінки 5/5"
        if check else
        "Ти викладач і твоя ціль допомогти студенту або перевірити прикріплену лабораторну. Опирайся на попередні запити. "
        "Будь менш ввічливим, намагайся завалити студента, щоб не було оцінки 5/5. Не оцінюй, поки не отримаєш текст лабораторної!"
    )

    history = cache_get_chat_history(session_id)
    cache_append_chat_message(session_id, "user", prompt)

    messages = [{"role": "system", "content": system}] + history
    reply = ""
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            client = _client()
            resp = client.chat.completions.create(model="gpt-4", messages=messages, temperature=0.7)
            reply = (resp.choices[0].message.content or "").strip()
            break
        except Exception as e:
            last_err = e
            if attempt < 2:
                _retry_sleep(attempt)
            else:
                reply = f"Сталася помилка: {e}"

    cache_append_chat_message(session_id, "assistant", reply)
    return reply


def ai_score(question: str, user_answer: str) -> Tuple[int, str]:
    """Ask GPT to score an answer strictly via JSON. Returns (score, feedback)."""
    prompt = (
        "Ти екзаменатор. Оціни лаконічно відповідь студента на питання.\n"
        "Поверни ТІЛЬКИ валідний JSON без пояснень у форматі:\n"
        "{\"score\": <0..100>, \"feedback\": \"<1-2 речення>\"}.\n"
        f"Питання: {question}\n"
        f"Відповідь: {user_answer}"
    )
    messages = [
        {"role": "system", "content": "Відповідай рівно одним JSON-об'єктом без пояснень."},
        {"role": "user", "content": prompt},
    ]
    try:
        data = _chat_completion_json(messages, temperature=0.1, max_retries=3)
        score = int(max(0, min(100, int(data.get("score", 0)))))
        feedback = str(data.get("feedback", "")).strip() or "Ок."
        return score, feedback
    except Exception:
        return 0, "Не вдалося автоматично оцінити."


def ai_summary(qa_log: List[Dict[str, object]]) -> Tuple[str, int, int]:
    """Summarize Q/A and estimate plagiarism strictly via JSON."""
    # average accuracy across entries that provide accuracy_score
    scores = [int(q.get("accuracy_score", 0)) for q in qa_log]
    overall = round(sum(scores) / max(1, len(scores))) if scores else 0
    ctx = "\n".join([f"Q: {q['question']}\nA: {q['answer']}\n" for q in qa_log])
    prompt = (
        "Проаналізуй короткий діалог студент-викладач. Поверни JSON у форматі:\n"
        "{\"summary\": \"2–4 речення\", \"plagiarism_score\": <0..100>}\n\n"
        f"{ctx}"
    )
    messages = [
        {"role": "system", "content": "Відповідай рівно одним JSON-об'єктом без пояснень."},
        {"role": "user", "content": prompt},
    ]
    try:
        data = _chat_completion_json(messages, temperature=0.1, max_retries=3)
        summary = str(data.get("summary", "")).strip() or "Короткий підсумок недоступний."
        plag = int(max(0, min(100, int(data.get("plagiarism_score", 0)))))
        return summary, overall, plag
    except Exception:
        return "Підсумок згенерувати не вдалося.", overall, 0
