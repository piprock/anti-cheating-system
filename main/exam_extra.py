import csv
import os
import tempfile
import logging

from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from .models import InterviewSession
from .services import AudioService, GPTService, ExamService
from .forms import VoiceAnswerUploadForm
from .constants import MIN_VOICE_ANSWER_CHARS
from .persist import persist_session_from_payload

# Initialize services & logger
audio_service = AudioService()
gpt_service = GPTService()
exam_service = ExamService()
logger = logging.getLogger(__name__)


def _parse_pib(fullname: str) -> tuple[str, str, str]:
    """Parse Ukrainian full name (ПІБ) into components."""
    parts = fullname.strip().split()
    last = parts[0] if len(parts) >= 1 else ""
    first = parts[1] if len(parts) >= 2 else ""
    middle = " ".join(parts[2:]) if len(parts) >= 3 else ""
    return first, last, middle


@csrf_exempt
def exam_speak_current_question(request, key: str):
    """
    Speak current exam question (for voice mode).
    Used after index is already set in cache.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    
    state = exam_service.get_exam_state(key)
    if not state:
        return JsonResponse({"error": "exam not started"}, status=400)

    current_q = exam_service.get_current_question(state)
    if current_q is None:
        return JsonResponse({"error": "no more questions"}, status=400)

    idx, total = exam_service.get_progress(state)
    
    # ПІБ (idx == 0) not spoken - text input only
    if idx > 0:
        try:
            audio_service.play_tts(current_q)
        except Exception as e:
            logger.warning("TTS playback failed for key=%s idx=%s: %s", key, idx, e)
    
    return JsonResponse({
        "ok": True,
        "idx": idx,
        "total": total,
        "question": current_q,
    })


@csrf_exempt
def exam_voice_answer_upload(request, key: str):
    """
    Voice answer from client (audio/webm in 'audio' field).
    Uses Whisper for recognition, GPT-4 for scoring, same cache structures.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    state = exam_service.get_exam_state(key)
    if not state:
        return JsonResponse({"error": "exam not started"}, status=400)

    form = VoiceAnswerUploadForm(files=request.FILES)
    if not form.is_valid():
        return JsonResponse({"error": form.errors.get("audio", ["invalid audio"])[0]}, status=400)
    audio_file = form.cleaned_data["audio"]

    tmp_path = None
    try:
        # Save uploaded audio to temporary file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        for chunk in audio_file.chunks():
            tmp.write(chunk)
        tmp.close()
        tmp_path = tmp.name
        
        # Recognize speech using Whisper
        user_answer = audio_service.recognize(tmp_path, language="uk", model_name="small")
        logger.info("Voice answer recognized for key=%s: %s", key, user_answer)
    except Exception as e: 
        logger.exception("Voice answer upload failed for key=%s", key)
        return JsonResponse({"error": f"voice decode failed: {str(e)}"}, status=500)
    finally:
        # Clean up temporary file
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    user_answer = (user_answer or "").strip()

    current_q = exam_service.get_current_question(state)
    if current_q is None:
        return JsonResponse({"error": "no more questions"}, status=400)

    idx, total = exam_service.get_progress(state)

    # idx == 0 is ПІБ, should be text input, so we shouldn't reach here
    # If answer too short or empty - assign 0 score without calling GPT
    if not user_answer or len(user_answer.strip()) < MIN_VOICE_ANSWER_CHARS:
        score = 0
        feedback = "Відповідь занадто коротка або відсутня."
    else:
        score, feedback = gpt_service.score_answer(current_q, user_answer)
    
    exam_service.record_answer(state, user_answer, score, feedback)
    exam_service.save_exam_state(key, state)
    last_entry = state["qa_log"][-1]

    # If more questions remain - return intermediate result and next question text
    next_q = exam_service.get_current_question(state)
    if next_q is not None:
        idx, total = exam_service.get_progress(state)
        return JsonResponse({
            "done": False,
            "idx": idx,
            "total": total,
            "feedback": last_entry["feedback"],
            "accuracy_score": last_entry["accuracy_score"],
            "answer": last_entry["answer"],
            "next_question": next_q,
        })

    # Exam complete - calculate summary and persist session
    graded = exam_service.get_graded_answers(state)
    summary_text, overall_acc, plag_score = gpt_service.summarize_exam(graded)

    first, last, middle = _parse_pib(state["student_fullname"])
    payload = exam_service.build_session_payload(state, summary_text, overall_acc, plag_score)
    persisted = persist_session_from_payload(key, payload)

    return JsonResponse({
        "done": True,
        "feedback": last_entry["feedback"],
        "accuracy_score": last_entry["accuracy_score"],
        "answer": last_entry["answer"],
        "summary": payload["summary"],
        "student": f"{last} {first}",
        "saved": persisted,
    })


def exam_export_session(request, session_id: int):
    """
    Вивантаження результатів конкретного екзамену у Excel-дружній CSV.
    """
    session = get_object_or_404(InterviewSession, pk=session_id)
    # Додаємо UTF‑8 BOM, щоб Excel коректно розпізнав кодування й кирилицю
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"exam_{session_id}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    # UTF‑8 BOM
    response.write("\ufeff")

    writer = csv.writer(response, delimiter=";")

    writer.writerow(["Сесія", session.id])
    writer.writerow(["Опитувальник", session.survey.title or session.survey.key])
    writer.writerow(["Студент", str(session.student) if session.student else ""])
    writer.writerow(["Початок", session.started_at])
    writer.writerow(["Кінець", session.ended_at])
    writer.writerow(["Тривалість, с", session.duration_sec])
    writer.writerow(["Середня точність, %", session.overall_accuracy])
    writer.writerow(["Плагіат, %", session.plagiarism_score])
    writer.writerow(["Погляд не на екран, %", session.gaze_not_looking_pct])
    writer.writerow(["Оцінка (1-5)", session.grade_5])
    writer.writerow([])

    writer.writerow(["#", "Питання", "Відповідь", "Точність", "Коментар"])
    for i, ans in enumerate(session.answers.all().order_by("created_at"), start=1):
        writer.writerow([i, ans.question, ans.answer, ans.accuracy_score, ans.feedback])

    return response
