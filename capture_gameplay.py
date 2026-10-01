from __future__ import annotations

import subprocess
import time
from pathlib import Path

from isaac_bot.navigation_runtime import navigate_to_door
from isaac_bot.win32 import find_window_for_pid, focus_window


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "isaac-reels" / "gameplay_capture.mp4"
GAME_PID = 20096


def main() -> None:
    capture = subprocess.Popen(
        [
            "ffmpeg", "-y", "-f", "gdigrab", "-framerate", "30",
            "-i", "desktop", "-t", "18", "-c:v", "libx264",
            "-preset", "ultrafast", "-crf", "18", str(OUTPUT),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    focus_window(find_window_for_pid(GAME_PID))
    time.sleep(2)
    print(navigate_to_door(timeout=12))
    time.sleep(5)
    capture.wait(timeout=20)


if __name__ == "__main__":
    main()
