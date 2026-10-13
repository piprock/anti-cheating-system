import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from main.models import Survey, TestAssignment, UserProfile, InterviewSession
from main.forms import SurveyForm


@pytest.fixture
def teacher_user(db):
    user = User.objects.create_user(
        username="prof_shevchenko",
        password="password123",
        first_name="Тарас",
        last_name="Шевченко"
    )
    user.profile.role = UserProfile.ROLE_TEACHER
    user.profile.middle_name = "Григорович"
    user.profile.save()
    return user


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        username="student_lesya",
        password="password123",
        first_name="Леся",
        last_name="Українка"
    )
    user.profile.role = UserProfile.ROLE_STUDENT
    user.profile.middle_name = "Петрівна"
    user.profile.group = "КН-21"
    user.profile.save()
    return user


@pytest.fixture
def sample_survey(db, teacher_user):
    survey = Survey.objects.create(
        key="math_test",
        title="Тест з математики",
        description="Перевірка знань з вищої математики",
        author=teacher_user,
        control_questions=[
            SurveyForm.DEFAULT_INTRO_QUESTION,
            "Скільки буде 2 + 2?",
            "Що таке інтеграл?"
        ],
        answer_time_sec=20,
        active=True,
        is_public=True
    )
    return survey


@pytest.mark.django_db
def test_tests_catalog_ui_cleanliness(client, teacher_user, sample_survey):
    """
    На /tests/ для викладача прибрати 3 кнопки (Створити тест, Панель викладача (CRUD), На головну).
    Для всіх: у списку тестів прибрати лейбли Час та Пройдено.
    Кнопки assign та edit мають однаковий розмір із 'Пройти тестування'.
    """
    client.force_login(teacher_user)
    resp = client.get(reverse("tests_list"))
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    # Перевірка: особливі кнопки викладача в шапці /tests/ прибрані
    assert "Панель викладача (CRUD)" not in html
    assert "На головну" not in html
    # Шапка не містить кнопку створення тесту
    assert '<a href="/teacher/tests/create/" class="table-btn"' not in html

    # Перевірка: у списку карток тестів немає лейблів 'Час' та 'Пройдено'
    assert "с./пит." not in html
    assert "разів" not in html
    assert "Час: " not in html
    assert "Пройдено: " not in html

    # Перевірка: кнопки мають спільний клас та розмір
    assert "test-card-action-btn" in html
    assert "Пройти тестування" in html
    # Текст у кнопках прибрано, тільки іконки з підказками
    assert "<span>Призначити</span>" not in html
    assert "<span>Редагувати</span>" not in html
    assert 'title="Призначити студентам"' in html
    assert 'title="Редагувати тест"' in html

    # Перевірка: при відсутності опису відображається плейсхолдер
    sample_survey.description = ""
    sample_survey.save()
    resp_nodesc = client.get(reverse("tests_list"))
    assert "Опис тесту відсутній." in resp_nodesc.content.decode("utf-8")


@pytest.mark.django_db
def test_teacher_tests_panel_ui(client, teacher_user, sample_survey):
    """
    На /teacher/tests/:
    - Прибрати 'Особистий кабінет' та 'Каталог для студентів'
    - У слові 'Створити тест' прибрати '+'
    - Кнопка 'Створити тест' розміщена праворуч і велика
    - Напис 'Панель викладача' прибрано
    """
    client.force_login(teacher_user)
    resp = client.get(reverse("teacher_tests_list"))
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    # Перевірка: у шапці сторінки керування тестами немає кнопок переходу до кабінету чи каталогу
    assert "Каталог для студентів" not in html
    assert "Панель викладача" not in html

    # Кнопка 'Створити тест' не містить плюсика у тексті (+ Створити тест)
    assert "+ Створити тест" not in html
    assert "+Створити тест" not in html
    assert "<span>Створити тест</span>" in html


@pytest.mark.django_db
def test_navigation_my_tests(client, teacher_user, student_user):
    """
    В навігації має бути посилання 'Мої тести' для викладача.
    """
    client.force_login(teacher_user)
    resp = client.get(reverse("main"))
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    assert "Мої тести" in html
    assert reverse("teacher_tests_list") in html

    # Для студента посилання на керування тестами в навігації відсутнє
    client.force_login(student_user)
    resp_student = client.get(reverse("main"))
    html_student = resp_student.content.decode("utf-8")
    assert 'href="/teacher/tests/"' not in html_student


@pytest.mark.django_db
def test_exam_prefill_and_intro_question(client, student_user, sample_survey):
    """
    Вступне запитання не змінюється, а якщо користувач авторизований,
    поле ПІБ на сторінці екзамену автоматично заповнюється.
    """
    client.force_login(student_user)
    resp = client.get(reverse("exam_page", kwargs={"key": sample_survey.key}))
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    # ПІБ студента заповнено
    assert student_user.profile.full_name in html
    assert 'value="Шевченко' not in html
    assert 'value="Українка Леся Петрівна"' in html


@pytest.mark.django_db
def test_survey_create_with_individual_times(client, teacher_user):
    """
    Створення тесту викладачем: кожне запитання має власне поле та окремий ліміт часу.
    Вступне запитання додається автоматично.
    """
    client.force_login(teacher_user)
    create_url = reverse("teacher_test_create")

    # Перевірка форми на сторінці створення: є картка запитання та поле часу для нього
    get_resp = client.get(create_url)
    assert get_resp.status_code == 200
    get_html = get_resp.content.decode("utf-8")
    assert "question_text" in get_html
    assert "question_time" in get_html
    assert "Додати запитання" in get_html

    data = {
        "title": "Новий тест з фізики",
        "key": "physics_101",
        "description": "Тест з механіки",
        "question_text": ["Що таке перший закон Ньютона?", "Що таке швидкість світла?"],
        "question_time": [25, 45],
        "active": True,
        "is_public": True
    }
    resp = client.post(create_url, data)
    assert resp.status_code == 302

    created_survey = Survey.objects.get(key="physics_101")
    assert created_survey.author == teacher_user
    assert len(created_survey.control_questions) == 3

    # Перше (вступне) запитання
    assert created_survey.control_questions[0]["text"] == SurveyForm.DEFAULT_INTRO_QUESTION
    # Індивідуальні запитання з власним часом
    assert created_survey.control_questions[1]["text"] == "Що таке перший закон Ньютона?"
    assert created_survey.control_questions[1]["time"] == 25
    assert created_survey.control_questions[2]["text"] == "Що таке швидкість світла?"
    assert created_survey.control_questions[2]["time"] == 45


@pytest.mark.django_db
def test_teacher_assign_test_flow(client, teacher_user, student_user, sample_survey):
    """
    Викладач може призначити тест студентові або групі.
    """
    client.force_login(teacher_user)
    assign_url = reverse("teacher_test_assign", kwargs={"survey_id": sample_survey.id})

    # Призначення студентові
    resp = client.post(assign_url, {
        "assign_type": "student",
        "students": [student_user.id],
        "notes": "Виконати до п'ятниці",
    })
    assert resp.status_code == 302
    assert TestAssignment.objects.filter(survey=sample_survey, student=student_user).exists()

    # Студент бачить призначений тест
    client.force_login(student_user)
    tests_resp = client.get(reverse("tests_list"))
    assert tests_resp.status_code == 200
    html = tests_resp.content.decode("utf-8")
    assert "Призначені вам завдання" in html
    assert "Виконати до п&#x27;ятниці" in html or "Виконати до п'ятниці" in html


@pytest.mark.django_db
def test_teacher_delete_or_deactivate_flow(client, teacher_user, sample_survey):
    """
    Видалення або деактивація тесту викладачем.
    """
    client.force_login(teacher_user)
    delete_url = reverse("teacher_test_delete", kwargs={"survey_id": sample_survey.id})

    # Перевірка сторінки підтвердження
    get_resp = client.get(delete_url)
    assert get_resp.status_code == 200
    assert "Ви впевнені, що хочете видалити тест?" in get_resp.content.decode("utf-8")

    # Деактивація
    post_resp = client.post(delete_url, {"action": "deactivate"})
    assert post_resp.status_code == 302
    sample_survey.refresh_from_db()
    assert sample_survey.active is False

    # Остаточне видалення
    post_delete = client.post(delete_url, {"action": "delete"})
    assert post_delete.status_code == 302
    assert not Survey.objects.filter(id=sample_survey.id).exists()
