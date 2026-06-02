# Copilot Instructions – Avatar (Django + AI Exam System)

Concise, project-specific guidance for AI coding agents working here.

## Core Structure
- `agent/` Django project config; `main/` holds app logic.
- Models (`main/models.py`): `Survey` (question list), `InterviewSession` (aggregated metrics + raw payload), `Answer` (per question), `Student` (ПІБ fields).
- **Service Layer Architecture (`main/services/`)**: All business logic encapsulated in testable service classes.
- **NEW:** All runtime state uses Django cache (thread/process-safe, persistent across restarts with Redis).
- Central logic split across modules:
  - `main/services/audio_service.py`: AudioService for recording, recognition (Whisper), TTS (ElevenLabs)
  - `main/services/gpt_service.py`: GPTService for chat, scoring, summarization (OpenAI)
  - `main/services/exam_service.py`: ExamService for exam state management, grading logic
  - `main/services/file_extractor.py`: FileExtractor for txt/csv/pdf/docx/rtf parsing
  - `main/services/gaze_service.py`: GazeService for gaze tracking, metrics calculation
  - `main/exam_controller.py`: exam endpoints using service layer
  - `main/handlers.py`: page views, chat, file analysis using service layer
  - `main/gaze.py`: gaze frame ingestion using GazeService
  - `main/cache_utils.py`: **unified cache interface for all session state**
  - `main/persist.py`: session persistence to database using services

## Service Layer Architecture

**All business logic encapsulated in testable service classes:**

### AudioService (`main/services/audio_service.py`)
- `record(duration, samplerate)` - Record audio from microphone
- `recognize(filename, language, model_name)` - Transcribe with Whisper
- `play_tts(text, voice_id, model_id)` - Text-to-speech with ElevenLabs

### GPTService (`main/services/gpt_service.py`)
- `chat(prompt, session_id, check)` - Chat with session memory
- `score_answer(question, user_answer)` - Score answer with JSON output
- `summarize_exam(qa_log)` - Summarize exam and detect plagiarism

### ExamService (`main/services/exam_service.py`)
- `start_exam(key, questions)` - Initialize exam session
- `get_exam_state(key)` / `save_exam_state(key, state)` - State management
- `get_current_question(state)` - Get current question
- `record_answer(state, answer, score, feedback)` - Record answer
- `build_session_payload(state, summary, accuracy, plagiarism)` - Build payload
- `compute_grade(accuracy, plagiarism, gaze_pct)` - Calculate final grade

### FileExtractor (`main/services/file_extractor.py`)
- `extract(uploaded_file, filename)` - Extract text from various formats
- Supports: TXT, CSV, PDF, DOCX, RTF with automatic encoding detection

### GazeService (`main/services/gaze_service.py`)
- `init_session(session_id)` - Initialize gaze session
- `increment_frame(session_id, not_looking)` - Increment counters
- `compute_not_looking_percent(session_id)` - Calculate percentage
- `get_stats(session_id)` - Get comprehensive statistics
- `update_calibration(session_id, ...)` - Update calibration parameters

**Benefits:**
- Separation of concerns: views orchestrate, services implement
- Testability: each service can be unit tested in isolation
- Extendability: easy to add new services or modify existing ones
- Cleaner views: minimal logic, clear intent

## Runtime State (Django Cache - Thread-Safe & Persistent)
**All global dictionaries removed. State now in Django cache via cache_utils.py:**

- **Exam state** `cache_get_exam_state(key)` / `cache_set_exam_state(key, state)`:
  - Progress: `index`, `questions`, `qa_log`, `student_fullname`, `started_at`
  - Scoped per exam key, isolated per student session
  - Timeout: 1 hour (3600s)

- **Gaze tracking** `cache_init_gaze_session(sid)` / `cache_set_gaze_session(sid, session)`:
  - Metrics: `frames`, `not_looking`, `start_ts`, `thresh_value`, calibration data
  - Scoped per session ID (sid), fully isolated
  - Timeout: 1 hour (3600s)

- **Chat history** `cache_get_chat_history(session_id)` / `cache_append_chat_message(...)`:
  - Per-user conversation turns (proper session scoping)
  - No more shared global state leaking across users
  - Timeout: 2 hours (7200s)

## Cache Utils Module (`main/cache_utils.py`)
**Central API for all session state. Use these functions exclusively:**

### Exam State
- `cache_get_exam_state(key)` → dict or None
- `cache_set_exam_state(key, state, timeout=3600)`
- `cache_reset_exam_state(key)`
- `cache_init_exam_state(key, questions)` → dict

### Gaze Tracking
- `cache_get_gaze_session(sid)` → dict or None
- `cache_set_gaze_session(sid, session, timeout=3600)`
- `cache_reset_gaze_session(sid)`
- `cache_init_gaze_session(sid)` → dict (auto-creates if missing)
- `cache_increment_gaze_frames(sid, not_looking=False)`
- `cache_reset_gaze_counters(sid)` (reset frames/not_looking, keep calibration)

### Chat History
- `cache_get_chat_history(session_id)` → list of messages
- `cache_set_chat_history(session_id, history, timeout=7200)`
- `cache_append_chat_message(session_id, role, content)`
- `cache_reset_chat_history(session_id)`

### Utility
- `cache_clear_all_session_data(identifier)` - wipe all state for session
- `cache_get_session_info(key)` - debugging/monitoring overview

## Exam Flow (Interactive)
1. `exam_start` initializes exam state via `cache_init_exam_state()` and speaks first question (first is always ПІБ, excluded from scoring).
2. `exam_answer` or `exam_voice_answer` appends answer: first gets fixed score 100; others scored by `ai_score` (expects JSON with `score` and `feedback` fields).
3. State updates saved via `cache_set_exam_state()` after each answer.
4. Finalization: build payload, `ai_summary` returns summary and plagiarism score (JSON format); `persist_session_from_payload` writes models.
5. JSON responses always include progress keys: `done`, `idx`, `total` plus `feedback` & next question.

## Grading / Metrics
- Accuracy mean excludes first (ПІБ) entry.
- `_compute_grade_5(acc, plag, gaze_pct)`: accuracy band -> base grade, minus plagiarism >=20 and gaze not-looking >=35. Clamp 1..5.
- Gaze percentage = `not_looking / frames * 100`. Reset via `cache_reset_gaze_counters(key)` on exam start.

## AI Integration
- Whisper loaded lazily via AudioService singleton pattern.
- OpenAI: GPTService uses `openai.OpenAI(...).chat.completions.create(model="gpt-4")`; all scoring/summary uses strict JSON format.
- ElevenLabs: AudioService streaming TTS aggregated then played (`sounddevice`). For headless deployments stub `play_tts`.

## File/Text Handling
- FileExtractor service supports TXT/CSV (encoding autodetect), PDF (page concat), DOCX (paragraph join), RTF (plain decode fallback).

## Extension Points
- New per-answer metric: add field to `Answer`, parse in GPTService.score_answer, include in payload + JSON.
- Plagiarism improvements: alter GPTService.summarize_exam prompt; keep JSON format with `summary` & `plagiarism_score` keys.
- Persist gaze detail: extend cache session structure in GazeService + add model fields; ensure grade logic updated in ExamService.
- Replace mic capture: accept uploaded WAV in voice endpoints → call AudioService.recognize unchanged.
- Add new service: create class in `main/services/`, add to `__init__.py`, instantiate in views.

## Pitfalls (RESOLVED)
- ~~Globals reset on process restart~~ → **FIXED**: All state now in Django cache (persistent with Redis backend).
- ~~Not multi-process safe~~ → **FIXED**: Django cache is thread/process-safe by design.
- ~~Shared `session_history` leaks context~~ → **FIXED**: Chat history properly scoped per session ID.
- Blocking audio + AI calls inside request thread; for scale push to async queue (future enhancement).
- JSON parsing: ensure GPT responses maintain expected structure (use temperature=0.1 for determinism).

## Secrets / Env
Required env vars: `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, optional `AGENT_ID`. Load via `.env` (`python-dotenv`).

## Typical Commands
```bash
python manage.py runserver
python manage.py makemigrations main
python manage.py migrate
python manage.py shell
```

## Testing Suggestions
- Add tests for: line parsing in `_ai_score` / `_ai_summary`, grade boundary conditions, session persistence producing correct counts & gaze pct.

## Safe Changes Checklist
- Use service classes for business logic - instantiate once per view module.
- Use `cache_utils` functions for all state management - never direct cache access.
- Maintain JSON format in AI prompts (don't revert to line-based parsing).
- Update both persistence (`submit_interview`, `persist_session_from_payload`) and models when adding fields.
- Preserve `FS = 16000` in AudioService unless adjusting Whisper config.
- Always scope cache keys properly: exam state by survey key, gaze by session ID, chat by session ID.
- When adding new functionality, prefer creating a new service class over adding functions to views.

## Cache Backend Configuration
For production with Redis:
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

For development (in-memory):
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'avatar-cache',
    }
}
```

Clarify further needs (e.g., gaze algorithm internals, async refactor) and request enhancements here.
