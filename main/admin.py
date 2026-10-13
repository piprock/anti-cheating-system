from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    UserProfile,
    Student,
    Survey,
    InterviewSession,
    Answer,
    ActivityLog,
    TeacherApplication,
)


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


@admin.register(TeacherApplication)
class TeacherApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "get_full_name",
        "department",
        "position",
        "status",
        "created_at",
        "reviewed_by",
        "reviewed_at",
    )
    list_filter = ("status", "created_at", "department")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "department",
        "position",
        "reason",
    )
    readonly_fields = ("created_at", "updated_at")
    actions = ["approve_applications", "reject_applications"]

    def get_full_name(self, obj):
        return obj.user.profile.full_name if hasattr(obj.user, "profile") else obj.user.username
    get_full_name.short_description = "ПІБ користувача"

    @admin.action(description="Схвалити обрані заявки (призначити роль 'Викладач')")
    def approve_applications(self, request, queryset):
        count = 0
        for app in queryset:
            if app.status != TeacherApplication.STATUS_APPROVED:
                app.approve(admin_user=request.user)
                count += 1
        self.message_user(request, f"Успішно схвалено {count} заявок та оновлено роль на 'Викладач'.")

    @admin.action(description="Відхилити обрані заявки")
    def reject_applications(self, request, queryset):
        count = 0
        for app in queryset:
            if app.status != TeacherApplication.STATUS_REJECTED:
                app.reject(admin_user=request.user)
                count += 1
        self.message_user(request, f"Відхилено {count} заявок.")

