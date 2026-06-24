import os
import unittest

from server.mob_interactions import BREED_ENERGY_COST, BREED_ENERGY_COST_PREDATOR
from server.server import GameServer


DB_PATH = "test_predator_breeding_brake.db"


def _cleanup(path):
    for _ in range(3):
        try:
            if os.path.exists(path):
                os.remove(path)
            break
        except PermissionError:
            import time
            time.sleep(0.1)


class TestPredatorBreedingBrake(unittest.TestCase):
    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    def _adult_pair(self, a, b, mob_type):
        self.server._ensure_client_mob(a, mob_type=mob_type)
        self.server._ensure_client_mob(b, mob_type=mob_type)
        cursor = self.server.db_conn.cursor()
        cursor.execute(
            f"UPDATE mob_health SET life_stage = 'adult', energy = 80, health = 100 WHERE mob_id IN ('mob_{a}', 'mob_{b}')"
        )
        self.server.db_conn.commit()

    def _energy(self, mob_id):
        return self.server._get_mob_health(mob_id)["energy"]

    def test_predator_breeding_pays_higher_post_success_cost(self):
        self._adult_pair("pred_a", "pred_b", "predator")

        child_id = self.server.mob_interactions.breed_mobs("mob_pred_a", "mob_pred_b")

        self.assertIsNotNone(child_id)
        self.assertEqual(self._energy("mob_pred_a"), 80 - BREED_ENERGY_COST_PREDATOR)
        self.assertEqual(self._energy("mob_pred_b"), 80 - BREED_ENERGY_COST_PREDATOR)
        self.assertGreater(BREED_ENERGY_COST_PREDATOR, BREED_ENERGY_COST)

    def test_predator_and_prey_share_fitness_gate_threshold(self):
        self._adult_pair("pred_low_a", "pred_low_b", "predator")
        cursor = self.server.db_conn.cursor()
        cursor.execute(
            "UPDATE mob_health SET energy = 45, health = 100 WHERE mob_id IN ('mob_pred_low_a', 'mob_pred_low_b')"
        )
        self.server.db_conn.commit()

        child_id = self.server.mob_interactions.breed_mobs("mob_pred_low_a", "mob_pred_low_b")

        self.assertIsNotNone(child_id)
