import os
import django
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agent.settings')
django.setup()

from django.contrib.auth.models import User
from main.models import UserProfile, Student, Survey, InterviewSession, Answer, ActivityLog

def populate():
    print("Clearing old test sessions and students...")
    InterviewSession.objects.all().delete()
    Answer.objects.all().delete()
    Student.objects.all().delete()
    ActivityLog.objects.all().delete()

    # Update teacher account piprock
    teacher_user, _ = User.objects.get_or_create(username="piprock")
    teacher_user.first_name = "Олександр"
    teacher_user.last_name = "Коваленко"
    teacher_user.email = "o.kovalenko@avatar-ai.edu"
    teacher_user.save()

    profile, _ = UserProfile.objects.get_or_create(user=teacher_user)
    profile.role = UserProfile.ROLE_TEACHER
    profile.middle_name = "Іванович"
    profile.group = "Кафедра ПІ"
    profile.save()

    # Create realistic Exam Survey
    survey, _ = Survey.objects.get_or_create(key="se_exam_kn31")
    survey.title = "Основи програмної інженерії (Екзамен)"
    survey.description = "Підсумковий усний екзамен для студентів групи КН-31. Дисципліна: Основи програмної інженерії."
    survey.author = teacher_user
    survey.answer_time_sec = 25
    survey.active = True
    survey.control_questions = [
        {"text": "Назвіть та поясніть принципи SOLID в об'єктно-орієнтованому проєктуванні.", "time": 25},
        {"text": "У чому полягає відмінність між патернами Factory Method та Abstract Factory?", "time": 25},
        {"text": "Поясніть концепцію рефакторингу коду та наведіть приклади запахів коду (code smells).", "time": 25},
        {"text": "Що таке безперервна інтеграція (CI) та які її основні етапи?", "time": 25},
        {"text": "Охарактеризуйте відмінності між юніт-тестуванням та інтеграційним тестуванням.", "time": 25},
    ]
    survey.save()

    # Also keep standard survey for reference
    s2, _ = Survey.objects.get_or_create(key="quiz_4b7c2d")
    s2.title = "Комп'ютерні мережі та безпека"
    s2.author = teacher_user
    s2.save()

    # Academic Cohort: 12 students from group КН-31
    # Durations between 9 and 14 mins (540s - 850s)
    # Grades: 5, 4, 5, 3, 4, 5, 4, 3, 2, 5, 4, 4
    cohort_data = [
        {"num": "01", "name": ("Максим", "Бондаренко", "Ігорович"), "dur": 685, "acc": 94, "plag": 6, "gaze": 7.4, "grade": 5, "susp": False},
        {"num": "02", "name": ("Анастасія", "Ковальчук", "Олегівна"), "dur": 742, "acc": 86, "plag": 11, "gaze": 10.2, "grade": 4, "susp": False},
        {"num": "03", "name": ("Дмитро", "Шевченко", "Сергійович"), "dur": 615, "acc": 92, "plag": 4, "gaze": 6.8, "grade": 5, "susp": False},
        {"num": "04", "name": ("Владислав", "Ткаченко", "Володимирович"), "dur": 810, "acc": 68, "plag": 14, "gaze": 12.5, "grade": 3, "susp": False},
        {"num": "05", "name": ("Софія", "Мельник", "Андріївна"), "dur": 690, "acc": 84, "plag": 8, "gaze": 8.9, "grade": 4, "susp": False},
        {"num": "06", "name": ("Ярослав", "Кравченко", "Васильович"), "dur": 630, "acc": 96, "plag": 5, "gaze": 5.4, "grade": 5, "susp": False},
        {"num": "07", "name": ("Богдан", "Олійник", "Миколайович"), "dur": 755, "acc": 82, "plag": 9, "gaze": 11.0, "grade": 4, "susp": False},
        {"num": "08", "name": ("Дарина", "Поліщук", "Олександрівна"), "dur": 595, "acc": 65, "plag": 15, "gaze": 14.2, "grade": 3, "susp": False},
        {"num": "09", "name": ("Артем", "Мороз", "Денисович"), "dur": 845, "acc": 44, "plag": 38, "gaze": 39.4, "grade": 2, "susp": True},
        {"num": "10", "name": ("Вікторія", "Лисенко", "Тарасівна"), "dur": 670, "acc": 91, "plag": 7, "gaze": 8.1, "grade": 5, "susp": False},
        {"num": "11", "name": ("Роман", "Клименко", "Олексійович"), "dur": 725, "acc": 85, "plag": 10, "gaze": 9.6, "grade": 4, "susp": False},
        {"num": "12", "name": ("Юлія", "Савченко", "Петрівна"), "dur": 660, "acc": 79, "plag": 8, "gaze": 11.2, "grade": 4, "susp": False},
    ]

    base_time = datetime(2024, 5, 24, 9, 15, 0)

    for i, data in enumerate(cohort_data):
        uname = f"student_{data['num']}"
        u, _ = User.objects.get_or_create(username=uname)
        u.first_name = data["name"][0]
        u.last_name = data["name"][1]
        u.save()

        p, _ = UserProfile.objects.get_or_create(user=u)
        p.middle_name = data["name"][2]
        p.group = "КН-31"
        p.role = UserProfile.ROLE_STUDENT
        p.save()

        st, _ = Student.objects.get_or_create(
            user=u,
            defaults={
                "first_name": data["name"][0],
                "last_name": data["name"][1],
                "middle_name": data["name"][2],
                "group": "КН-31",
            }
        )

        sess_start = base_time + timedelta(minutes=i * 22)
        sess_end = sess_start + timedelta(seconds=data["dur"])

        session = InterviewSession.objects.create(
            id=101 + i,
            user=u,
            student=st,
            survey=survey,
            started_at=sess_start,
            ended_at=sess_end,
            duration_sec=data["dur"],
            overall_accuracy=data["acc"],
            plagiarism_score=data["plag"],
            dialogue_result=f"Підсумок сесії студента {data['name'][1]} {data['name'][0]}. Точність: {data['acc']}%. Порушення: {'Виявлено значні девіації погляду' if data['susp'] else 'Не зафіксовано'}.",
            gaze_not_looking_pct=data["gaze"],
            grade_5=data["grade"],
            status="done"
        )

        # Create answers for session
        for q_idx, q_item in enumerate(survey.control_questions):
            Answer.objects.create(
                session=session,
                question=q_item["text"],
                answer=f"Відповідь студента на запитання №{q_idx+1} щодо теми {q_item['text'][:30]}...",
                accuracy_score=max(30, min(100, data["acc"] + (q_idx % 3 - 1) * 5)),
                feedback="Задовільне володіння термінологією, зміст розкрито коректно." if data["grade"] >= 4 else "Потребує глибшого аргументування понять.",
                question_order=q_idx + 1
            )

        ActivityLog.objects.create(
            user=u,
            action=ActivityLog.ACTION_EXAM_SUBMIT,
            details=f"Студент {st} успішно склав екзамен '{survey.title}'. Оцінка: {data['grade']}.",
            session=session,
            created_at=sess_end
        )

    print("Successfully populated 12 academic cohort sessions for group КН-31!")

if __name__ == "__main__":
    populate()
