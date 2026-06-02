"""
URL configuration for agent project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from main import exam_extra
from main.handlers import (
    main as main_view,
    about,
    contact,
    record_and_respond,
    anylize_file,
    exam_page,
    gaze_stats,
    submit_interview,
)
from main.gaze import gaze_frame
from main.exam_controller import exam_start, exam_answer

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', main_view, name="main"),
    path('about/', about, name="about"),
    path('contact/', contact, name="contact"),
    path('record/', record_and_respond, name="record_and_respond"),
    path('anylizefile/', anylize_file, name="anylize_file"),

    # існуюче:
    path('exam/<str:key>/', exam_page, name='exam_page'),
    path('gaze/frame/', gaze_frame, name='gaze_frame'),
    path('api/submit_interview/<str:key>/', submit_interview, name='submit_interview'),
    path('api/gaze/stats/<str:sid>/', gaze_stats, name='gaze_stats'),

    # НОВЕ: інтерактивний діалог
    path('api/exam/start/<str:key>/', exam_start, name='exam_start'),
    path('api/exam/answer/<str:key>/', exam_answer, name='exam_answer'),
    path('api/exam/voice_answer/<str:key>/', exam_extra.exam_voice_answer_upload, name='exam_voice_answer'),
    path('api/exam/speak/<str:key>/', exam_extra.exam_speak_current_question, name='exam_speak_current_question'),
    path('api/exam/export/<int:session_id>/', exam_extra.exam_export_session, name='exam_export_session'),
]
