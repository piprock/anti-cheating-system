"""
Centralized const package for the Avatar AI exam system.

Organized into modular sub-packages:
- const.errors: Error codes and localized human-readable messages.
- const.validation: Form validation boundaries, length limits, file size extremes.
- const.exam: Exam grading bands, penalties, gaze thresholds, cache timeouts.
"""

from .errors import *
from .validation import *
from .exam import *
