"""
Programmatic tray icons for the Vocatype desktop client.

Generates simple, dependency-light icons (solid colored rounded squares with a
microphone glyph) so the system tray can reflect application state without
bundling external image assets.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

# App colors
_IDLE_COLOR = (127, 0, 255)  # purple
_RECORDING_COLOR = (225, 29, 72)  # red
_SIZE = 64


def _icon_bytes(icon: Image.Image) -> bytes:
    import io

    buf = io.BytesIO()
    icon.save(buf, format="PNG")
    return buf.getvalue()


def _draw_mic(draw: ImageDraw.ImageDraw, color: tuple[int, int, int]) -> None:
    """Draw a simple microphone glyph centered in the icon."""
    cx, cy = _SIZE // 2, _SIZE // 2
    mic_w, mic_h = 14, 22

    # Mic body
    draw.rounded_rectangle(
        [cx - mic_w // 2, cy - mic_h // 2, cx + mic_w // 2, cy + mic_h // 2],
        radius=5,
        fill=color,
    )
    # Mic stand (arc)
    draw.arc(
        [cx - mic_w, cy - mic_h // 2, cx + mic_w, cy + mic_h // 2 + 6],
        start=180,
        end=360,
        fill=color,
        width=3,
    )
    # Stem
    draw.line([cx, cy + mic_h // 2, cx, cy + mic_h // 2 + 6], fill=color, width=3)
    # Base
    draw.line([cx - 8, cy + mic_h // 2 + 8, cx + 8, cy + mic_h // 2 + 8], fill=color, width=3)


def create_icon(recording: bool = False, size: int = _SIZE) -> Image.Image:
    """Create a tray icon for the given state."""
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)

    bg = _RECORDING_COLOR if recording else _IDLE_COLOR
    radius = size // 5
    draw.rounded_rectangle([2, 2, size - 2, size - 2], radius=radius, fill=bg)

    _draw_mic(draw, (255, 255, 255))
    return icon


def load_or_create_icon(recording: bool = False) -> Image.Image:
    """Load a bundled icon file if present, otherwise generate one."""
    icon_path = Path(__file__).resolve().parent.parent / "icon.png"
    if not recording and icon_path.exists():
        try:
            return Image.open(icon_path).convert("RGBA")
        except Exception:
            pass
    return create_icon(recording=recording)


def icon_bytes(recording: bool = False) -> bytes:
    """Return icon bytes (for pystray.image or tests)."""
    return _icon_bytes(load_or_create_icon(recording=recording))
