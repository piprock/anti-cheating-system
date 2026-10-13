"""
Validation extremes and limits (file sizes, lengths, timeouts).
"""

# Розміри файлів у байтах
MAX_AUDIO_FILE_BYTES: int = 25 * 1024 * 1024       # 25 MB
MAX_DOC_FILE_BYTES: int = 10 * 1024 * 1024         # 10 MB

# Обмеження рядків аутентифікації
MIN_USERNAME_LEN: int = 3
MAX_USERNAME_LEN: int = 150
MIN_PASSWORD_LEN: int = 6
MAX_PASSWORD_LEN: int = 128
MAX_NAME_LEN: int = 100
MAX_GROUP_LEN: int = 50

# Обмеження відповідей
MIN_VOICE_ANSWER_CHARS: int = 5
MAX_SESSION_DURATION_SEC: int = 5 * 60             # 5 хвилин максимум

__all__ = [
    "MAX_AUDIO_FILE_BYTES",
    "MAX_DOC_FILE_BYTES",
    "MIN_USERNAME_LEN",
    "MAX_USERNAME_LEN",
    "MIN_PASSWORD_LEN",
    "MAX_PASSWORD_LEN",
    "MAX_NAME_LEN",
    "MAX_GROUP_LEN",
    "MIN_VOICE_ANSWER_CHARS",
    "MAX_SESSION_DURATION_SEC",
]
