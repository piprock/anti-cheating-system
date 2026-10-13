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
    last_name = forms.CharField(
        label="Прізвище",
        max_length=MAX_NAME_LEN,
        widget=forms.TextInput(attrs={"placeholder": "Шевченко", "autocomplete": "family-name"}),
    )
    first_name = forms.CharField(
        label="Ім'я",
        max_length=MAX_NAME_LEN,
        widget=forms.TextInput(attrs={"placeholder": "Тарас", "autocomplete": "given-name"}),
    )
    middle_name = forms.CharField(
        label="По батькові",
        max_length=MAX_NAME_LEN,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Григорович (необов'язково)", "autocomplete": "additional-name"}),
    )
    group = forms.CharField(
        label="Група",
        max_length=MAX_GROUP_LEN,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "КН-41 (необов'язково)"}),
    )
    email = forms.EmailField(
        label="Електронна пошта",
        required=False,
        widget=forms.EmailInput(attrs={"placeholder": "student@example.com", "autocomplete": "email"}),
    )


class TeacherApplicationForm(forms.Form):
    """Форма для подачі заявки на отримання ролі 'Викладач'."""
    department = forms.CharField(
        label="Кафедра / Факультет",
        max_length=150,
        widget=forms.TextInput(attrs={
            "placeholder": "Наприклад, Кафедра комп'ютерних наук",
            "autocomplete": "organization",
        })
    )
    position = forms.CharField(
        label="Посада / Науковий ступінь",
        max_length=150,
        widget=forms.TextInput(attrs={
            "placeholder": "Наприклад, Доцент, Асистент, Старший викладач",
            "autocomplete": "organization-title",
        })
    )
    phone = forms.CharField(
        label="Контактний телефон",
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "+380 ... (необов'язково)",
            "autocomplete": "tel",
        })
    )
    reason = forms.CharField(
        label="Обґрунтування запиту та мотивація",
        widget=forms.Textarea(attrs={
            "rows": 4,
            "placeholder": "Опишіть дисципліни, які ви викладаєте, або мету використання системи Avatar AI...",
        })
    )


class SurveyForm(forms.ModelForm):
    """
    Форма створення та редагування тесту (Survey) для викладачів.
    Кожне запитання має окреме поле формулювання та власний ліміт часу.
    Вступне запитання для ПІБ є фіксованим за замовчуванням.
    """
    DEFAULT_INTRO_QUESTION = "Будь ласка, назвіть ваше прізвище, ім'я та по батькові"

    class Meta:
        from .models import Survey
        model = Survey
        fields = ["title", "key", "description", "active", "is_public"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Наприклад: Основи об'єктно-орієнтованого програмування"}),
            "key": forms.TextInput(attrs={"placeholder": "oop_basics_exam"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Короткий опис теми та інструкції до тесту..."}),
        }
        labels = {
            "title": "Назва тесту",
            "key": "Унікальний код / ключ тесту",
            "description": "Опис тесту",
            "active": "Тест активний",
            "is_public": "Відкритий доступ (будь-хто може проходити)",
        }

    def clean_key(self):
        key = (self.cleaned_data.get("key") or "").strip().lower().replace(" ", "_")
        if not key:
            raise forms.ValidationError("Ключ тесту не може бути порожнім.")
        from .models import Survey
        qs = Survey.objects.filter(key=key)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f"Тест із ключем '{key}' вже існує. Оберіть інший код.")
        return key

    def clean(self):
        cleaned = super().clean()
        question_texts = self.data.getlist("question_text") if hasattr(self.data, "getlist") else []
        question_times = self.data.getlist("question_time") if hasattr(self.data, "getlist") else []

        # Підтримка зворотної сумісності (якщо передано одним текстом або списком)
        if not question_texts:
            raw_text = (self.data.get("questions_text") or "").strip()
            if raw_text:
                question_texts = [line.strip() for line in raw_text.splitlines() if line.strip()]
                question_times = [15] * len(question_texts)
            elif isinstance(self.data.get("question_text"), list):
                question_texts = self.data.get("question_text")
                question_times = self.data.get("question_time") or [15] * len(question_texts)

        items = []
        for i, q_text in enumerate(question_texts):
            text = (q_text or "").strip()
            if not text:
                continue
            time_val = 15
            if i < len(question_times):
                try:
                    time_val = int(question_times[i])
                    time_val = max(5, min(300, time_val))
                except (ValueError, TypeError):
                    time_val = 15
            items.append({"text": text, "time": time_val})

        if not items:
            raise forms.ValidationError("Тест повинен містити хоча б одне екзаменаційне запитання з визначеним часом.")

        self.cleaned_questions = items
        return cleaned

    def save(self, commit=True, author=None):
        survey = super().save(commit=False)
        if author and not survey.author:
            survey.author = author

        questions = getattr(self, "cleaned_questions", [])
        # Вступне запитання з власним часом
        intro_q = {"text": self.DEFAULT_INTRO_QUESTION, "time": 10}
        survey.control_questions = [intro_q] + questions

        # Для зворотної сумісності моделі зберігаємо час першого запитання або 15с
        if questions:
            survey.answer_time_sec = questions[0].get("time", 15)
        else:
            survey.answer_time_sec = 15

        if commit:
            survey.save()
        return survey


class TestAssignmentForm(forms.Form):
    """
    Форма призначення тесту окремим студентам або академічній групі.
    """
    __test__ = False

    ASSIGN_STUDENT = "student"
    ASSIGN_GROUP = "group"
    ASSIGN_CHOICES = [
        (ASSIGN_STUDENT, "Окремим студентам"),
        (ASSIGN_GROUP, "Академічній групі"),
    ]

    assign_type = forms.ChoiceField(
        choices=ASSIGN_CHOICES,
        widget=forms.RadioSelect,
        initial=ASSIGN_STUDENT,
        label="Кому призначити",
    )
    students = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(profile__role="student").order_by("last_name", "first_name", "username"),
        required=False,
        label="Оберіть студентів",
        widget=forms.SelectMultiple(attrs={"size": 6}),
    )
    group = forms.CharField(
        required=False,
        max_length=50,
        label="Академічна група",
        widget=forms.TextInput(attrs={"placeholder": "Наприклад: КН-21 або ПЗ-19"}),
    )
    due_date = forms.DateField(
        required=False,
        label="Термін здачі (дедлайн)",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    notes = forms.CharField(
        required=False,
        label="Коментар / вказівки для студентів",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Додаткові вказівки чи дедлайн..."}),
    )

    def clean(self):
        cleaned = super().clean()
        assign_type = cleaned.get("assign_type")
        students = cleaned.get("students")
        group = (cleaned.get("group") or "").strip()

        if assign_type == self.ASSIGN_STUDENT:
            if not students:
                raise forms.ValidationError("Будь ласка, оберіть хоча б одного студента зі списку.")
        elif assign_type == self.ASSIGN_GROUP:
            if not group:
                raise forms.ValidationError("Будь ласка, вкажіть академічну групу для призначення.")
        return cleaned


__all__ = [
    "VoiceAnswerUploadForm",
    "FileAnalyzeForm",
    "SubmitInterviewForm",
    "UserLoginForm",
    "RegistrationStep1Form",
    "RegistrationStep2Form",
    "UserRegistrationForm",
    "UserProfileEditForm",
    "TeacherApplicationForm",
    "SurveyForm",
    "TestAssignmentForm",
]

