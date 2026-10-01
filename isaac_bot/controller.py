"""Launch Isaac, start a normal run, and provide scripted controls."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from .bridge import LuaBridge
from .protocol import Action
from .navigation_runtime import navigate_to_door, navigate_to_point
from .runtime import print_result, probe, run_loop
from .visualizer import run_visualizer
from .win32 import focus_window, release, tap, wait_for_window


ROOT = Path(__file__).resolve().parents[1]
GAME_DIR = ROOT / "game"
EXE = GAME_DIR / "isaac-ng.exe"

VK = {
    "enter": 0x0D,
    "escape": 0x1B,
    "space": 0x20,
    "a": 0x41,
    "d": 0x44,
    "e": 0x45,
    "q": 0x51,
    "s": 0x53,
    "w": 0x57,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "lctrl": 0xA2,
    "lshift": 0xA0,
}


def launch_game() -> tuple[subprocess.Popen[bytes], int]:
    if not EXE.is_file():
        raise FileNotFoundError(EXE)
    process = subprocess.Popen([str(EXE), "--luadebug"], cwd=GAME_DIR)
    hwnd = wait_for_window(process.pid)
    focus_window(hwnd)
    # The native window appears before the title screen starts accepting input.
    time.sleep(6.0)
    return process, hwnd


def start_standard_run(hwnd: int) -> None:
    """Navigate the default keyboard menu path: title -> main -> new run -> Isaac."""
    focus_window(hwnd)
    # Title screen -> main menu. Escape is intentionally avoided because it can
    # open the quit prompt when the game is already at the title screen.
    tap(VK["space"])
    time.sleep(1.0)
    # New Run -> default character (Isaac) -> Normal.
    for delay in (0.8, 0.8, 1.5):
        tap(VK["enter"])
        time.sleep(delay)


def ensure_standard_run(hwnd: int, attempts: int = 3) -> dict:
    """Start a run and verify it through Lua, retrying while startup screens settle."""
    last_error: Exception | None = None
    for _ in range(attempts):
        start_standard_run(hwnd)
        try:
            with LuaBridge(timeout=0.15) as bridge:
                return bridge.wait_for("hello", timeout=3.0)
        except TimeoutError as error:
            last_error = error
    raise RuntimeError(f"standard run did not reach the Lua bridge after {attempts} attempts") from last_error


def keyboard_smoke_test(hwnd: int) -> None:
    """Move briefly in a square, then shoot once in each direction."""
    focus_window(hwnd)
    for key in ("w", "d", "s", "a", "up", "right", "down", "left"):
        tap(VK[key], 0.25)
        time.sleep(0.05)
    for key in VK.values():
        release(key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="launch Isaac and optionally start a normal run")
    start.add_argument("--no-run", action="store_true", help="stop at the title/menu")
    start.add_argument("--smoke-test", action="store_true", help="perform a short input test after starting")
    sub.add_parser("probe", help="verify the protocol and print one observation")
    play = sub.add_parser("play", help="run the neutral agent loop without recording")
    play.add_argument("--seconds", type=float, default=60.0)
    record = sub.add_parser("record", help="run and record an episode as JSONL")
    record.add_argument("--seconds", type=float, default=60.0)
    record.add_argument("--output", type=Path, default=ROOT / "runs")
    benchmark = sub.add_parser("benchmark", help="run a transport soak test")
    benchmark.add_argument("--seconds", type=float, default=300.0)
    navigate = sub.add_parser("navigate", help="navigate through an open door using A*")
    navigate.add_argument("--door", type=int, choices=range(8), default=None)
    navigate.add_argument("--timeout", type=float, default=20.0)
    point = sub.add_parser("navigate-point", help="navigate to room world coordinates using A*")
    point.add_argument("--x", type=float, required=True)
    point.add_argument("--y", type=float, required=True)
    point.add_argument("--timeout", type=float, default=15.0)
    sub.add_parser("visualize", help="open the live schematic AI perception view")
    combat = sub.add_parser("combat", help="fight enemies in the current room")
    combat.add_argument("--seconds", type=float, default=60.0)
    rooms = sub.add_parser("rooms", help="continuously clear rooms and move through doors")
    rooms.add_argument("--count", type=int, default=20, help="rooms to process; 0 means until stopped")
    rooms.add_argument("--room-timeout", type=float, default=60.0)
    rooms.add_argument("--log", type=Path, default=ROOT / "runs" / "room_traversal.jsonl")
    runs = sub.add_parser("runs", help="run interactively and wait for R before restarting")
    runs.add_argument("--room-timeout", type=float, default=60.0)
    runs.add_argument("--log", type=Path, default=ROOT / "runs" / "room_traversal.jsonl")
    studio = sub.add_parser("studio", help="embed Isaac and the world model in one window")
    studio.add_argument("--pid", type=int, default=None)
    studio.add_argument("--layout", choices=("side", "reels"), default="reels")
    args = parser.parse_args()

    if args.command == "start":
        process, hwnd = launch_game()
        print(f"Isaac started: pid={process.pid}, hwnd={hwnd}", flush=True)
        if not args.no_run:
            hello = ensure_standard_run(hwnd)
            print(f"Standard run verified: run_id={hello['run_id']}", flush=True)
        if args.smoke_test:
            time.sleep(2.0)
            keyboard_smoke_test(hwnd)
            print("Control smoke test completed", flush=True)
    elif args.command == "probe":
        print_result(probe())
    elif args.command == "play":
        print_result(run_loop(args.seconds))
    elif args.command == "record":
        print_result(run_loop(args.seconds, output_dir=args.output))
    elif args.command == "benchmark":
        print_result(run_loop(args.seconds))
    elif args.command == "navigate":
        print_result(navigate_to_door(args.door, args.timeout))
    elif args.command == "navigate-point":
        print_result(navigate_to_point(args.x, args.y, args.timeout))
    elif args.command == "visualize":
        run_visualizer()
    elif args.command == "combat":
        from .combat_runtime import fight_room
        print_result(fight_room(args.seconds))
    elif args.command == "rooms":
        from .run_runtime import traverse_rooms
        print_result(traverse_rooms(args.count, args.room_timeout, args.log))
    elif args.command == "runs":
        from .run_runtime import interactive_runs
        interactive_runs(args.room_timeout, args.log)
    elif args.command == "studio":
        from .studio import run_studio
        run_studio(args.pid, args.layout)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(130)
