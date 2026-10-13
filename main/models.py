from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver


class UserProfile(models.Model):
    """
    Extensible profile for application users with role-based access.
    
    Roles:
    - admin: full system access, management of users and exams
    - teacher: creates exams, monitors sessions, reviews anti-cheating stats
    - student: takes exams, reviews personal history and statistics
    """
    ROLE_ADMIN = "admin"
    ROLE_TEACHER = "teacher"
    ROLE_STUDENT = "student"

    ROLE_CHOICES = [
        (ROLE_ADMIN, "Адміністратор"),
        (ROLE_TEACHER, "Викладач"),
        (ROLE_STUDENT, "Студент"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STUDENT, verbose_name="Роль")
    middle_name = models.CharField(max_length=100, blank=True, default="", verbose_name="По батькові")
    group = models.CharField(max_length=50, blank=True, default="", verbose_name="Академічна група")
    extra_data = models.JSONField(default=dict, blank=True, verbose_name="Додаткові дані")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    class Meta:
        verbose_name = "Профіль користувача"
        verbose_name_plural = "Профілі користувачів"

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"

    @property
    def full_name(self) -> str:
        parts = [self.user.last_name, self.user.first_name, self.middle_name]
        name = " ".join([p.strip() for p in parts if p and p.strip()]).strip()
        return name or self.user.username

    @property
    def is_admin(self) -> bool:
        return self.role == self.ROLE_ADMIN or self.user.is_superuser

    @property
    def is_teacher(self) -> bool:
        return self.role == self.ROLE_TEACHER

    @property
    def is_student(self) -> bool:
        return self.role == self.ROLE_STUDENT


Profile = UserProfile


class Student(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="student_records")
    first_name = models.CharField(max_length=100)
    last_name  = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, default="")
    group = models.CharField(max_length=50, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        pib = f"{self.last_name} {self.first_name} {self.middle_name}".strip()
        if self.group:
            return f"{pib} ({self.group})"
        return pib


class Survey(models.Model):
    key = models.CharField(max_length=64, unique=True, verbose_name="Унікальний ключ (код)")
    title = models.CharField(max_length=200, blank=True, verbose_name="Назва тесту")
    description = models.TextField(blank=True, default="", verbose_name="Опис тесту")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_surveys", verbose_name="Автор / Викладач")
    is_public = models.BooleanField(default=True, verbose_name="Відкритий доступ (для всіх)")
    control_questions = models.JSONField(default=list, blank=True, verbose_name="Контрольні запитання")
    answer_time_sec = models.IntegerField(default=10, verbose_name="Час на відповідь (сек.)")
    active = models.BooleanField(default=True, verbose_name="Активний")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Тест / Опитування"
        verbose_name_plural = "Тести / Опитування"

    def __str__(self):
        return self.title or self.key

    @property
    def question_count(self) -> int:
        if not self.control_questions:
            return 0
        cq = self.control_questions
        first_q = cq[0]
        first_q_text = first_q.get("text", "") if isinstance(first_q, dict) else str(first_q)
        if cq and any(kw in first_q_text.lower() for kw in ["піб", "прізвище", "ім'я", "fullname", "name"]):
            return max(0, len(cq) - 1)
        return len(cq)

    @property
    def exam_questions(self) -> list[dict]:
        """Normalized exam questions (excluding intro question) with individual text and time."""
        cq = self.control_questions or []
        if not cq:
            return []
        first_q = cq[0]
        first_q_text = first_q.get("text", "") if isinstance(first_q, dict) else str(first_q)
        items = cq[1:] if any(kw in first_q_text.lower() for kw in ["піб", "прізвище", "ім'я", "fullname", "name"]) else cq
        res = []
        for q in items:
            if isinstance(q, dict):
                res.append({
                    "text": q.get("text", ""),
                    "time": q.get("time", self.answer_time_sec or 15)
                })
            else:
                res.append({
                    "text": str(q),
                    "time": self.answer_time_sec or 15
                })
        return res


class TestAssignment(models.Model):
    __test__ = False

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="assignments", verbose_name="Тест")
    student = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="test_assignments", verbose_name="Студент")
    group = models.CharField(max_length=50, blank=True, default="", verbose_name="Академічна група")
    due_date = models.DateField(null=True, blank=True, verbose_name="Термін здачі (дедлайн)")
    notes = models.TextField(blank=True, default="", verbose_name="Коментар / Інструкції")
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="given_assignments", verbose_name="Призначив викладач")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата призначення")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Призначення тесту"
        verbose_name_plural = "Призначення тестів"

    def __str__(self):
        target = self.student.username if self.student else (f"Група {self.group}" if self.group else "Всі")
        return f"{self.survey.key} -> {target}"

    @property
    def is_overdue(self) -> bool:
        if not self.due_date:
            return False
        from django.utils import timezone
        return timezone.localdate() > self.due_date

    @property
    def instructions(self) -> str:
        return self.notes


class InterviewSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="interview_sessions")
    survey = models.ForeignKey(Survey, on_delete=models.PROTECT, related_name="sessions")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="sessions",
                                null=True, blank=True)
    started_at = models.DateTimeField()
    ended_at   = models.DateTimeField(null=True, blank=True)
    duration_sec = models.IntegerField(default=0)

    # метрики/результати
    overall_accuracy = models.IntegerField(default=0)
    plagiarism_score = models.IntegerField(default=0)
    dialogue_result  = models.TextField(blank=True)
    gaze_not_looking_pct = models.FloatField(default=0.0)
    grade_5 = models.IntegerField(default=0)

    # технічні поля
    raw_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, default="in_progress")  # in_progress|done
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        student_str = str(self.student) if self.student else (self.user.username if self.user else "Анонім")
        return f"Сесія #{self.id} - {self.survey.key} ({student_str})"


class Answer(models.Model):
    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name="answers")
    question = models.TextField()
    answer   = models.TextField()
    accuracy_score = models.IntegerField(default=0)
    feedback = models.TextField(blank=True, default="")
    question_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["question_order", "id"]


class ActivityLog(models.Model):
    """
    Audit log tracking all critical system events (logins, logouts, exams, updates, tests).
    """
    ACTION_LOGIN = "login"
    ACTION_LOGOUT = "logout"
    ACTION_EXAM_START = "exam_start"
    ACTION_EXAM_SUBMIT = "exam_submit"
    ACTION_PROFILE_UPDATE = "profile_update"
    ACTION_TEACHER_REQUEST = "teacher_request"
    ACTION_SURVEY_CREATE = "survey_create"
    ACTION_SURVEY_UPDATE = "survey_update"
    ACTION_SURVEY_DELETE = "survey_delete"
    ACTION_SURVEY_ASSIGN = "survey_assign"

    ACTION_CHOICES = [
        (ACTION_LOGIN, "Вхід у систему"),
        (ACTION_LOGOUT, "Вихід із системи"),
        (ACTION_EXAM_START, "Початок тесту"),
        (ACTION_EXAM_SUBMIT, "Завершення тесту"),
        (ACTION_PROFILE_UPDATE, "Оновлення профілю"),
        (ACTION_TEACHER_REQUEST, "Запит на статус викладача"),
        (ACTION_SURVEY_CREATE, "Створення тесту"),
        (ACTION_SURVEY_UPDATE, "Оновлення тесту"),
        (ACTION_SURVEY_DELETE, "Видалення тесту"),
        (ACTION_SURVEY_ASSIGN, "Призначення тесту"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="activity_logs")
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    details = models.TextField(blank=True, default="")
    session = models.ForeignKey(InterviewSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="activity_logs")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Журнал дій"
        verbose_name_plural = "Журнали дій"

    def __str__(self):
        user_str = self.user.username if self.user else "Система"
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {user_str} - {self.get_action_display()}"


class TeacherApplication(models.Model):
    """
    Заявка користувача (студента) на розширення функцій акаунту до ролі 'Викладач'.
    Розглядається та затверджується адміністратором системи.
    """
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "На розгляді"),
        (STATUS_APPROVED, "Схвалено"),
        (STATUS_REJECTED, "Відхилено"),
        (STATUS_CANCELLED, "Скасовано"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="teacher_applications", verbose_name="Користувач")
    department = models.CharField(max_length=150, blank=True, default="", verbose_name="Кафедра / Факультет")
    position = models.CharField(max_length=150, blank=True, default="", verbose_name="Посада / Науковий ступінь")
    reason = models.TextField(verbose_name="Обґрунтування запиту / Мотивація")
    phone = models.CharField(max_length=30, blank=True, default="", verbose_name="Контактний телефон")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Статус")
    admin_notes = models.TextField(blank=True, default="", verbose_name="Коментар адміністратора")
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_teacher_applications", verbose_name="Розглянув адміністратор"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата розгляду")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата подачі")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заявка на статус викладача"
        verbose_name_plural = "Заявки на статус викладача"

    def __str__(self):
        return f"Заявка #{self.id} від {self.user.username} ({self.get_status_display()})"

    @property
    def is_pending(self) -> bool:
        return self.status == self.STATUS_PENDING

    @property
    def is_approved(self) -> bool:
        return self.status == self.STATUS_APPROVED

    @property
    def is_rejected(self) -> bool:
        return self.status == self.STATUS_REJECTED

    def approve(self, admin_user=None, notes=""):
        from django.utils import timezone
        self.status = self.STATUS_APPROVED
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        if notes:
            self.admin_notes = notes
        self.save()

        # Update UserProfile role
        if hasattr(self.user, "profile"):
            self.user.profile.role = UserProfile.ROLE_TEACHER
            self.user.profile.save(update_fields=["role"])

        ActivityLog.objects.create(
            user=self.user,
            action=ActivityLog.ACTION_TEACHER_REQUEST,
            details=f"Заявку на статус 'Викладач' схвалено адміністратором {admin_user.username if admin_user else 'системи'}."
        )

    def reject(self, admin_user=None, notes=""):
        from django.utils import timezone
        self.status = self.STATUS_REJECTED
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        if notes:
            self.admin_notes = notes
        self.save()

        ActivityLog.objects.create(
            user=self.user,
            action=ActivityLog.ACTION_TEACHER_REQUEST,
            details=f"Заявку на статус 'Викладач' відхилено адміністратором {admin_user.username if admin_user else 'системи'}. {notes}".strip()
        )



# ----- Signals for Profile Lifecycle and Logging -----

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        role = UserProfile.ROLE_ADMIN if instance.is_superuser else UserProfile.ROLE_STUDENT
        UserProfile.objects.create(user=instance, role=role)
    else:
        if hasattr(instance, "profile"):
            if instance.is_superuser and instance.profile.role != UserProfile.ROLE_ADMIN:
                instance.profile.role = UserProfile.ROLE_ADMIN
                instance.profile.save(update_fields=["role"])


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    ActivityLog.objects.create(
        user=user,
        action=ActivityLog.ACTION_LOGIN,
        details=f"Користувач {user.username} увійшов в систему."
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user:
        ActivityLog.objects.create(
            user=user,
            action=ActivityLog.ACTION_LOGOUT,
            details=f"Користувач {user.username} вийшов з системи."
        )
