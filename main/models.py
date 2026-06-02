from django.db import models

class Student(models.Model):
    first_name = models.CharField(max_length=100)
    last_name  = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, default="")  # нове
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()

class Survey(models.Model):
    key = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=200, blank=True)
    control_questions = models.JSONField(default=list, blank=True)
    # Тривалість відповіді на одне запитання (секунди)
    answer_time_sec = models.IntegerField(default=10)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class InterviewSession(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.PROTECT, related_name="sessions")
    # дозволяємо створити сесію ДО того, як дізналися ПІБ
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="sessions",
                                null=True, blank=True)  # змінено
    started_at = models.DateTimeField()
    ended_at   = models.DateTimeField(null=True, blank=True)  # змінено
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

class Answer(models.Model):
    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name="answers")
    question = models.TextField()
    answer   = models.TextField()
    accuracy_score = models.IntegerField(default=0)
    feedback = models.TextField(blank=True, default="")  # нове
    question_order = models.IntegerField(default=0)       # нове
    created_at = models.DateTimeField(auto_now_add=True)  # нове
