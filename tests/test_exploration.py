import unittest

from isaac_bot.exploration import FloorExplorer
from isaac_bot.navigation import GridMap, astar


def obs(room, doors, room_type=1, keys=0, coins=0):
    return {
        "stage": 1, "stage_type": 0, "room_index": room, "room_type": room_type,
        "doors": doors, "player": {"keys": keys, "coins": coins},
    }


def door(slot, target, target_type=1, open=True, locked=False, target_visited=0):
    return {
        "slot": slot, "target_room": target, "target_type": target_type,
        "open": open, "locked": locked, "target_visited": target_visited,
    }


class ExplorationTests(unittest.TestCase):
    def test_prefers_treasure_frontier(self):
        explorer = FloorExplorer()
        current = obs(10, [door(0, 9), door(1, 11, 4)])
        explorer.observe(obs(9, [door(2, 10)]))
        chosen = explorer.choose_door(current)
        self.assertEqual(chosen["target_room"], 11)

    def test_routes_back_to_known_room_with_frontier(self):
        explorer = FloorExplorer()
        explorer.observe(obs(10, [door(0, 9), door(1, 11)]))
        explorer.observe(obs(11, [door(2, 10)]))
        chosen = explorer.choose_door(obs(11, [door(2, 10)]))
        self.assertEqual(chosen["target_room"], 10)

    def test_does_not_route_to_closed_remote_frontier(self):
        explorer = FloorExplorer()
        explorer.observe(obs(10, [door(0, 9), door(1, 12, open=False)]))
        chosen = explorer.choose_door(obs(9, [door(2, 10)]))
        self.assertIsNone(chosen)

    def test_locked_door_requires_key(self):
        explorer = FloorExplorer()
        locked = door(1, 12, 4, open=False, locked=True)
        self.assertIsNone(explorer.choose_door(obs(10, [locked], keys=0)))
        self.assertEqual(explorer.choose_door(obs(10, [locked], keys=1))["target_room"], 12)

    def test_floor_change_resets_graph(self):
        explorer = FloorExplorer()
        explorer.observe(obs(10, []))
        changed = obs(20, [])
        changed["stage"] = 2
        explorer.observe(changed)
        self.assertEqual(set(explorer.rooms), {20})

    def test_game_visited_unknown_room_is_not_frontier(self):
        explorer = FloorExplorer()
        chosen = explorer.choose_door(obs(10, [door(0, 9, target_visited=1)]))
        self.assertIsNone(chosen)

    def test_unreachable_pickup_path_is_detectable(self):
        grid = GridMap(3, 3, (0, 4, 0, 4, 4, 4, 0, 4, 0), 0, 0, 40)
        with self.assertRaises(ValueError):
            astar(grid, (0, 0), (2, 2))


if __name__ == "__main__":
    unittest.main()
