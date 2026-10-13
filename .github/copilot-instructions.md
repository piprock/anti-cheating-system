# Copilot Instructions – Avatar (Django + AI Exam System)

Concise, project-specific guidance for AI coding agents working in this repository.

## Core Structure
- `agent/`: Django project configuration (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`).
- `main/`: Primary application package containing models, views, services, templates, and static assets.
- **Models (`main/models.py`)**:
  - `UserProfile`: Role-based profile extending Django `User` (`role`: `student`, `teacher`, `admin`; `middle_name`, `group`, `full_name`).
  - `ActivityLog`: User action audit trail (`action`: login, logout, profile update, exam start, exam submit, role change).
  - `TeacherApplication`: Request for role elevation to teacher (`department`, `position`, `phone`, `reason`, `status`: pending/approved/rejected/cancelled, `admin_notes`, `reviewed_by`).
  - `Student`: Full name (`first_name`, `last_name`, `middle_name`) and creation timestamp.
  - `Survey`: Exam definition (`key`, `title`, `description`, `author`, `is_public`, `control_questions` JSON list of `{"text": ..., "time": ...}` dicts or legacy strings, `answer_time_sec` fallback, `active`).
  - `TestAssignment`: Assignment of tests to individual students or academic groups (`survey`, `student`, `group`, `assigned_by`, `due_date`, `notes`).
  - `InterviewSession`: Completed exam session with aggregated metrics (`overall_accuracy`, `plagiarism_score`, `gaze_not_looking_pct`, `grade_5`, `dialogue_result`, `raw_payload`, `status`).
  - `Answer`: Individual question response (`question`, `answer`, `accuracy_score`, `feedback`, `question_order`).
- **Service Layer Architecture (`main/services/`)**: All business logic encapsulated into isolated, unit-tested service classes.
- **Runtime State (`main/cache_utils.py`)**: All transient state (exam progress, gaze metrics, chat history) is stored in the Django cache rather than global variables.
- **Central Modules**:
  - `const/`: Centralized modular constants package (`const/errors/messages.py`, `const/validation/bounds.py`, `const/exam/metrics.py`). Validation limits must strictly use `bounds` (never `extremes`). Re-exported in `main/constants.py`.
  - `main/auth_views.py`: Authentication (login, logout), 2-step registration wizard, role-based dashboard with paginated activity log, user settings (`/settings/` with tabs `profile`, `teacher`, `security`), teacher application review, session inspector.
  - `main/survey_views.py`: Public test catalog (`/tests/`), teacher CRUD panel (`/teacher/tests/`, create/edit with dynamic per-question cards and individual time limits, delete/deactivate), and test assignment (`/teacher/tests/<id>/assign/`).
  - `main/management/commands/seed_admin.py`: Idempotent superuser seeding from root `.env` (`ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL`).
  - `main/services/audio_service.py`: `AudioService` for microphone recording, Whisper speech recognition, and ElevenLabs TTS.
  - `main/services/gpt_service.py`: `GPTService` for chat, answer scoring, and exam summarization with OpenAI (`gpt-4o-mini`).
  - `main/services/exam_service.py`: `ExamService` for exam session progression, payload building, and 5-point grade calculation.
  - `main/services/file_extractor.py`: `FileExtractor` for parsing TXT, CSV, PDF, DOCX, and RTF uploads.
  - `main/services/gaze_service.py`: `GazeService` for tracking gaze coordinates, calibration samples, and computing off-screen percentages.
  - `main/exam_controller.py`: Interactive exam endpoints (`exam_start`, `exam_answer`, local mic `exam_voice_answer`).
  - `main/exam_extra.py`: Web client voice answer upload (`exam_voice_answer_upload`), TTS question trigger (`exam_speak_current_question`), and CSV export (`exam_export_session`).
  - `main/handlers.py`: General web views (`main`, `gaze_view`, `about`, `contact`, `exam_page`), voice assistant chat (`record_and_respond`), file analysis (`anylize_file`), gaze stats and reset API (`gaze_stats`, `gaze_reset`), and interview submission (`submit_interview`).
  - `main/gaze.py`: Computer vision frame processor (`gaze_frame`) using dlib 68-landmark predictor and `GazeService`.
  - `main/cache_utils.py`: Unified cache API for exam state, gaze counters, and chat history.
  - `main/persist.py`: Session persistence (`persist_session_from_payload`) that creates `InterviewSession` and `Answer` database records.
  - `main/constants.py`: Re-exports modular constants from root `const/` package for backward compatibility.
  - `main/forms.py`: Django forms (`RegistrationStep1Form`, `RegistrationStep2Form`, `UserProfileEditForm`, `TeacherApplicationForm`, `SurveyForm`, `TestAssignmentForm`, `VoiceAnswerUploadForm`, `FileAnalyzeForm`, `SubmitInterviewForm`).
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
   - First question is always student ПІБ prompt (`DEFAULT_INTRO_QUESTION`, auto-filled if logged in).
   - Speaks first question via `AudioService.play_tts()`. Returns question time `answer_time_sec`.
2. **Answering**:
   - **Text Answer (`/api/exam/answer/<key>/`)**: JSON POST `{"answer": "..."}` handled by `exam_controller.exam_answer`.
   - **Web Voice Answer (`/api/exam/voice_answer/<key>/`)**: Multipart POST with audio file handled by `exam_extra.exam_voice_answer_upload`. Transcribed with Whisper (`AudioService.recognize`).
   - **First Question Handling**: Index 0 is always student ПІБ. Stored in `student_fullname`, assigned score 100, excluded from academic scoring.
   - **Subsequent Questions**: Evaluated by `GPTService.score_answer()`. State updated via `ExamService.record_answer()`. Countdown timer dynamically adapts to each question's individual `answer_time_sec`.
3. **Question Progression**:
   - Intermediate responses return: `{"done": False, "idx": N, "total": M, "feedback": "...", "accuracy_score": S, "answer": "...", "next_question": "...", "answer_time_sec": T}`.
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
Root-level `.env` is the single source of truth (never duplicate in subdirectories).
Required:
- `OPENAI_API_KEY`: API key for OpenAI (`gpt-4o-mini`).
- `ELEVENLABS_API_KEY`: API key for ElevenLabs TTS.
Admin Seeding (Optional, defaults provided):
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL`: Seed credentials for the superuser.
Optional:
- `AGENT_ID`: Agent identification string if needed.

## Authentication, Authorization & Roles
- **Role Hierarchy (`UserProfile.role`)**:
  - `student`: Standard exam taker; accesses personal dashboard with exam history, grades, and accuracy stats.
  - `teacher`: Evaluator; views all student sessions, filterable by academic group, with CSV export capabilities.
  - `admin`: Superuser; manages all user accounts, views global statistics, and accesses Django admin (`/admin/`).
- **Registration**: 2-stage wizard strictly in 1 column with left-aligned labels:
  - Stage 1: `username`, `email` (optional), `password`, `password_confirm` (cached in `request.session['reg_step1']`).
  - Stage 2: `last_name`, `first_name`, `middle_name` (optional), `group` (optional) -> creates `User` + `UserProfile` and auto-logs in.
- **Admin Seeding**: Automated on migrate or manually via `python manage.py seed_admin` (idempotent, reads credentials from root `.env`).
- **Audit Trail (`ActivityLog`)**: Logs user events (login, logout, profile update, exam start/submit, role change). On the dashboard, activity history is paginated (`10/page`, `?log_page=N`), collapsed by default, and auto-expands when navigating pages.
- **User Settings (`/settings/`)**: Multi-tab interface (`tab=profile`, `teacher`, `security`). Direct requests to legacy `/profile/edit/` redirect to `?tab=profile`. Form input examples are strictly placed in `placeholder` attributes (never as hint text beneath fields).
- **Teacher Applications**: Students apply for teacher role from Settings (`tab=teacher`). Administrators approve or reject requests directly in Dashboard or Django admin, promoting the user to `ROLE_TEACHER` with an audit record (`ACTION_ROLE_CHANGE`).

## UI/UX Design System & Accessibility

### Design Philosophy & Anti-Slop Rules
- **Typography**: Strictly single font family `Comfortaa, sans-serif` across the entire application (`main/static/css/style.css`).
- **Spacing & Radii**: Systematic 4px/8px grid (`--space-1` to `--space-16`). Strict radii: 6px (`--radius-sm`), 8px (`--radius-md`), 12px (`--radius-lg`). Oversized pill shapes (`border-radius: 133px`) are prohibited.
- **Anti-Slop**: No neon glows, card gradients, floating 3D clay blobs, or decorative clutter. No emojis in UI controls — use inline SVG icons (`.ui-icon`) with `stroke="currentColor"`.
- **Branding**: Platform name is strictly **Avatar AI** (replaces legacy "Teacher AI" / "Teach AI").

### Themes & Color Tokens
- **Dark Theme (Default)**: Deep neutral charcoal (`--bg-page: #18181B`, `--bg-card: #27272A`, `--border-color: #3F3F46`, text `#F4F4F5`, vibrant accent `--orange: #FF9820`).
- **Light Theme (`[data-theme="light"]`)**: Warm ivory/alabaster (`--bg-page: #FAF7F2`, `--bg-card: #FFFFFF`, `--border-color: #E7DFD5`, warm charcoal text `#292524`, accent `--orange: #FF8A00`). Cool dark blues (`#0F172A`) are strictly forbidden.
- **Logo Switching**: Responsive dual logos (`dark_theme_logo.png` & `light_theme_logo.png`) in header toggled purely via CSS `[data-theme="..."]` to prevent FOUT and JS delay.
- **Anti-Flicker**: An early inline script in `<head>` of `main/templates/main/base.html` reads `localStorage` and sets `data-theme`, `data-font-scale`, and `data-colorblind` before first DOM paint.

### Accessibility Suite (`main/static/js/a11y.js`, `a11y.css`)
- **State Persistence**: Stored in `localStorage` as `avatarai_a11y_settings` (with legacy fallback).
- **Content Scaling (`data-font-scale`)**: `normal` (100%), `large` (125%), `xlarge` (150%) without horizontal viewport overflow.
- **Colorblind Adaptation (`data-colorblind`)**:
  - `none`: Default semantic tokens.
  - `protanopia-deuteranopia`: Royal Blue (`#2563EB`) & Amber (`#D97706`).
  - `tritanopia`: Emerald (`#059669`) & Rose (`#E11D48`).
  - `high-contrast`: 2px solid high-contrast borders and underlined interactive elements.
- **Status Dual-Coding**: Never convey meaning through color alone; status badges (e.g. `#gazeStatus`) must pair color with SVG icons and descriptive text.
- **Interaction & Contrast**: Touch targets min 44×44px. Hover and focus states must maintain high contrast (e.g. button hover text must never blend into background). Focus rings use `outline: 2px solid var(--orange); outline-offset: 2px`.

### Modular CSS Architecture
- `main/static/css/style.css`: Design tokens (`:root`, themes), typography, grid, resets, utilities.
- `main/static/css/header.css`: Fixed 2-row header, nav links, profile dropdown, pure CSS theme-based logo switching.
- `main/static/css/footer.css`: 3-tier footer: `.footer-container` (columns) -> `.footer-marquee` (running ticker) -> `.footer-bottom` (copyright).
- `main/static/css/a11y.css`: Accessible popover modal, font scaling modifiers, colorblind overrides.
- `main/static/css/auth.css`: Authentication pages, role badges, history cards, toasters, step indicators.
- `main/static/css/layout.css`: Layout utilities, micro-tooltips (`.ui-tooltip`).
- `main/static/css/forms.css`: Left-aligned form fields and validation styles.
- `main/static/css/exam.css`: Proctoring exam layout, camera viewport, question cards, gaze pills.

### Header, Navigation, Toasts & Tooltips
- **2-Row Header**:
  - Row 1: Dual-theme Logo (left, no subtitle text) + Theme Quick Button, Accessibility trigger, and Profile Dropdown (right).
  - Row 2: Main navigation links (left-aligned: "Головна", "Моніторинг погляду", "Про нас") + mobile burger toggle (right). Standalone "Кабінет" button is removed from nav and integrated into the Profile Dropdown.
- **Profile Dropdown**: Displays short name "Ім'я Прізвище", opening into user card (full name, role badge, group, email, dashboard link, profile editor, Django admin link for superusers, and logout at bottom).
- **Toaster Notifications (`#toastContainer`)**: Floating stack at top-right for flash messages (success, error, info), auto-dismissing after 4.5s (pauses on hover), with inline close button.
- **Micro-Tooltips (`.ui-tooltip`)**: Accessible SVG hover/focus tooltips for secondary descriptions and metrics (e.g. grading scales, activity log purpose, pupil detection hints) to prevent visual clutter.
- **Form Layout**: Strict 1-column layout, left-aligned labels, headings, and input fields. Examples must be HTML `placeholder` attributes rather than sub-field hint clutter.

### Marquee (Running Text)
- Continuous ticker (`.footer-marquee`) animates leftward (`marqueeScrollLeft 48s linear infinite`).
- Optically centered via `padding: var(--space-6) 0 var(--space-4)` with `line-height: 1` to compensate for Comfortaa font ascender/descender metrics.


## Common Commands
> **Important**: Always run commands using the project virtual environment (`.venv`), never global Python!

```bash
# Windows (PowerShell / CMD using .venv directly):
.venv\Scripts\python manage.py runserver
.venv\Scripts\python manage.py makemigrations main
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py seed_admin
.venv\Scripts\python manage.py shell
.venv\Scripts\pytest

# Linux / macOS (or when .venv is activated):
source .venv/bin/activate
python manage.py runserver
pytest
```

## Testing Guidelines
- The project uses `pytest`, `pytest-django`, and `pytest-cov` configured in [`pytest.ini`](file:///c:/Users/yural/PycharmProjects/anti-cheating-system/pytest.ini).
- All unit tests are located in [`main/tests/`](file:///c:/Users/yural/PycharmProjects/anti-cheating-system/main/tests/):
  - `test_auth.py`: Authentication, roles, 2-step registration, dashboard stats, profile editing, and `const` exports.
  - `test_audio_service.py`: Recording, recognition, and TTS mocks.
  - `test_exam_service.py`: Exam initialization, answer recording, and grade computation.
  - `test_file_extractor.py`: Format parsing for TXT, CSV, PDF, DOCX, and RTF.
  - `test_gaze_service.py`: Frame counting, calibration, and off-screen percentage computation.
  - `test_gpt_service.py`: Chat history accumulation, answer scoring, and summarization.
  - `test_persist.py`: Session and answer database record creation from payloads.
  - `test_survey_crud.py`: Test creation, editing, deletion, public catalog, and student/group assignment.
- When creating or modifying tests, mock external AI APIs (OpenAI, ElevenLabs, Whisper) to avoid network calls and rate limits.

## Safe Changes Checklist
- Always encapsulate business logic in `main/services/`, instantiating services at module level or dependency-injecting them.
- Always use `main/cache_utils.py` functions for session state — never access `django.core.cache.cache` with arbitrary hardcoded keys.
- Place constants in modular `const/` package; validation limits must strictly be named `bounds.py` (never `extremes`).
- Preserve strict JSON schemas in `GPTService` completions.
- Update both models (`main/models.py`) and persistence logic (`main/persist.py`) when adding new metrics or session fields.
- Keep audio sample rate aligned to `AUDIO_SAMPLE_RATE = 16000` (`main/constants.py`).
- Maintain UI consistency with single font `Comfortaa`, 4px/8px grid, SVG icons, and left-aligned 1-column form layouts.
- Render secondary explanatory descriptions inside `.ui-tooltip` icons rather than plain paragraph clutter.
- Ensure all UI changes support both `[data-theme="dark"]` and `[data-theme="light"]`, with status colors respecting `[data-colorblind]`.
- Increment CSS cache version query string in templates (`?v=...`) whenever updating stylesheets.
- Tests/Surveys: `control_questions` stores `{"text": ..., "time": ...}`; keep `Survey.exam_questions` normalized, question 0 as fixed ПІБ intro, and dynamic frontend timer per question.
- Always run tests and manage commands using `.venv`, never global Python.
- Run `pytest` before finalizing changes to ensure service coverage and test integrity.
