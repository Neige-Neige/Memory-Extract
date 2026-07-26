#!/usr/bin/env python3
# Copyright (c) 2026 Neige-Neige
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Bundle Memory Extract into a Windows .exe via PyInstaller.

Usage::

    pip install pyinstaller
    python build_exe.py

Output::

    dist/Memory-Extract/
        Memory-Extract.exe   ← double-click to launch
        _internal/                   ← Qt DLLs + Python runtime
        ...

The whole `dist/Memory-Extract/` folder is what you ship — zip
it and send it to whoever wants to use the app without installing
Python.

Notes
-----
* We use **--onedir** (a folder with the .exe inside) rather than
  --onefile because PySide6 ships ~150 MB of Qt libraries; --onefile
  would unzip them to a temp dir on every launch (5-10 s startup),
  --onedir launches in well under a second.
* Texture cache and config go to ``%APPDATA%\\memory_extract``
  so the bundle stays read-only and signing-friendly.
* No icon by default — drop a ``.ico`` next to this script and pass it
  via ``--icon`` if you want one.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP_NAME = "Memory-Extract"
ENTRY = HERE / "app_qt.py"


def _conda_runtime_binaries() -> list[str]:
    """DLLs that PyInstaller can miss in Conda-based Python installs."""
    bin_dir = Path(sys.prefix) / "Library" / "bin"
    names = [
        "ffi.dll",
        "libbz2.dll",
        "libcrypto-3-x64.dll",
        "libexpat.dll",
        "liblzma.dll",
        "libmpdec-4.dll",
        "libssl-3-x64.dll",
    ]
    return [
        f"{bin_dir / name}{';.' if sys.platform == 'win32' else ':. '}"
        for name in names
        if (bin_dir / name).exists()
    ]


def main() -> int:
    if shutil.which("pyinstaller") is None:
        try:
            import PyInstaller  # noqa: F401
        except ImportError:
            print("PyInstaller is not installed.")
            print("Run:  pip install pyinstaller")
            return 1

    if not ENTRY.exists():
        print(f"Entry point {ENTRY} not found — run this script from the project root.")
        return 1

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--noconfirm",
        "--clean",
        "--windowed",          # no black console window
        "--onedir",            # folder bundle, fast launch
        # Quietly drop the Qt modules we don't use to shave ~80MB:
        "--exclude-module", "PySide6.QtNetwork",
        "--exclude-module", "PySide6.QtMultimedia",
        "--exclude-module", "PySide6.QtMultimediaWidgets",
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtWebEngineWidgets",
        "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "PySide6.Qt3DCore",
        "--exclude-module", "PySide6.QtCharts",
        "--exclude-module", "PySide6.QtDataVisualization",
        "--exclude-module", "PySide6.QtSql",
        "--exclude-module", "PySide6.QtPdf",
        "--exclude-module", "PySide6.QtPdfWidgets",
        "--exclude-module", "PySide6.QtTest",
        "--exclude-module", "PySide6.QtBluetooth",
        "--exclude-module", "PySide6.QtPositioning",
        "--exclude-module", "PySide6.QtSerialPort",
        "--icon", str(HERE / "app.ico"),
        str(ENTRY),
    ]
    for binary in _conda_runtime_binaries():
        cmd[cmd.index(str(ENTRY)):cmd.index(str(ENTRY))] = ["--add-binary", binary]

    print("Running PyInstaller …")
    print("  " + " ".join(cmd))
    print()
    try:
        subprocess.check_call(cmd, cwd=str(HERE))
    except subprocess.CalledProcessError as exc:
        print(f"\nPyInstaller failed (exit {exc.returncode}).")
        return exc.returncode

    out_dir = HERE / "dist" / APP_NAME
    if out_dir.is_dir():
        print()
        print(f"Bundle ready: {out_dir}")
        print(f"  zip it (or use Windows .zip Send-To) and ship the whole folder.")
        print(f"  Recipients double-click {APP_NAME}.exe — no Python install needed.")
    else:
        print(f"Hmm, expected output at {out_dir} but it's missing — check PyInstaller logs.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
