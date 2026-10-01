from __future__ import annotations

import subprocess
import time
from pathlib import Path

from isaac_bot.navigation_runtime import navigate_to_point


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "isaac-reels" / "enemy_room_studio.mp4"


def main() -> None:
    capture = subprocess.Popen(
        [
            "ffmpeg", "-y", "-f", "gdigrab", "-draw_mouse", "0",
            "-framerate", "30", "-i", "title=Isaac Bot Studio — REELS",
            "-t", "12", "-c:v", "libx264", "-preset", "ultrafast",
            "-crf", "18", str(OUTPUT),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    for x, y in [(500.0, 180.0), (500.0, 380.0), (400.0, 280.0)]:
        try:
            print(navigate_to_point(x, y, timeout=3), flush=True)
        except Exception as error:
            print(f"target {(x, y)} failed: {error}", flush=True)
        time.sleep(0.25)
    capture.wait(timeout=18)


if __name__ == "__main__":
    main()
