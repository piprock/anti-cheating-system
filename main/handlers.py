"""
HTTP handlers that are not part of the exam controller flow.

Contains light endpoints for:
- main/about/contact pages
- ad-hoc teacher chat (record_and_respond) and file analysis (anylize_file)
- exam_page rendering and gaze_stats reporting
- submit_interview for bulk payload ingestion
"""
from __future__ import annotations

from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse

from .services import AudioService, GPTService, FileExtractor, GazeService
from .forms import FileAnalyzeForm, SubmitInterviewForm
from .constants import MIN_VOICE_ANSWER_CHARS
import logging
from .models import Survey
from .persist import persist_session_from_payload

# Initialize services & logger
audio_service = AudioService()
gpt_service = GPTService()
file_extractor = FileExtractor()
gaze_service = GazeService()
logger = logging.getLogger(__name__)


def _get_session_id(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def main(request):
    return render(request, 'main/index.html')


def about(request):
    return render(request, 'main/about.html')


def contact(request):
    return render(request, 'main/contact.html')


@csrf_exempt
def record_and_respond(request):
    """Record audio, transcribe, chat with GPT, and speak response."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        audio_path = audio_service.record()
        text = audio_service.recognize(audio_path)
        if not text or len(text.strip()) < MIN_VOICE_ANSWER_CHARS:
            return JsonResponse({"status_code": 200, "answer": "", "question": text, "feedback": "Занадто короткий запит."}, status=200)
        reply = gpt_service.chat(text, session_id=_get_session_id(request))
        audio_service.play_tts(reply)
        logger.info("record_and_respond chat success sid=%s", _get_session_id(request))
        return JsonResponse({"status_code": 200, "answer": reply, "question": text}, status=200)
    except Exception as e:
        logger.exception("record_and_respond failed")
        return JsonResponse({"status_code": 500, "error": str(e)}, status=200)


@csrf_exempt
def anylize_file(request):
    """Extract text from uploaded file, analyze with GPT, and speak response."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    
    try:
        form = FileAnalyzeForm(files=request.FILES)
        if not form.is_valid():
            return JsonResponse({"error": form.errors.get("file", ["invalid file"])[0]}, status=400)
        file = form.cleaned_data["file"]
        text = file_extractor.extract(file, file.name)
        reply = gpt_service.chat(text, session_id=_get_session_id(request), check=True)
        audio_service.play_tts(reply)
        logger.info("File analyzed sid=%s name=%s", _get_session_id(request), file.name)
        return JsonResponse({"status_code": 200, "answer": reply, "question": "*прикріплений файл*"}, status=200)
    except Exception as e:
        logger.exception("anylize_file failed")
        return JsonResponse({"status_code": 500, "error": str(e)}, status=200)


def exam_page(request, key: str):
    survey = get_object_or_404(Survey, key=key, active=True)
    return render(request, "main/exam.html", {"survey": survey, "sid": key})


def gaze_stats(request, sid: str):
    """Return gaze tracking statistics for session."""
    return JsonResponse(gaze_service.get_stats(sid))




@csrf_exempt
def submit_interview(request, key: str):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    get_object_or_404(Survey, key=key, active=True)

    import json
    try:
        raw = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"error": f"invalid json: {e}"}, status=400)
    form = SubmitInterviewForm(data={
        "student_fullname": (raw.get("student", {}) or {}).get("fullname", ""),
        "overall_accuracy": raw.get("overall_accuracy"),
        "plagiarism_score": raw.get("plagiarism_score"),
        "gaze_not_looking_pct": raw.get("gaze_not_looking_pct"),
    })
    if not form.is_valid():
        return JsonResponse({"error": form.errors}, status=400)
    payload = raw  # keep original structure for persistence service

    # Delegate persistence and metrics to common helper
    saved = persist_session_from_payload(key, payload)
    student_info = payload.get("student") or {}
    first = (student_info.get("first_name") or "").strip()
    last = (student_info.get("last_name") or "").strip()

    resp = {
        "ok": True,
        "session_id": saved.get("session_id"),
        "student": f"{last} {first}".strip(),
        "duration_sec": saved.get("duration_sec"),
        "gaze_not_looking_pct": saved.get("gaze_not_looking_pct"),
        "grade_5": saved.get("grade_5"),
    }
    logger.info("Interview persisted key=%s session_id=%s", key, resp["session_id"])
    return JsonResponse(resp, status=200)
