from __future__ import annotations

import math
import subprocess
import time
from pathlib import Path
from typing import Any

from isaac_bot.bridge import LuaBridge
from isaac_bot.navigation_runtime import navigate_to_door
from isaac_bot.protocol import Action


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "isaac-reels" / "continuous-bot-run-60s.mp4"
DURATION = 60.0


def latest_observation(timeout: float = 3.0) -> dict[str, Any]:
    with LuaBridge(timeout=0.03) as bridge:
        return bridge.wait_for("observation", timeout)


def fight_until_clear(deadline: float) -> None:
    with LuaBridge(timeout=0.01) as bridge:
        observation = bridge.wait_for("observation", 3.0)
        while time.monotonic() < deadline and not observation.get("room_clear", False):
            enemies = [entity for entity in observation["entities"] if entity["kind"] == "enemy"]
            if not enemies:
                bridge.send(Action())
            else:
                player = observation["player"]
                px, py = float(player["x"]), float(player["y"])
                target = min(enemies, key=lambda e: math.hypot(float(e["x"]) - px, float(e["y"]) - py))
                dx, dy = float(target["x"]) - px, float(target["y"]) - py
                distance = max(1.0, math.hypot(dx, dy))
                shoot_x, shoot_y = dx / distance, dy / distance

                # Orbit the target while keeping a comfortable firing distance.
                orbit_sign = -1.0 if (int(observation["frame"]) // 75) % 2 else 1.0
                move_x, move_y = -shoot_y * orbit_sign, shoot_x * orbit_sign
                if distance < 135:
                    move_x -= shoot_x * 0.8
                    move_y -= shoot_y * 0.8
                elif distance > 260:
                    move_x += shoot_x * 0.35
                    move_y += shoot_y * 0.35
                scale = max(1.0, abs(move_x), abs(move_y))
                bridge.send(Action(move_x=move_x / scale, move_y=move_y / scale, shoot_x=shoot_x, shoot_y=shoot_y))

            tick_end = time.monotonic() + 1 / 30
            while time.monotonic() < tick_end:
                message = bridge.receive()
                if message and message.get("type") == "observation":
                    observation = message
                elif message is None:
                    break
            remaining = tick_end - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
        bridge.send(Action())


def main() -> None:
    capture = subprocess.Popen(
        [
            "ffmpeg", "-y", "-f", "gdigrab", "-draw_mouse", "0",
            "-framerate", "30", "-i", "title=Isaac Bot Studio — REELS",
            "-t", str(DURATION), "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "18", "-pix_fmt", "yuv420p", str(OUTPUT),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    started = time.monotonic()
    deadline = started + DURATION
    previous_room: int | None = None
    previous_slot: int | None = None
    time.sleep(1.0)

    while time.monotonic() < deadline - 1.0:
        try:
            observation = latest_observation()
            room = int(observation["room_index"])
            enemies = [entity for entity in observation["entities"] if entity["kind"] == "enemy"]
            print(f"room={room} enemies={len(enemies)} clear={observation.get('room_clear')}", flush=True)
            if enemies or not observation.get("room_clear", False):
                fight_until_clear(min(deadline - 0.5, time.monotonic() + 18.0))
                continue

            doors = [door for door in observation["doors"] if door.get("open")]
            if not doors:
                time.sleep(0.25)
                continue
            candidates = [door for door in doors if int(door["slot"]) != previous_slot]
            chosen = candidates[0] if candidates else doors[0]
            result = navigate_to_door(int(chosen["slot"]), timeout=min(12.0, deadline - time.monotonic()))
            print(result, flush=True)
            if result.get("success"):
                previous_room = room
                # Opposite door pairs are 0↔2 and 1↔3.
                previous_slot = int(chosen["slot"]) ^ 2
            else:
                previous_slot = None
        except Exception as error:
            print(f"phase failed: {error}", flush=True)
            time.sleep(0.3)

    capture.wait(timeout=15)
    print(f"saved {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
