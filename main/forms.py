"""Forms for validating incoming request data.

Lightweight validation layer to keep view logic clean and consistent.

We intentionally keep forms minimal: more complex schema (e.g. full interview
payload) should be validated deeper in service layer if business rules grow.
"""
from __future__ import annotations

from django import forms


class VoiceAnswerUploadForm(forms.Form):
    audio = forms.FileField(required=True)

    def clean_audio(self):  # type: ignore[override]
        f = self.cleaned_data["audio"]
        # Basic size guard (e.g. < 25MB)
        max_bytes = 25 * 1024 * 1024
        if f.size > max_bytes:
            raise forms.ValidationError("Файл занадто великий (макс 25MB).")
        return f


class FileAnalyzeForm(forms.Form):
    file = forms.FileField(required=True)

    def clean_file(self):  # type: ignore[override]
        f = self.cleaned_data["file"]
        max_bytes = 10 * 1024 * 1024
        if f.size > max_bytes:
            raise forms.ValidationError("Файл занадто великий (макс 10MB).")
        return f


class SubmitInterviewForm(forms.Form):
    # Raw JSON already parsed in view – represent minimal required fields.
    student_fullname = forms.CharField(required=False, max_length=256)
    overall_accuracy = forms.FloatField(required=False)
    plagiarism_score = forms.FloatField(required=False)
    gaze_not_looking_pct = forms.FloatField(required=False)

    # answers list is validated structurally in service layer; here we just
    # confirm presence if provided.
    def clean(self):  # type: ignore[override]
        cleaned = super().clean()
        return cleaned


__all__ = [
    "VoiceAnswerUploadForm",
    "FileAnalyzeForm",
    "SubmitInterviewForm",
]
