"""High-level loop that clears rooms and advances through open doors."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

from .bridge import LuaBridge
from .combat_runtime import fight_room
from .exploration import FloorExplorer, ROOM_BOSS
from .navigation_runtime import navigate_to_door, navigate_to_floor_exit, navigate_to_point
from .win32 import find_process_by_name, focus_window, tap, wait_for_window


def _observation(timeout: float = 3.0) -> dict[str, Any]:
    with LuaBridge(timeout=0.02) as bridge:
        return bridge.wait_for("observation", timeout)


def _choose_door(observation: dict[str, Any], previous_room: int | None) -> dict[str, Any] | None:
    doors = [door for door in observation["doors"] if door.get("open")]
    if not doors:
        return None
    forward = [door for door in doors if int(door.get("target_room", -1)) != previous_room]
    candidates = forward or doors
    player = observation["player"]
    return min(
        candidates,
        key=lambda door: math.hypot(float(door["x"]) - player["x"], float(door["y"]) - player["y"]),
    )


def _collect_safe_pickups(limit: int = 4) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect free, generally beneficial pickups after a room is clear."""
    collected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    attempted: set[int] = set()
    for _ in range(limit):
        observation = _observation()
        player = observation["player"]
        candidates = []
        for entity in observation["entities"]:
            if entity.get("kind") != "pickup" or int(entity.get("seed", 0)) in attempted:
                continue
            variant = int(entity.get("variant", -1))
            if entity.get("shop_item") or float(entity.get("price", 0)) != 0:
                continue
            if variant == 10 and int(player["hearts"]) >= int(player["max_hearts"]):
                continue
            if variant not in {10, 20, 30, 40, 69, 100, 350}:
                continue
            candidates.append(entity)
        if not candidates:
            break
        px, py = float(player["x"]), float(player["y"])
        pickup = min(candidates, key=lambda item: math.hypot(float(item["x"])-px, float(item["y"])-py))
        attempted.add(int(pickup["seed"]))
        try:
            result = navigate_to_point(float(pickup["x"]), float(pickup["y"]), timeout=8.0)
        except (ValueError, RuntimeError) as error:
            skipped.append({"seed": int(pickup["seed"]), "reason": str(error)})
            continue
        if result["success"]:
            collected.append({
                "seed": int(pickup["seed"]), "variant": int(pickup["variant"]),
                "subtype": int(pickup["subtype"]),
            })
        else:
            skipped.append({"seed": int(pickup["seed"]), "reason": "navigation_timeout"})
        time.sleep(0.15)
    return collected, skipped


def traverse_rooms(count: int = 20, room_timeout: float = 60.0, log_path: Path | None = None) -> dict[str, Any]:
    """Clear and leave rooms until count is reached or the run can no longer advance."""
    results: list[dict[str, Any]] = []
    previous_room: int | None = None
    explorer = FloorExplorer()
    floors_completed = 0
    started = time.monotonic()
    stop_reason = "room_limit"

    while count <= 0 or len(results) < count:
        observation = _observation()
        explorer.observe(observation)
        room_index = int(observation["room_index"])
        hearts = observation["player"]["hearts"] + observation["player"]["soul_hearts"]
        if hearts <= 0:
            stop_reason = "player_dead"
            break

        combat = fight_room(timeout=room_timeout)
        entry: dict[str, Any] = {
            "run_id": int(observation["run_id"]),
            "stage": int(observation["stage"]),
            "room": room_index,
            "combat": combat,
        }
        if not combat["success"]:
            entry["transition"] = None
            results.append(entry)
            stop_reason = str(combat.get("stop_reason", "combat_timeout"))
            break

        collected, skipped_pickups = _collect_safe_pickups()
        entry["pickups_collected"] = collected
        entry["pickups_skipped"] = skipped_pickups
        observation = _observation()
        explorer.observe(observation)

        if int(observation["room_type"]) == ROOM_BOSS and not observation.get("floor_exits"):
            time.sleep(0.75)
            observation = _observation()
            explorer.observe(observation)
        floor_exits = observation.get("floor_exits", [])
        if int(observation["room_type"]) == ROOM_BOSS and floor_exits:
            floor_transition = navigate_to_floor_exit(floor_exits[0], timeout=15.0)
            entry["floor_transition"] = floor_transition
            entry["transition"] = None
            entry["exploration"] = explorer.snapshot()
            results.append(entry)
            if log_path is not None:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            if not floor_transition["success"]:
                stop_reason = "floor_exit_timeout"
                break
            floors_completed += 1
            previous_room = None
            time.sleep(1.0)
            continue

        chosen = explorer.choose_door(observation)
        if chosen is None:
            entry["transition"] = None
            entry["exploration"] = explorer.snapshot()
            results.append(entry)
            stop_reason = "floor_explored_no_exit"
            break

        transition = navigate_to_door(int(chosen["slot"]), timeout=20.0, allow_locked=True)
        entry["transition"] = transition
        entry["exploration"] = explorer.snapshot()
        results.append(entry)
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if not transition["success"]:
            stop_reason = "door_timeout"
            break
        explorer.note_transition(room_index, int(transition["to_room"]))
        previous_room = room_index
        time.sleep(0.25)

    return {
        "success": stop_reason == "room_limit",
        "stop_reason": stop_reason,
        "rooms_processed": len(results),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "floors_completed": floors_completed,
        "exploration": explorer.snapshot(),
        "rooms": results,
    }


def _set_auto_restart(enabled: bool) -> None:
    with LuaBridge(timeout=0.05) as bridge:
        bridge.command("AUTO_RESTART", "1" if enabled else "0")


def _restart_and_wait(previous_run_id: int | None, timeout: float = 8.0) -> dict[str, Any]:
    with LuaBridge(timeout=0.05) as bridge:
        # This is the clean path while Lua callbacks are still ticking.
        bridge.command("RESTART")
        lua_deadline = time.monotonic() + 1.0
        while time.monotonic() < lua_deadline:
            bridge.hello()
            message = bridge.receive()
            if message and message.get("type") == "observation":
                if previous_run_id is None or int(message["run_id"]) != previous_run_id:
                    return message

        # On the game-over screen MC_POST_UPDATE no longer runs, so Lua cannot
        # receive UDP commands. Use Isaac's native hold-R restart as fallback.
        pid = find_process_by_name("isaac-ng.exe")
        if pid is None:
            raise RuntimeError("Isaac process is not running")
        hwnd = wait_for_window(pid, timeout=2.0)
        focus_window(hwnd)
        tap(0x52, duration=1.25)  # Virtual-key R; Isaac requires a hold.

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            bridge.hello()
            message = bridge.receive()
            if message and message.get("type") == "observation":
                if previous_run_id is None or int(message["run_id"]) != previous_run_id:
                    return message
        raise TimeoutError("new run did not start after Lua RESTART or native hold-R fallback")


def _run_summary(result: dict[str, Any]) -> dict[str, Any]:
    rooms = result["rooms"]
    combats = [entry["combat"] for entry in rooms]
    return {
        "run_id": rooms[0]["run_id"] if rooms else None,
        "stop_reason": result["stop_reason"],
        "elapsed_seconds": result["elapsed_seconds"],
        "rooms_processed": len(rooms),
        "highest_stage": max((entry["stage"] for entry in rooms), default=None),
        "enemies_killed": sum(item["kills_observed"] for item in combats),
        "damage_taken": sum(item["health_lost"] for item in combats),
        "tears_observed": sum(item["unique_tears_observed"] for item in combats),
        "combat_time_seconds": round(sum(item["elapsed_seconds"] for item in combats), 3),
        "projectile_frames": sum(item.get("projectile_frames", 0) for item in combats),
        "danger_frames": sum(item.get("danger_frames", 0) for item in combats),
        "dodge_frames": sum(item.get("dodge_frames", 0) for item in combats),
        "contact_danger_frames": sum(item.get("contact_danger_frames", 0) for item in combats),
        "pickups_collected": sum(len(entry.get("pickups_collected", [])) for entry in rooms),
        "floors_completed": result.get("floors_completed", 0),
        "unique_rooms": result.get("exploration", {}).get("unique_rooms", 0),
        "backtracks": result.get("exploration", {}).get("backtracks", 0),
    }


def interactive_runs(room_timeout: float = 60.0, log_path: Path | None = None) -> None:
    """Run autonomously, show statistics, then wait for R before restarting."""
    _set_auto_restart(False)
    while True:
        print("\nIsaac Bot autonomous run started. Auto-restart is OFF.\n", flush=True)
        try:
            result = traverse_rooms(count=0, room_timeout=room_timeout, log_path=log_path)
        except Exception as error:
            result = {
                "stop_reason": f"controller_error: {type(error).__name__}: {error}",
                "elapsed_seconds": 0.0,
                "rooms": [],
            }
        summary = _run_summary(result)
        print("\n" + "=" * 56, flush=True)
        print("RUN FINISHED / CONTROLLER STOPPED", flush=True)
        print("=" * 56, flush=True)
        for key, value in summary.items():
            print(f"{key.replace('_', ' ').title():24} {value}", flush=True)
        print("=" * 56, flush=True)

        while True:
            choice = input("Press R to start a new run, or Q to quit: ").strip().lower()
            if choice == "q":
                return
            if choice == "r":
                try:
                    observation = _restart_and_wait(summary["run_id"])
                except Exception as error:
                    print(f"Restart failed: {type(error).__name__}: {error}", flush=True)
                    print("The controller is still active; press R to retry or Q to quit.", flush=True)
                    continue
                else:
                    print(f"New run confirmed: run_id={observation['run_id']}", flush=True)
                    break
            print("Unknown key. Use R or Q.", flush=True)
