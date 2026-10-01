"""Stage 3 target selection and predictive shooting policy."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .avoidance import AvoidanceDecision, choose_safe_movement
from .navigation import GridMap
from .protocol import Action


def intercept_point(player: tuple[float, float], enemy: dict[str, Any], tear_speed: float = 10.0) -> tuple[float, float]:
    """Solve a constant-velocity interception, falling back to direct aim."""
    rx, ry = float(enemy["x"]) - player[0], float(enemy["y"]) - player[1]
    vx, vy = float(enemy["vx"]), float(enemy["vy"])
    a = vx*vx + vy*vy - tear_speed*tear_speed
    b = 2.0 * (rx*vx + ry*vy)
    c = rx*rx + ry*ry
    t = 0.0
    if abs(a) < 1e-8:
        if abs(b) > 1e-8:
            t = max(0.0, -c / b)
    else:
        discriminant = b*b - 4*a*c
        if discriminant >= 0:
            root = math.sqrt(discriminant)
            candidates = [value for value in ((-b-root)/(2*a), (-b+root)/(2*a)) if value > 0]
            if candidates:
                t = min(candidates)
    t = min(t, 45.0)
    return float(enemy["x"]) + vx*t, float(enemy["y"]) + vy*t


def normalized(dx: float, dy: float, strength: float = 1.0) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return 0.0, 0.0
    return dx/length*strength, dy/length*strength


@dataclass(slots=True)
class CombatPolicy:
    preferred_distance: float = 180.0
    minimum_distance: float = 125.0
    maximum_distance: float = 260.0
    target_seed: int | None = None
    last_avoidance: AvoidanceDecision | None = None
    target_last_hp: float | None = None
    target_stale_frames: int = 0
    stale_target_limit: int = 120

    def select_target(self, observation: dict[str, Any]) -> dict[str, Any] | None:
        enemies = [entity for entity in observation["entities"] if entity["kind"] == "enemy" and entity["hp"] > 0]
        if not enemies:
            self.target_seed = None
            self.target_last_hp = None
            self.target_stale_frames = 0
            return None
        current = next((enemy for enemy in enemies if int(enemy["seed"]) == self.target_seed), None)
        if current:
            hp = float(current["hp"])
            if self.target_last_hp is None or hp < self.target_last_hp - 1e-4:
                self.target_stale_frames = 0
            else:
                self.target_stale_frames += 1
            self.target_last_hp = hp
            if self.target_stale_frames < self.stale_target_limit or len(enemies) == 1:
                return current
        player = observation["player"]
        alternatives = [enemy for enemy in enemies if int(enemy["seed"]) != self.target_seed] or enemies
        current = min(alternatives, key=lambda enemy: math.hypot(enemy["x"]-player["x"], enemy["y"]-player["y"]))
        self.target_seed = int(current["seed"])
        self.target_last_hp = float(current["hp"])
        self.target_stale_frames = 0
        return current

    def _safe_movement(self, observation: dict[str, Any], move: tuple[float, float]) -> tuple[float, float]:
        if move == (0.0, 0.0):
            return move
        grid = GridMap.from_observation(observation)
        player = observation["player"]
        future = (float(player["x"]) + move[0]*28, float(player["y"]) + move[1]*28)
        if grid.passable(grid.world_to_cell(future)):
            return move
        alternatives = ((-move[1], move[0]), (move[1], -move[0]), (0.0, 0.0))
        for candidate in alternatives:
            future = (float(player["x"])+candidate[0]*28, float(player["y"])+candidate[1]*28)
            if grid.passable(grid.world_to_cell(future)):
                return candidate
        return 0.0, 0.0

    def act(self, observation: dict[str, Any]) -> tuple[Action, dict[str, Any] | None, tuple[float, float] | None]:
        target = self.select_target(observation)
        if not target:
            self.last_avoidance = None
            return Action(), None, None
        player = observation["player"]
        px, py = float(player["x"]), float(player["y"])
        aim = intercept_point((px, py), target)
        shoot_x, shoot_y = normalized(aim[0]-px, aim[1]-py)
        distance = math.hypot(float(target["x"])-px, float(target["y"])-py)
        if distance < self.minimum_distance:
            move = normalized(px-float(target["x"]), py-float(target["y"]), 0.85)
        elif distance > self.maximum_distance:
            move = normalized(float(target["x"])-px, float(target["y"])-py, 0.45)
        else:
            # Gentle orbit prevents a stationary firing solution without trying
            # to solve projectile dodging (that belongs to stage 4).
            move = normalized(-(float(target["y"])-py), float(target["x"])-px, 0.28)
        move = self._safe_movement(observation, move)
        self.last_avoidance = choose_safe_movement(observation, move)
        move_x, move_y = self.last_avoidance.move
        return Action(move_x=move_x, move_y=move_y, shoot_x=shoot_x, shoot_y=shoot_y), target, aim
