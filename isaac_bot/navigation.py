"""Grid pathfinding and local steering for empty Isaac rooms."""

from __future__ import annotations

import heapq
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .protocol import Action


Cell = tuple[int, int]
Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class GridMap:
    width: int
    height: int
    cells: tuple[int, ...]
    origin_x: float
    origin_y: float
    cell_size: float = 40.0

    @classmethod
    def from_observation(cls, observation: dict[str, Any]) -> "GridMap":
        raw = observation["grid"]
        width, height = int(raw["width"]), int(raw["height"])
        cells = tuple(int(value) for value in raw["cells"])
        if width <= 0 or height <= 0 or len(cells) != int(raw["size"]):
            raise ValueError("invalid collision grid dimensions")
        return cls(width, height, cells, float(raw["origin_x"]), float(raw["origin_y"]), float(raw["cell_size"]))

    def index(self, cell: Cell) -> int:
        x, y = cell
        return y * self.width + x

    def contains(self, cell: Cell) -> bool:
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height and self.index(cell) < len(self.cells)

    def passable(self, cell: Cell) -> bool:
        return self.contains(cell) and self.cells[self.index(cell)] == 0

    def neighbors(self, cell: Cell) -> list[Cell]:
        x, y = cell
        return [candidate for candidate in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)) if self.passable(candidate)]

    def cell_to_world(self, cell: Cell) -> Point:
        return self.origin_x + cell[0] * self.cell_size, self.origin_y + cell[1] * self.cell_size

    def world_to_cell(self, point: Point) -> Cell:
        return (
            round((point[0] - self.origin_x) / self.cell_size),
            round((point[1] - self.origin_y) / self.cell_size),
        )

    def nearest_passable(self, cell: Cell, max_radius: int = 4) -> Cell:
        if self.passable(cell):
            return cell
        for radius in range(1, max_radius + 1):
            candidates: list[Cell] = []
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if abs(dx) + abs(dy) == radius:
                        candidate = (cell[0] + dx, cell[1] + dy)
                        if self.passable(candidate):
                            candidates.append(candidate)
            if candidates:
                return min(candidates, key=lambda item: abs(item[0] - cell[0]) + abs(item[1] - cell[1]))
        raise ValueError(f"no passable cell near {cell}")


def astar(grid: GridMap, start: Cell, goal: Cell) -> list[Cell]:
    start = grid.nearest_passable(start)
    goal = grid.nearest_passable(goal)
    frontier: list[tuple[float, Cell]] = [(0.0, start)]
    came_from: dict[Cell, Cell | None] = {start: None}
    cost: dict[Cell, float] = {start: 0.0}
    while frontier:
        _, current = heapq.heappop(frontier)
        if current == goal:
            break
        for neighbor in grid.neighbors(current):
            new_cost = cost[current] + 1.0
            if neighbor not in cost or new_cost < cost[neighbor]:
                cost[neighbor] = new_cost
                priority = new_cost + abs(goal[0] - neighbor[0]) + abs(goal[1] - neighbor[1])
                heapq.heappush(frontier, (priority, neighbor))
                came_from[neighbor] = current
    if goal not in came_from:
        raise ValueError(f"no path from {start} to {goal}")
    path: list[Cell] = []
    current: Cell | None = goal
    while current is not None:
        path.append(current)
        current = came_from[current]
    return list(reversed(path))


def door_approach_point(observation: dict[str, Any], slot: int, inset: float = 18.0) -> Point:
    door = next((door for door in observation["doors"] if int(door["slot"]) == slot), None)
    if door is None:
        raise ValueError(f"door slot {slot} is not present")
    grid = observation["grid"]
    center_x = float(grid["origin_x"]) + (int(grid["width"]) - 1) * float(grid["cell_size"]) / 2
    center_y = float(grid["origin_y"]) + (int(grid["height"]) - 1) * float(grid["cell_size"]) / 2
    dx, dy = center_x - float(door["x"]), center_y - float(door["y"])
    length = max(1.0, math.hypot(dx, dy))
    return float(door["x"]) + dx / length * inset, float(door["y"]) + dy / length * inset


@dataclass(slots=True)
class Navigator:
    waypoint_radius: float = 12.0
    goal_radius: float = 9.0
    stuck_window: int = 18
    stuck_distance: float = 5.0
    path: list[Cell] = field(default_factory=list)
    waypoint: int = 1
    target: Point | None = None
    recent_positions: deque[Point] = field(default_factory=lambda: deque(maxlen=18))
    replans: int = 0

    def plan(self, observation: dict[str, Any], target: Point) -> None:
        grid = GridMap.from_observation(observation)
        player = observation["player"]
        start = grid.world_to_cell((float(player["x"]), float(player["y"])))
        goal = grid.world_to_cell(target)
        self.path = astar(grid, start, goal)
        self.waypoint = 1 if len(self.path) > 1 else 0
        self.target = target
        self.recent_positions = deque(maxlen=self.stuck_window)

    def _is_stuck(self) -> bool:
        if len(self.recent_positions) < self.recent_positions.maxlen:
            return False
        first, last = self.recent_positions[0], self.recent_positions[-1]
        return math.dist(first, last) < self.stuck_distance

    def act(self, observation: dict[str, Any]) -> tuple[Action, bool]:
        if self.target is None or not self.path:
            raise RuntimeError("navigator has no plan")
        player = observation["player"]
        position = (float(player["x"]), float(player["y"]))
        self.recent_positions.append(position)
        if math.dist(position, self.target) <= self.goal_radius:
            return Action(), True
        if self._is_stuck():
            self.replans += 1
            self.plan(observation, self.target)
        grid = GridMap.from_observation(observation)
        while self.waypoint < len(self.path) - 1:
            waypoint = grid.cell_to_world(self.path[self.waypoint])
            if math.dist(position, waypoint) > self.waypoint_radius:
                break
            self.waypoint += 1
        waypoint = self.target if self.waypoint >= len(self.path) - 1 else grid.cell_to_world(self.path[self.waypoint])
        dx, dy = waypoint[0] - position[0], waypoint[1] - position[1]
        scale = max(1.0, abs(dx), abs(dy))
        return Action(move_x=dx / scale, move_y=dy / scale), False
