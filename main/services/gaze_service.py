"""
GazeService: Manages gaze tracking sessions and metrics.

Provides:
- Session initialization and state management
- Frame increment operations
- Not-looking percentage calculation
- Calibration management
"""
from __future__ import annotations

from typing import Dict, Any, Optional
import logging
from django.utils import timezone
from datetime import datetime

from ..constants import (
    GAZE_DEFAULT_THRESH,
    GAZE_PENALTY_THRESHOLD_PCT,
    GAZE_MAX_SAMPLES,
    GAZE_CALIBRATION_MIN_SAMPLES,
)

from ..cache_utils import (
    cache_get_gaze_session,
    cache_set_gaze_session,
    cache_init_gaze_session,
    cache_reset_gaze_session,
    cache_increment_gaze_frames,
    cache_reset_gaze_counters,
    compute_gaze_percent,
)


logger = logging.getLogger(__name__)


class GazeService:
    """Service for gaze tracking operations."""

    def __init__(self):
        pass

    def init_session(self, session_id: str) -> Dict[str, Any]:
        """
        Initialize or retrieve gaze tracking session.
        
        If session exists, returns it. Otherwise creates new session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Gaze session state dict
        """
        return cache_init_gaze_session(session_id)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve gaze tracking session.
        
        Returns None if session doesn't exist.
        """
        return cache_get_gaze_session(session_id)

    def save_session(self, session_id: str, session: Dict[str, Any]) -> None:
        """Save gaze session state to cache."""
        cache_set_gaze_session(session_id, session)

    def reset_session(self, session_id: str) -> None:
        """Delete gaze tracking session from cache."""
        cache_reset_gaze_session(session_id)

    def increment_frame(self, session_id: str, not_looking: bool = False) -> None:
        """
        Atomically increment frame counters.
        
        Args:
            session_id: Session identifier
            not_looking: If True, increment not_looking counter as well
        """
        cache_increment_gaze_frames(session_id, not_looking=not_looking)

    def reset_counters(self, session_id: str) -> None:
        """
        Reset frame counters (keeps calibration data).
        
        Args:
            session_id: Session identifier
        """
        cache_reset_gaze_counters(session_id)

    def compute_not_looking_percent(self, session_id: str) -> float:
        """
        Compute percentage of frames where student was not looking at screen.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Percentage (0.0-100.0) rounded to 1 decimal place
        """
        return compute_gaze_percent(session_id)

    def get_stats(self, session_id: str) -> Dict[str, Any]:
        """
        Get comprehensive gaze statistics.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict with frames, not_looking, percentage, calibration status
        """
        session = self.init_session(session_id)
        frames = int(session.get("frames", 0))
        not_looking = int(session.get("not_looking", 0))
        pct = self.compute_not_looking_percent(session_id)
        
        # Parse timezone-aware start timestamp
        start_ts_str = session.get("start_ts")
        elapsed_sec = 0
        if start_ts_str:
            try:
                start_dt = datetime.fromisoformat(start_ts_str)
                elapsed_sec = int((timezone.now() - start_dt).total_seconds())
            except (ValueError, TypeError):
                logger.warning("Invalid start_ts format for session %s", session_id)
        
        return {
            "frames": frames,
            "not_looking": not_looking,
            "not_looking_pct": pct,
            "calibrated": session.get("calibrated", False),
            "thresh_value": session.get("thresh_value", 170),
            "elapsed_sec": elapsed_sec,
        }

    def update_calibration(
        self,
        session_id: str,
        thresh_value: Optional[int] = None,
        calibrated: Optional[bool] = None,
        manual: Optional[bool] = None
    ) -> None:
        """
        Update calibration parameters.
        
        Args:
            session_id: Session identifier
            thresh_value: New threshold value
            calibrated: Calibration status
            manual: Manual calibration flag
        """
        session = self.init_session(session_id)
        if thresh_value is not None:
            session["thresh_value"] = thresh_value
        if calibrated is not None:
            session["calibrated"] = calibrated
        if manual is not None:
            session["manual"] = manual
        self.save_session(session_id, session)

    def add_threshold_sample(self, session_id: str, sample: int) -> None:
        """
        Add a threshold calibration sample.
        
        Args:
            session_id: Session identifier
            sample: Threshold sample value
        """
        session = self.init_session(session_id)
        samples = session.get("thresh_samples", [])
        samples.append(sample)
        # enforce max length
        if len(samples) > GAZE_MAX_SAMPLES:
            samples = samples[-GAZE_MAX_SAMPLES:]
        session["thresh_samples"] = samples
        # try calibration if enough samples collected
        if len(samples) >= GAZE_CALIBRATION_MIN_SAMPLES and not session.get("calibrated", False):
            session["thresh_value"] = int(sum(samples) / len(samples))
            session["calibrated"] = True
        self.save_session(session_id, session)

    def get_threshold_samples(self, session_id: str) -> list:
        """Get all threshold calibration samples."""
        session = self.init_session(session_id)
        return session.get("thresh_samples", [])
