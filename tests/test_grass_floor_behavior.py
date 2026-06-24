import unittest

from client.brain_registry import GRASS_EAT_FLOOR, get_function


class TestGrassFloorBehavior(unittest.TestCase):
    def test_residual_nearest_grass_moves_instead_of_eating(self):
        func = get_function("action_eat")
        memory = {
            "last_look": {
                "tiles": [
                    {"centerX": 0, "centerY": 0, "grass": GRASS_EAT_FLOOR - 0.1, "distance": 0.0},
                    {"centerX": 10, "centerY": 0, "grass": GRASS_EAT_FLOOR + 2.0, "distance": 10.0},
                ],
                "mobs": [],
            }
        }

        result = func([], memory, [], {"position": {"x": 0, "y": 0}, "mob_type": "prey"})

        self.assertEqual(result["action"], "MOVE_MOB")
        self.assertEqual(result["payload"]["targetLocation"], {"x": 10, "y": 0})

    def test_best_visible_grass_above_floor_beats_nearest_trace(self):
        func = get_function("action_eat")
        memory = {
            "last_look": {
                "tiles": [
                    {"centerX": 0, "centerY": 0, "grass": 0.0, "distance": 0.0},
                    {"centerX": 2, "centerY": 0, "grass": GRASS_EAT_FLOOR + 0.1, "distance": 2.0},
                    {"centerX": 12, "centerY": 0, "grass": GRASS_EAT_FLOOR + 5.0, "distance": 12.0},
                ],
                "mobs": [],
            }
        }

        result = func([], memory, [], {"position": {"x": 0, "y": 0}, "mob_type": "prey"})

        self.assertEqual(result["action"], "MOVE_MOB")
        self.assertEqual(result["payload"]["targetLocation"], {"x": 12, "y": 0})

    def test_viable_nearest_grass_still_eats(self):
        func = get_function("action_eat")
        memory = {
            "last_look": {
                "tiles": [
                    {"centerX": 0, "centerY": 0, "grass": GRASS_EAT_FLOOR, "distance": 0.0},
                    {"centerX": 10, "centerY": 0, "grass": GRASS_EAT_FLOOR + 5.0, "distance": 10.0},
                ],
                "mobs": [],
            }
        }

        result = func([], memory, [], {"position": {"x": 0, "y": 0}, "mob_type": "prey"})

        self.assertEqual(result["action"], "EAT_GRASS")
