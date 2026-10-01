"""Crash-safe JSONL episode recording."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, TextIO


class EpisodeRecorder:
    def __init__(self, output_dir: Path, metadata: dict[str, Any]) -> None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)
        self.path = output_dir / f"episode-{stamp}-{os.getpid()}.jsonl"
        self.file: TextIO = self.path.open("x", encoding="utf-8", buffering=1)
        self.write("metadata", metadata)

    def write(self, kind: str, payload: dict[str, Any]) -> None:
        record = {"recorded_at": time.time(), "kind": kind, "payload": payload}
        self.file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    def close(self) -> None:
        if not self.file.closed:
            self.file.flush()
            os.fsync(self.file.fileno())
            self.file.close()

    def __enter__(self) -> "EpisodeRecorder":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
