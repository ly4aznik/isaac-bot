from __future__ import annotations

import subprocess
import time
from pathlib import Path

from isaac_bot.navigation_runtime import navigate_to_point
from isaac_bot.win32 import find_process_by_name, find_window_for_pid, focus_window


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "isaac-reels" / "enemy_gameplay_desktop.mp4"


def main() -> None:
    pid = find_process_by_name("isaac-ng.exe")
    if pid is None:
        raise RuntimeError("Isaac is not running")
    capture = subprocess.Popen(
        [
            "ffmpeg", "-y", "-f", "gdigrab", "-draw_mouse", "0",
            "-framerate", "30", "-i", "desktop", "-t", "12",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            str(OUTPUT),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    focus_window(find_window_for_pid(pid))
    time.sleep(0.5)
    for x, y in [(500.0, 180.0), (500.0, 380.0), (380.0, 260.0)]:
        try:
            print(navigate_to_point(x, y, timeout=3), flush=True)
        except Exception as error:
            print(f"target {(x, y)} failed: {error}", flush=True)
    capture.wait(timeout=18)


if __name__ == "__main__":
    main()
