from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone

from .audio import record_audio, recognize_speech, speak
from .gpt_utils import chat_with_gpt
from .file_extract import extract_text_from_file
"""Deprecated legacy views module.

All functionality formerly here was refactored into dedicated modules:
 - handlers.py (page/views + chat + file analysis)
 - exam_controller.py (interactive exam flow)
 - gaze.py / gaze_utils.py (gaze frame ingestion + metrics)

This file is kept as a stub to avoid import errors in any
older references. Remove it once all legacy imports are purged.
"""

from django.http import JsonResponse

def deprecated(request, *args, **kwargs):  # pragma: no cover
    return JsonResponse({
        "error": "Legacy views removed. Use handlers.py & exam_controller.py endpoints."
    }, status=410)
