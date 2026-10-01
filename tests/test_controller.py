import ctypes
import json
import socket
import tempfile
import unittest
from pathlib import Path

from isaac_bot.bridge import LuaBridge
from isaac_bot.protocol import Action
from isaac_bot.recording import EpisodeRecorder
from isaac_bot.win32 import INPUT


class ControllerTests(unittest.TestCase):
    def test_action_defaults_are_idle(self):
        self.assertEqual(Action().move_x, 0.0)
        self.assertFalse(Action().bomb)

    def test_action_axes_are_clamped(self):
        action = Action(move_x=4, shoot_y=-3).clamped()
        self.assertEqual(action.move_x, 1.0)
        self.assertEqual(action.shoot_y, -1.0)

    def test_win64_input_layout_is_valid(self):
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        self.assertEqual(ctypes.sizeof(INPUT), expected)

    def test_bridge_parses_versioned_observation(self):
        with LuaBridge(timeout=0.2) as bridge:
            sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            address = bridge.socket.getsockname()
            sender.sendto(b'{"v":1,"type":"observation","frame":10}', address)
            message = None
            for _ in range(5):
                candidate = bridge.receive()
                if candidate and candidate.get("type") == "observation" and candidate.get("frame") == 10:
                    message = candidate
                    break
            self.assertIsNotNone(message)
            self.assertEqual(message["frame"], 10)
            self.assertGreaterEqual(bridge.stats.observations, 1)
            sender.close()

    def test_recorder_writes_parseable_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            with EpisodeRecorder(Path(directory), {"test": True}) as recorder:
                recorder.write("event", {"event": "new_room"})
                path = recorder.path
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["kind"] for record in records], ["metadata", "event"])


if __name__ == "__main__":
    unittest.main()
