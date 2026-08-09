# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Offline speech-to-text via `faster-whisper` (`tiny.en` by default) — audio never
  leaves the machine in offline mode.
- Online text cleaning via **DeepSeek V4 Flash** (`deepseek-v4-flash`): whisper
  transcribes locally, DeepSeek adds punctuation and fixes grammar in online mode.
- `TRANSCRIPTION_MODE` config (`online` / `offline`) plus a per-request
  `X-Transcription-Mode` header override (used by the Web Studio toggle).
- New services: `app/services/whisper.py`, `app/services/deepseek.py`,
  `app/services/prompts.py` (tone detection + prompt builder shared with tests).
- Web Studio redesign: online/offline mode switch, live backend status, pipeline
  indicator, tone chips, raw transcript, latency readout.
- Repository foundation: README, LICENSE (Apache-2.0), CONTRIBUTING, CHANGELOG.
- Ruff lint configuration for `backend/` and `desktop/`.
- Unit test suites for the backend (transcription, schemas, Gemini service, audio route)
  and desktop client (hotkey parsing, recorder, config).
- GitHub Actions CI: `test.yaml` (lint + test on push/PR), `docker.yaml`
  (multi-arch image publish on tags/master), `release.yaml` (desktop binaries).
- API token authentication for `/process-audio`.
- Prometheus `/metrics` endpoint and structured request logging.
- JSON structured logging mode (`LOG_FORMAT=json`) for container/Cloud Run use.
- Simple in-process rate limiting on the audio endpoint.
- Desktop tray recording indicator: the tray icon turns red and the tooltip
  shows "recording…" while the hotkey is held.
- "Launch at login" system tray toggle (Windows VBS / macOS LaunchAgent /
  Linux autostart desktop entry).
- Dependency automation: Renovate config and Dependabot for pip and
  GitHub Actions.
- PyInstaller spec (`desktop/vocatype.spec`) for building the desktop client.
- Web Studio `/preview` now has an optional API token field (persisted in
  localStorage) so it works when `/process-audio` auth is enabled.

### Changed

- Replaced Gemini (multimodal transcription) with whisper local STT + DeepSeek
  cleaning: cheaper, faster, and fully offline-capable.
- API version aligned to `0.3.0`.
- WebM/OGG/MP3 uploads now decoded via PyAV in `whisper.py` (previously the
  WAV-only path rejected them).
- Desktop microphone recording now uses `sounddevice` (bundles PortAudio
  binaries) instead of PyAudio, which has no binary wheels on Python 3.13+.
- Fixed `.gitignore` typo (`*.DS_Store5` → `*.DS_Store`).
- Desktop API client now sends the configured API token as `X-API-Token`.
- PyInstaller spec collects `_sounddevice_data` (PortAudio DLLs) and the tray
  "launch at login" checked state uses the correct `lambda item:` signature.

## [0.1.0] - 2026-08-07

### Added

- FastAPI backend with Gemini 1.5 Flash integration.
  - `POST /process-audio` — multipart audio + context, returns cleaned text.
  - `GET /health` — liveness probe for Cloud Run / load balancers.
  - Interactive Web Studio preview UI at `/preview`.
  - Context-aware tone selection (casual / professional / neutral).
  - Speak-to-edit mode for transforming selected text.
  - Multi-language support hint.
- Desktop Python client.
  - Global hotkey (default `Ctrl+Space`) push-to-talk recording.
  - Microphone recording via PyAudio into an in-memory WAV buffer.
  - Active-window context detection (Windows / macOS / Linux).
  - Clipboard + simulated-paste text injection with typing fallback.
  - System tray icon with quit menu.
- Dockerfile for the backend (non-root user, health check, Cloud Run ready).
- Android Gradle project scaffold.
