"""Short-horizon projectile prediction and movement selection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .navigation import GridMap


Move = tuple[float, float]


@dataclass(slots=True)
class AvoidanceDecision:
    move: Move
    danger: bool
    dodging: bool
    risk: float
    closest_distance: float | None
    threatening_projectiles: int
    threatening_contacts: int


def _closest_approach(
    player: tuple[float, float],
    player_velocity: Move,
    projectile: dict[str, Any],
    horizon_frames: float,
) -> tuple[float, float]:
    """Return (distance, time) for two constant-velocity bodies."""
    rx = float(projectile["x"]) - player[0]
    ry = float(projectile["y"]) - player[1]
    rvx = float(projectile["vx"]) - player_velocity[0]
    rvy = float(projectile["vy"]) - player_velocity[1]
    speed_sq = rvx * rvx + rvy * rvy
    if speed_sq < 1e-9:
        t = 0.0
    else:
        t = max(0.0, min(horizon_frames, -(rx * rvx + ry * rvy) / speed_sq))
    return math.hypot(rx + rvx * t, ry + rvy * t), t


def _candidate_moves(preferred: Move) -> list[Move]:
    diagonal = 1.0 / math.sqrt(2.0)
    moves: list[Move] = [preferred]
    moves.extend([
        (0.0, 0.0), (1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0),
        (diagonal, diagonal), (diagonal, -diagonal), (-diagonal, diagonal), (-diagonal, -diagonal),
    ])
    unique: list[Move] = []
    for move in moves:
        if not any(math.hypot(move[0]-old[0], move[1]-old[1]) < 1e-6 for old in unique):
            unique.append(move)
    return unique


def _path_is_passable(grid: GridMap, player: tuple[float, float], move: Move, player_speed: float, horizon: float) -> bool:
    # Check several points so a safe endpoint cannot hide a wall crossed en route.
    for fraction in (0.25, 0.5, 0.75, 1.0):
        point = (
            player[0] + move[0] * player_speed * horizon * fraction,
            player[1] + move[1] * player_speed * horizon * fraction,
        )
        if not grid.passable(grid.world_to_cell(point)):
            return False
    return True


def choose_safe_movement(
    observation: dict[str, Any],
    preferred: Move,
    *,
    horizon_frames: float = 24.0,
    player_speed: float = 4.0,
    safety_radius: float = 27.0,
) -> AvoidanceDecision:
    """Choose a collision-grid-safe move with the lowest predicted projectile risk."""
    projectiles = [entity for entity in observation["entities"] if entity["kind"] == "projectile"]
    enemies = [entity for entity in observation["entities"] if entity["kind"] == "enemy" and entity.get("hp", 0) > 0]

    player = (float(observation["player"]["x"]), float(observation["player"]["y"]))
    grid = GridMap.from_observation(observation)
    assessments: list[tuple[float, float, Move, int, int]] = []
    preferred_assessment: tuple[float, float, Move, int, int] | None = None

    for move in _candidate_moves(preferred):
        if not _path_is_passable(grid, player, move, player_speed, horizon_frames):
            continue
        velocity = (move[0] * player_speed, move[1] * player_speed)
        risk = 0.0
        closest = math.inf
        threatening = 0
        contact_threats = 0
        for projectile in projectiles:
            distance, when = _closest_approach(player, velocity, projectile, horizon_frames)
            closest = min(closest, distance)
            radius = safety_radius + min(12.0, float(projectile.get("size", 0.0)) * 0.35)
            if distance < radius:
                threatening += 1
                severity = (radius - distance) / radius
                urgency = 1.0 - when / horizon_frames
                risk += 100.0 * severity * severity + 25.0 * urgency
        for enemy in enemies:
            distance, when = _closest_approach(player, velocity, enemy, min(14.0, horizon_frames))
            contact_radius = 25.0 + min(24.0, float(enemy.get("size", 10.0)) * 0.7)
            if distance < contact_radius:
                contact_threats += 1
                severity = (contact_radius - distance) / contact_radius
                urgency = 1.0 - when / min(14.0, horizon_frames)
                risk += 140.0 * severity * severity + 35.0 * urgency
        deviation = (move[0] - preferred[0]) ** 2 + (move[1] - preferred[1]) ** 2
        score = risk + deviation * 2.5
        assessment = (score, closest, move, threatening, contact_threats)
        assessments.append(assessment)
        if move == preferred:
            preferred_assessment = assessment

    if not assessments:
        return AvoidanceDecision(
            (0.0, 0.0), True, preferred != (0.0, 0.0), math.inf, 0.0,
            len(projectiles), len(enemies),
        )

    best = min(assessments, key=lambda item: (item[0], -item[1]))
    baseline = preferred_assessment or best
    danger = baseline[3] > 0 or baseline[4] > 0
    selected = best[2] if danger else preferred
    dodging = danger and math.hypot(selected[0]-preferred[0], selected[1]-preferred[1]) > 0.15
    closest_projectile = None if not projectiles or math.isinf(best[1]) else best[1]
    return AvoidanceDecision(selected, danger, dodging, best[0], closest_projectile, baseline[3], baseline[4])
