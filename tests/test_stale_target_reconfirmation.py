import unittest

from client.brain_registry import get_function


class TestStaleTargetReconfirmation(unittest.TestCase):
    def test_action_eat_mob_clears_missing_carcass(self):
        func = get_function("action_eat_mob")
        memory = {
            "eat_target": {
                "mobId": "dead_1",
                "mob_type": "prey",
                "alive": False,
                "distance": 1.0,
                "position": {"x": 1, "y": 0},
            },
            "last_look": {"mobs": []},
            "carcass_lock_ticks": 2,
        }

        result = func([], memory, [], {"mob_type": "predator", "position": {"x": 0, "y": 0}})

        self.assertEqual(result["action"], "MOVE_MOB")
        self.assertNotIn("eat_target", memory)
        self.assertEqual(memory["carcass_lock_ticks"], 0)
        self.assertIn("dead_1", memory["carcass_cooldown"])

    def test_action_attack_routes_dead_visible_target_to_carcass(self):
        func = get_function("action_attack")
        dead_prey = {
            "mobId": "prey_1",
            "mob_type": "prey",
            "alive": False,
            "distance": 1.0,
            "position": {"x": 1, "y": 0},
        }
        memory = {"attack_target": {"mobId": "prey_1"}, "last_look": {"mobs": [dead_prey]}}

        result = func([], memory, [], {"mob_type": "predator", "position": {"x": 0, "y": 0}})

        self.assertEqual(result["next"], "action_eat_mob")
        self.assertEqual(memory["eat_target"]["mobId"], "prey_1")
        self.assertNotIn("attack_target", memory)

    def test_action_attack_clears_missing_target(self):
        func = get_function("action_attack")
        memory = {
            "attack_target": {"mobId": "prey_1", "position": {"x": 1, "y": 0}},
            "last_look": {"mobs": []},
        }

        result = func([], memory, [], {"mob_type": "predator", "position": {"x": 0, "y": 0}})

        self.assertEqual(result["action"], "MOVE_MOB")
        self.assertNotIn("attack_target", memory)

    def test_action_breed_reconfirms_current_look(self):
        func = get_function("action_breed")
        stale_target = {
            "mobId": "mate_1",
            "mob_type": "prey",
            "alive": True,
            "distance": 1.0,
            "position": {"x": 1, "y": 0},
            "fitnessScore": 1.0,
        }
        memory = {"breed_target": stale_target, "last_look": {"mobs": []}}

        result = func(
            [],
            memory,
            [],
            {"mob_type": "prey", "life_stage": "adult", "vision": 10.0, "position": {"x": 0, "y": 0}},
        )

        self.assertEqual(result["action"], "MOVE_MOB")
        self.assertNotIn("breed_target", memory)
