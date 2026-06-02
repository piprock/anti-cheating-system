"""
GPTService: Encapsulates all OpenAI GPT interactions.

Provides:
- Chat with session memory (stored in Django cache)
- Answer scoring with strict JSON output
- Exam summary with plagiarism detection
"""
from __future__ import annotations

from typing import List, Dict, Tuple, Any
import json
import os
import time
import logging
from dotenv import load_dotenv

from ..cache_utils import cache_get_chat_history, cache_append_chat_message

import openai

logger = logging.getLogger(__name__)


class GPTService:
    """Service for OpenAI GPT operations: chat, scoring, summarization."""

    def __init__(self):
        # Load environment variables from .env if present
        try:
            load_dotenv()
        except Exception:
            # Safe to ignore; just log
            logger.debug("dotenv load failed or not present")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set – GPT features disabled.")
            self.client = None
        else:
            try:
                self.client = openai.OpenAI(api_key=api_key)
            except Exception as e:
                logger.error("Failed to initialize OpenAI client: %s", e)
                self.client = None

    def _retry_sleep(self, attempt: int, base: float = 0.3, factor: float = 1.5, cap: float = 2.0) -> None:
        """Sleep with exponential backoff."""
        delay = min(cap, base * (factor ** attempt))
        time.sleep(delay)

    def _chat_completion_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_retries: int = 2,
        model: str = "gpt-4o-mini",
        max_tokens: int = 200
    ) -> Dict[str, Any]:
        """
        Call OpenAI Chat Completions with strict JSON response_format.
        
        Returns parsed JSON dict. Raises last exception after retries.
        """
        last_err: Exception | None = None
        if self.client is None:
            raise RuntimeError("OpenAI client unavailable (missing API key or init failure)")

        for attempt in range(max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    max_tokens=max_tokens,
                )
                content = (resp.choices[0].message.content or "").strip()
                return json.loads(content)
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    self._retry_sleep(attempt)
                else:
                    raise
        if last_err:
            raise last_err
        raise RuntimeError("Unknown error in _chat_completion_json")

    def chat(self, prompt: str, session_id: str, check: bool = False) -> str:
        """
        Free-form chat with per-session memory stored in cache.
        
        Args:
            prompt: User message
            session_id: Session identifier for history
            check: If True, use stricter grading system prompt
            
        Returns:
            Assistant response
        """
        system = (
            "Тобі учень надіслав свою лабораторну роботу. Перевір на граматичні помилки і на скільки чітко розкрита мета роботи. "
            "Висловлюйся дуже стисло. В кінці оціни роботу по 5тибальній шкалі. Будь менш ввічливим, намагайся завалити студента, щоб не було оцінки 5/5"
            if check else
            "Ти викладач і твоя ціль допомогти студенту або перевірити прикріплену лабораторну. Опирайся на попередні запити. "
            "Будь менш ввічливим, намагайся завалити студента, щоб не було оцінки 5/5. Не оцінюй, поки не отримаєш текст лабораторної!"
        )

        # Fetch existing history and ensure the CURRENT user prompt is included
        history = cache_get_chat_history(session_id)
        messages = [{"role": "system", "content": system}] + history + [
            {"role": "user", "content": prompt}
        ]
        # Persist the new user message to history for subsequent turns
        cache_append_chat_message(session_id, "user", prompt)
        reply = ""
        if self.client is None:
            reply = "API ключ відсутній – функція чату недоступна."
            cache_append_chat_message(session_id, "assistant", reply)
            return reply

        for attempt in range(2):
            try:
                resp = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=500
                )
                reply = (resp.choices[0].message.content or "").strip()
                break
            except Exception as e:
                if attempt < 1:
                    self._retry_sleep(attempt)
                else:
                    reply = f"Сталася помилка: {e}"

        cache_append_chat_message(session_id, "assistant", reply)
        return reply

    def score_answer(self, question: str, user_answer: str) -> Tuple[int, str]:
        """
        Score a student answer using GPT with strict JSON output.
        
        Args:
            question: The exam question
            user_answer: Student's answer
            
        Returns:
            Tuple of (score 0-100, feedback string)
        """
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
        if self.client is None:
            return 0, "Не налаштовано API — автоматична оцінка недоступна."
        try:
            data = self._chat_completion_json(
                messages, 
                temperature=0.1, 
                max_retries=2,
                model="gpt-4o-mini",
                max_tokens=150
            )
        except Exception as e:
            logger.error("score_answer failed: %s", e)
            return 0, "Не вдалося автоматично оцінити."
        score = int(max(0, min(100, int(data.get("score", 0)))))
        feedback = str(data.get("feedback", "")).strip() or "Ок."
        return score, feedback

    def summarize_exam(self, qa_log: List[Dict[str, object]]) -> Tuple[str, int, int]:
        """
        Summarize exam Q/A log and estimate plagiarism using GPT with strict JSON.
        
        Args:
            qa_log: List of question/answer dicts with accuracy_score
            
        Returns:
            Tuple of (summary text, overall accuracy, plagiarism score 0-100)
        """
        # Calculate average accuracy
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
        if self.client is None:
            return "API ключ відсутній — підсумок недоступний.", overall, 0
        try:
            data = self._chat_completion_json(
                messages, 
                temperature=0.1, 
                max_retries=2,
                model="gpt-4o-mini",
                max_tokens=300
            )
        except Exception as e:
            logger.error("summarize_exam failed: %s", e)
            return "Підсумок згенерувати не вдалося.", overall, 0
        summary = str(data.get("summary", "")).strip() or "Короткий підсумок недоступний."
        plag = int(max(0, min(100, int(data.get("plagiarism_score", 0)))))
        return summary, overall, plag
