from __future__ import annotations

import subprocess
import time
from pathlib import Path

from capture_continuous_bot_run import latest_observation
from isaac_bot.navigation_runtime import navigate_to_door


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "isaac-reels"
GAME = OUT / "continuous-game-raw.mp4"
MODEL = OUT / "continuous-model-raw.mp4"
FINAL = OUT / "continuous-bot-run-game-and-model-60s.mp4"
DURATION = 60.0


def recorder(title: str, output: Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            "ffmpeg", "-y", "-f", "gdigrab", "-draw_mouse", "0",
            "-framerate", "30", "-i", f"title={title}", "-t", str(DURATION),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(output),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    game_capture = recorder("Binding of Isaac: Repentance+ v1.9.7.14", GAME)
    model_capture = recorder("Isaac Bot — Internal World Model", MODEL)
    deadline = time.monotonic() + DURATION
    previous_slot: int | None = None
    time.sleep(1.0)

    while time.monotonic() < deadline - 1.0:
        observation = latest_observation()
        doors = [door for door in observation["doors"] if door.get("open")]
        if not doors:
            time.sleep(0.2)
            continue
        candidates = [door for door in doors if int(door["slot"]) != previous_slot]
        chosen = candidates[0] if candidates else doors[0]
        result = navigate_to_door(int(chosen["slot"]), timeout=min(12.0, deadline - time.monotonic()))
        print(result, flush=True)
        previous_slot = int(chosen["slot"]) ^ 2 if result.get("success") else None

    game_capture.wait(timeout=15)
    model_capture.wait(timeout=15)
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(GAME), "-i", str(MODEL),
            "-filter_complex",
            "[0:v]scale=1080:608:force_original_aspect_ratio=decrease,pad=1080:608:(ow-iw)/2:(oh-ih)/2:black[g];"
            "[1:v]scale=1080:900:force_original_aspect_ratio=increase,crop=1080:900[m];"
            "[g][m]vstack=inputs=2[stack];[stack]pad=1080:1920:0:206:black[out]",
            "-map", "[out]", "-t", str(DURATION), "-c:v", "libx264",
            "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(FINAL),
        ],
        check=True,
    )
    print(f"saved {FINAL}", flush=True)


if __name__ == "__main__":
    main()
