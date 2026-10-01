"""Live navigation loops built on the versioned Lua bridge."""

from __future__ import annotations

import math
import time
from typing import Any

from .bridge import LuaBridge
from .navigation import Navigator, door_approach_point
from .protocol import Action


def _latest_observation(bridge: LuaBridge, timeout: float = 3.0) -> dict[str, Any]:
    return bridge.wait_for("observation", timeout)


def navigate_to_point(x: float, y: float, timeout: float = 15.0, tick_hz: float = 30.0) -> dict[str, Any]:
    period = 1.0 / tick_hz
    with LuaBridge(timeout=0.01) as bridge:
        observation = _latest_observation(bridge)
        navigator = Navigator()
        navigator.plan(observation, (x, y))
        bridge.command("GOAL", f"{x} {y} NAVIGATE_POINT")
        deadline = time.monotonic() + timeout
        frames = 0
        last_observation = observation
        while time.monotonic() < deadline:
            started = time.monotonic()
            action, arrived = navigator.act(last_observation)
            bridge.send(action)
            frames += 1
            if arrived:
                bridge.send(Action())
                bridge.command("CLEAR_GOAL")
                return {
                    "success": True, "target": [x, y], "frames": frames,
                    "replans": navigator.replans, "path_cells": len(navigator.path),
                    "position": [last_observation["player"]["x"], last_observation["player"]["y"]],
                }
            while time.monotonic() - started < period:
                message = bridge.receive()
                if message and message.get("type") == "observation":
                    last_observation = message
                if message is None:
                    break
            remaining = period - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)
        bridge.send(Action())
        bridge.command("CLEAR_GOAL")
        return {
            "success": False, "target": [x, y], "frames": frames,
            "replans": navigator.replans,
            "position": [last_observation["player"]["x"], last_observation["player"]["y"]],
        }


def navigate_to_door(
    slot: int | None = None,
    timeout: float = 20.0,
    tick_hz: float = 30.0,
    allow_locked: bool = False,
) -> dict[str, Any]:
    period = 1.0 / tick_hz
    with LuaBridge(timeout=0.01) as bridge:
        observation = _latest_observation(bridge)
        doors = [
            door for door in observation["doors"]
            if door.get("open") or (allow_locked and door.get("locked") and observation["player"].get("keys", 0) > 0)
        ]
        if not doors:
            raise RuntimeError("current room has no open doors")
        if slot is None:
            px, py = observation["player"]["x"], observation["player"]["y"]
            chosen = min(doors, key=lambda door: math.hypot(door["x"] - px, door["y"] - py))
            slot = int(chosen["slot"])
        else:
            chosen = next((door for door in doors if int(door["slot"]) == slot), None)
            if chosen is None:
                raise ValueError(f"door slot {slot} is absent, closed, or cannot be unlocked")

        original_room = int(observation["room_index"])
        target = door_approach_point(observation, slot, inset=52.0)
        navigator = Navigator()
        navigator.plan(observation, target)
        bridge.command("GOAL", f"{target[0]} {target[1]} DOOR_{slot}")
        phase = "approach"
        frames = 0
        deadline = time.monotonic() + timeout
        last_observation = observation

        while time.monotonic() < deadline:
            tick_started = time.monotonic()
            if phase == "approach":
                action, arrived = navigator.act(last_observation)
                player = last_observation["player"]
                close_enough = math.hypot(
                    float(player["x"]) - target[0], float(player["y"]) - target[1]
                ) <= 20.0
                if arrived or close_enough:
                    phase = "cross"
            if phase == "cross":
                player = last_observation["player"]
                dx, dy = float(chosen["x"]) - float(player["x"]), float(chosen["y"]) - float(player["y"])
                scale = max(1.0, abs(dx), abs(dy))
                action = Action(move_x=dx / scale, move_y=dy / scale)
            bridge.send(action)
            frames += 1

            while time.monotonic() - tick_started < period:
                message = bridge.receive()
                if message and message.get("type") == "observation":
                    last_observation = message
                    if int(message["room_index"]) != original_room:
                        bridge.send(Action())
                        bridge.command("CLEAR_GOAL")
                        return {
                            "success": True,
                            "door_slot": slot,
                            "from_room": original_room,
                            "to_room": int(message["room_index"]),
                            "frames": frames,
                            "replans": navigator.replans,
                            "path_cells": len(navigator.path),
                        }
                if message is None:
                    break
            remaining = period - (time.monotonic() - tick_started)
            if remaining > 0:
                time.sleep(remaining)

        bridge.send(Action())
        bridge.command("CLEAR_GOAL")
        return {
            "success": False,
            "door_slot": slot,
            "from_room": original_room,
            "phase": phase,
            "frames": frames,
            "replans": navigator.replans,
            "last_position": last_observation["player"],
        }


def navigate_to_floor_exit(exit_data: dict[str, Any], timeout: float = 15.0, tick_hz: float = 30.0) -> dict[str, Any]:
    """Walk onto a trapdoor/stair grid entity and confirm a stage transition."""
    period = 1.0 / tick_hz
    target = (float(exit_data["x"]), float(exit_data["y"]))
    with LuaBridge(timeout=0.01) as bridge:
        observation = _latest_observation(bridge)
        original_stage = (int(observation["stage"]), int(observation["stage_type"]))
        navigator = Navigator(goal_radius=3.0)
        navigator.plan(observation, target)
        bridge.command("GOAL", f"{target[0]} {target[1]} FLOOR_EXIT")
        deadline = time.monotonic() + timeout
        frames = 0
        last_observation = observation
        while time.monotonic() < deadline:
            started = time.monotonic()
            action, arrived = navigator.act(last_observation)
            if arrived:
                player = last_observation["player"]
                dx, dy = target[0] - float(player["x"]), target[1] - float(player["y"])
                scale = max(1.0, abs(dx), abs(dy))
                action = Action(move_x=dx / scale, move_y=dy / scale)
            bridge.send(action)
            frames += 1
            while time.monotonic() - started < period:
                message = bridge.receive()
                if message and message.get("type") == "observation":
                    last_observation = message
                    current_stage = (int(message["stage"]), int(message["stage_type"]))
                    if current_stage != original_stage:
                        bridge.send(Action())
                        bridge.command("CLEAR_GOAL")
                        return {
                            "success": True, "from_stage": list(original_stage),
                            "to_stage": list(current_stage), "frames": frames,
                        }
                if message is None:
                    break
            remaining = period - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)
        bridge.send(Action())
        bridge.command("CLEAR_GOAL")
        return {"success": False, "from_stage": list(original_stage), "frames": frames}
