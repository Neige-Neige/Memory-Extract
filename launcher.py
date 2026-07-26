#!/usr/bin/env python3
# Copyright (c) 2026 Neige-Neige
# SPDX-License-Identifier: AGPL-3.0-or-later
#
"""Tiny launcher for Memory Extract.

Lets you pick between the Qt (PySide6) and Tk versions with one click.
Remembers your last choice and offers a "skip the launcher next time" toggle.

Run via:  python launcher.py
or double-click 启动.bat
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk


HERE = Path(__file__).resolve().parent
LAUNCHER_CONFIG = HERE / ".launcher.json"

APP_QT = HERE / "app_qt.py"
APP_TK = HERE / "app.py"


def load_launcher_config() -> dict:
    if not LAUNCHER_CONFIG.exists():
        return {}
    try:
        return json.loads(LAUNCHER_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_launcher_config(data: dict) -> None:
    try:
        LAUNCHER_CONFIG.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _python_executable() -> str:
    """Return the path to a python that owns a real GUI window. Prefers
    pythonw.exe on Windows so the launched app doesn't drag a black
    console along with it."""
    exe = Path(sys.executable)
    if os.name == "nt":
        candidate = exe.with_name("pythonw.exe")
        if candidate.exists():
            return str(candidate)
    return str(exe)


def launch(target: Path, remember_as: str | None = None) -> None:
    if not target.exists():
        messagebox.showerror("启动器", f"找不到 {target.name}，确认文件存在。")
        return
    cfg = load_launcher_config()
    if remember_as is not None:
        cfg["last_choice"] = remember_as
    save_launcher_config(cfg)

    creationflags = 0
    if os.name == "nt":
        # DETACHED_PROCESS so the child fully decouples from our console.
        creationflags = 0x00000008
    try:
        subprocess.Popen(
            [_python_executable(), str(target)],
            cwd=str(HERE),
            creationflags=creationflags,
        )
    except Exception as exc:  # noqa: BLE001
        messagebox.showerror("启动器", f"启动失败：{exc}")
        return


class Launcher:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.cfg = load_launcher_config()

        root.title("Memory Extract · 启动器")
        root.geometry("520x420")
        try:
            root.tk.call("tk", "scaling", 1.2)
        except Exception:
            pass

        # If skip-launcher is set, immediately fire the previous choice and quit.
        if self.cfg.get("skip_launcher") and self.cfg.get("last_choice"):
            target = APP_QT if self.cfg["last_choice"] == "qt" else APP_TK
            launch(target)
            root.after(100, root.destroy)
            return

        self._build_ui()

    def _build_ui(self) -> None:
        bg = "#F6F2FA"
        accent = "#33539E"
        muted = "#7F6C86"
        self.root.configure(bg=bg)

        title_font = tkfont.Font(family="Microsoft YaHei UI", size=18, weight="bold")
        body_font = tkfont.Font(family="Microsoft YaHei UI", size=11)
        small_font = tkfont.Font(family="Microsoft YaHei UI", size=9)
        btn_font = tkfont.Font(family="Microsoft YaHei UI", size=12, weight="bold")
        sub_font = tkfont.Font(family="Microsoft YaHei UI", size=9)

        wrap = tk.Frame(self.root, bg=bg, padx=24, pady=20)
        wrap.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            wrap, text="📚 Memory Extract",
            font=title_font, bg=bg, fg=accent,
        ).pack(anchor="w")
        tk.Label(
            wrap,
            text="选个版本来逛你的对话归档。",
            font=body_font, bg=bg, fg=muted,
        ).pack(anchor="w", pady=(2, 16))

        # Qt button (recommended)
        qt_frame = tk.Frame(wrap, bg="#FFFFFF", bd=0, highlightthickness=1,
                            highlightbackground="#E4D8EA")
        qt_frame.pack(fill=tk.X, pady=(0, 10))
        qt_inner = tk.Frame(qt_frame, bg="#FFFFFF", padx=16, pady=12)
        qt_inner.pack(fill=tk.BOTH)

        tk.Label(
            qt_inner, text="🪄 Qt 版（推荐）",
            font=btn_font, bg="#FFFFFF", fg=accent,
        ).pack(anchor="w")
        tk.Label(
            qt_inner,
            text="顺滑 · 多层筛选 · 引用源可点击 · DeepSeek 多轮 + 跨对话",
            font=sub_font, bg="#FFFFFF", fg=muted,
        ).pack(anchor="w", pady=(2, 10))
        tk.Button(
            qt_inner, text="启动 Qt 版", font=btn_font,
            bg=accent, fg="#FFFFFF", activebackground="#2A4480",
            activeforeground="#FFFFFF", bd=0, padx=16, pady=8,
            cursor="hand2",
            command=self._launch_qt,
        ).pack(anchor="w")

        # Tk button (legacy)
        tk_frame = tk.Frame(wrap, bg="#FFFFFF", bd=0, highlightthickness=1,
                            highlightbackground="#E4D8EA")
        tk_frame.pack(fill=tk.X, pady=(0, 10))
        tk_inner = tk.Frame(tk_frame, bg="#FFFFFF", padx=16, pady=12)
        tk_inner.pack(fill=tk.BOTH)

        tk.Label(
            tk_inner, text="🛠 Tk 版（旧版）",
            font=btn_font, bg="#FFFFFF", fg="#A5678E",
        ).pack(anchor="w")
        tk.Label(
            tk_inner,
            text="同样的功能，运行更卡，但不用装 PySide6。",
            font=sub_font, bg="#FFFFFF", fg=muted,
        ).pack(anchor="w", pady=(2, 10))
        tk.Button(
            tk_inner, text="启动 Tk 版", font=btn_font,
            bg="#A5678E", fg="#FFFFFF", activebackground="#874E72",
            activeforeground="#FFFFFF", bd=0, padx=16, pady=8,
            cursor="hand2",
            command=self._launch_tk,
        ).pack(anchor="w")

        # Footer: skip-launcher option
        footer = tk.Frame(wrap, bg=bg)
        footer.pack(fill=tk.X, pady=(8, 0))
        self.skip_var = tk.BooleanVar(value=bool(self.cfg.get("skip_launcher")))
        tk.Checkbutton(
            footer, text="下次记住选择，直接启动（按住 Shift 启动可再次出现此窗口）",
            variable=self.skip_var, bg=bg, fg=muted,
            activebackground=bg, activeforeground=muted,
            font=small_font, anchor="w",
        ).pack(side=tk.LEFT)

        last = self.cfg.get("last_choice")
        if last:
            tk.Label(
                wrap,
                text=f"上次启动：{ {'qt': 'Qt 版', 'tk': 'Tk 版'}.get(last, last) }",
                font=small_font, bg=bg, fg=muted,
            ).pack(anchor="w", pady=(8, 0))

    # ------------------------------------------------- Actions

    def _launch_qt(self) -> None:
        self._maybe_save_skip("qt")
        launch(APP_QT, remember_as="qt")
        self.root.after(150, self.root.destroy)

    def _launch_tk(self) -> None:
        self._maybe_save_skip("tk")
        launch(APP_TK, remember_as="tk")
        self.root.after(150, self.root.destroy)

    def _maybe_save_skip(self, choice: str) -> None:
        cfg = load_launcher_config()
        cfg["last_choice"] = choice
        cfg["skip_launcher"] = bool(self.skip_var.get())
        save_launcher_config(cfg)


def main() -> None:
    # Hold Shift while starting to bypass auto-launch even if "skip_launcher" is on.
    shift_held = False
    if os.name == "nt":
        try:
            import ctypes
            VK_SHIFT = 0x10
            shift_held = bool(ctypes.windll.user32.GetAsyncKeyState(VK_SHIFT) & 0x8000)
        except Exception:
            pass

    if shift_held:
        cfg = load_launcher_config()
        cfg["skip_launcher"] = False
        save_launcher_config(cfg)

    root = tk.Tk()
    Launcher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
