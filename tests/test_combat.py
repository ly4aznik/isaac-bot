import unittest

from isaac_bot.combat import CombatPolicy, intercept_point
from isaac_bot.avoidance import choose_safe_movement


def observation(enemy=None):
    entities = [] if enemy is None else [enemy]
    return {
        "player": {"x": 120.0, "y": 240.0},
        "entities": entities,
        "grid": {
            "width": 13, "height": 7, "size": 91, "cell_size": 40,
            "origin_x": 40, "origin_y": 120,
            "cells": [4 if i//13 in (0, 6) or i%13 in (0, 12) else 0 for i in range(91)],
        },
    }


class CombatTests(unittest.TestCase):
    def test_stationary_intercept_is_enemy_position(self):
        enemy = {"x": 300.0, "y": 200.0, "vx": 0.0, "vy": 0.0}
        self.assertEqual(intercept_point((100.0, 100.0), enemy), (300.0, 200.0))

    def test_moving_enemy_is_led(self):
        enemy = {"x": 200.0, "y": 200.0, "vx": 0.0, "vy": 2.0}
        x, y = intercept_point((100.0, 200.0), enemy)
        self.assertEqual(x, 200.0)
        self.assertGreater(y, 200.0)

    def test_policy_selects_nearest_enemy_and_shoots(self):
        far = {"kind":"enemy", "seed":1, "x":400.0, "y":240.0, "vx":0, "vy":0, "hp":10}
        near = {"kind":"enemy", "seed":2, "x":220.0, "y":240.0, "vx":0, "vy":0, "hp":10}
        obs = observation()
        obs["entities"] = [far, near]
        action, target, aim = CombatPolicy().act(obs)
        self.assertEqual(target["seed"], 2)
        self.assertGreater(action.shoot_x, 0)
        self.assertAlmostEqual(action.shoot_y, 0)
        self.assertIsNotNone(aim)

    def test_policy_idles_without_enemy(self):
        action, target, aim = CombatPolicy().act(observation())
        self.assertIsNone(target)
        self.assertEqual((action.shoot_x, action.shoot_y), (0.0, 0.0))
        self.assertIsNone(aim)

    def test_incoming_projectile_triggers_perpendicular_dodge(self):
        obs = observation()
        obs["entities"] = [{
            "kind": "projectile", "seed": 10, "x": 60.0, "y": 240.0,
            "vx": 5.0, "vy": 0.0, "size": 5.0,
        }]
        decision = choose_safe_movement(obs, (0.0, 0.0))
        self.assertTrue(decision.danger)
        self.assertTrue(decision.dodging)
        self.assertGreater(abs(decision.move[1]), 0.5)

    def test_projectile_moving_away_does_not_override_preferred_move(self):
        obs = observation()
        obs["entities"] = [{
            "kind": "projectile", "seed": 11, "x": 60.0, "y": 240.0,
            "vx": -5.0, "vy": 0.0, "size": 5.0,
        }]
        preferred = (0.0, 0.4)
        decision = choose_safe_movement(obs, preferred)
        self.assertFalse(decision.danger)
        self.assertEqual(decision.move, preferred)

    def test_dodge_keeps_shooting_at_enemy(self):
        enemy = {"kind":"enemy", "seed":2, "x":320.0, "y":240.0, "vx":0, "vy":0, "hp":10}
        projectile = {"kind":"projectile", "seed":3, "x":60.0, "y":240.0, "vx":5, "vy":0, "size":5}
        obs = observation()
        obs["entities"] = [enemy, projectile]
        policy = CombatPolicy()
        action, _, _ = policy.act(obs)
        self.assertTrue(policy.last_avoidance and policy.last_avoidance.danger)
        self.assertGreater(action.shoot_x, 0.0)
        self.assertNotEqual((action.move_x, action.move_y), (0.0, 0.0))

    def test_second_enemy_is_treated_as_contact_hazard(self):
        obs = observation()
        obs["entities"] = [
            {"kind":"enemy", "seed":1, "x":170.0, "y":240.0, "vx":-2, "vy":0, "hp":10, "size":12},
            {"kind":"enemy", "seed":2, "x":320.0, "y":240.0, "vx":0, "vy":0, "hp":10, "size":12},
        ]
        decision = choose_safe_movement(obs, (1.0, 0.0))
        self.assertTrue(decision.danger)
        self.assertGreater(decision.threatening_contacts, 0)
        self.assertNotEqual(decision.move, (1.0, 0.0))

    def test_stale_undamaged_target_is_replaced(self):
        first = {"kind":"enemy", "seed":1, "x":200.0, "y":240.0, "vx":0, "vy":0, "hp":10, "size":10}
        second = {"kind":"enemy", "seed":2, "x":300.0, "y":240.0, "vx":0, "vy":0, "hp":10, "size":10}
        obs = observation()
        obs["entities"] = [first, second]
        policy = CombatPolicy(stale_target_limit=3)
        self.assertEqual(policy.select_target(obs)["seed"], 1)
        policy.select_target(obs)
        policy.select_target(obs)
        self.assertEqual(policy.select_target(obs)["seed"], 2)


if __name__ == "__main__":
    unittest.main()
