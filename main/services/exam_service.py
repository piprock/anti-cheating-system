"""
ExamService: Manages exam session state, question flow, and grading.

Encapsulates:
- Exam session initialization and state management
- Question progression logic
- Answer recording and scoring
- Grade computation based on accuracy, plagiarism, and gaze metrics
"""
from __future__ import annotations

from typing import Dict, Any, List, Tuple, Optional
from django.utils import timezone
import logging

from ..constants import (
    PLAGIARISM_PENALTY_THRESHOLD,
    GAZE_PENALTY_THRESHOLD_PCT,
    GRADE_BANDS,
)

from ..cache_utils import (
    cache_get_exam_state,
    cache_set_exam_state,
    cache_init_exam_state,
    cache_reset_exam_state,
    cache_reset_gaze_counters,
)


logger = logging.getLogger(__name__)


class ExamService:
    """Service for exam session management and grading logic."""

    def __init__(self):
        pass

    def start_exam(self, key: str, questions: List[str]) -> Dict[str, Any]:
        """
        Initialize a new exam session.
        
        Args:
            key: Exam session key (usually survey key)
            questions: List of question strings
            
        Returns:
            Initialized exam state dict
        """
        state = cache_init_exam_state(key, questions)
        cache_reset_gaze_counters(key)  # Reset gaze tracking
        return state

    def get_exam_state(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve current exam state.
        
        Returns None if exam not started.
        """
        return cache_get_exam_state(key)

    def save_exam_state(self, key: str, state: Dict[str, Any]) -> None:
        """Save exam state to cache."""
        cache_set_exam_state(key, state)

    def reset_exam(self, key: str) -> None:
        """Delete exam session state."""
        cache_reset_exam_state(key)

    def get_current_question(self, state: Dict[str, Any]) -> Optional[str]:
        """
        Get the current question from exam state.
        
        Returns None if exam completed.
        """
        idx = state.get("index", 0)
        questions = state.get("questions", [])
        if idx >= len(questions):
            return None
        return questions[idx]

    def record_answer(
        self,
        state: Dict[str, Any],
        answer: str,
        score: int,
        feedback: str
    ) -> Dict[str, Any]:
        """
        Record an answer in the exam state.
        
        Args:
            state: Current exam state
            answer: Student's answer text
            score: Accuracy score (0-100)
            feedback: Feedback text
            
        Returns:
            Updated exam state
        """
        idx = state["index"]
        questions = state["questions"]
        if idx < len(questions):
            q = questions[idx]
            state["qa_log"].append({
                "question": q,
                "answer": answer,
                "accuracy_score": score,
                "feedback": feedback,
            })
            state["index"] += 1
        return state

    def advance_to_next_question(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Move to next question without recording answer.
        
        Returns updated state.
        """
        state["index"] += 1
        return state

    def is_exam_complete(self, state: Dict[str, Any]) -> bool:
        """Check if all questions have been answered."""
        return state["index"] >= len(state.get("questions", []))

    def get_progress(self, state: Dict[str, Any]) -> Tuple[int, int]:
        """
        Get exam progress.
        
        Returns:
            Tuple of (current_index, total_questions)
        """
        return state["index"], len(state.get("questions", []))

    def build_session_payload(
        self,
        state: Dict[str, Any],
        summary_text: str,
        overall_accuracy: int,
        plagiarism_score: int
    ) -> Dict[str, Any]:
        """
        Build complete session payload for persistence.
        
        Args:
            state: Exam state
            summary_text: AI-generated summary
            overall_accuracy: Overall accuracy percentage
            plagiarism_score: Plagiarism score (0-100)
            
        Returns:
            Payload dict ready for persistence
        """
        first, last, middle = self._parse_pib(state["student_fullname"])
        # Exclude first answer (ПІБ) from graded answers
        graded_answers = [
            {
                "question": row["question"],
                "answer": row["answer"],
                "accuracy_score": row["accuracy_score"],
                "feedback": row.get("feedback", ""),
            }
            for i, row in enumerate(state["qa_log"]) if i != 0
        ]
        return {
            "student": {
                "first_name": first or "Unknown",
                "last_name": last or "Student"
            },
            "answers": graded_answers,
            "summary": {
                "dialogue_result": summary_text,
                "overall_accuracy": overall_accuracy,
                "plagiarism_score": plagiarism_score,
            },
        }

    def compute_grade(self, accuracy: int, plagiarism: int, gaze_pct: float) -> int:
        """
        Compute final grade (1-5) based on metrics.
        
        Args:
            accuracy: Overall accuracy percentage
            plagiarism: Plagiarism score (0-100)
            gaze_pct: Percentage of time not looking at screen
            
        Returns:
            Grade from 1 to 5
        """
        # Base grade from accuracy bands
        base = 1
        for threshold, grade in GRADE_BANDS:
            if accuracy >= threshold:
                base = grade
                break
        
        # Penalties
        if plagiarism >= PLAGIARISM_PENALTY_THRESHOLD:
            base -= 1
        if gaze_pct >= GAZE_PENALTY_THRESHOLD_PCT:
            base -= 1
        
        return max(1, min(5, base))

    def _parse_pib(self, fullname: str) -> Tuple[str, str, str]:
        """
        Parse Ukrainian full name (ПІБ) into components.
        
        Returns:
            Tuple of (first_name, last_name, middle_name)
        """
        parts = fullname.strip().split()
        last = parts[0] if len(parts) >= 1 else ""
        first = parts[1] if len(parts) >= 2 else ""
        middle = " ".join(parts[2:]) if len(parts) >= 3 else ""
        return first, last, middle

    def get_graded_answers(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get answers excluding first (ПІБ) entry.
        
        Returns:
            List of graded answer dicts
        """
        return [row for i, row in enumerate(state.get("qa_log", [])) if i != 0]

    def calculate_average_accuracy(self, qa_log: List[Dict[str, Any]]) -> int:
        """
        Calculate average accuracy from Q/A log.
        
        Args:
            qa_log: List of answer dicts with accuracy_score
            
        Returns:
            Average accuracy as integer percentage
        """
        scores = [int(q.get("accuracy_score", 0)) for q in qa_log]
        return round(sum(scores) / max(1, len(scores))) if scores else 0
