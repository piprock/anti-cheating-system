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
    key = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=200, blank=True)
    control_questions = models.JSONField(default=list, blank=True)
    answer_time_sec = models.IntegerField(default=10)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or self.key


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
    Audit log tracking all critical system events (logins, logouts, exams, updates).
    """
    ACTION_LOGIN = "login"
    ACTION_LOGOUT = "logout"
    ACTION_EXAM_START = "exam_start"
    ACTION_EXAM_SUBMIT = "exam_submit"
    ACTION_PROFILE_UPDATE = "profile_update"

    ACTION_CHOICES = [
        (ACTION_LOGIN, "Вхід у систему"),
        (ACTION_LOGOUT, "Вихід із системи"),
        (ACTION_EXAM_START, "Початок тесту"),
        (ACTION_EXAM_SUBMIT, "Завершення тесту"),
        (ACTION_PROFILE_UPDATE, "Оновлення профілю"),
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
