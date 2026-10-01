"""Continuous single-room combat loop and metrics."""

from __future__ import annotations

import time
from typing import Any

from .bridge import LuaBridge
from .combat import CombatPolicy
from .protocol import Action


def fight_room(timeout: float = 60.0, tick_hz: float = 30.0) -> dict[str, Any]:
    period = 1.0 / tick_hz
    with LuaBridge(timeout=0.008) as bridge:
        observation = bridge.wait_for("observation", 3.0)
        policy = CombatPolicy()
        initial_hearts = observation["player"]["hearts"] + observation["player"]["soul_hearts"]
        initial_room = observation["room_index"]
        initial_enemy_seeds = {e["seed"] for e in observation["entities"] if e["kind"] == "enemy"}
        seen_tears: set[int] = set()
        killed_seeds: set[int] = set()
        last_enemy_seeds = set(initial_enemy_seeds)
        target_switches = 0
        last_target = None
        frames = 0
        started_at = time.monotonic()
        deadline = started_at + timeout
        last_observation_at = started_at
        game_over = False
        telemetry_timeout = False
        projectile_frames = 0
        danger_frames = 0
        dodge_frames = 0
        closest_predicted_distance: float | None = None
        contact_danger_frames = 0

        while time.monotonic() < deadline:
            tick_started = time.monotonic()
            action, target, aim = policy.act(observation)
            projectile_count = sum(1 for entity in observation["entities"] if entity["kind"] == "projectile")
            if projectile_count:
                projectile_frames += 1
            avoidance = policy.last_avoidance
            if avoidance and avoidance.danger:
                danger_frames += 1
            if avoidance and avoidance.dodging:
                dodge_frames += 1
            if avoidance and avoidance.threatening_contacts:
                contact_danger_frames += 1
            if avoidance and avoidance.closest_distance is not None:
                closest_predicted_distance = (
                    avoidance.closest_distance if closest_predicted_distance is None
                    else min(closest_predicted_distance, avoidance.closest_distance)
                )
            if target:
                target_seed = int(target["seed"])
                if target_seed != last_target:
                    target_switches += 1
                    last_target = target_seed
                bridge.command("GOAL", f"{aim[0]} {aim[1]} ENEMY_{target_seed}")
            else:
                bridge.command("CLEAR_GOAL")
            bridge.send(action)
            frames += 1

            while time.monotonic() - tick_started < period:
                message = bridge.receive()
                if message and message.get("type") == "observation":
                    observation = message
                    last_observation_at = time.monotonic()
                    current_enemies = {e["seed"] for e in observation["entities"] if e["kind"] == "enemy"}
                    killed_seeds.update(last_enemy_seeds - current_enemies)
                    last_enemy_seeds = current_enemies
                    seen_tears.update(e["seed"] for e in observation["entities"] if e["kind"] == "tear")
                elif message and message.get("type") == "event" and message.get("event") == "game_end":
                    game_over = bool(message.get("game_over", True))
                    break
                if message is None:
                    break
            if game_over:
                break
            if time.monotonic() - last_observation_at > 2.0:
                telemetry_timeout = True
                break
            if observation["room_clear"] and not any(e["kind"] == "enemy" for e in observation["entities"]):
                bridge.send(Action())
                bridge.command("CLEAR_GOAL")
                break
            remaining = period - (time.monotonic() - tick_started)
            if remaining > 0:
                time.sleep(remaining)

        bridge.send(Action())
        bridge.command("CLEAR_GOAL")
        final_hearts = observation["player"]["hearts"] + observation["player"]["soul_hearts"]
        success = bool(observation["room_clear"]) and not game_over and not telemetry_timeout
        stop_reason = (
            "room_clear" if success else
            "game_over" if game_over else
            "telemetry_timeout" if telemetry_timeout else
            "combat_timeout"
        )
        return {
            "success": success,
            "stop_reason": stop_reason,
            "room_index": initial_room,
            "elapsed_seconds": round(time.monotonic()-started_at, 3),
            "control_frames": frames,
            "initial_enemies": len(initial_enemy_seeds),
            "kills_observed": len(killed_seeds),
            "unique_tears_observed": len(seen_tears),
            "target_switches": target_switches,
            "health_lost": initial_hearts-final_hearts,
            "remaining_enemies": sum(1 for e in observation["entities"] if e["kind"] == "enemy"),
            "projectile_frames": projectile_frames,
            "danger_frames": danger_frames,
            "dodge_frames": dodge_frames,
            "contact_danger_frames": contact_danger_frames,
            "closest_predicted_projectile_distance": (
                None if closest_predicted_distance is None else round(closest_predicted_distance, 3)
            ),
        }
