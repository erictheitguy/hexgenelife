import math
import unittest

from client.brain_registry import FLEE_MIN_PERSISTENCE_TICKS, get_function


class TestFleeBehavior(unittest.TestCase):
    def test_equal_speed_prey_increases_distance_for_several_ticks(self):
        move = get_function("evaluate_movement")
        memory = {}
        predator_pos = {"x": 0, "y": 0}
        prey_pos = {"x": 2, "y": 0}
        mob_state = {
            "mob_type": "prey",
            "position": dict(prey_pos),
            "physical": {"speed": 1.0, "persistence": 5.0, "wander_dist": 3.0},
        }

        distances = []
        for _ in range(4):
            memory["threat"] = {
                "mobId": "pred",
                "mob_type": "predator",
                "alive": True,
                "position": dict(predator_pos),
                "distance": math.dist((prey_pos["x"], prey_pos["y"]), (0, 0)),
            }
            result = move([], memory, [], mob_state)
            self.assertEqual(result["action"], "MOVE_MOB")
            prey_pos = result["payload"]["targetLocation"]
            mob_state["position"] = dict(prey_pos)
            distances.append(math.dist((prey_pos["x"], prey_pos["y"]), (0, 0)))

        self.assertEqual(distances, sorted(distances))
        self.assertGreater(distances[-1], distances[0])
        self.assertGreaterEqual(memory["wander_steps"], FLEE_MIN_PERSISTENCE_TICKS)

    def test_danger_routes_to_flee_before_hunger_can_graze(self):
        danger = get_function("evaluate_danger")
        memory = {
            "last_look": {
                "mobs": [
                    {
                        "mobId": "pred",
                        "mob_type": "predator",
                        "alive": True,
                        "position": {"x": 1, "y": 0},
                        "distance": 1.0,
                    }
                ],
                "tiles": [
                    {"centerX": 0, "centerY": 0, "grass": 10.0, "distance": 0.0},
                ],
            }
        }
        mob_state = {
            "mob_type": "prey",
            "vision": 10.0,
            "hunger": 50.0,
            "position": {"x": 0, "y": 0},
        }

        result = danger([50, 0, 10, 100], memory, ["evaluate_flee", "evaluate_hunger"], mob_state)

        self.assertEqual(result["next"], "evaluate_flee")
        self.assertIn("threat", memory)
