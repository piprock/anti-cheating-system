"""
Persistence helpers: create InterviewSession and Answer records from payloads.

Uses service layer for gaze metrics and django.utils.timezone for timestamps.
"""
from __future__ import annotations

from typing import Dict, Any
from datetime import datetime
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Student, Survey, InterviewSession, Answer
from .services import GazeService, ExamService
from .constants import MAX_SESSION_DURATION_SEC
import logging

# Initialize services
logger = logging.getLogger(__name__)
gaze_service = GazeService()
exam_service = ExamService()


def persist_session_from_payload(key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Persist exam session from payload to database.
    
    Args:
        key: Survey key
        payload: Session data including student info, answers, and summary
        
    Returns:
        Dict with session_id, duration_sec, gaze_not_looking_pct, grade_5
    """
    survey = get_object_or_404(Survey, key=key, active=True)

    student_info = payload.get("student") or {}
    first = (student_info.get("first_name") or "").strip() or "Студент"
    last = (student_info.get("last_name") or "").strip() or "БезПрізвища"
    student, _ = Student.objects.get_or_create(first_name=first, last_name=last)

    # Get gaze stats from service
    s = gaze_service.init_session(key)
    gaze_pct = gaze_service.compute_not_looking_percent(key)

    # Flexible parsing for start_ts (supports legacy epoch float/int and new ISO string)
    raw_start = s.get("start_ts")
    started_at: datetime
    try:
        if isinstance(raw_start, (int, float)):
            started_at = datetime.fromtimestamp(float(raw_start), tz=timezone.get_current_timezone())
        elif isinstance(raw_start, str):
            # Attempt ISO parse; if naive, attach current timezone
            parsed = datetime.fromisoformat(raw_start)
            if parsed.tzinfo is None:
                started_at = timezone.make_aware(parsed)
            else:
                started_at = parsed
        else:
            started_at = timezone.now()
    except Exception:
        logger.warning("Failed to parse start_ts=%r; falling back to now()", raw_start)
        started_at = timezone.now()
    ended_at = timezone.now()
    duration = int((ended_at - started_at).total_seconds())
    if duration > MAX_SESSION_DURATION_SEC:
        duration = MAX_SESSION_DURATION_SEC

    summary = payload.get("summary") or {}
    acc = int(summary.get("overall_accuracy", 0))
    plag = int(summary.get("plagiarism_score", 0))
    diag = str(summary.get("dialogue_result", ""))

    # Compute grade using service
    grade = exam_service.compute_grade(acc, plag, gaze_pct)

    session = InterviewSession.objects.create(
        survey=survey,
        student=student,
        started_at=started_at,
        ended_at=ended_at,
        duration_sec=duration,
        overall_accuracy=acc,
        plagiarism_score=plag,
        dialogue_result=diag,
        gaze_not_looking_pct=gaze_pct,
        grade_5=grade,
        raw_payload=payload,
    )

    for i, a in enumerate(payload.get("answers") or []):
        Answer.objects.create(
            session=session,
            question=str(a.get("question") or ""),
            answer=str(a.get("answer") or ""),
            accuracy_score=int(a.get("accuracy_score") or 0),
            feedback=str(a.get("feedback") or ""),
            question_order=i,
        )

    return {
        "session_id": session.id,
        "duration_sec": duration,
        "gaze_not_looking_pct": gaze_pct,
        "grade_5": grade,
    }
