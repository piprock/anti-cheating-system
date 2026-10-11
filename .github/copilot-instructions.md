# Copilot Instructions – Avatar (Django + AI Exam System)

Concise, project-specific guidance for AI coding agents working in this repository.

## Core Structure
- `agent/`: Django project configuration (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`).
- `main/`: Primary application package containing models, views, services, templates, and static assets.
- **Models (`main/models.py`)**:
  - `Student`: Full name (`first_name`, `last_name`, `middle_name`) and creation timestamp.
  - `Survey`: Exam definition (`key`, `title`, `control_questions` JSON list, `answer_time_sec`, `active`).
  - `InterviewSession`: Completed exam session with aggregated metrics (`overall_accuracy`, `plagiarism_score`, `gaze_not_looking_pct`, `grade_5`, `dialogue_result`, `raw_payload`, `status`).
  - `Answer`: Individual question response (`question`, `answer`, `accuracy_score`, `feedback`, `question_order`).
- **Service Layer Architecture (`main/services/`)**: All business logic encapsulated into isolated, unit-tested service classes.
- **Runtime State (`main/cache_utils.py`)**: All transient state (exam progress, gaze metrics, chat history) is stored in the Django cache rather than global variables.
- **Central Modules**:
  - `main/services/audio_service.py`: `AudioService` for microphone recording, Whisper speech recognition, and ElevenLabs TTS.
  - `main/services/gpt_service.py`: `GPTService` for chat, answer scoring, and exam summarization with OpenAI (`gpt-4o-mini`).
  - `main/services/exam_service.py`: `ExamService` for exam session progression, payload building, and 5-point grade calculation.
  - `main/services/file_extractor.py`: `FileExtractor` for parsing TXT, CSV, PDF, DOCX, and RTF uploads.
  - `main/services/gaze_service.py`: `GazeService` for tracking gaze coordinates, calibration samples, and computing off-screen percentages.
  - `main/exam_controller.py`: Interactive exam endpoints (`exam_start`, `exam_answer`, local mic `exam_voice_answer`).
  - `main/exam_extra.py`: Web client voice answer upload (`exam_voice_answer_upload`), TTS question trigger (`exam_speak_current_question`), and CSV export (`exam_export_session`).
  - `main/handlers.py`: General web views (`main`, `about`, `contact`, `exam_page`), voice assistant chat (`record_and_respond`), file analysis (`anylize_file`), gaze stats API (`gaze_stats`), and interview submission (`submit_interview`).
  - `main/gaze.py`: Computer vision frame processor (`gaze_frame`) using dlib 68-landmark predictor and `GazeService`.
  - `main/cache_utils.py`: Unified cache API for exam state, gaze counters, and chat history.
  - `main/persist.py`: Session persistence (`persist_session_from_payload`) that creates `InterviewSession` and `Answer` database records.
  - `main/constants.py`: Centralized thresholds and timeouts (e.g. `PLAGIARISM_PENALTY_THRESHOLD=20`, `GAZE_PENALTY_THRESHOLD_PCT=35.0`, `GRADE_BANDS`, `AUDIO_SAMPLE_RATE=16000`).
  - `main/forms.py`: Django forms for request validation (`VoiceAnswerUploadForm`, `FileAnalyzeForm`, `SubmitInterviewForm`).
- **Legacy Files (Deprecated)**:
  - `main/audio.py`, `main/file_extract.py`, `main/gaze_utils.py`, `main/gpt_utils.py`, `main/views.py`. These files are deprecated remnants from pre-service refactoring. Do not add new logic to or import from these legacy files.

## Service Layer Architecture

### AudioService (`main/services/audio_service.py`)
- `record(duration=5, samplerate=16000)`: Record mono audio from microphone to a temporary WAV file.
- `recognize(filename, language="uk", model_name="small")`: Transcribe audio using Whisper with fallback handling.
- `play_tts(text, voice_id="9Sj8ugvpK1DmcAXyvi3a", model_id="eleven_multilingual_v2")`: Convert text to speech via ElevenLabs and play via `sounddevice` (safe no-op on headless environments).

### GPTService (`main/services/gpt_service.py`)
- Uses OpenAI `gpt-4o-mini` with strict JSON response format (`response_format={"type": "json_object"}`).
- `chat(prompt, session_id, check=False)`: Free-form conversational assistant maintaining per-session message history in cache.
- `score_answer(question, user_answer)`: Returns `Tuple[int, str]` containing `(score, feedback)`. Score is clamped to 0–100.
- `summarize_exam(qa_log)`: Evaluates Q&A log and returns `Tuple[str, int, int]` containing `(summary_text, overall_accuracy, plagiarism_score)`.

### ExamService (`main/services/exam_service.py`)
- `start_exam(key, questions)`: Initializes exam session in cache and resets gaze counters.
- `get_exam_state(key)` / `save_exam_state(key, state)`: Retrieve or save exam dictionary.
- `reset_exam(key)`: Clear exam state from cache.
- `get_current_question(state)`: Returns current question string or `None` if finished.
- `record_answer(state, answer, score, feedback)`: Appends entry to `qa_log` and increments question index.
- `advance_to_next_question(state)`: Moves to next question without recording an answer.
- `is_exam_complete(state)`: Checks whether all questions have been answered.
- `get_progress(state)`: Returns `(current_index, total_questions)`.
- `build_session_payload(state, summary_text, overall_accuracy, plagiarism_score)`: Constructs database-ready payload, excluding the first ПІБ answer from graded metrics.
- `compute_grade(accuracy, plagiarism, gaze_pct)`: Calculates final 1–5 grade based on accuracy bands and penalties.
- `get_graded_answers(state)`: Returns answers excluding the initial ПІБ entry.
- `calculate_average_accuracy(qa_log)`: Calculates integer mean accuracy percentage.

### FileExtractor (`main/services/file_extractor.py`)
- `extract(uploaded_file, filename)`: Unified parser supporting:
  - TXT / CSV: UTF-8 with automatic fallback to cp1251.
  - PDF: Page concatenation via `PyPDF2`.
  - DOCX: Paragraph joining via `python-docx`.
  - RTF: Stripping via `striprtf` or raw UTF-8 fallback.

### GazeService (`main/services/gaze_service.py`)
- `init_session(session_id)`: Retrieve or initialize session state in cache.
- `get_session(session_id)` / `save_session(session_id, session)` / `reset_session(session_id)`: State management.
- `increment_frame(session_id, not_looking=False)`: Atomically increments frame counters.
- `reset_counters(session_id)`: Resets frame and not-looking counters while preserving eye calibration.
- `compute_not_looking_percent(session_id)`: Returns percentage (0.0–100.0) of off-screen frames.
- `get_stats(session_id)`: Returns dictionary with `frames`, `not_looking`, `not_looking_pct`, `calibrated`, `thresh_value`, and `elapsed_sec`.
- `update_calibration(session_id, thresh_value=..., calibrated=..., manual=...)`: Updates calibration values.
- `add_threshold_sample(session_id, sample)`: Adds sample and auto-calibrates once min threshold samples (20) are reached.

## Runtime State (Django Cache)
All runtime state is isolated and managed through [`main/cache_utils.py`](file:///c:/Users/yural/PycharmProjects/anti-cheating-system/main/cache_utils.py):
- **Exam State**: Keyed by `exam:<key>`. Timeout: 1 hour (3600s). Holds question list, current index, `qa_log`, `student_fullname`, `started_at`.
- **Gaze Tracking**: Keyed by `gaze:<sid>`. Timeout: 1 hour (3600s). Holds frame counters, `not_looking`, calibration samples, threshold value.
- **Chat History**: Keyed by `chat_history:<session_id>`. Timeout: 2 hours (7200s). Scoped per browser session ID.

### Cache Utils Functions (`main/cache_utils.py`)
- **Exam**:
  - `cache_get_exam_state(key)` -> `dict | None`
  - `cache_set_exam_state(key, state, timeout=3600)`
  - `cache_reset_exam_state(key)`
  - `cache_init_exam_state(key, questions)` -> `dict`
- **Gaze**:
  - `cache_get_gaze_session(sid)` -> `dict | None`
  - `cache_set_gaze_session(sid, session, timeout=3600)`
  - `cache_reset_gaze_session(sid)`
  - `cache_init_gaze_session(sid)` -> `dict`
  - `cache_increment_gaze_frames(sid, not_looking=False)`
  - `cache_reset_gaze_counters(sid)`
  - `compute_gaze_percent(sid)` -> `float`
- **Chat**:
  - `cache_get_chat_history(session_id)` -> `List[dict]`
  - `cache_set_chat_history(session_id, history, timeout=7200)`
  - `cache_append_chat_message(session_id, role, content)`
  - `cache_reset_chat_history(session_id)`
- **Utilities**:
  - `cache_clear_all_session_data(identifier)`
  - `cache_get_session_info(key)`

## Exam Flow
1. **Start (`/api/exam/start/<key>/`)**:
   - Fetches active `Survey` by `key`.
   - Initializes exam state via `ExamService.start_exam()` and resets gaze counters.
   - Speaks first question (student ПІБ prompt) via `AudioService.play_tts()`.
2. **Answering**:
   - **Text Answer (`/api/exam/answer/<key>/`)**: JSON POST `{"answer": "..."}` handled by `exam_controller.exam_answer`.
   - **Web Voice Answer (`/api/exam/voice_answer/<key>/`)**: Multipart POST with audio file handled by `exam_extra.exam_voice_answer_upload`. Transcribed with Whisper (`AudioService.recognize`).
   - **First Question Handling**: Index 0 is always student ПІБ. Stored in `student_fullname`, assigned score 100, excluded from academic scoring.
   - **Subsequent Questions**: Evaluated by `GPTService.score_answer()`. State updated via `ExamService.record_answer()`.
3. **Question Progression**:
   - Intermediate responses return: `{"done": False, "idx": N, "total": M, "feedback": "...", "accuracy_score": S, "answer": "...", "next_question": "..."}`.
4. **Finalization**:
   - When all questions are answered, `GPTService.summarize_exam(graded_answers)` produces summary text and plagiarism score.
   - `ExamService.build_session_payload()` structures the session data.
   - `persist_session_from_payload()` saves `InterviewSession` and `Answer` database records and calculates final grade via `ExamService.compute_grade()`.
   - Final JSON response returns `done: True`, summary, grade, and persistence confirmation.

## Grading & Metrics
- Evaluated by `ExamService.compute_grade(accuracy, plagiarism, gaze_pct)` using constants from `main/constants.py`:
  - **Accuracy Bands**: >=90 -> 5, >=75 -> 4, >=60 -> 3, >=40 -> 2, <40 -> 1.
  - **Plagiarism Penalty**: -1 grade if `plagiarism >= PLAGIARISM_PENALTY_THRESHOLD` (20%).
  - **Gaze Penalty**: -1 grade if `gaze_not_looking_pct >= GAZE_PENALTY_THRESHOLD_PCT` (35%).
  - Final grade is clamped between 1 and 5.
- Off-screen gaze percentage is calculated as `100.0 * not_looking / max(1, frames)`.

## AI Integration Details
- **Whisper**: Lazy-loaded singleton in `AudioService` (`model_name="small"`, sample rate 16000 Hz).
- **OpenAI**: `GPTService` uses `openai.OpenAI()` with model `gpt-4o-mini`. Strict JSON schemas are enforced via `response_format={"type": "json_object"}` with `temperature=0.1` for determinism.
- **ElevenLabs**: TTS via ElevenLabs client, outputting 16 kHz PCM played through `sounddevice`.

## Environment Variables (.env)
Required:
- `OPENAI_API_KEY`: API key for OpenAI (`gpt-4o-mini`).
- `ELEVENLABS_API_KEY`: API key for ElevenLabs TTS.
Optional:
- `AGENT_ID`: Agent identification string if needed.

## Common Commands
```bash
# Run development server
python manage.py runserver

# Database migrations
python manage.py makemigrations main
python manage.py migrate

# Django interactive shell
python manage.py shell

# Run test suite with pytest & coverage
pytest
```

## Testing Guidelines
- The project uses `pytest`, `pytest-django`, and `pytest-cov` configured in [`pytest.ini`](file:///c:/Users/yural/PycharmProjects/anti-cheating-system/pytest.ini).
- All unit tests are located in [`main/tests/`](file:///c:/Users/yural/PycharmProjects/anti-cheating-system/main/tests/):
  - `test_audio_service.py`: Recording, recognition, and TTS mocks.
  - `test_exam_service.py`: Exam initialization, answer recording, and grade computation.
  - `test_file_extractor.py`: Format parsing for TXT, CSV, PDF, DOCX, and RTF.
  - `test_gaze_service.py`: Frame counting, calibration, and off-screen percentage computation.
  - `test_gpt_service.py`: Chat history accumulation, answer scoring, and summarization.
  - `test_persist.py`: Session and answer database record creation from payloads.
- When creating or modifying tests, mock external AI APIs (OpenAI, ElevenLabs, Whisper) to avoid network calls and rate limits.

## Safe Changes Checklist
- Always encapsulate business logic in `main/services/`, instantiating services at module level or dependency-injecting them.
- Always use `main/cache_utils.py` functions for session state — never access `django.core.cache.cache` with arbitrary hardcoded keys.
- Preserve strict JSON schemas in `GPTService` completions.
- Update both models (`main/models.py`) and persistence logic (`main/persist.py`) when adding new metrics or session fields.
- Keep audio sample rate aligned to `AUDIO_SAMPLE_RATE = 16000` (`main/constants.py`).
- Run `pytest` before finalizing changes to ensure service coverage and test integrity.
