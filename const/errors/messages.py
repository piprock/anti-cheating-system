"""
Centralized Error Messages and Codes.
"""

# Аутентифікація та реєстрація
ERR_INVALID_CREDENTIALS = "Невірний логін або пароль."
ERR_ACCOUNT_DISABLED = "Обліковий запис деактивовано."
ERR_USERNAME_TAKEN = "Користувач із таким логіном вже існує."
ERR_PASSWORD_MISMATCH = "Паролі не співпадають."
ERR_PASSWORD_TOO_SHORT = "Пароль повинен містити не менше 6 символів."
ERR_REQUIRED_FIELD = "Це поле є обов'язковим для заповнення."

# Файли та медіа
ERR_FILE_TOO_LARGE = "Файл занадто великий."
ERR_AUDIO_TOO_LARGE = "Файл аудіо занадто великий (макс. 25MB)."
ERR_DOCUMENT_TOO_LARGE = "Файл документа занадто великий (макс. 10MB)."
ERR_VOICE_CAPTURE_FAILED = "Помилка захоплення голосу з мікрофона."
ERR_VOICE_TOO_SHORT = "Занадто короткий голосовий запит."

# Екзаменаційна сесія
ERR_EXAM_NOT_STARTED = "Екзаменаційну сесію не знайдено або не розпочато."
ERR_NO_MORE_QUESTIONS = "Всі запитання екзамену вже вичерпано."
ERR_INVALID_JSON = "Некоректний формат JSON запиту."
ERR_SESSION_ACCESS_DENIED = "У вас немає доступу до цієї екзаменаційної сесії."

# Повідомлення успіху
SUCCESS_REGISTRATION = "Реєстрація успішна! Ласкаво просимо до Avatar AI."
SUCCESS_PROFILE_UPDATED = "Профіль успішно оновлено."
SUCCESS_LOGIN = "Вхід виконано успішно."

__all__ = [
    "ERR_INVALID_CREDENTIALS",
    "ERR_ACCOUNT_DISABLED",
    "ERR_USERNAME_TAKEN",
    "ERR_PASSWORD_MISMATCH",
    "ERR_PASSWORD_TOO_SHORT",
    "ERR_REQUIRED_FIELD",
    "ERR_FILE_TOO_LARGE",
    "ERR_AUDIO_TOO_LARGE",
    "ERR_DOCUMENT_TOO_LARGE",
    "ERR_VOICE_CAPTURE_FAILED",
    "ERR_VOICE_TOO_SHORT",
    "ERR_EXAM_NOT_STARTED",
    "ERR_NO_MORE_QUESTIONS",
    "ERR_INVALID_JSON",
    "ERR_SESSION_ACCESS_DENIED",
    "SUCCESS_REGISTRATION",
    "SUCCESS_PROFILE_UPDATED",
    "SUCCESS_LOGIN",
]

