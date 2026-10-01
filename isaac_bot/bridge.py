"""Reliable-enough localhost UDP transport for the Isaac Lua bridge."""

from __future__ import annotations

import json
import socket
import time
from collections.abc import Iterator
from typing import Any

from .protocol import Action, BridgeStats, PROTOCOL_VERSION


class ProtocolError(RuntimeError):
    pass


class LuaBridge:
    def __init__(self, host: str = "127.0.0.1", port: int = 21666, timeout: float = 0.25, role: str = "controller") -> None:
        self.address = (host, port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, 0))
        self.socket.settimeout(timeout)
        self.sequence = 0
        now = time.monotonic()
        self.stats = BridgeStats(started_at=now, last_packet_at=now)
        self.role = role
        if role == "controller":
            self.hello()
        elif role == "observer":
            self.observe()
        else:
            raise ValueError("role must be 'controller' or 'observer'")

    def close(self) -> None:
        self.socket.close()

    def __enter__(self) -> "LuaBridge":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _send(self, payload: str) -> None:
        self.socket.sendto(payload.encode("ascii"), self.address)

    def hello(self) -> None:
        self._send(f"V{PROTOCOL_VERSION} HELLO")

    def observe(self) -> None:
        self._send(f"V{PROTOCOL_VERSION} OBSERVE")

    def command(self, name: str, value: str = "") -> None:
        safe_name = name.upper().replace(" ", "_")
        self._send(f"V{PROTOCOL_VERSION} COMMAND {safe_name} {value}".rstrip())

    def send(self, action: Action) -> int:
        self.sequence += 1
        action = action.clamped()
        values = (
            self.sequence, action.move_x, action.move_y, action.shoot_x, action.shoot_y,
            int(action.bomb), int(action.item), int(action.pill), int(action.card), int(action.drop),
        )
        self._send(f"V{PROTOCOL_VERSION} ACTION " + " ".join(map(str, values)))
        return self.sequence

    def receive(self) -> dict[str, Any] | None:
        try:
            payload, _ = self.socket.recvfrom(65535)
        except (TimeoutError, ConnectionResetError):
            return None
        now = time.monotonic()
        self.stats.packets_received += 1
        self.stats.last_packet_at = now
        try:
            message = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.stats.malformed_packets += 1
            return None
        if message.get("v") != PROTOCOL_VERSION:
            raise ProtocolError(f"protocol mismatch: expected {PROTOCOL_VERSION}, got {message.get('v')}")
        message_type = message.get("type")
        if message_type == "observation":
            self.stats.observations += 1
            frame = message.get("frame")
            if isinstance(frame, int):
                if self.stats.last_frame is not None and frame > self.stats.last_frame + 2:
                    self.stats.missing_frames += max(0, (frame - self.stats.last_frame) // 2 - 1)
                self.stats.last_frame = frame
        elif message_type == "event":
            self.stats.events += 1
        return message

    def messages(self, duration: float) -> Iterator[dict[str, Any]]:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            message = self.receive()
            if message is not None:
                yield message

    def wait_for(self, message_type: str, timeout: float = 3.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.hello()
            message = self.receive()
            if message and message.get("type") == message_type:
                return message
        raise TimeoutError(f"no {message_type!r} packet from Lua bridge in {timeout:.1f}s")
