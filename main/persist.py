"""
Persistence helpers: create InterviewSession and Answer records from payloads.

Uses service layer for gaze metrics and django.utils.timezone for timestamps.
"""
from __future__ import annotations

from typing import Dict, Any
from datetime import datetime
from django.shortcuts import get_object_or_404
from django.utils import timezone

from django.contrib.auth.models import User
from .models import Student, Survey, InterviewSession, Answer, ActivityLog
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

    user = None
    user_id = payload.get("user_id")
    if user_id:
        user = User.objects.filter(id=user_id).first()

    student_info = payload.get("student") or {}
    first = (student_info.get("first_name") or "").strip() or "Студент"
    last = (student_info.get("last_name") or "").strip() or "БезПрізвища"
    middle = (student_info.get("middle_name") or "").strip()

    student_kwargs = {"first_name": first, "last_name": last}
    if user:
        student_kwargs["user"] = user

    student, _ = Student.objects.get_or_create(**student_kwargs)
    if middle and not student.middle_name:
        student.middle_name = middle
    if user and hasattr(user, "profile") and user.profile.group and not student.group:
        student.group = user.profile.group
    student.save()

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
        user=user,
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
        status="done",
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

    # Record activity log
    try:
        ActivityLog.objects.create(
            user=user,
            action=ActivityLog.ACTION_EXAM_SUBMIT,
            details=f"Завершено тест '{survey.title or survey.key}': оцінка {grade}/5, точність {acc}%, відхилення погляду {gaze_pct:.1f}%.",
            session=session,
            metadata={
                "survey_key": survey.key,
                "grade_5": grade,
                "accuracy": acc,
                "plagiarism": plag,
                "gaze_not_looking_pct": gaze_pct,
                "duration_sec": duration,
            }
        )
    except Exception as exc:
        logger.warning("Failed to record activity log for exam session: %s", exc)

    return {
        "session_id": session.id,
        "duration_sec": duration,
        "gaze_not_looking_pct": gaze_pct,
        "grade_5": grade,
    }
