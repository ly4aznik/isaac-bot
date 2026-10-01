"""One visible window combining a live Isaac capture and the AI world model."""

from __future__ import annotations

import subprocess
import time
import tkinter as tk
from tkinter import ttk

from PIL import ImageGrab, ImageTk

from .controller import EXE, GAME_DIR, ensure_standard_run
from .visualizer import C, SchematicVisualizer
from .win32 import find_process_by_name, find_window_for_pid, wait_for_window


class StudioWindow:
    def __init__(self, root: tk.Tk, pid: int | None = None, layout: str = "reels") -> None:
        if layout not in {"side", "reels"}:
            raise ValueError("layout must be 'side' or 'reels'")
        self.layout = layout
        self.root = root
        self.root.title(f"Isaac Bot Studio — {layout.upper()}")
        self.root.configure(bg=C["background"])
        if layout == "side":
            self.root.geometry("1600x900")
            self.root.minsize(1100, 650)
        else:
            screen_height = self.root.winfo_screenheight()
            height = min(1200, max(800, int(screen_height * 0.90)))
            width = max(520, int(height * 9 / 16))
            self.root.geometry(f"{width}x{height}")
            self.root.minsize(520, 760)
        self.fullscreen = False
        self.process: subprocess.Popen[bytes] | None = None
        self.capture_image: ImageTk.PhotoImage | None = None
        self.capture_alive = True

        if pid is None:
            pid = find_process_by_name("isaac-ng.exe")
        if pid is None:
            self.process = subprocess.Popen([str(EXE), "--luadebug"], cwd=GAME_DIR)
            pid = self.process.pid
            self.game_hwnd = wait_for_window(pid, timeout=30)
            time.sleep(6)
            ensure_standard_run(self.game_hwnd)
        else:
            self.game_hwnd = find_window_for_pid(pid)
            if not self.game_hwnd:
                raise RuntimeError(f"Isaac process {pid} has no visible window")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Studio.TFrame", background=C["background"])
        style.configure("Studio.TLabel", background=C["background"], foreground=C["text"])

        header = ttk.Frame(root, style="Studio.TFrame", padding=(12, 8))
        header.pack(fill="x")
        ttk.Label(header, text="ISAAC BOT STUDIO", style="Studio.TLabel", font=("Consolas", 13, "bold")).pack(side="left")
        layout_label = "GAME LEFT / MODEL RIGHT" if layout == "side" else "GAME TOP / MODEL BOTTOM — REELS"
        ttk.Label(header, text=layout_label, style="Studio.TLabel", font=("Consolas", 10)).pack(side="right")

        orientation = "horizontal" if layout == "side" else "vertical"
        panes = tk.PanedWindow(root, orient=orientation, sashwidth=6, bg=C["grid"], bd=0, relief="flat")
        panes.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.game_host = tk.Frame(panes, bg="black", bd=0, highlightthickness=0)
        self.model_host = tk.Frame(panes, bg=C["background"], bd=0, highlightthickness=0)
        if layout == "side":
            panes.add(self.game_host, minsize=540, stretch="always")
            panes.add(self.model_host, minsize=430, stretch="always")
        else:
            panes.add(self.game_host, minsize=250, stretch="always")
            panes.add(self.model_host, minsize=420, stretch="always")
        self.game_view = tk.Label(self.game_host, bg="black", bd=0, highlightthickness=0)
        self.game_view.pack(fill="both", expand=True)
        self.visualizer = SchematicVisualizer(self.model_host, embedded=True, compact=(layout == "reels"))

        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Escape>", self._leave_fullscreen)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(1, self._capture_frame)

    def _capture_frame(self) -> None:
        if not self.capture_alive:
            return
        try:
            image = ImageGrab.grab(window=self.game_hwnd, include_layered_windows=True)
            width, height = self.game_host.winfo_width(), self.game_host.winfo_height()
            if width > 10 and height > 10 and image.width > 0 and image.height > 0:
                ratio = min(width / image.width, height / image.height)
                size = (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
                image = image.resize(size)
                self.capture_image = ImageTk.PhotoImage(image)
                self.game_view.configure(image=self.capture_image, text="")
        except (OSError, tk.TclError) as error:
            self.game_view.configure(image="", text=f"GAME CAPTURE UNAVAILABLE\n{error}", fg=C["muted"])
        self.root.after(50, self._capture_frame)

    def _toggle_fullscreen(self, _event: object = None) -> None:
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def _leave_fullscreen(self, _event: object = None) -> None:
        if self.fullscreen:
            self.fullscreen = False
            self.root.attributes("-fullscreen", False)

    def close(self) -> None:
        self.capture_alive = False
        self.visualizer.close()
        self.root.destroy()


def run_studio(pid: int | None = None, layout: str = "reels") -> None:
    root = tk.Tk()
    StudioWindow(root, pid, layout)
    root.mainloop()
