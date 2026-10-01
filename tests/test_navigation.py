import random
import unittest

from isaac_bot.navigation import GridMap, Navigator, astar, door_approach_point


def make_grid(width=13, height=7, blocked=()):
    cells = []
    blocked = set(blocked)
    for y in range(height):
        for x in range(width):
            wall = x in (0, width - 1) or y in (0, height - 1)
            cells.append(4 if wall or (x, y) in blocked else 0)
    return GridMap(width, height, tuple(cells), 40.0, 120.0)


class NavigationTests(unittest.TestCase):
    def test_astar_routes_around_obstacle(self):
        grid = make_grid(blocked={(6, y) for y in range(1, 5)})
        path = astar(grid, (2, 3), (10, 3))
        self.assertEqual(path[0], (2, 3))
        self.assertEqual(path[-1], (10, 3))
        self.assertTrue(all(grid.passable(cell) for cell in path))
        self.assertGreater(len(path), 9)

    def test_world_cell_round_trip(self):
        grid = make_grid()
        for cell in ((1, 1), (6, 3), (11, 5)):
            self.assertEqual(grid.world_to_cell(grid.cell_to_world(cell)), cell)

    def test_one_hundred_repeatable_routes(self):
        randomizer = random.Random(42)
        grid = make_grid(blocked={(6, 2), (6, 3), (6, 4)})
        passable = [(x, y) for y in range(grid.height) for x in range(grid.width) if grid.passable((x, y))]
        for _ in range(100):
            start, goal = randomizer.sample(passable, 2)
            path = astar(grid, start, goal)
            self.assertEqual((path[0], path[-1]), (start, goal))

    def test_door_target_is_inside_room(self):
        observation = {
            "grid": {"width": 13, "height": 7, "cell_size": 40, "origin_x": 40, "origin_y": 120},
            "doors": [{"slot": 0, "x": 40, "y": 240}],
        }
        x, y = door_approach_point(observation, 0, inset=40)
        self.assertGreater(x, 40)
        self.assertEqual(y, 240)

    def test_navigator_reaches_target(self):
        grid = make_grid()
        observation = {
            "grid": {
                "width": grid.width, "height": grid.height, "size": len(grid.cells),
                "cell_size": grid.cell_size, "origin_x": grid.origin_x,
                "origin_y": grid.origin_y, "cells": list(grid.cells),
            },
            "player": {"x": 120.0, "y": 240.0},
        }
        navigator = Navigator()
        navigator.plan(observation, (400.0, 240.0))
        action, arrived = navigator.act(observation)
        self.assertFalse(arrived)
        self.assertGreater(action.move_x, 0)


if __name__ == "__main__":
    unittest.main()
