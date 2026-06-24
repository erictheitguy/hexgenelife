import json
import os
import unittest
from unittest.mock import AsyncMock, patch

from server.server import GameServer


DB_PATH = "test_live_fitness_score.db"


def _cleanup(path):
    for _ in range(3):
        try:
            if os.path.exists(path):
                os.remove(path)
            break
        except PermissionError:
            import time
            time.sleep(0.1)


class TestLiveFitnessScore(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    def _fitness(self, mob_id):
        row = self.server.db_conn.execute(
            "SELECT fitnessScore FROM mob_genes WHERE mob_id = ?",
            (mob_id,),
        ).fetchone()
        return row["fitnessScore"]

    async def test_metabolism_updates_live_fitness_for_breedable_mob(self):
        self.server._ensure_client_mob("fit", mob_type="prey")
        cursor = self.server.db_conn.cursor()
        cursor.execute(
            "UPDATE mob_health SET life_stage = 'adult', energy = 80, health = 90, fat = 10 WHERE mob_id = 'mob_fit'"
        )
        self.server.db_conn.commit()

        await self.server._process_metabolism()

        self.assertGreater(self._fitness("mob_fit"), 0.0)

    async def test_metabolism_sets_zero_fitness_for_ineligible_mob(self):
        self.server._ensure_client_mob("tired", mob_type="prey")
        cursor = self.server.db_conn.cursor()
        cursor.execute(
            "UPDATE mob_health SET life_stage = 'adult', energy = 0, health = 100, fat = 0 WHERE mob_id = 'mob_tired'"
        )
        self.server.db_conn.commit()

        await self.server._process_metabolism()

        self.assertEqual(self._fitness("mob_tired"), 0.0)

    async def test_predation_death_preserves_last_live_fitness(self):
        self.server._ensure_client_mob("pred", mob_type="predator", physical_overrides={"attack_power": 10.0})
        self.server._ensure_client_mob("victim", mob_type="prey")
        cursor = self.server.db_conn.cursor()
        cursor.execute("UPDATE mob_health SET health = 1 WHERE mob_id = 'mob_victim'")
        cursor.execute("UPDATE mob_genes SET fitnessScore = 0.4321 WHERE mob_id = 'mob_victim'")
        self.server.db_conn.commit()

        await self.server._handle_attack_mob(
            {"mobId": "mob_pred", "targetId": "mob_victim"},
            AsyncMock(),
        )

        self.assertEqual(self._fitness("mob_victim"), 0.4321)

    async def test_metabolism_death_preserves_last_live_fitness(self):
        self.server._ensure_client_mob("starve", mob_type="prey")
        cursor = self.server.db_conn.cursor()
        cursor.execute(
            "UPDATE mob_health SET health = 1, hunger = 50, energy = 0, fat = 0 WHERE mob_id = 'mob_starve'"
        )
        cursor.execute("UPDATE mob_genes SET fitnessScore = 0.7654 WHERE mob_id = 'mob_starve'")
        self.server.db_conn.commit()

        await self.server._process_metabolism()

        self.assertEqual(self._fitness("mob_starve"), 0.7654)

    async def test_look_includes_fitness_score_scan_path(self):
        self.server._ensure_client_mob("observer", mob_type="prey")
        self.server._ensure_client_mob("target", mob_type="prey")
        cursor = self.server.db_conn.cursor()
        cursor.execute(
            "UPDATE mobs SET position = ?, is_active = 1 WHERE mob_id = 'mob_observer'",
            (json.dumps({"x": 0, "y": 0}),),
        )
        cursor.execute(
            "UPDATE mobs SET position = ?, is_active = 1 WHERE mob_id = 'mob_target'",
            (json.dumps({"x": 1, "y": 0}),),
        )
        cursor.execute("UPDATE mob_genes SET fitnessScore = 0.5 WHERE mob_id = 'mob_observer'")
        cursor.execute("UPDATE mob_genes SET fitnessScore = 0.9 WHERE mob_id = 'mob_target'")
        self.server.db_conn.commit()
        mock_ws = AsyncMock()

        with patch.object(self.server, "get_nearby_mob_ids", return_value=None):
            await self.server._handle_look({"mobId": "mob_observer"}, mock_ws)

        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["payload"]["mob_self"]["fitnessScore"], 0.5)
        target = next(m for m in sent["payload"]["mobs"] if m["mobId"] == "mob_target")
        self.assertEqual(target["fitnessScore"], 0.9)

    async def test_look_includes_fitness_score_spatial_path(self):
        self.server._ensure_client_mob("observer_sp", mob_type="prey")
        self.server._ensure_client_mob("target_sp", mob_type="prey")
        cursor = self.server.db_conn.cursor()
        cursor.execute(
            "UPDATE mobs SET position = ?, is_active = 1 WHERE mob_id = 'mob_observer_sp'",
            (json.dumps({"x": 0, "y": 0}),),
        )
        cursor.execute(
            "UPDATE mobs SET position = ?, is_active = 1 WHERE mob_id = 'mob_target_sp'",
            (json.dumps({"x": 1, "y": 0}),),
        )
        cursor.execute("UPDATE mob_genes SET fitnessScore = 0.7 WHERE mob_id = 'mob_target_sp'")
        self.server.db_conn.commit()
        mock_ws = AsyncMock()

        with patch.object(self.server, "get_nearby_mob_ids", return_value={"mob_observer_sp", "mob_target_sp"}):
            await self.server._handle_look({"mobId": "mob_observer_sp"}, mock_ws)

        sent = json.loads(mock_ws.send.call_args[0][0])
        target = next(m for m in sent["payload"]["mobs"] if m["mobId"] == "mob_target_sp")
        self.assertEqual(target["fitnessScore"], 0.7)
