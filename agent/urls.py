"""
URL configuration for agent project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path
from django.views.generic.base import RedirectView
from main import exam_extra
from main.handlers import (
    main as main_view,
    gaze_view,
    about,
    contact,
    record_and_respond,
    anylize_file,
    exam_page,
    gaze_stats,
    gaze_reset,
    submit_interview,
)
from main.gaze import gaze_frame
from main.exam_controller import exam_start, exam_answer
from main.auth_views import (
    login_view,
    logout_view,
    register_view,
    dashboard_view,
    session_detail_view,
    profile_edit_view,
    settings_view,
    review_teacher_application_view,
)
from main.survey_views import (
    tests_list_view,
    teacher_tests_list_view,
    teacher_test_create_view,
    teacher_test_edit_view,
    teacher_test_delete_view,
    teacher_test_assign_view,
    teacher_assignment_delete_view,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('favicon.ico', RedirectView.as_view(url='/static/images/icon.ico', permanent=True)),
    path('', main_view, name="main"),
    path('gaze/', gaze_view, name="gaze"),
    path('about/', about, name="about"),
    path('contact/', contact, name="contact"),
    path('record/', record_and_respond, name="record_and_respond"),
    path('anylizefile/', anylize_file, name="anylize_file"),

    # Авторизація, реєстрація, налаштування та кабінет
    path('login/', login_view, name="login"),
    path('logout/', logout_view, name="logout"),
    path('register/', register_view, name="register"),
    path('dashboard/', dashboard_view, name="dashboard"),
    path('profile/', dashboard_view, name="profile"),
    path('settings/', settings_view, name="settings"),
    path('settings/review/<int:app_id>/', review_teacher_application_view, name="review_teacher_application"),
    path('profile/edit/', profile_edit_view, name="profile_edit"),
    path('session/<int:session_id>/', session_detail_view, name="session_detail"),

    # Тести: публічний каталог та панель керування викладача
    path('tests/', tests_list_view, name='tests_list'),
    path('teacher/tests/', teacher_tests_list_view, name='teacher_tests_list'),
    path('teacher/tests/create/', teacher_test_create_view, name='teacher_test_create'),
    path('teacher/tests/<int:survey_id>/edit/', teacher_test_edit_view, name='teacher_test_edit'),
    path('teacher/tests/<int:survey_id>/delete/', teacher_test_delete_view, name='teacher_test_delete'),
    path('teacher/tests/<int:survey_id>/assign/', teacher_test_assign_view, name='teacher_test_assign'),
    path('teacher/assignments/<int:assignment_id>/delete/', teacher_assignment_delete_view, name='teacher_assignment_delete'),

    # Проходження тестування та моніторинг
    path('exam/<str:key>/', exam_page, name='exam_page'),
    path('gaze/frame/', gaze_frame, name='gaze_frame'),
    path('api/submit_interview/<str:key>/', submit_interview, name='submit_interview'),
    path('api/gaze/stats/<str:sid>/', gaze_stats, name='gaze_stats'),
    path('api/gaze/reset/<str:sid>/', gaze_reset, name='gaze_reset'),

    # Інтерактивний діалог
    path('api/exam/start/<str:key>/', exam_start, name='exam_start'),
    path('api/exam/answer/<str:key>/', exam_answer, name='exam_answer'),
    path('api/exam/voice_answer/<str:key>/', exam_extra.exam_voice_answer_upload, name='exam_voice_answer'),
    path('api/exam/speak/<str:key>/', exam_extra.exam_speak_current_question, name='exam_speak_current_question'),
    path('api/exam/export/<int:session_id>/', exam_extra.exam_export_session, name='exam_export_session'),
]
