"""Forms for validating incoming request data.

Lightweight validation layer to keep view logic clean and consistent.
Integrates with centralized constants from `const` package.
"""
from __future__ import annotations

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate

from const.errors.messages import (
    ERR_INVALID_CREDENTIALS,
    ERR_ACCOUNT_DISABLED,
    ERR_USERNAME_TAKEN,
    ERR_PASSWORD_MISMATCH,
    ERR_AUDIO_TOO_LARGE,
    ERR_DOCUMENT_TOO_LARGE,
)
from const.validation.bounds import (
    MAX_AUDIO_FILE_BYTES,
    MAX_DOC_FILE_BYTES,
    MIN_USERNAME_LEN,
    MAX_USERNAME_LEN,
    MIN_PASSWORD_LEN,
    MAX_NAME_LEN,
    MAX_GROUP_LEN,
)


class VoiceAnswerUploadForm(forms.Form):
    audio = forms.FileField(required=True)

    def clean_audio(self):  # type: ignore[override]
        f = self.cleaned_data["audio"]
        if f.size > MAX_AUDIO_FILE_BYTES:
            raise forms.ValidationError(ERR_AUDIO_TOO_LARGE)
        return f


class FileAnalyzeForm(forms.Form):
    file = forms.FileField(required=True)

    def clean_file(self):  # type: ignore[override]
        f = self.cleaned_data["file"]
        if f.size > MAX_DOC_FILE_BYTES:
            raise forms.ValidationError(ERR_DOCUMENT_TOO_LARGE)
        return f


class SubmitInterviewForm(forms.Form):
    student_fullname = forms.CharField(required=False, max_length=256)
    overall_accuracy = forms.FloatField(required=False)
    plagiarism_score = forms.FloatField(required=False)
    gaze_not_looking_pct = forms.FloatField(required=False)

    def clean(self):  # type: ignore[override]
        return super().clean()


class UserLoginForm(forms.Form):
    username = forms.CharField(
        label="Логін",
        max_length=MAX_USERNAME_LEN,
        widget=forms.TextInput(attrs={"placeholder": "Ваш логін", "autocomplete": "username"})
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"placeholder": "Ваш пароль", "autocomplete": "current-password"})
    )

    def clean(self):
        cleaned = super().clean()
        username = (cleaned.get("username") or "").strip()
        password = cleaned.get("password")
        if username and password:
            user = authenticate(username=username, password=password)
            if user is None:
                raise forms.ValidationError(ERR_INVALID_CREDENTIALS)
            if not user.is_active:
                raise forms.ValidationError(ERR_ACCOUNT_DISABLED)
            self.user = user
        return cleaned


class RegistrationStep1Form(forms.Form):
    """Етап 1 реєстрації: обліковий запис (логін, пошта, пароль та підтвердження)."""
    username = forms.CharField(
        label="Логін",
        min_length=MIN_USERNAME_LEN,
        max_length=MAX_USERNAME_LEN,
        widget=forms.TextInput(attrs={"placeholder": "Придумайте логін (від 3 символів)", "autocomplete": "username"})
    )
    email = forms.EmailField(
        label="Електронна пошта",
        required=False,
        widget=forms.EmailInput(attrs={"placeholder": "student@example.com (необов'язково)", "autocomplete": "email"})
    )
    password = forms.CharField(
        label="Пароль",
        min_length=MIN_PASSWORD_LEN,
        widget=forms.PasswordInput(attrs={"placeholder": "Мінімум 6 символів", "autocomplete": "new-password"})
    )
    password_confirm = forms.CharField(
        label="Підтвердження пароля",
        widget=forms.PasswordInput(attrs={"placeholder": "Повторіть пароль", "autocomplete": "new-password"})
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(ERR_USERNAME_TAKEN)
        return username

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password")
        p2 = cleaned.get("password_confirm")
        if p1 and p2 and p1 != p2:
            self.add_error("password_confirm", ERR_PASSWORD_MISMATCH)
        return cleaned


class RegistrationStep2Form(forms.Form):
    """Етап 2 реєстрації: персональні дані (прізвище, ім'я, по батькові, група)."""
    last_name = forms.CharField(
        label="Прізвище",
        max_length=MAX_NAME_LEN,
        widget=forms.TextInput(attrs={"placeholder": "Ваше прізвище", "autocomplete": "family-name"})
    )
    first_name = forms.CharField(
        label="Ім'я",
        max_length=MAX_NAME_LEN,
        widget=forms.TextInput(attrs={"placeholder": "Ваше ім'я", "autocomplete": "given-name"})
    )
    middle_name = forms.CharField(
        label="По батькові",
        max_length=MAX_NAME_LEN,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "По батькові (необов'язково)", "autocomplete": "additional-name"})
    )
    group = forms.CharField(
        label="Академічна група",
        max_length=MAX_GROUP_LEN,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Наприклад, КН-41 (необов'язково)"})
    )


class UserRegistrationForm(forms.Form):
    """Повна форма для зворотної сумісності або одномоментної реєстрації."""
    username = forms.CharField(
        label="Логін",
        max_length=MAX_USERNAME_LEN,
        widget=forms.TextInput(attrs={"placeholder": "Придумайте логін", "autocomplete": "username"})
    )
    email = forms.EmailField(
        label="Електронна пошта",
        required=False,
        widget=forms.EmailInput(attrs={"placeholder": "student@example.com", "autocomplete": "email"})
    )
    last_name = forms.CharField(
        label="Прізвище",
        max_length=MAX_NAME_LEN,
        widget=forms.TextInput(attrs={"placeholder": "Прізвище"})
    )
    first_name = forms.CharField(
        label="Ім'я",
        max_length=MAX_NAME_LEN,
        widget=forms.TextInput(attrs={"placeholder": "Ім'я"})
    )
    middle_name = forms.CharField(
        label="По батькові",
        max_length=MAX_NAME_LEN,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "По батькові (необов'язково)"})
    )
    group = forms.CharField(
        label="Академічна група",
        max_length=MAX_GROUP_LEN,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Наприклад, КН-41 (необов'язково)"})
    )
    password = forms.CharField(
        label="Пароль",
        min_length=MIN_PASSWORD_LEN,
        widget=forms.PasswordInput(attrs={"placeholder": "Мінімум 6 символів", "autocomplete": "new-password"})
    )
    password_confirm = forms.CharField(
        label="Підтвердження пароля",
        widget=forms.PasswordInput(attrs={"placeholder": "Повторіть пароль", "autocomplete": "new-password"})
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(ERR_USERNAME_TAKEN)
        return username

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password")
        p2 = cleaned.get("password_confirm")
        if p1 and p2 and p1 != p2:
            self.add_error("password_confirm", ERR_PASSWORD_MISMATCH)
        return cleaned


class UserProfileEditForm(forms.Form):
    last_name = forms.CharField(label="Прізвище", max_length=MAX_NAME_LEN)
    first_name = forms.CharField(label="Ім'я", max_length=MAX_NAME_LEN)
    middle_name = forms.CharField(label="По батькові", max_length=MAX_NAME_LEN, required=False)
    group = forms.CharField(label="Група", max_length=MAX_GROUP_LEN, required=False)
    email = forms.EmailField(label="Електронна пошта", required=False)


__all__ = [
    "VoiceAnswerUploadForm",
    "FileAnalyzeForm",
    "SubmitInterviewForm",
    "UserLoginForm",
    "RegistrationStep1Form",
    "RegistrationStep2Form",
    "UserRegistrationForm",
    "UserProfileEditForm",
]
