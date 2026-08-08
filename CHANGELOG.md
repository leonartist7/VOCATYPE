# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

### Changed

- Migrated from the deprecated `google-generativeai` SDK to the officially
  supported `google-genai` package (client-based API, `generate_content`).
- Default Gemini model is now `gemini-flash-latest` (stable alias); older
  models like `gemini-1.5-flash` / `gemini-2.x` are unavailable to new
  accounts.
- Desktop microphone recording now uses `sounddevice` (bundles PortAudio
  binaries) instead of PyAudio, which has no binary wheels on Python 3.13+.
- Fixed `.gitignore` typo (`*.DS_Store5` → `*.DS_Store`).
- Desktop API client now sends the configured API token as `X-API-Token`.

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
