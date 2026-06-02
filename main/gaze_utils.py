"""
Gaze helpers: DEPRECATED - use cache_utils instead.

This module is kept for backward compatibility but now delegates
to the unified cache_utils module. All new code should import from cache_utils.

Deprecated functions (use cache_utils equivalents):
- get_or_init_gaze_session() -> cache_init_gaze_session()
- save_gaze_session() -> cache_set_gaze_session()
- reset_gaze_for_key() -> cache_reset_gaze_counters()
"""
from __future__ import annotations

from typing import Dict, Any
from .cache_utils import (
    cache_get_gaze_session,
    cache_set_gaze_session,
    cache_init_gaze_session,
    cache_reset_gaze_counters,
)


def get_or_init_gaze_session(sid: str) -> Dict[str, Any]:
    """DEPRECATED: Use cache_init_gaze_session from cache_utils."""
    return cache_init_gaze_session(sid)


def save_gaze_session(sid: str, sess: Dict[str, Any]) -> None:
    """DEPRECATED: Use cache_set_gaze_session from cache_utils."""
    cache_set_gaze_session(sid, sess)


def reset_gaze_for_key(sid: str) -> None:
    """DEPRECATED: Use cache_reset_gaze_counters from cache_utils."""
    cache_reset_gaze_counters(sid)


def compute_not_looking_pct(sess: Dict[str, Any]) -> float:
    frames = int(sess.get("frames", 0))
    not_looking = int(sess.get("not_looking", 0))
    return round(100.0 * not_looking / max(1, frames), 1)


def get_gaze_stats_dict(sid: str) -> Dict[str, Any]:
    sess = cache_init_gaze_session(sid)
    return {
        "sid": sid,
        "frames": int(sess.get("frames", 0)),
        "not_looking": int(sess.get("not_looking", 0)),
        "notLookingPct": compute_not_looking_pct(sess),
        "start_ts": sess.get("start_ts"),
    }
