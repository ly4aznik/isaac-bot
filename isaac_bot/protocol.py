"""Versioned messages shared by the Python runtime and the Lua mod."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


PROTOCOL_VERSION = 1


@dataclass(slots=True)
class Action:
    move_x: float = 0.0
    move_y: float = 0.0
    shoot_x: float = 0.0
    shoot_y: float = 0.0
    bomb: bool = False
    item: bool = False
    pill: bool = False
    card: bool = False
    drop: bool = False

    def clamped(self) -> "Action":
        values = asdict(self)
        for key in ("move_x", "move_y", "shoot_x", "shoot_y"):
            values[key] = max(-1.0, min(1.0, float(values[key])))
        return Action(**values)


@dataclass(slots=True)
class BridgeStats:
    packets_received: int = 0
    malformed_packets: int = 0
    observations: int = 0
    events: int = 0
    last_frame: int | None = None
    missing_frames: int = 0
    started_at: float = 0.0
    last_packet_at: float = 0.0

    def snapshot(self, now: float) -> dict[str, Any]:
        elapsed = max(1e-9, now - self.started_at)
        return {
            **asdict(self),
            "elapsed_seconds": elapsed,
            "packets_per_second": self.packets_received / elapsed,
            "observation_hz": self.observations / elapsed,
            "silence_seconds": max(0.0, now - self.last_packet_at),
        }
