import os
import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.management import call_command

from main.models import UserProfile, Student, Survey, InterviewSession, Answer, ActivityLog
from main.persist import persist_session_from_payload
from main.management.commands.seed_admin import seed_admin_user


@pytest.mark.django_db
def test_user_profile_creation_and_roles():
    # Regular user gets student role by default
    user = User.objects.create_user(username="student1", password="password123", first_name="Іван", last_name="Франко")
    assert hasattr(user, "profile")
    assert user.profile.role == UserProfile.ROLE_STUDENT
    assert user.profile.is_student is True
    assert user.profile.is_teacher is False
    assert user.profile.is_admin is False
    assert user.profile.full_name == "Франко Іван"

    # Superuser gets admin role
    admin_user = User.objects.create_superuser(username="admin1", password="password123", email="admin@avatar.ai")
    assert admin_user.profile.role == UserProfile.ROLE_ADMIN
    assert admin_user.profile.is_admin is True

    # Teacher role
    teacher = User.objects.create_user(username="teacher1", password="password123")
    teacher.profile.role = UserProfile.ROLE_TEACHER
    teacher.profile.save()
    assert teacher.profile.is_teacher is True


@pytest.mark.django_db
def test_seed_admin_command(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "supertestadmin")
    monkeypatch.setenv("ADMIN_PASSWORD", "testpass999")
    monkeypatch.setenv("ADMIN_EMAIL", "testadmin@avatar.ai")

    res = seed_admin_user()
    assert res is True

    admin_user = User.objects.get(username="supertestadmin")
    assert admin_user.is_superuser is True
    assert admin_user.is_staff is True
    assert admin_user.profile.role == UserProfile.ROLE_ADMIN
    assert admin_user.check_password("testpass999") is True

    # Calling management command
    call_command("seed_admin")


@pytest.mark.django_db
def test_registration_view(client):
    url = reverse("register")
    response = client.get(url)
    assert response.status_code == 200

    data = {
        "username": "newstudent",
        "email": "student@example.com",
        "last_name": "Шевченко",
        "first_name": "Тарас",
        "middle_name": "Григорович",
        "group": "КН-21",
        "password": "strongpassword123",
        "password_confirm": "strongpassword123",
    }
    post_res = client.post(url, data, follow=True)
    assert post_res.status_code == 200

    user = User.objects.get(username="newstudent")
    assert user.first_name == "Шевченко" or user.last_name == "Шевченко"
    assert user.profile.role == UserProfile.ROLE_STUDENT
    assert user.profile.group == "КН-21"
    assert user.profile.middle_name == "Григорович"

    # Student model record was created as well
    student = Student.objects.filter(user=user).first()
    assert student is not None
    assert student.group == "КН-21"


@pytest.mark.django_db
def test_login_and_logout_views(client):
    user = User.objects.create_user(username="testuser", password="password123")
    login_url = reverse("login")

    # Invalid login
    res_bad = client.post(login_url, {"username": "testuser", "password": "wrong"})
    assert res_bad.status_code == 200
    assert "_auth_user_id" not in client.session

    # Valid login
    res_good = client.post(login_url, {"username": "testuser", "password": "password123"}, follow=True)
    assert res_good.status_code == 200
    assert client.session["_auth_user_id"] == str(user.id)

    # Activity log for login recorded
    login_log = ActivityLog.objects.filter(user=user, action=ActivityLog.ACTION_LOGIN).first()
    assert login_log is not None

    # Logout
    logout_url = reverse("logout")
    res_logout = client.get(logout_url, follow=True)
    assert res_logout.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_dashboard_and_exam_history(client):
    user = User.objects.create_user(username="student_dash", password="password123", first_name="Леся", last_name="Українка")
    user.profile.group = "ІПЗ-31"
    user.profile.save()

    survey = Survey.objects.create(key="history_survey", title="Тест з історії", control_questions=["ПІБ", "Q1"])

    # Create exam session tied to user
    payload = {
        "user_id": user.id,
        "student": {"first_name": "Леся", "last_name": "Українка", "middle_name": "Петрівна"},
        "answers": [
            {"question": "Q1", "answer": "A1", "accuracy_score": 85, "feedback": "Гарно"},
        ],
        "summary": {"dialogue_result": "Чудова робота", "overall_accuracy": 85, "plagiarism_score": 0},
    }
    saved = persist_session_from_payload(survey.key, payload)
    session_id = saved["session_id"]

    session = InterviewSession.objects.get(id=session_id)
    assert session.user == user
    assert session.overall_accuracy == 85

    # Check activity log for exam submit
    submit_log = ActivityLog.objects.filter(user=user, action=ActivityLog.ACTION_EXAM_SUBMIT).first()
    assert submit_log is not None

    # Access dashboard as authenticated student
    client.force_login(user)
    dash_res = client.get(reverse("dashboard"))
    assert dash_res.status_code == 200
    assert "history_survey" in dash_res.content.decode("utf-8")
    assert "85%" in dash_res.content.decode("utf-8")

    # Access session detail as student
    detail_url = reverse("session_detail", kwargs={"session_id": session_id})
    detail_res = client.get(detail_url)
    assert detail_res.status_code == 200
    assert "Чудова робота" in detail_res.content.decode("utf-8")

    # Other student cannot view this session
    other_student = User.objects.create_user(username="other", password="password123")
    client.force_login(other_student)
    forbidden_res = client.get(detail_url)
    assert forbidden_res.status_code == 403

    # Teacher CAN view this session
    teacher = User.objects.create_user(username="teacher_view", password="password123")
    teacher.profile.role = UserProfile.ROLE_TEACHER
    teacher.profile.save()
    client.force_login(teacher)
    teacher_res = client.get(detail_url)
    assert teacher_res.status_code == 200


@pytest.mark.django_db
def test_profile_edit_view(client):
    user = User.objects.create_user(username="editor", password="password123", first_name="Старе", last_name="Прізвище")
    client.force_login(user)

    url = reverse("profile_edit")
    get_res = client.get(url)
    assert get_res.status_code == 200

    post_res = client.post(url, {
        "first_name": "НовеІмя",
        "last_name": "НовеПрізвище",
        "middle_name": "НовеПоБатькові",
        "group": "КН-99",
        "email": "updated@example.com",
    }, follow=True)
    assert post_res.status_code == 200

    user.refresh_from_db()
    assert user.first_name == "НовеІмя"
    assert user.last_name == "НовеПрізвище"
    assert user.profile.middle_name == "НовеПоБатькові"
    assert user.profile.group == "КН-99"
    assert user.email == "updated@example.com"


@pytest.mark.django_db
def test_two_step_registration_flow(client):
    url = reverse("register")

    # Step 1 GET: Initial step
    res_step1_get = client.get(url)
    assert res_step1_get.status_code == 200
    assert "Етап 1 з 2" in res_step1_get.content.decode("utf-8")
    assert "Реєстрація студента" in res_step1_get.content.decode("utf-8")

    # Step 1 POST: Send login, email, password, password confirmation
    step1_data = {
        "step": "1",
        "username": "stepstudent",
        "email": "step@example.com",
        "password": "SecretPassword123!",
        "password_confirm": "SecretPassword123!",
    }
    res_step1_post = client.post(url, step1_data, follow=True)
    assert res_step1_post.status_code == 200
    # Must redirect or advance to Step 2
    assert "Етап 2 з 2" in res_step1_post.content.decode("utf-8")
    assert "Персональні дані" in res_step1_post.content.decode("utf-8")
    assert client.session.get("reg_step1") is not None
    assert client.session["reg_step1"]["username"] == "stepstudent"

    # Step 2 POST: Send name, group
    step2_data = {
        "step": "2",
        "last_name": "Коваленко",
        "first_name": "Олександр",
        "middle_name": "Сергійович",
        "group": "КІ-32",
    }
    res_step2_post = client.post(url, step2_data, follow=True)
    assert res_step2_post.status_code == 200

    # User created and logged in
    user = User.objects.get(username="stepstudent")
    assert user.last_name == "Коваленко"
    assert user.first_name == "Олександр"
    assert user.profile.middle_name == "Сергійович"
    assert user.profile.group == "КІ-32"
    assert user.email == "step@example.com"
    assert user.profile.is_student is True

    # Toast success message rendered in toast container
    content = res_step2_post.content.decode("utf-8")
    assert "toast toast--success" in content
    assert "Реєстрація успішна! Ласкаво просимо до Avatar AI." in content
    assert "profile-dropdown" in content


def test_const_package_exports():
    import const
    from const.errors import messages
    from const.validation import bounds
    from const.exam import metrics

    assert hasattr(const, "ERR_INVALID_CREDENTIALS")
    assert hasattr(const, "SUCCESS_REGISTRATION")
    assert hasattr(const, "MIN_PASSWORD_LEN")
    assert hasattr(const, "GAZE_PENALTY_THRESHOLD_PCT")

    assert messages.SUCCESS_REGISTRATION == "Реєстрація успішна! Ласкаво просимо до Avatar AI."
    assert bounds.MIN_PASSWORD_LEN == 6
    assert metrics.GAZE_PENALTY_THRESHOLD_PCT == 35.0


@pytest.mark.django_db
def test_header_two_rows_and_profile_dropdown(client):
    user = User.objects.create_user(
        username="vasyl_user",
        password="password123",
        first_name="Василь",
        last_name="Симоненко",
    )
    user.profile.group = "КН-10"
    user.profile.save()

    client.force_login(user)
    res = client.get(reverse("main"))
    assert res.status_code == 200
    content = res.content.decode("utf-8")

    # Header has 2 rows
    assert "header-topbar" in content
    assert "header-mainbar" in content

    # Row 1 has quick theme, a11y, and profile dropdown button with short name "Ім'я Прізвище"
    assert "themeQuickBtn" in content
    assert "a11yOpenBtn" in content
    assert "profileDropdownBtn" in content
    assert "Василь Симоненко" in content

    # Dropdown menu contains detailed info and logout button at bottom
    assert "profileDropdownMenu" in content
    assert "Вийти з системи" in content
    assert "profile-dropdown__item--logout" in content

    # "Кабінет" button removed from main navigation
    assert '<a class="" href="/dashboard/">Кабінет</a>' not in content
    assert "Особистий кабінет" in content  # Present in profile dropdown

    # Row 1 contains logo, subtitle removed
    assert "Avatar AI – Інтелектуальна система екзаменації" not in content
    assert "header-topbar__left" in content


@pytest.mark.django_db
def test_tooltips_on_dashboard_and_gaze(client):
    user = User.objects.create_user(
        username="tooltip_user",
        password="password123",
        first_name="Олена",
        last_name="Теліга",
    )
    client.force_login(user)

    # Dashboard tooltips
    dash_res = client.get(reverse("dashboard"))
    assert dash_res.status_code == 200
    dash_html = dash_res.content.decode("utf-8")
    assert 'data-tooltip="Успішно складено:' in dash_html
    assert 'data-tooltip="Шкала від 1 до 5"' in dash_html

    # Gaze monitoring tooltip
    gaze_res = client.get(reverse("gaze"))
    assert gaze_res.status_code == 200
    gaze_html = gaze_res.content.decode("utf-8")
    assert "Підказка: Зелене коло позначає виявлену область зіниці." in gaze_html
    assert "ui-tooltip" in gaze_html


