"""
Tests for COR-1: death idempotency in handle_attack_mob.

A corpse stays is_active=1 for several ticks so predators can eat the carcass,
so it remains "attackable". handle_attack_mob must record the death (timestamp,
fitness, carcass meat, death log) EXACTLY ONCE per target — every subsequent
attack on the corpse must be rejected with TARGET_ALREADY_DEAD and must not
re-run the death block.

Run from the project root:
    .venv/bin/python -m pytest tests/test_death_idempotency.py -v
"""
import os
import unittest
from unittest.mock import AsyncMock

from server.server import GameServer

DB_PATH = "test_death_idempotency.db"


def _cleanup(path: str):
    for _ in range(3):
        try:
            if os.path.exists(path):
                os.remove(path)
            break
        except PermissionError:
            import time
            time.sleep(0.1)


class TestDeathIdempotency(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    def _make_predator_and_prey(self):
        """Create a strong predator and a near-dead prey at the same spot."""
        pred_id = self.server._ensure_client_mob(
            "killer", mob_type="predator",
            physical_overrides={"attack_power": 100.0},
        )
        prey_id = self.server._ensure_client_mob(
            "victim", mob_type="prey",
            physical_overrides={"defense": 0.0},
        )
        cursor = self.server.db_conn.cursor()
        # Prey on the brink so one hit kills it; predator has full energy.
        cursor.execute(
            "UPDATE mob_health SET health = 1.0 WHERE mob_id = ?", (prey_id,)
        )
        cursor.execute(
            "UPDATE mob_health SET energy = 100.0 WHERE mob_id = ?", (pred_id,)
        )
        self.server.db_conn.commit()
        return pred_id, prey_id

    def _death_row(self, mob_id):
        cursor = self.server.db_conn.cursor()
        cursor.execute(
            "SELECT death, fitnessScore FROM mob_genes WHERE mob_id = ?",
            (mob_id,),
        )
        return cursor.fetchone()

    async def test_kill_records_death_once(self):
        """A normal attack that kills a living target records death/fitness/meat."""
        pred_id, prey_id = self._make_predator_and_prey()
        mock_ws = AsyncMock()

        await self.server._handle_attack_mob(
            {"mobId": pred_id, "targetId": prey_id}, mock_ws
        )

        row = self._death_row(prey_id)
        self.assertIsNotNone(row["death"], "death timestamp must be set")
        self.assertTrue(row["death"], "death timestamp must be non-zero")
        self.assertIsNotNone(row["fitnessScore"], "fitness must be computed")

        # Carcass meat pool initialised on mob_health.fat.
        cursor = self.server.db_conn.cursor()
        cursor.execute("SELECT fat FROM mob_health WHERE mob_id = ?", (prey_id,))
        self.assertGreater(cursor.fetchone()["fat"], 0.0,
                           "carcass meat must be initialised")

        # No error sent for a successful kill.
        mock_ws.send_error.assert_not_called()

    async def test_second_attack_does_not_rewrite_death(self):
        """Second attack on the dead target must not change death/fitness."""
        pred_id, prey_id = self._make_predator_and_prey()
        mock_ws = AsyncMock()

        await self.server._handle_attack_mob(
            {"mobId": pred_id, "targetId": prey_id}, mock_ws
        )
        first = self._death_row(prey_id)

        # Attack the corpse again (same tick).
        await self.server._handle_attack_mob(
            {"mobId": pred_id, "targetId": prey_id}, mock_ws
        )
        second = self._death_row(prey_id)

        self.assertEqual(first["death"], second["death"],
                         "death timestamp must not be rewritten")
        self.assertEqual(first["fitnessScore"], second["fitnessScore"],
                         "fitness must not be recomputed")

    async def test_second_attack_sends_target_already_dead(self):
        """A second attack on a dead target sends TARGET_ALREADY_DEAD."""
        pred_id, prey_id = self._make_predator_and_prey()

        # First attack: route send_error through a spy so we can assert later.
        sent = []

        async def fake_send_error(ws, code, msg, extra=None):
            sent.append(code)

        self.server.send_error = fake_send_error  # type: ignore[assignment]
        mock_ws = AsyncMock()

        await self.server._handle_attack_mob(
            {"mobId": pred_id, "targetId": prey_id}, mock_ws
        )
        self.assertNotIn("TARGET_ALREADY_DEAD", sent,
                         "first (killing) attack must not error")

        await self.server._handle_attack_mob(
            {"mobId": pred_id, "targetId": prey_id}, mock_ws
        )
        self.assertIn("TARGET_ALREADY_DEAD", sent,
                      "second attack on corpse must send TARGET_ALREADY_DEAD")

    async def test_death_logged_exactly_once_across_many_attacks(self):
        """The predation death line must be logged exactly once for many attacks."""
        pred_id, prey_id = self._make_predator_and_prey()
        mock_ws = AsyncMock()

        with self.assertLogs("Server.MobInteractions", level="INFO") as cm:
            # Kill, then hammer the corpse repeatedly.
            for _ in range(6):
                await self.server._handle_attack_mob(
                    {"mobId": pred_id, "targetId": prey_id}, mock_ws
                )

        death_lines = [
            line for line in cm.output
            if "died cause=predation" in line and prey_id in line
        ]
        self.assertEqual(len(death_lines), 1,
                         f"expected exactly one predation death log, got "
                         f"{len(death_lines)}: {death_lines}")

    async def test_carcass_meat_not_reapplied_on_repeat_attack(self):
        """Repeated attacks must not refill carcass meat back to baseline."""
        pred_id, prey_id = self._make_predator_and_prey()
        mock_ws = AsyncMock()

        await self.server._handle_attack_mob(
            {"mobId": pred_id, "targetId": prey_id}, mock_ws
        )

        cursor = self.server.db_conn.cursor()
        # Simulate some carcass being eaten (drain meat below baseline).
        cursor.execute(
            "UPDATE mob_health SET fat = 12.0 WHERE mob_id = ?", (prey_id,)
        )
        self.server.db_conn.commit()

        # Re-attack the corpse — must NOT top the meat back up.
        await self.server._handle_attack_mob(
            {"mobId": pred_id, "targetId": prey_id}, mock_ws
        )

        cursor.execute("SELECT fat FROM mob_health WHERE mob_id = ?", (prey_id,))
        self.assertEqual(cursor.fetchone()["fat"], 12.0,
                         "carcass meat must not be re-applied on a repeat attack")


if __name__ == "__main__":
    unittest.main()
