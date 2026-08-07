# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Vocatype desktop client.
#
# Build with:
#   pyinstaller --clean --noconfirm desktop/vocatype.spec
#   (run from the repo root)

from pathlib import Path

app_root = Path(SPECPATH) / "app"

a = Analysis(
    [str(app_root / "main.py")],
    pathex=[str(app_root)],
    binaries=[],
    datas=[(str(app_root), "app")],
    hiddenimports=[
        "pynput.keyboard._win32",
        "pynput.keyboard._xorg",
        "pynput.keyboard._darwin",
        "pystray._win32",
        "pystray._xorg",
        "pystray._darwin",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "IPython",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="vocatype",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # system-tray app, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
