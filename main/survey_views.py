"""
Views for Survey (Test) management and public catalog.

Handles:
- Public/Student tests catalog (tests_list)
- Teacher CRUD panel for tests (list, create, edit, delete)
- Test assignment to individual students or academic groups
"""
from __future__ import annotations

import uuid
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.http import HttpResponseForbidden, HttpRequest, HttpResponse
from django.contrib.auth.models import User

from .models import (
    Survey,
    TestAssignment,
    UserProfile,
    InterviewSession,
    ActivityLog,
)
from .forms import SurveyForm, TestAssignmentForm

logger = logging.getLogger(__name__)


def _can_manage_tests(user: User) -> bool:
    """Helper to check if user has teacher or admin privileges."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = getattr(user, "profile", None)
    if profile and (profile.is_teacher or profile.is_admin):
        return True
    return False


def tests_list_view(request: HttpRequest) -> HttpResponse:
    """
    Public and student catalog of all active tests.
    Anyone (even anonymous users) can view available tests and pass them.
    If authenticated, highlights tests assigned to the student or their group.
    """
    q = (request.GET.get("q") or "").strip()
    can_manage = _can_manage_tests(request.user)

    # Base queryset for public viewing: active tests (or all if teacher/admin)
    if can_manage:
        surveys_qs = Survey.objects.all()
    else:
        surveys_qs = Survey.objects.filter(active=True)

    if q:
        surveys_qs = surveys_qs.filter(
            Q(title__icontains=q) |
            Q(key__icontains=q) |
            Q(description__icontains=q)
        )

    surveys = surveys_qs.select_related("author").annotate(
        sessions_total=Count("sessions")
    ).order_by("-created_at")

    # If user is student, find personalized assignments and completed tests
    assigned_tests: list[dict] = []
    completed_sessions_map: dict[str, InterviewSession] = {}

    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        user_group = profile.group if profile else ""

        # Fetch all user's assignments
        assign_query = Q(student=request.user)
        if user_group:
            assign_query |= Q(group__iexact=user_group)

        user_assignments = TestAssignment.objects.filter(
            assign_query,
            survey__active=True
        ).select_related("survey", "assigned_by").order_by("-created_at")

        # Fetch user's passed sessions
        user_sessions = InterviewSession.objects.filter(
            Q(user=request.user) | Q(student__user=request.user)
        ).select_related("survey").order_by("-started_at")

        for s in user_sessions:
            if s.survey.key not in completed_sessions_map:
                completed_sessions_map[s.survey.key] = s

        seen_survey_keys = set()
        for a in user_assignments:
            if a.survey.key not in seen_survey_keys:
                seen_survey_keys.add(a.survey.key)
                assigned_tests.append({
                    "assignment": a,
                    "survey": a.survey,
                    "is_completed": a.survey.key in completed_sessions_map,
                    "session": completed_sessions_map.get(a.survey.key),
                })

    context = {
        "surveys": surveys,
        "assigned_tests": assigned_tests,
        "completed_sessions_map": completed_sessions_map,
        "q": q,
        "can_manage": can_manage,
        "total_active_count": Survey.objects.filter(active=True).count(),
    }
    return render(request, "main/tests_list.html", context)


@login_required
def teacher_tests_list_view(request: HttpRequest) -> HttpResponse:
    """
    Teacher CRUD Panel: List all tests with management controls, statistics,
    and assignments overview.
    """
    if not _can_manage_tests(request.user):
        return HttpResponseForbidden("Доступ дозволено лише викладачам та адміністраторам.")

    q = (request.GET.get("q") or "").strip()
    surveys_qs = Survey.objects.select_related("author").annotate(
        sessions_total=Count("sessions"),
        assignments_total=Count("assignments"),
        avg_grade=Avg("sessions__grade_5"),
    ).order_by("-created_at")

    if q:
        surveys_qs = surveys_qs.filter(
            Q(title__icontains=q) |
            Q(key__icontains=q) |
            Q(description__icontains=q)
        )

    # General statistics
    total_tests = Survey.objects.count()
    active_tests = Survey.objects.filter(active=True).count()
    total_assignments = TestAssignment.objects.count()
    total_sessions = InterviewSession.objects.count()

    context = {
        "surveys": surveys_qs,
        "q": q,
        "total_tests": total_tests,
        "active_tests": active_tests,
        "total_assignments": total_assignments,
        "total_sessions": total_sessions,
    }
    return render(request, "main/teacher/tests_list.html", context)


@login_required
def teacher_test_create_view(request: HttpRequest) -> HttpResponse:
    """
    Teacher CRUD: Create a new test / survey.
    """
    if not _can_manage_tests(request.user):
        return HttpResponseForbidden("Доступ дозволено лише викладачам та адміністраторам.")

    if request.method == "POST":
        form = SurveyForm(data=request.POST)
        if form.is_valid():
            survey = form.save(commit=True, author=request.user)
            ActivityLog.objects.create(
                user=request.user,
                action=ActivityLog.ACTION_SURVEY_CREATE,
                details=f"Викладач {request.user.username} створив тест '{survey.title or survey.key}' ({survey.key}).",
                metadata={"survey_key": survey.key, "title": survey.title}
            )
            messages.success(request, f"Тест '{survey.title or survey.key}' успішно створено!")
            return redirect("teacher_tests_list")
        else:
            q_texts = request.POST.getlist("question_text")
            q_times = request.POST.getlist("question_time")
            questions_data = []
            for t, tm in zip(q_texts, q_times):
                try:
                    tm_val = int(tm)
                except (ValueError, TypeError):
                    tm_val = 15
                questions_data.append({"text": t, "time": tm_val})
            if not questions_data:
                questions_data = [{"text": "", "time": 15}]
    else:
        # Pre-generate suggested code
        random_suffix = uuid.uuid4().hex[:6]
        suggested_key = f"quiz_{random_suffix}"
        form = SurveyForm(initial={
            "key": suggested_key,
            "active": True,
            "is_public": True,
        })
        questions_data = [{"text": "", "time": 15}]

    return render(request, "main/teacher/test_form.html", {
        "form": form,
        "questions_data": questions_data,
        "is_create": True,
    })


@login_required
def teacher_test_edit_view(request: HttpRequest, survey_id: int) -> HttpResponse:
    """
    Teacher CRUD: Edit an existing test / survey.
    """
    if not _can_manage_tests(request.user):
        return HttpResponseForbidden("Доступ дозволено лише викладачам та адміністраторам.")

    survey = get_object_or_404(Survey, id=survey_id)

    if request.method == "POST":
        form = SurveyForm(data=request.POST, instance=survey)
        if form.is_valid():
            survey = form.save(commit=True, author=survey.author or request.user)
            ActivityLog.objects.create(
                user=request.user,
                action=ActivityLog.ACTION_SURVEY_UPDATE,
                details=f"Викладач {request.user.username} оновив тест '{survey.title or survey.key}' ({survey.key}).",
                metadata={"survey_key": survey.key, "title": survey.title}
            )
            messages.success(request, f"Тест '{survey.title or survey.key}' успішно оновлено!")
            return redirect("teacher_tests_list")
        else:
            q_texts = request.POST.getlist("question_text")
            q_times = request.POST.getlist("question_time")
            questions_data = []
            for t, tm in zip(q_texts, q_times):
                try:
                    tm_val = int(tm)
                except (ValueError, TypeError):
                    tm_val = 15
                questions_data.append({"text": t, "time": tm_val})
            if not questions_data:
                questions_data = [{"text": "", "time": 15}]
    else:
        form = SurveyForm(instance=survey)
        questions_data = survey.exam_questions
        if not questions_data:
            questions_data = [{"text": "", "time": getattr(survey, "answer_time_sec", 15) or 15}]

    return render(request, "main/teacher/test_form.html", {
        "form": form,
        "survey": survey,
        "questions_data": questions_data,
        "is_create": False,
    })


@login_required
def teacher_test_delete_view(request: HttpRequest, survey_id: int) -> HttpResponse:
    """
    Teacher CRUD: Delete or deactivate an existing test.
    Handles foreign key protect constraint gracefully.
    """
    if not _can_manage_tests(request.user):
        return HttpResponseForbidden("Доступ дозволено лише викладачам та адміністраторам.")

    survey = get_object_or_404(Survey, id=survey_id)
    sessions_count = survey.sessions.count()

    if request.method == "POST":
        action = request.POST.get("action", "delete")

        if action == "deactivate":
            survey.active = False
            survey.save(update_fields=["active"])
            ActivityLog.objects.create(
                user=request.user,
                action=ActivityLog.ACTION_SURVEY_UPDATE,
                details=f"Викладач {request.user.username} деактивував тест '{survey.title or survey.key}'.",
                metadata={"survey_key": survey.key}
            )
            messages.info(request, f"Тест '{survey.title or survey.key}' деактивовано (нові проходження заблоковано).")
            return redirect("teacher_tests_list")

        # Full deletion
        survey_title = survey.title or survey.key
        if sessions_count > 0:
            survey.sessions.all().delete()

        survey.delete()
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.ACTION_SURVEY_DELETE,
            details=f"Викладач {request.user.username} видалив тест '{survey_title}'.",
        )
        messages.success(request, f"Тест '{survey_title}' успішно видалено.")
        return redirect("teacher_tests_list")

    return render(request, "main/teacher/test_confirm_delete.html", {
        "survey": survey,
        "sessions_count": sessions_count,
    })


@login_required
def teacher_test_assign_view(request: HttpRequest, survey_id: int) -> HttpResponse:
    """
    Assign a test to individual students or an academic group.
    """
    if not _can_manage_tests(request.user):
        return HttpResponseForbidden("Доступ дозволено лише викладачам та адміністраторам.")

    survey = get_object_or_404(Survey, id=survey_id)

    if request.method == "POST":
        form = TestAssignmentForm(data=request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            assign_type = cd["assign_type"]
            due_date = cd.get("due_date")
            notes = cd.get("notes", "").strip()

            if assign_type == TestAssignmentForm.ASSIGN_STUDENT:
                students = cd.get("students") or []
                created_count = 0
                for st_user in students:
                    obj, created = TestAssignment.objects.get_or_create(
                        survey=survey,
                        student=st_user,
                        defaults={
                            "assigned_by": request.user,
                            "due_date": due_date,
                            "notes": notes,
                        }
                    )
                    if not created:
                        obj.due_date = due_date
                        obj.notes = notes
                        obj.assigned_by = request.user
                        obj.save()
                    created_count += 1

                ActivityLog.objects.create(
                    user=request.user,
                    action=ActivityLog.ACTION_SURVEY_ASSIGN,
                    details=f"Викладач {request.user.username} призначив тест '{survey.title or survey.key}' для {created_count} студентів.",
                    metadata={"survey_key": survey.key, "students_count": created_count}
                )
                messages.success(request, f"Тест успішно призначено для {created_count} студентів!")

            elif assign_type == TestAssignmentForm.ASSIGN_GROUP:
                group = cd["group"].strip()
                TestAssignment.objects.create(
                    survey=survey,
                    group=group,
                    assigned_by=request.user,
                    due_date=due_date,
                    notes=notes,
                )
                ActivityLog.objects.create(
                    user=request.user,
                    action=ActivityLog.ACTION_SURVEY_ASSIGN,
                    details=f"Викладач {request.user.username} призначив тест '{survey.title or survey.key}' академічній групі {group}.",
                    metadata={"survey_key": survey.key, "group": group}
                )
                messages.success(request, f"Тест успішно призначено для академічної групи '{group}'!")

            return redirect("teacher_test_assign", survey_id=survey.id)
    else:
        form = TestAssignmentForm()

    # Existing assignments for this survey
    assignments = survey.assignments.select_related("student", "assigned_by", "student__profile").order_by("-created_at")

    # Available known groups
    existing_groups = sorted([
        g for g in UserProfile.objects.exclude(group="").values_list("group", flat=True).distinct() if g
    ])

    return render(request, "main/teacher/test_assign.html", {
        "survey": survey,
        "form": form,
        "assignments": assignments,
        "existing_groups": existing_groups,
    })


@login_required
def teacher_assignment_delete_view(request: HttpRequest, assignment_id: int) -> HttpResponse:
    """
    Revoke / delete an existing assignment.
    """
    if not _can_manage_tests(request.user):
        return HttpResponseForbidden("Доступ дозволено лише викладачам та адміністраторам.")

    assignment = get_object_or_404(TestAssignment, id=assignment_id)
    survey_id = assignment.survey.id
    target_str = assignment.student.username if assignment.student else f"група {assignment.group}"

    assignment.delete()
    messages.info(request, f"Призначення для {target_str} скасовано.")
    return redirect("teacher_test_assign", survey_id=survey_id)
