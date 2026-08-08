# Vocatype

> AI-powered dictation that types what you say — instantly, everywhere.

Vocatype is a hands-free voice dictation system. Hold a global hotkey, speak, release, and
clean, context-aware text is typed into whatever app you're in. It strips filler words,
adapts tone to the active application (casual in WhatsApp, professional in Gmail), and
even lets you edit selected text by voice ("make this more formal").

## Features

- 🎙️ **Push-to-talk dictation** — hold the hotkey, speak, release, done.
- 🧠 **AI cleaning** — filler words removed, grammar fixed, lists and paragraphs auto-formatted.
- 🎭 **Context-aware tone** — automatically matches the app you're dictating into.
- ✏️ **Speak-to-edit** — select text, speak a command, and watch it transform.
- 🌍 **Multilingual** — transcribes and processes in the spoken language.
- 🖥️ **Desktop client** — Windows/macOS/Linux with a system-tray presence.
- 🌐 **Web Studio** — record and test from the browser at `/preview`.
- 🔌 **FastAPI backend** — single self-hostable service, deploys to Cloud Run or Docker.
- 📱 **Android** (WIP) — dictation on the go.

## Architecture

```
┌────────────────┐      audio + context       ┌──────────────────────┐
│  Desktop app   │ ─────────────────────────► │    FastAPI backend   │
│  (hotkey · mic │                             │  /process-audio      │
│   · clipboard) │ ◄───────────────────────── │   Gemini Flash API   │
└────────────────┘      cleaned text          └──────────────────────┘
       │                                             │
       │      Windows / macOS / Linux                │ Gemini API
       │                                            ▼
       │                          ┌──────────────────────────┐
       │                          │   Web Studio (preview)   │
       │                          └──────────────────────────┘
```

```
backend/    FastAPI service — Gemini integration, tone/prompt engine, Web Studio
desktop/    Python desktop client — hotkey, recording, window context, text injection
android/    Android client (in progress)
```

## Getting Started

### 1. Backend

Prerequisites: Python 3.12+, a [Gemini API key](https://aistudio.google.com/app/apikey).

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your GEMINI_API_KEY
uvicorn app.main:app --reload
```

The API is now at `http://localhost:8000`, with the interactive Web Studio at
[http://localhost:8000/preview](http://localhost:8000/preview) and API docs at
[http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Desktop client

Prerequisites: Python 3.12+, a microphone.

```bash
cd desktop
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

Press **Ctrl+Space** (configurable via `HOTKEY_COMBO`), hold to speak, release to dictate.

### 3. Docker

```bash
cd backend
docker build -t vocatype-backend .
docker run -p 8000:8080 -e GEMINI_API_KEY=your-key vocatype-backend
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `GEMINI_API_KEY` | — | Gemini API key (required) |
| `GEMINI_MODEL` | `gemini-flash-latest` | Model used for transcription (stable alias) |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Bind port |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins |
| `BACKEND_URL` | `http://localhost:8000` | Desktop client → backend URL |
| `HOTKEY_COMBO` | `ctrl+space` | Desktop global hotkey |
| `SAMPLE_RATE` | `16000` | Desktop mic sample rate |
| `CHANNELS` | `1` | Desktop mic channels |
| `CHUNK_SIZE` | `1024` | Desktop mic buffer size |

## API

### `POST /process-audio`

Multipart request: `audio_file` (`.wav`, `.m4a`, `.webm`, `.ogg`, `.mp3`, `.flac`, `.aac`,
`.3gp`) + `context` (JSON string).

**Request**

```
context: {
  "app_name": "com.google.android.gm",
  "platform": "windows",
  "selected_text": "optional existing text to transform",
  "language": "en"
}
```

**Response**

```json
{
  "processed_text": "The cleaned, formatted text.",
  "raw_transcript": "The word-for-word raw transcription.",
  "tone_applied": "professional"
}
```

### `GET /health`

Liveness/readiness probe for load balancers and container orchestrators.

## Deployment

The backend is a stateless FastAPI service. Deploy it anywhere containers run:

- **Cloud Run** — build and deploy with the included `Dockerfile` (non-root, health-checked).
- **Docker** — `docker build .` and run anywhere.
- **Bare metal** — `uvicorn app.main:app` behind any reverse proxy.

## Development

```bash
# Backend tests + lint
cd backend && pytest && ruff check .

# Desktop tests + lint
cd desktop && pytest && ruff check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution workflow.

## Repository Structure

- `backend/` — FastAPI service (routes, services, models, config, Dockerfile)
- `desktop/` — Python desktop client (hotkey, recorder, context, injector, tray)
- `android/` — Android client (in progress)
- `.github/workflows/` — CI/CD pipelines (test, docker, release)

## License

Apache License 2.0 — see [LICENSE](LICENSE).
