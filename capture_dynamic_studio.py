from __future__ import annotations

import subprocess
import time
from pathlib import Path

from isaac_bot.navigation_runtime import navigate_to_point


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "isaac-reels" / "dynamic_studio.mp4"


def main() -> None:
    capture = subprocess.Popen(
        [
            "ffmpeg", "-y", "-f", "gdigrab", "-draw_mouse", "0", "-framerate", "30",
            "-i", "title=Isaac Bot Studio — REELS", "-t", "32",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            str(OUTPUT),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    targets = [(500.0, 280.0), (120.0, 280.0), (320.0, 180.0), (320.0, 400.0)]
    for x, y in targets:
        try:
            result = navigate_to_point(x, y, timeout=7)
            print(result, flush=True)
        except Exception as error:
            print(f"target {(x, y)} failed: {error}", flush=True)
        time.sleep(0.5)
    capture.wait(timeout=40)


if __name__ == "__main__":
    main()
