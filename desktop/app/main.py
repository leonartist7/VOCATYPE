"""
Vocatype Desktop Client — Main Entry Point.

System tray application that:
1. Listens for a global hotkey (Ctrl+Space by default).
2. Records microphone audio while the hotkey is held.
3. On release, sends audio + window context to the backend.
4. Pastes the processed text into the active field.
"""

from __future__ import annotations

import logging
import threading

from app import autostart
from app.api_client import close_client, send_audio
from app.config import config
from app.context import get_active_window_context
from app.hotkey import HotkeyListener
from app.icon import load_or_create_icon
from app.injector import inject_text
from app.recorder import AudioRecorder

# ── Logging ─────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("vocatype-desktop")

# ── Globals ─────────────────────────────────────────────────────────────────────

recorder = AudioRecorder()
_processing = False
_processing_lock = threading.Lock()
_tray_icon = None  # set once the tray icon is created


def on_hotkey_press() -> None:
    """Called when the hotkey combo is pressed down — start recording."""
    global _processing
    with _processing_lock:
        if _processing:
            logger.warning("Still processing previous recording — ignoring press.")
            return
    recorder.start_recording()
    _set_recording_state(True)


def on_hotkey_release() -> None:
    """
    Called when the trigger key is released — stop recording and process.
    Runs the send+paste pipeline in a background thread to avoid blocking the hotkey listener.
    """
    global _processing

    with _processing_lock:
        if _processing:
            return
        _processing = True
    _set_recording_state(False)

    # Run processing in a background thread
    thread = threading.Thread(target=_process_recording, daemon=True)
    thread.start()


def _set_recording_state(recording: bool) -> None:
    """Reflect the recording state in the tray icon, if present."""
    global _tray_icon
    if _tray_icon is None:
        return
    try:
        icon = load_or_create_icon(recording=recording)
        _tray_icon.icon = icon
        _tray_icon.title = (
            "Vocatype — recording…" if recording else f"Vocatype ({config.hotkey_combo})"
        )
    except Exception as e:  # pragma: no cover — defensive; tray is optional
        logger.warning("Failed to update tray icon: %s", e)


def _process_recording() -> None:
    """Stop recording, detect context, send to backend, inject result."""
    global _processing

    try:
        # 1. Stop recording and get WAV bytes
        wav_bytes = recorder.stop_recording()
        if wav_bytes is None:
            logger.warning("No audio recorded.")
            return

        # 2. Detect active window context
        context = get_active_window_context()
        logger.info("Context: %s", context)

        # 3. Send to backend
        processed_text = send_audio(wav_bytes, context)
        if processed_text is None:
            logger.error("Backend returned no text.")
            return

        # 4. Inject into active field
        success = inject_text(processed_text)
        if success:
            logger.info("✅ Dictation complete: '%s'", processed_text[:80])
        else:
            logger.error("Failed to inject text.")

    except Exception as e:
        logger.error("Processing pipeline error: %s", e, exc_info=True)

    finally:
        with _processing_lock:
            _processing = False


# ── System Tray ─────────────────────────────────────────────────────────────────


def _create_tray_icon():
    """Create and return a system tray icon with a menu."""
    try:
        import pystray
    except ImportError:
        logger.error("pystray not installed. Running without system tray.")
        return None

    def on_quit(icon, item):
        """Quit the application."""
        logger.info("Quit requested from tray menu.")
        icon.stop()

    def on_auto_start_toggle(icon, item):
        """Enable/disable launch-at-login."""
        enabled = item.checked
        if enabled:
            autostart.disable()
            logger.info("Auto-start disabled.")
        else:
            autostart.enable()
            logger.info("Auto-start enabled.")
        if _tray_icon is not None:
            _tray_icon.update_menu()

    menu = pystray.Menu(
        pystray.MenuItem(
            f"Vocatype — {config.hotkey_combo}",
            lambda: None,
            enabled=False,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Launch at login",
            on_auto_start_toggle,
            checked=lambda icon, item: autostart.is_enabled(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )

    icon = pystray.Icon(
        name="vocatype",
        icon=load_or_create_icon(recording=False),
        title=f"Vocatype ({config.hotkey_combo})",
        menu=menu,
    )

    return icon


def main() -> None:
    """Application entry point."""
    logger.info("═══════════════════════════════════════════════")
    logger.info("  Vocatype Desktop Client")
    logger.info("  Backend: %s", config.backend_url)
    logger.info("  Hotkey:  %s", config.hotkey_combo)
    logger.info("  Platform: %s", config.platform)
    logger.info("═══════════════════════════════════════════════")

    # Start the hotkey listener
    hotkey_listener = HotkeyListener(
        on_press_callback=on_hotkey_press,
        on_release_callback=on_hotkey_release,
    )
    hotkey_listener.start()

    # Start system tray (this blocks on the main thread)
    global _tray_icon
    _tray_icon = _create_tray_icon()

    try:
        if _tray_icon is not None:
            logger.info("System tray icon active. Right-click to quit.")
            _tray_icon.run()  # Blocks until icon.stop() is called
        else:
            # Fallback: just wait for keyboard interrupt
            logger.info("Running without tray. Press Ctrl+C to quit.")
            import time

            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    finally:
        logger.info("Shutting down...")
        hotkey_listener.stop()
        recorder.cleanup()
        close_client()
        logger.info("Goodbye!")


if __name__ == "__main__":
    main()
