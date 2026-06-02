"""
Exam controller views: start/answer/voice endpoints with service layer.

Responsibilities:
- Manage per-exam state via ExamService
- Score answers via GPTService
- Summarize and persist session via persist module
- Handle audio via AudioService
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Any

from django.http import JsonResponse, HttpRequest
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from .models import Survey
from .services import AudioService, GPTService, ExamService
from .persist import persist_session_from_payload
from .constants import MIN_VOICE_ANSWER_CHARS

logger = logging.getLogger(__name__)

# Initialize services
audio_service = AudioService()
gpt_service = GPTService()
exam_service = ExamService()

# ----- Shared helpers for DRY exam flow -----

def _save_answers(state: Dict[str, Any], question: str, user_answer: str) -> tuple[int, str]:
    """Save answer and return score/feedback. First answer (ПІБ) gets special handling."""
    idx = int(state.get("index", 0))
    if idx == 0:
        state["student_fullname"] = user_answer
        score, feedback = 100, "ПІБ збережено."
    else:
        score, feedback = gpt_service.score_answer(question, user_answer)
    
    exam_service.record_answer(state, user_answer, score, feedback)
    return score, feedback


def _finalize_and_persist(key: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """Finalize exam: summarize, build payload, persist to database."""
    graded = exam_service.get_graded_answers(state)
    summary_text, overall_acc, plag_score = gpt_service.summarize_exam(graded)
    payload = exam_service.build_session_payload(state, summary_text, overall_acc, plag_score)
    persisted = persist_session_from_payload(key, payload)
    
    last_entry = state.get("qa_log", [{}])[-1]
    first, last, _ = exam_service._parse_pib(state.get("student_fullname", ""))
    
    return {
        "done": True,
        "feedback": last_entry.get("feedback", ""),
        "accuracy_score": last_entry.get("accuracy_score", 0),
        "answer": last_entry.get("answer", ""),
        "summary": payload["summary"],
        "student": f"{last} {first}",
        "saved": persisted,
    }


def _handle_exam_answer_common(key: str, user_answer: str, speak_next: bool = False) -> Dict[str, Any]:
    """Common flow for text and voice answers."""
    state = exam_service.get_exam_state(key)
    if not state:
        return {"error": "exam not started"}
    
    current_q = exam_service.get_current_question(state)
    if current_q is None:
        return {"error": "no more questions"}
    
    score, feedback = _save_answers(state, current_q, (user_answer or "").strip())
    exam_service.save_exam_state(key, state)

    # Check if there's a next question
    next_q = exam_service.get_current_question(state)
    if next_q is not None:
        if speak_next:
            try:
                audio_service.play_tts(next_q)
            except Exception:
                pass
        
        idx, total = exam_service.get_progress(state)
        return {
            "done": False,
            "idx": idx,
            "total": total,
            "feedback": feedback,
            "accuracy_score": score,
            "answer": state["qa_log"][-1]["answer"],
            "next_question": next_q,
        }
    
    # Exam complete - finalize
    return _finalize_and_persist(key, state)
@csrf_exempt
def exam_start(request: HttpRequest, key: str) -> JsonResponse:
    """Initialize exam session and speak first question."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    
    survey = get_object_or_404(Survey, key=key, active=True)
    cq = survey.control_questions or []
    questions = [q if isinstance(q, str) else str(q) for q in cq]
    
    state = exam_service.start_exam(key, questions)
    first_question = questions[0] if questions else ""
    
    if first_question:
        try:
            audio_service.play_tts(first_question)
        except Exception:
            pass
    
    return JsonResponse({
        "ok": True,
        "question": first_question,
        "idx": 0,
        "total": len(questions),
        "answer_time_sec": getattr(survey, "answer_time_sec", 10) or 10,
    })
@csrf_exempt
def exam_answer(request: HttpRequest, key: str) -> JsonResponse:
    """Handle text answer submission."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"error": f"invalid json: {e}"}, status=400)
    
    user_answer = (data.get("answer") or "").strip()
    result = _handle_exam_answer_common(key, user_answer, speak_next=False)
    
    if "error" in result:
        return JsonResponse(result, status=400)
    return JsonResponse(result)
@csrf_exempt
def exam_voice_answer(request: HttpRequest, key: str) -> JsonResponse:
    """Handle voice answer via microphone recording."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        audio_path = audio_service.record(duration=10)
        user_answer = audio_service.recognize(audio_path)
    except Exception as exc:
        logger.error("Voice capture failed: %s", exc)
        return JsonResponse({"error": "voice capture failed"}, status=500)
    
    ua = (user_answer or "").strip()
    if len(ua) < MIN_VOICE_ANSWER_CHARS:
        logger.info("Voice answer too short; treating as empty for key=%s", key)
    result = _handle_exam_answer_common(key, ua, speak_next=True)
    
    if "error" in result:
        return JsonResponse(result, status=400)
    return JsonResponse(result)
