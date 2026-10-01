"""Persistent floor graph and frontier selection for stage 5 exploration."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


ROOM_SHOP = 2
ROOM_TREASURE = 4
ROOM_BOSS = 5


@dataclass(slots=True)
class RoomMemory:
    room_index: int
    room_type: int
    visits: int = 0
    doors: dict[int, dict[str, Any]] = field(default_factory=dict)


@dataclass(slots=True)
class FloorExplorer:
    floor_key: tuple[int, int] | None = None
    rooms: dict[int, RoomMemory] = field(default_factory=dict)
    transitions: int = 0
    backtracks: int = 0
    special_rooms: set[int] = field(default_factory=set)

    def observe(self, observation: dict[str, Any]) -> None:
        floor_key = (int(observation["stage"]), int(observation["stage_type"]))
        if self.floor_key != floor_key:
            self.floor_key = floor_key
            self.rooms.clear()
            self.transitions = 0
            self.backtracks = 0
            self.special_rooms.clear()
        index = int(observation["room_index"])
        room = self.rooms.get(index)
        if room is None:
            room = RoomMemory(index, int(observation["room_type"]))
            self.rooms[index] = room
        room.room_type = int(observation["room_type"])
        room.visits += 1
        room.doors = {int(door["slot"]): dict(door) for door in observation["doors"]}
        if room.room_type not in (1, 0):
            self.special_rooms.add(room.room_type)

    @staticmethod
    def _door_accessible(door: dict[str, Any], keys: int) -> bool:
        return bool(door.get("open")) or (bool(door.get("locked")) and keys > 0)

    def _known_paths(self, start: int) -> dict[int, list[int]]:
        paths = {start: [start]}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            room = self.rooms.get(current)
            if room is None:
                continue
            for door in room.doors.values():
                target = int(door.get("target_room", -1))
                if target in self.rooms and target not in paths:
                    paths[target] = paths[current] + [target]
                    queue.append(target)
        return paths

    @staticmethod
    def _frontier_priority(door: dict[str, Any], coins: int) -> int:
        room_type = int(door.get("target_type", 0))
        if room_type == ROOM_TREASURE:
            return 0
        if room_type == ROOM_SHOP:
            return 1 if coins >= 5 else 4
        if room_type == ROOM_BOSS:
            return 3
        return 2

    def choose_door(self, observation: dict[str, Any]) -> dict[str, Any] | None:
        """Route toward the best reachable edge leading to an unvisited room."""
        self.observe(observation)
        current = int(observation["room_index"])
        player = observation["player"]
        keys, coins = int(player["keys"]), int(player["coins"])
        paths = self._known_paths(current)
        candidates: list[tuple[int, int, int, dict[str, Any], list[int]]] = []
        for origin, path in paths.items():
            room = self.rooms[origin]
            for door in room.doors.values():
                target = int(door.get("target_room", -1))
                if target in self.rooms:
                    continue
                # A controller may be attached in the middle of a floor. The
                # game's descriptor then knows rooms that this Python process
                # has not observed; they are not unexplored frontiers.
                if int(door.get("target_visited", 0)) > 0:
                    continue
                if not self._door_accessible(door, keys):
                    continue
                priority = self._frontier_priority(door, coins)
                candidates.append((priority, len(path), target, door, path))
        if not candidates:
            return None
        _, _, _, frontier, path = min(candidates, key=lambda item: (item[0], item[1], item[2]))
        if len(path) == 1:
            return frontier
        next_room = path[1]
        current_room = self.rooms[current]
        return next(
            (door for door in current_room.doors.values()
             if int(door.get("target_room", -1)) == next_room and self._door_accessible(door, keys)),
            None,
        )

    def note_transition(self, from_room: int, to_room: int) -> None:
        self.transitions += 1
        if to_room in self.rooms:
            self.backtracks += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "floor": list(self.floor_key) if self.floor_key else None,
            "unique_rooms": len(self.rooms),
            "transitions": self.transitions,
            "backtracks": self.backtracks,
            "special_room_types": sorted(self.special_rooms),
        }
