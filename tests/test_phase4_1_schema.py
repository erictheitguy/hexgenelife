"""
Tests for Phase 4.1 — Schema & Mob Data Model Expansion.

Validates:
    - New tables (mob_physical, brain_functions) exist
    - Extended columns in mob_health and mob_brain
    - _ensure_client_mob populates all tables with correct defaults
    - Prey vs predator type-specific defaults
    - brain_functions seeded with starter functions
    - _get_mob_health and _get_mob_physical return extended fields
    - MOB_UPDATE and WORLD_UPDATE payloads include new data

Run from the project root:
    python -m pytest tests/test_phase4_1_schema.py -v
"""
import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock

from server.server import (
    GameServer,
    DEFAULT_MOB_PHYSICAL,
    DEFAULT_MOB_HEALTH_EXT,
    DEFAULT_DECISION_TREE,
)

DB_PATH = "test_phase4_1.db"


def _cleanup(path: str):
    for _ in range(3):
        try:
            if os.path.exists(path):
                os.remove(path)
            break
        except PermissionError:
            import time
            time.sleep(0.1)


class TestPhase41Tables(unittest.TestCase):
    """Verify all Phase 4.1 tables and columns exist."""

    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    def test_mob_physical_table_exists(self):
        cursor = self.server.db_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mob_physical'")
        self.assertIsNotNone(cursor.fetchone(), "mob_physical table must exist")

    def test_brain_functions_table_exists(self):
        cursor = self.server.db_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='brain_functions'")
        self.assertIsNotNone(cursor.fetchone(), "brain_functions table must exist")

    def test_mob_physical_columns(self):
        """mob_physical must have all expected columns including camouflage."""
        cursor = self.server.db_conn.cursor()
        cursor.execute("PRAGMA table_info(mob_physical)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {"mob_id", "size", "speed", "mass", "vision",
                    "metabolism_active", "metabolism_resting",
                    "diet_type", "attack_power", "defense", "camouflage"}
        self.assertTrue(expected.issubset(columns),
                        f"Missing columns: {expected - columns}")

    def test_mob_health_extended_columns(self):
        """mob_health must include Phase 4.1 extensions."""
        cursor = self.server.db_conn.cursor()
        cursor.execute("PRAGMA table_info(mob_health)")
        columns = {row[1] for row in cursor.fetchall()}
        new_cols = {"energy", "life_stage", "birth_tick", "max_age"}
        self.assertTrue(new_cols.issubset(columns),
                        f"Missing columns: {new_cols - columns}")

    def test_mob_brain_extended_columns(self):
        """mob_brain must include decision_tree and memory."""
        cursor = self.server.db_conn.cursor()
        cursor.execute("PRAGMA table_info(mob_brain)")
        columns = {row[1] for row in cursor.fetchall()}
        new_cols = {"decision_tree", "memory"}
        self.assertTrue(new_cols.issubset(columns),
                        f"Missing columns: {new_cols - columns}")


class TestBrainFunctionsSeeding(unittest.TestCase):
    """Verify brain_functions table is seeded with starter functions."""

    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    def test_starter_functions_seeded(self):
        cursor = self.server.db_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM brain_functions")
        count = cursor.fetchone()[0]
        self.assertGreaterEqual(count, 7, "Should have at least 7 starter functions")

    def test_expected_function_ids(self):
        cursor = self.server.db_conn.cursor()
        cursor.execute("SELECT function_id FROM brain_functions")
        ids = {row[0] for row in cursor.fetchall()}
        expected = {"evaluate_state", "evaluate_hunger", "evaluate_danger",
                    "evaluate_movement", "action_eat", "action_move", "action_look"}
        self.assertTrue(expected.issubset(ids),
                        f"Missing functions: {expected - ids}")

    def test_function_has_required_fields(self):
        cursor = self.server.db_conn.cursor()
        cursor.execute("SELECT * FROM brain_functions WHERE function_id = 'evaluate_state'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        # Check non-null required fields
        row_dict = dict(row)
        self.assertIsNotNone(row_dict["function_name"])
        self.assertIsNotNone(row_dict["function_code"])
        self.assertIsNotNone(row_dict["description"])

    def test_no_duplicate_seeding(self):
        """Creating a second server instance should not duplicate functions."""
        self.server.close()
        server2 = GameServer(db_path=DB_PATH)
        cursor = server2.db_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM brain_functions")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 7, "Should not duplicate on re-init")
        server2.close()


class TestEnsureClientMobPhase41(unittest.TestCase):
    """Verify _ensure_client_mob populates all Phase 4.1 tables."""

    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    def test_creates_mob_physical_row(self):
        self.server._ensure_client_mob("phys_test")
        cursor = self.server.db_conn.cursor()
        cursor.execute("SELECT * FROM mob_physical WHERE mob_id = 'mob_phys_test'")
        row = cursor.fetchone()
        self.assertIsNotNone(row, "mob_physical row must exist after creation")

    def test_prey_defaults(self):
        """Prey mob should have prey-specific physical defaults."""
        self.server._ensure_client_mob("prey1", mob_type="prey")
        phys = self.server._get_mob_physical("mob_prey1")
        self.assertEqual(phys["diet_type"], 0.0, "Prey diet_type should be 0.0")
        self.assertAlmostEqual(phys["camouflage"], 0.7, places=2)
        self.assertAlmostEqual(phys["speed"], 1.3, places=2)
        self.assertAlmostEqual(phys["defense"], 1.2, places=2)

    def test_predator_defaults(self):
        """Predator mob should have predator-specific physical defaults."""
        self.server._ensure_client_mob("pred1", mob_type="predator")
        phys = self.server._get_mob_physical("mob_pred1")
        self.assertEqual(phys["diet_type"], 1.0, "Predator diet_type should be 1.0")
        self.assertAlmostEqual(phys["attack_power"], 8.0, places=2)
        self.assertAlmostEqual(phys["speed"], 1.5, places=2)
        self.assertAlmostEqual(phys["vision"], 15.0, places=2)
        self.assertAlmostEqual(phys["camouflage"], 0.6, places=2)

    def test_physical_overrides(self):
        """Custom overrides should take precedence over type defaults."""
        overrides = {"size": 5.0, "speed": 0.5}
        self.server._ensure_client_mob("custom1", mob_type="prey",
                                        physical_overrides=overrides)
        phys = self.server._get_mob_physical("mob_custom1")
        self.assertEqual(phys["size"], 5.0)
        self.assertEqual(phys["speed"], 0.5)

    def test_mob_health_extended_values(self):
        """mob_health should have Phase 4.1 extended columns."""
        self.server._ensure_client_mob("health_ext")
        health = self.server._get_mob_health("mob_health_ext")
        self.assertIn("energy", health)
        self.assertIn("life_stage", health)
        self.assertIn("birth_tick", health)
        self.assertIn("max_age", health)
        self.assertEqual(health["energy"], 50.0)
        self.assertEqual(health["life_stage"], "adult")

    def test_mob_brain_decision_tree(self):
        """mob_brain should have a populated decision_tree JSON."""
        self.server._ensure_client_mob("brain_test")
        cursor = self.server.db_conn.cursor()
        cursor.execute(
            "SELECT decision_tree, memory FROM mob_brain WHERE mob_id = 'mob_brain_test'"
        )
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        tree = json.loads(row["decision_tree"])
        self.assertIn("root", tree)
        self.assertIn("nodes", tree)
        memory = json.loads(row["memory"])
        self.assertIsInstance(memory, dict)

    def test_mob_type_stored_correctly(self):
        """mob_type in mobs table should reflect the type passed."""
        self.server._ensure_client_mob("typed", mob_type="predator")
        cursor = self.server.db_conn.cursor()
        cursor.execute("SELECT mob_type FROM mobs WHERE mob_id = 'mob_typed'")
        self.assertEqual(cursor.fetchone()[0], "predator")


class TestGetMobPhysical(unittest.TestCase):
    """Tests for _get_mob_physical helper."""

    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    def test_returns_defaults_for_unknown_mob(self):
        phys = self.server._get_mob_physical("nonexistent")
        self.assertEqual(phys, DEFAULT_MOB_PHYSICAL)

    def test_returns_all_fields(self):
        self.server._ensure_client_mob("full_phys")
        phys = self.server._get_mob_physical("mob_full_phys")


class TestPhase41Payloads(unittest.IsolatedAsyncioTestCase):
    """Verify MOB_UPDATE and WORLD_UPDATE include Phase 4.1 data."""

    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    async def test_mob_update_includes_physical(self):
        """MOB_UPDATE broadcast after move should include 'physical' key."""
        self.server._ensure_client_mob("bcast")
        mock_ws = AsyncMock()
        self.server.clients.add(mock_ws)
        self.server._ws_to_mob[mock_ws] = "mob_bcast"

        await self.server._handle_move_mob(
            {"mobId": "mob_bcast", "targetLocation": {"x": 1, "y": 1}},
            mock_ws,
        )

        sent_msgs = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        mob_updates = [m for m in sent_msgs if m["type"] == "MOB_UPDATE"]
        self.assertTrue(len(mob_updates) >= 1)
        payload = mob_updates[0]["payload"]
        self.assertIn("physical", payload)
        self.assertIn("camouflage", payload["physical"])

    async def test_mob_update_health_has_energy(self):
        """MOB_UPDATE health dict should include energy and life_stage."""
        self.server._ensure_client_mob("en_test")
        mock_ws = AsyncMock()
        self.server.clients.add(mock_ws)
        self.server._ws_to_mob[mock_ws] = "mob_en_test"

        await self.server._handle_move_mob(
            {"mobId": "mob_en_test", "targetLocation": {"x": 2, "y": 2}},
            mock_ws,
        )

        sent_msgs = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        mob_updates = [m for m in sent_msgs if m["type"] == "MOB_UPDATE"]
        health = mob_updates[0]["payload"]["health"]
        self.assertIn("energy", health)
        self.assertIn("life_stage", health)

    async def test_world_update_includes_physical(self):
        """WORLD_UPDATE mobs should include physical data."""
        self.server._ensure_client_mob("ws_phys")
        mock_ws = AsyncMock()
        await self.server._handle_request_world_state(
            {"clientId": "ws_phys"}, mock_ws
        )

        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "WORLD_UPDATE")
        mobs = sent["payload"]["mobs"]
        self.assertTrue(len(mobs) >= 1)
        # At least one mob should have physical data
        mob = next(m for m in mobs if m["mob_id"] == "mob_ws_phys")
        self.assertIn("physical", mob)
        self.assertIn("health", mob)


if __name__ == "__main__":
    unittest.main()
