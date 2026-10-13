import os
import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.management import call_command

from main.models import (
    UserProfile,
    Student,
    Survey,
    InterviewSession,
    Answer,
    ActivityLog,
    TeacherApplication,
)
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


@pytest.mark.django_db
def test_settings_page_view_and_tabs(client):
    user = User.objects.create_user(
        username="settings_user",
        password="password123",
        first_name="Іван",
        last_name="Котляревський",
    )
    user.profile.group = "КН-11"
    user.profile.save()

    # Anonymous user redirected to login
    anon_res = client.get(reverse("settings"))
    assert anon_res.status_code == 302
    assert "/login/" in anon_res.url

    # Authenticated student access
    client.force_login(user)
    res = client.get(reverse("settings"))
    assert res.status_code == 200
    content = res.content.decode("utf-8")

    # Has 3 tabs and layout
    assert "settings-layout" in content
    assert "Редагувати профіль" in content
    assert "Статус викладача" in content
    assert "Безпека та пароль" in content
    assert "panel-profile" in content
    assert "panel-teacher" in content
    assert "panel-security" in content

    # Header dropdown contains settings link
    main_res = client.get(reverse("main"))
    assert reverse("settings") in main_res.content.decode("utf-8")


@pytest.mark.django_db
def test_settings_profile_update(client):
    user = User.objects.create_user(
        username="updater_user",
        password="password123",
        first_name="СтареІмя",
        last_name="СтареПрізвище",
    )
    user.profile.middle_name = "СтареПоБатькові"
    user.profile.group = "СТ-01"
    user.profile.save()
    Student.objects.create(user=user, first_name="СтареІмя", last_name="СтареПрізвище", group="СТ-01")

    client.force_login(user)
    post_data = {
        "form_action": "profile",
        "first_name": "НовеІмя",
        "last_name": "НовеПрізвище",
        "middle_name": "НовеПоБатькові",
        "group": "КІ-42",
        "email": "new_email@avatar.ai",
    }
    res = client.post(reverse("settings"), post_data, follow=True)
    assert res.status_code == 200

    user.refresh_from_db()
    assert user.first_name == "НовеІмя"
    assert user.last_name == "НовеПрізвище"
    assert user.email == "new_email@avatar.ai"
    assert user.profile.middle_name == "НовеПоБатькові"
    assert user.profile.group == "КІ-42"

    # Synchronized with Student record
    student = Student.objects.get(user=user)
    assert student.first_name == "НовеІмя"
    assert student.group == "КІ-42"

    # Activity log created
    log = ActivityLog.objects.filter(user=user, action=ActivityLog.ACTION_PROFILE_UPDATE).first()
    assert log is not None


@pytest.mark.django_db
def test_settings_teacher_application_flow_and_admin_review(client):
    # 1. Student registers and applies for teacher role
    student_user = User.objects.create_user(
        username="aspirant_petro",
        password="password123",
        first_name="Петро",
        last_name="Могила",
    )
    student_user.profile.group = "АСП-2"
    student_user.profile.save()

    client.force_login(student_user)

    # Submit teacher application
    app_data = {
        "form_action": "teacher_application",
        "department": "Кафедра штучного інтелекту",
        "position": "Асистент",
        "phone": "+380501112233",
        "reason": "Проведення лабораторних іспитів з комп'ютерного зору",
    }
    apply_res = client.post(reverse("settings"), app_data, follow=True)
    assert apply_res.status_code == 200
    res_text = apply_res.content.decode("utf-8")
    assert "Заявку на отримання статусу" in res_text
    assert "успішно надіслано" in res_text

    # Application record exists
    app = TeacherApplication.objects.filter(user=student_user).first()
    assert app is not None
    assert app.status == TeacherApplication.STATUS_PENDING
    assert app.department == "Кафедра штучного інтелекту"
    assert app.position == "Асистент"

    # Activity log recorded
    log = ActivityLog.objects.filter(user=student_user, action=ActivityLog.ACTION_TEACHER_REQUEST).first()
    assert log is not None

    # Tab shows pending banner
    settings_res = client.get(f"{reverse('settings')}?tab=teacher")
    assert "Ваша заявка знаходиться на розгляді адміністратора" in settings_res.content.decode("utf-8")

    # 2. Admin reviews and approves the application
    admin_user = User.objects.create_superuser(
        username="sysadmin",
        password="adminpassword123",
        email="admin@avatar.ai",
    )
    client.force_login(admin_user)

    # Admin dashboard displays pending application
    dash_res = client.get(reverse("dashboard"))
    assert "Заявки на статус викладача" in dash_res.content.decode("utf-8")
    assert "aspirant_petro" in dash_res.content.decode("utf-8")

    # Admin approves
    approve_res = client.post(
        reverse("review_teacher_application", kwargs={"app_id": app.id}),
        {"action": "approve", "notes": "Документи підтверджено"},
        follow=True
    )
    assert approve_res.status_code == 200

    app.refresh_from_db()
    assert app.status == TeacherApplication.STATUS_APPROVED
    assert app.reviewed_by == admin_user
    student_user.refresh_from_db()
    assert student_user.profile.role == UserProfile.ROLE_TEACHER
    assert student_user.profile.is_teacher is True

    # 3. Student visits settings: now shows active teacher privileges banner
    client.force_login(student_user)
    student_settings = client.get(f"{reverse('settings')}?tab=teacher")
    assert student_settings.status_code == 200
    student_text = student_settings.content.decode("utf-8")
    assert "Ваш акаунт має статус" in student_text
    assert "Викладач" in student_text
    assert "Доступні викладацькі функції в системі" in student_text
    assert "teacher-bullet-list" in student_text
    assert "settings-user-card" not in student_text

    # 4. Admin also has active teacher status badge and banner
    client.force_login(admin_user)
    admin_settings = client.get(f"{reverse('settings')}?tab=teacher")
    assert admin_settings.status_code == 200
    admin_text = admin_settings.content.decode("utf-8")
    assert "Активна" in admin_text
    assert "Ваш акаунт має статус" in admin_text
    assert "Викладач" in admin_text


@pytest.mark.django_db
def test_settings_teacher_application_cancellation(client):
    user = User.objects.create_user(username="canceller", password="password123")
    client.force_login(user)

    # Submit application
    client.post(reverse("settings"), {
        "form_action": "teacher_application",
        "department": "Кафедра ПЗ",
        "position": "Викладач",
        "reason": "Тест",
    }, follow=True)

    app = TeacherApplication.objects.filter(user=user).first()
    assert app.status == TeacherApplication.STATUS_PENDING

    # Cancel application
    cancel_res = client.post(reverse("settings"), {
        "form_action": "cancel_teacher_application",
    }, follow=True)
    assert cancel_res.status_code == 200
    assert "Заявку на отримання статусу викладача скасовано" in cancel_res.content.decode("utf-8")

    app.refresh_from_db()
    assert app.status == TeacherApplication.STATUS_CANCELLED


@pytest.mark.django_db
def test_settings_change_password(client):
    user = User.objects.create_user(username="pass_user", password="oldPassword123!")
    client.force_login(user)

    res = client.post(reverse("settings"), {
        "form_action": "change_password",
        "old_password": "oldPassword123!",
        "new_password1": "newSecurePassword456!",
        "new_password2": "newSecurePassword456!",
    }, follow=True)
    assert res.status_code == 200
    assert "Пароль успішно змінено!" in res.content.decode("utf-8")

    user.refresh_from_db()
    assert user.check_password("newSecurePassword456!") is True



