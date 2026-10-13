from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Student, Survey, InterviewSession, Answer, ActivityLog


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Профіль"
    fk_name = "user"


# Re-register UserAdmin with inline UserProfile
admin.site.unregister(User)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ("username", "email", "first_name", "last_name", "get_role", "is_staff")
    list_filter = ("is_staff", "is_superuser", "is_active", "profile__role")

    def get_role(self, instance):
        if hasattr(instance, "profile"):
            return instance.profile.get_role_display()
        return "-"
    get_role.short_description = "Роль"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "middle_name", "group", "created_at")
    list_filter = ("role", "group")
    search_fields = ("user__username", "user__first_name", "user__last_name", "group", "middle_name")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "middle_name", "group", "user", "created_at")
    search_fields = ("first_name", "last_name", "middle_name", "group")
    list_filter = ("group",)


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "answer_time_sec", "active", "created_at")
    search_fields = ("key", "title")


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ("question", "answer", "accuracy_score", "feedback", "question_order", "created_at")


@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "survey", "student", "user", "duration_sec", "overall_accuracy",
        "plagiarism_score", "gaze_not_looking_pct", "grade_5", "status", "started_at"
    )
    list_filter = ("survey", "grade_5", "status")
    search_fields = ("survey__key", "survey__title", "student__last_name", "user__username")
    inlines = [AnswerInline]


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "details", "session")
    list_filter = ("action", "created_at")
    search_fields = ("user__username", "details")
    readonly_fields = ("created_at",)
