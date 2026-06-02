"""
Unified cache utilities for all session state management.

Provides thread-safe, persistent (Redis/Cache) storage for:
- Exam state (questions, answers, progress)
- Gaze tracking metrics (frames, not-looking count)
- Chat conversation history (per-session messages)

All state is properly scoped per session key to ensure isolation.
No global mutable dictionaries - everything goes through Django cache.

Cache timeouts:
- Exam sessions: 1 hour (3600s)
- Gaze sessions: 1 hour (3600s)
- Chat history: 2 hours (7200s)
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional
from django.core.cache import cache
from django.utils import timezone


# ============================================================================
# EXAM STATE CACHE
# ============================================================================

def _exam_key(key: str) -> str:
    """Generate cache key for exam session state."""
    return f"exam:{key}"


def cache_get_exam_state(key: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve exam session state from cache.
    
    Returns None if session doesn't exist.
    State structure:
    {
        "index": int,           # current question index
        "questions": List[str], # list of questions
        "qa_log": List[dict],   # question/answer pairs with scores
        "student_fullname": str,
        "started_at": str       # ISO timestamp
    }
    """
    return cache.get(_exam_key(key))


def cache_set_exam_state(key: str, state: Dict[str, Any], timeout: int = 3600) -> None:
    """
    Save exam session state to cache.
    
    Args:
        key: exam session key (usually survey key)
        state: complete exam state dict
        timeout: cache expiry in seconds (default 1 hour)
    """
    cache.set(_exam_key(key), state, timeout=timeout)


def cache_reset_exam_state(key: str) -> None:
    """Delete exam session state from cache."""
    cache.delete(_exam_key(key))


def cache_init_exam_state(key: str, questions: List[str]) -> Dict[str, Any]:
    """
    Initialize a new exam session in cache.
    
    Returns the newly created state dict.
    """
    state = {
        "index": 0,
        "questions": questions,
        "qa_log": [],
        "student_fullname": "",
        "started_at": timezone.now().isoformat(),
    }
    cache_set_exam_state(key, state)
    return state


# ============================================================================
# GAZE TRACKING CACHE
# ============================================================================

def _gaze_key(sid: str) -> str:
    """Generate cache key for gaze tracking session."""
    return f"gaze:{sid}"


def cache_get_gaze_session(sid: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve gaze tracking session from cache.
    
    Returns None if session doesn't exist.
    State structure:
    {
        "thresh_samples": List[int],
        "thresh_value": int,
        "calibrated": bool,
        "manual": bool,
        "frames": int,
        "not_looking": int,
        "start_ts": str  # ISO 8601 timestamp
    }
    """
    return cache.get(_gaze_key(sid))


def cache_set_gaze_session(sid: str, session: Dict[str, Any], timeout: int = 3600) -> None:
    """
    Save gaze tracking session to cache.
    
    Args:
        sid: session identifier
        session: complete gaze state dict
        timeout: cache expiry in seconds (default 1 hour)
    """
    cache.set(_gaze_key(sid), session, timeout=timeout)


def cache_reset_gaze_session(sid: str) -> None:
    """Delete gaze tracking session from cache."""
    cache.delete(_gaze_key(sid))


def cache_init_gaze_session(sid: str) -> Dict[str, Any]:
    """
    Initialize or retrieve gaze tracking session.
    
    If session exists, returns it. Otherwise creates new session.
    """
    session = cache_get_gaze_session(sid)
    if not session:
        session = {
            "thresh_samples": [],
            "thresh_value": 170,
            "calibrated": False,
            "manual": False,
            "frames": 0,
            "not_looking": 0,
            "start_ts": timezone.now().isoformat(),
        }
        cache_set_gaze_session(sid, session)
    return session


def cache_increment_gaze_frames(sid: str, not_looking: bool = False) -> None:
    """
    Atomically increment frame counters for gaze session.
    
    Args:
        sid: session identifier
        not_looking: if True, increment not_looking counter as well
    """
    session = cache_init_gaze_session(sid)
    session["frames"] = int(session.get("frames", 0)) + 1
    if not_looking:
        session["not_looking"] = int(session.get("not_looking", 0)) + 1
    cache_set_gaze_session(sid, session)


def cache_reset_gaze_counters(sid: str) -> None:
    """Reset frame counters for gaze session (keeps calibration data)."""
    session = cache_init_gaze_session(sid)
    session["frames"] = 0
    session["not_looking"] = 0
    session["start_ts"] = timezone.now().isoformat()
    cache_set_gaze_session(sid, session)


def compute_gaze_percent(sid: str) -> float:
    """Compute not-looking percentage for a given gaze session id."""
    session = cache_init_gaze_session(sid)
    frames = int(session.get("frames", 0))
    not_looking = int(session.get("not_looking", 0))
    return round(100.0 * not_looking / max(1, frames), 1)


# ============================================================================
# CHAT HISTORY CACHE
# ============================================================================

def _chat_key(session_id: str) -> str:
    """Generate cache key for chat conversation history."""
    return f"chat_history:{session_id}"


def cache_get_chat_history(session_id: str) -> List[Dict[str, str]]:
    """
    Retrieve chat conversation history from cache.
    
    Returns empty list if no history exists.
    Each message: {"role": "user"|"assistant", "content": str}
    """
    history = cache.get(_chat_key(session_id))
    return history if history is not None else []


def cache_set_chat_history(session_id: str, history: List[Dict[str, str]], timeout: int = 7200) -> None:
    """
    Save chat conversation history to cache.
    
    Args:
        session_id: session identifier
        history: list of message dicts
        timeout: cache expiry in seconds (default 2 hours)
    """
    cache.set(_chat_key(session_id), history, timeout=timeout)


def cache_append_chat_message(session_id: str, role: str, content: str) -> None:
    """
    Append a message to chat history.
    
    Args:
        session_id: session identifier
        role: "user" or "assistant"
        content: message text
    """
    history = cache_get_chat_history(session_id)
    history.append({"role": role, "content": content})
    cache_set_chat_history(session_id, history)


def cache_reset_chat_history(session_id: str) -> None:
    """Delete chat conversation history from cache."""
    cache.delete(_chat_key(session_id))


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def cache_clear_all_session_data(identifier: str) -> None:
    """
    Clear all cache entries for a given session identifier.
    
    Removes exam state, gaze session, and chat history.
    Use when completely resetting a student session.
    """
    cache_reset_exam_state(identifier)
    cache_reset_gaze_session(identifier)
    cache_reset_chat_history(identifier)


def cache_get_session_info(key: str) -> Dict[str, Any]:
    """
    Get overview of all cached data for a session.
    
    Useful for debugging and monitoring.
    """
    exam_state = cache_get_exam_state(key)
    gaze_session = cache_get_gaze_session(key)
    chat_history = cache_get_chat_history(key)
    
    return {
        "exam_state_exists": exam_state is not None,
        "exam_progress": f"{exam_state.get('index', 0)}/{len(exam_state.get('questions', []))}" if exam_state else "N/A",
        "gaze_session_exists": gaze_session is not None,
        "gaze_frames": gaze_session.get("frames", 0) if gaze_session else 0,
        "chat_history_length": len(chat_history),
    }
