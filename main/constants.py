"""Centralized constants for the Avatar exam system.

Avoids magic numbers scattered across code. Import from this module
whenever fixed threshold or configuration values are needed.
"""

from __future__ import annotations

# Audio / Whisper
AUDIO_SAMPLE_RATE: int = 16000
DEFAULT_RECORD_DURATION_SEC: int = 5

# Gaze tracking
GAZE_DEFAULT_THRESH: int = 170
GAZE_CENTER_SCALE_FACTOR: float = 1.3
GAZE_MAX_SAMPLES: int = 60
GAZE_CALIBRATION_MIN_SAMPLES: int = 20
GAZE_PENALTY_THRESHOLD_PCT: float = 35.0

# Exam / Grading
PLAGIARISM_PENALTY_THRESHOLD: int = 20
GRADE_BANDS: tuple[tuple[int, int], ...] = (
    (90, 5),
    (75, 4),
    (60, 3),
    (40, 2),
    (0, 1),  # fallback
)

# Cache timeouts (seconds)
EXAM_STATE_TIMEOUT: int = 3600
GAZE_STATE_TIMEOUT: int = 3600
CHAT_HISTORY_TIMEOUT: int = 7200

# Voice answer minimal length to attempt scoring
MIN_VOICE_ANSWER_CHARS: int = 5

# Persistence limits
MAX_SESSION_DURATION_SEC: int = 5 * 60

__all__ = [
    "AUDIO_SAMPLE_RATE",
    "DEFAULT_RECORD_DURATION_SEC",
    "GAZE_DEFAULT_THRESH",
    "GAZE_CENTER_SCALE_FACTOR",
    "GAZE_MAX_SAMPLES",
    "GAZE_CALIBRATION_MIN_SAMPLES",
    "GAZE_PENALTY_THRESHOLD_PCT",
    "PLAGIARISM_PENALTY_THRESHOLD",
    "GRADE_BANDS",
    "EXAM_STATE_TIMEOUT",
    "GAZE_STATE_TIMEOUT",
    "CHAT_HISTORY_TIMEOUT",
    "MIN_VOICE_ANSWER_CHARS",
    "MAX_SESSION_DURATION_SEC",
]