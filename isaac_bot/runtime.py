"""Agent loop, health probe and repeatable benchmark commands."""

from __future__ import annotations

import json
import platform
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .bridge import LuaBridge
from .protocol import Action, PROTOCOL_VERSION
from .recording import EpisodeRecorder


def run_loop(
    duration: float,
    output_dir: Path | None = None,
    auto_restart: bool = True,
    tick_hz: float = 30.0,
) -> dict[str, Any]:
    period = 1.0 / tick_hz
    deadline = time.monotonic() + duration
    latest_observation: dict[str, Any] | None = None
    metadata = {
        "protocol": PROTOCOL_VERSION,
        "duration": duration,
        "tick_hz": tick_hz,
        "auto_restart": auto_restart,
        "python": platform.python_version(),
    }
    recorder = EpisodeRecorder(output_dir, metadata) if output_dir else None
    # A short receive timeout lets us drain UDP without stretching a 30 Hz tick.
    with LuaBridge(timeout=min(0.005, period / 4)) as bridge:
        bridge.command("AUTO_RESTART", "1" if auto_restart else "0")
        bridge.hello()
        try:
            while time.monotonic() < deadline:
                started = time.monotonic()
                sequence = bridge.send(Action())
                if recorder:
                    recorder.write("action", {"sequence": sequence, **asdict(Action())})
                while time.monotonic() - started < period:
                    message = bridge.receive()
                    if message is None:
                        break
                    if message.get("type") == "observation":
                        latest_observation = message
                    if recorder:
                        recorder.write(str(message.get("type", "message")), message)
                remaining = period - (time.monotonic() - started)
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            bridge.send(Action())
            if recorder:
                recorder.write("summary", bridge.stats.snapshot(time.monotonic()))
                recorder.close()
        return {
            "latest_observation": latest_observation,
            "stats": bridge.stats.snapshot(time.monotonic()),
            "recording": str(recorder.path) if recorder else None,
        }


def probe(timeout: float = 3.0) -> dict[str, Any]:
    with LuaBridge() as bridge:
        hello = bridge.wait_for("hello", timeout)
        bridge.send(Action())
        observation = bridge.wait_for("observation", timeout)
        return {"hello": hello, "observation": observation}


def print_result(result: dict[str, Any]) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))
