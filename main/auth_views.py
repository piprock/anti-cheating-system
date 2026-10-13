import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.models import User

from .models import (
    UserProfile,
    InterviewSession,
    Survey,
    Student,
    ActivityLog,
    TeacherApplication,
)
from .forms import (
    UserLoginForm,
    RegistrationStep1Form,
    RegistrationStep2Form,
    UserRegistrationForm,
    UserProfileEditForm,
    TeacherApplicationForm,
)

logger = logging.getLogger(__name__)


def login_view(request):
    """User authentication view."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = UserLoginForm(data=request.POST)
        if form.is_valid():
            user = form.user
            login(request, user)
            messages.success(request, f"Вітаємо, {user.first_name or user.username}! Ви успішно увійшли.")
            next_url = request.GET.get("next") or request.POST.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect("dashboard")
    else:
        form = UserLoginForm()

    return render(request, "main/login.html", {"form": form})


def logout_view(request):
    """User logout view."""
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, "Ви вийшли з системи.")
    return redirect("main")


def register_view(request):
    """
    2-Step User Registration wizard for students.
    Step 1: Account credentials (username, email, password, confirm).
    Step 2: Personal details (last_name, first_name, middle_name, group).
    """
    if request.user.is_authenticated:
        return redirect("dashboard")

    # Allow backward compatible single-form submission if both step1 and step2 fields present
    if request.method == "POST" and "password" in request.POST and "last_name" in request.POST:
        form = UserRegistrationForm(data=request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            user = User.objects.create_user(
                username=cd["username"],
                email=cd["email"],
                password=cd["password"],
                first_name=cd["first_name"],
                last_name=cd["last_name"],
            )
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = UserProfile.ROLE_STUDENT
            profile.middle_name = cd.get("middle_name", "").strip()
            profile.group = cd.get("group", "").strip()
            profile.save()

            Student.objects.create(
                user=user,
                first_name=cd["first_name"],
                last_name=cd["last_name"],
                middle_name=cd.get("middle_name", "").strip(),
                group=cd.get("group", "").strip(),
            )
            login(request, user)
            messages.success(request, "Реєстрація успішна! Ласкаво просимо до Avatar AI.")
            return redirect("dashboard")
        return render(request, "main/register.html", {"form": form, "step": 1})

    step = str(request.POST.get("step") or request.GET.get("step", "1"))

    if step == "2":
        step1_data = request.session.get("reg_step1")
        if not step1_data:
            return redirect(f"{request.path}?step=1")

        if request.method == "POST":
            form = RegistrationStep2Form(data=request.POST)
            if form.is_valid():
                cd2 = form.cleaned_data
                user = User.objects.create_user(
                    username=step1_data["username"],
                    email=step1_data.get("email", ""),
                    password=step1_data["password"],
                    first_name=cd2["first_name"].strip(),
                    last_name=cd2["last_name"].strip(),
                )

                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.role = UserProfile.ROLE_STUDENT
                profile.middle_name = cd2.get("middle_name", "").strip()
                profile.group = cd2.get("group", "").strip()
                profile.save()

                Student.objects.create(
                    user=user,
                    first_name=cd2["first_name"].strip(),
                    last_name=cd2["last_name"].strip(),
                    middle_name=cd2.get("middle_name", "").strip(),
                    group=cd2.get("group", "").strip(),
                )

                # Clear session state
                request.session.pop("reg_step1", None)

                # Log user in
                login(request, user)
                messages.success(request, "Реєстрація успішна! Ласкаво просимо до Avatar AI.")
                return redirect("dashboard")
        else:
            form = RegistrationStep2Form()

        return render(request, "main/register.html", {
            "form": form,
            "step": 2,
            "step1_data": step1_data,
        })

    # Step 1 (default)
    if request.method == "POST":
        form = RegistrationStep1Form(data=request.POST)
        if form.is_valid():
            request.session["reg_step1"] = form.cleaned_data
            return redirect(f"{request.path}?step=2")
    else:
        initial = request.session.get("reg_step1", {})
        form = RegistrationStep1Form(initial=initial)

    return render(request, "main/register.html", {"form": form, "step": 1})


@login_required
def dashboard_view(request):
    """
    Role-aware personal cabinet and exam history dashboard.
    """
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if profile.is_admin:
        # Admin Dashboard: comprehensive stats, user management, all sessions
        users = User.objects.select_related("profile").order_by("-date_joined")
        sessions = InterviewSession.objects.select_related("survey", "student", "user").order_by("-started_at")[:50]
        recent_logs = ActivityLog.objects.select_related("user").order_by("-created_at")[:30]

        total_users_count = User.objects.count()
        students_count = UserProfile.objects.filter(role=UserProfile.ROLE_STUDENT).count()
        teachers_count = UserProfile.objects.filter(role=UserProfile.ROLE_TEACHER).count()
        admins_count = UserProfile.objects.filter(role=UserProfile.ROLE_ADMIN).count()
        total_sessions_count = InterviewSession.objects.count()
        total_surveys_count = Survey.objects.count()

        pending_applications = TeacherApplication.objects.filter(
            status=TeacherApplication.STATUS_PENDING
        ).select_related("user", "user__profile").order_by("-created_at")
        pending_applications_count = pending_applications.count()

        avg_metrics = InterviewSession.objects.aggregate(
            avg_accuracy=Avg("overall_accuracy"),
            avg_grade=Avg("grade_5"),
            avg_gaze=Avg("gaze_not_looking_pct"),
            avg_plag=Avg("plagiarism_score")
        )

        context = {
            "profile": profile,
            "role": "admin",
            "users": users,
            "sessions": sessions,
            "recent_logs": recent_logs,
            "total_users_count": total_users_count,
            "students_count": students_count,
            "teachers_count": teachers_count,
            "admins_count": admins_count,
            "total_sessions_count": total_sessions_count,
            "total_surveys_count": total_surveys_count,
            "pending_applications": pending_applications,
            "pending_applications_count": pending_applications_count,
            "avg_metrics": avg_metrics,
        }
        return render(request, "main/dashboard.html", context)

    elif profile.is_teacher:
        # Teacher Dashboard: student performance, anti-cheating alerts, sessions
        sessions = InterviewSession.objects.select_related("survey", "student", "user").order_by("-started_at")[:100]
        students = Student.objects.select_related("user").order_by("last_name", "first_name")
        surveys = Survey.objects.filter(active=True)

        avg_metrics = InterviewSession.objects.aggregate(
            avg_accuracy=Avg("overall_accuracy"),
            avg_grade=Avg("grade_5"),
            avg_gaze=Avg("gaze_not_looking_pct"),
            avg_plag=Avg("plagiarism_score")
        )

        suspicious_count = InterviewSession.objects.filter(
            Q(gaze_not_looking_pct__gte=35.0) | Q(plagiarism_score__gte=20)
        ).count()

        context = {
            "profile": profile,
            "role": "teacher",
            "sessions": sessions,
            "students": students,
            "surveys": surveys,
            "avg_metrics": avg_metrics,
            "total_sessions_count": InterviewSession.objects.count(),
            "suspicious_count": suspicious_count,
        }
        return render(request, "main/dashboard.html", context)

    else:
        # Student Dashboard: personal history, passed exams, detailed stats
        # Search for sessions tied directly to this user OR by student match
        user_sessions = InterviewSession.objects.filter(
            Q(user=request.user) |
            Q(student__user=request.user)
        ).select_related("survey", "student").order_by("-started_at").distinct()

        total_taken = user_sessions.count()
        passed_count = user_sessions.filter(grade_5__gte=3).count()

        stats = user_sessions.aggregate(
            avg_accuracy=Avg("overall_accuracy"),
            avg_grade=Avg("grade_5"),
            avg_gaze=Avg("gaze_not_looking_pct"),
            avg_duration=Avg("duration_sec"),
            avg_plag=Avg("plagiarism_score"),
        )

        recent_logs = ActivityLog.objects.filter(user=request.user).order_by("-created_at")[:15]
        available_surveys = Survey.objects.filter(active=True)[:5]

        context = {
            "profile": profile,
            "role": "student",
            "sessions": user_sessions,
            "total_taken": total_taken,
            "passed_count": passed_count,
            "stats": stats,
            "recent_logs": recent_logs,
            "available_surveys": available_surveys,
        }
        return render(request, "main/dashboard.html", context)


@login_required
def session_detail_view(request, session_id: int):
    """
    Detailed review of a completed exam session, including questions, answers,
    accuracy scores, AI feedback, and anti-cheating gaze metrics.
    """
    session = get_object_or_404(
        InterviewSession.objects.select_related("survey", "student", "user").prefetch_related("answers"),
        id=session_id
    )

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Permission check: student can only view their own sessions
    if not (profile.is_admin or profile.is_teacher):
        is_owner = (session.user_id == request.user.id) or (
            session.student and session.student.user_id == request.user.id
        )
        if not is_owner:
            return HttpResponseForbidden("У вас немає доступу до цієї екзаменаційної сесії.")

    answers = session.answers.all().order_by("question_order", "id")

    return render(request, "main/session_detail.html", {
        "session": session,
        "answers": answers,
        "profile": profile,
    })


@login_required
def profile_edit_view(request):
    """Update user personal profile details (ПІБ, group)."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = UserProfileEditForm(data=request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            user = request.user
            user.first_name = cd["first_name"].strip()
            user.last_name = cd["last_name"].strip()
            if cd.get("email"):
                user.email = cd["email"].strip()
            user.save()

            profile.middle_name = cd.get("middle_name", "").strip()
            profile.group = cd.get("group", "").strip()
            profile.save()

            # Keep student records synchronized
            Student.objects.filter(user=user).update(
                first_name=user.first_name,
                last_name=user.last_name,
                middle_name=profile.middle_name,
                group=profile.group
            )

            ActivityLog.objects.create(
                user=user,
                action=ActivityLog.ACTION_PROFILE_UPDATE,
                details="Оновлено контактні дані та академічну групу в профілі."
            )

            messages.success(request, "Дані профілю успішно оновлено!")
            return redirect("dashboard")
    else:
        form = UserProfileEditForm(initial={
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "middle_name": profile.middle_name,
            "group": profile.group,
            "email": request.user.email,
        })

    return render(request, "main/profile_edit.html", {"form": form, "profile": profile})


@login_required
def settings_view(request):
    """
    User settings view with multi-tab layout:
    - profile: Edit personal details (ПІБ, group, email).
    - teacher: Teacher role application / status review.
    - security: Password change.
    """
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    requested_tab = request.POST.get("active_tab") or request.GET.get("tab") or "profile"
    if requested_tab not in ("profile", "teacher", "security"):
        requested_tab = "profile"

    profile_form = None
    teacher_form = None
    password_form = None

    latest_teacher_app = TeacherApplication.objects.filter(user=request.user).first()
    pending_teacher_app = TeacherApplication.objects.filter(
        user=request.user, status=TeacherApplication.STATUS_PENDING
    ).first()

    if request.method == "POST":
        form_action = request.POST.get("form_action")
        if not form_action:
            if "department" in request.POST:
                form_action = "teacher_application"
            elif "old_password" in request.POST:
                form_action = "change_password"
            elif "first_name" in request.POST:
                form_action = "profile"

        if form_action == "profile":
            profile_form = UserProfileEditForm(data=request.POST)
            if profile_form.is_valid():
                cd = profile_form.cleaned_data
                user = request.user
                user.first_name = cd["first_name"].strip()
                user.last_name = cd["last_name"].strip()
                if cd.get("email"):
                    user.email = cd["email"].strip()
                user.save()

                profile.middle_name = cd.get("middle_name", "").strip()
                profile.group = cd.get("group", "").strip()
                profile.save()

                Student.objects.filter(user=user).update(
                    first_name=user.first_name,
                    last_name=user.last_name,
                    middle_name=profile.middle_name,
                    group=profile.group
                )

                ActivityLog.objects.create(
                    user=user,
                    action=ActivityLog.ACTION_PROFILE_UPDATE,
                    details="Оновлено контактні дані та академічну групу в налаштуваннях."
                )

                messages.success(request, "Дані профілю успішно оновлено!")
                return redirect(f"{reverse('settings')}?tab=profile")
            else:
                requested_tab = "profile"

        elif form_action == "teacher_application":
            if profile.is_teacher or profile.is_admin:
                messages.info(request, "Ваш обліковий запис уже має розширений статус.")
                return redirect(f"{reverse('settings')}?tab=teacher")

            if pending_teacher_app:
                messages.warning(request, "У вас уже є активна заявка на розгляді адміністратора.")
                return redirect(f"{reverse('settings')}?tab=teacher")

            teacher_form = TeacherApplicationForm(data=request.POST)
            if teacher_form.is_valid():
                cd = teacher_form.cleaned_data
                TeacherApplication.objects.create(
                    user=request.user,
                    department=cd["department"].strip(),
                    position=cd["position"].strip(),
                    phone=cd.get("phone", "").strip(),
                    reason=cd["reason"].strip(),
                )

                ActivityLog.objects.create(
                    user=request.user,
                    action=ActivityLog.ACTION_TEACHER_REQUEST,
                    details=f"Подано заявку на роль 'Викладач' ({cd['department'].strip()}, {cd['position'].strip()})."
                )

                messages.success(
                    request,
                    "Заявку на отримання статусу 'Викладач' успішно надіслано! Очікуйте на підтвердження адміністратора."
                )
                return redirect(f"{reverse('settings')}?tab=teacher")
            else:
                requested_tab = "teacher"

        elif form_action == "cancel_teacher_application":
            if pending_teacher_app:
                pending_teacher_app.status = TeacherApplication.STATUS_CANCELLED
                pending_teacher_app.save(update_fields=["status"])
                messages.info(request, "Заявку на отримання статусу викладача скасовано.")
            return redirect(f"{reverse('settings')}?tab=teacher")

        elif form_action == "change_password":
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Пароль успішно змінено!")
                return redirect(f"{reverse('settings')}?tab=security")
            else:
                requested_tab = "security"

    if profile_form is None:
        profile_form = UserProfileEditForm(initial={
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "middle_name": profile.middle_name,
            "group": profile.group,
            "email": request.user.email,
        })

    if teacher_form is None:
        teacher_form = TeacherApplicationForm()

    if password_form is None:
        password_form = PasswordChangeForm(user=request.user)

    context = {
        "profile": profile,
        "active_tab": requested_tab,
        "profile_form": profile_form,
        "teacher_form": teacher_form,
        "password_form": password_form,
        "latest_teacher_app": latest_teacher_app,
        "pending_teacher_app": pending_teacher_app,
    }
    return render(request, "main/settings.html", context)


@login_required
def review_teacher_application_view(request, app_id: int):
    """Admin endpoint to approve or reject a teacher application."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile.is_admin:
        return HttpResponseForbidden("Тільки адміністратор має доступ до розгляду заявок.")

    app = get_object_or_404(TeacherApplication, id=app_id)
    if request.method == "POST":
        action = request.POST.get("action")
        notes = request.POST.get("notes", "").strip()
        if action == "approve":
            app.approve(admin_user=request.user, notes=notes)
            messages.success(request, f"Заявку користувача {app.user.username} схвалено. Надано статус 'Викладач'.")
        elif action == "reject":
            app.reject(admin_user=request.user, notes=notes)
            messages.info(request, f"Заявку користувача {app.user.username} відхилено.")
    return redirect(request.POST.get("next") or "dashboard")

