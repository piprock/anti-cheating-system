from django.contrib import admin
from .models import Student, Survey, InterviewSession, Answer

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "created_at")
    search_fields = ("first_name", "last_name")

@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "answer_time_sec", "active", "created_at")
    search_fields = ("key", "title")

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0

@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "survey", "student", "duration_sec", "overall_accuracy",
                    "plagiarism_score", "gaze_not_looking_pct", "grade_5", "started_at", "ended_at")
    inlines = [AnswerInline]
