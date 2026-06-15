"""
Tests for client-side mob retirement (COR-2 / ADD-3).

When the server removes a mob (MOB_EATEN) or reports it gone (MOB_NOT_FOUND),
the client must retire it from HexGenLifeClient.mob_objects — the dict the
autonomous_loop iterates — not just from the StateManager's _state["mobs"].

Run from the project root:
    .venv/bin/python -m pytest tests/test_client_mob_retirement.py -v
"""
import json
import unittest
from unittest.mock import MagicMock

from client.mob import Mob
from client.websocket_client import HexGenLifeClient


class TestRetireMobHelper(unittest.TestCase):

    def setUp(self):
        self.client = HexGenLifeClient("ws://mock:8765", "test_client")

    def _seed(self, mob_id):
        import asyncio
        self.client.mob_objects[mob_id] = Mob(mob_id, mob_type="prey")
        self.client._look_events[mob_id] = asyncio.Event()
        self.client._stale_perception[mob_id] = True
        self.client._look_timeout_streak[mob_id] = 1
        self.client._last_sent_action[mob_id] = {"type": "MOVE_MOB", "payload": {}}
        self.client._look_in_flight.add(mob_id)
        self.client._current_acting_mob = mob_id

    def test_retire_clears_all_bookkeeping(self):
        self._seed("mob_a")
        self.client.retire_mob("mob_a", reason="test")
        self.assertNotIn("mob_a", self.client.mob_objects)
        self.assertNotIn("mob_a", self.client._look_events)
        self.assertNotIn("mob_a", self.client._stale_perception)
        self.assertNotIn("mob_a", self.client._look_timeout_streak)
        self.assertNotIn("mob_a", self.client._last_sent_action)
        self.assertNotIn("mob_a", self.client._look_in_flight)
        self.assertIsNone(self.client._current_acting_mob)

    def test_retire_is_idempotent(self):
        self._seed("mob_b")
        self.client.retire_mob("mob_b")
        # Second call must not raise.
        self.client.retire_mob("mob_b")
        self.assertNotIn("mob_b", self.client.mob_objects)

    def test_retire_unknown_id_does_not_raise(self):
        # Calling on a mob that was never owned must be safe.
        self.client.retire_mob("never_existed")
        self.assertNotIn("never_existed", self.client.mob_objects)

    def test_retire_preserves_current_acting_mob_when_different(self):
        self._seed("mob_c")
        self.client._current_acting_mob = "mob_other"
        self.client.retire_mob("mob_c")
        self.assertEqual(self.client._current_acting_mob, "mob_other")


class TestMobEatenRetirement(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = HexGenLifeClient("ws://mock:8765", "test_client")
        self.client.mob_objects["mob_eaten"] = Mob("mob_eaten", mob_type="prey")

    async def _feed(self, message):
        async def _messages():
            yield json.dumps(message)
        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda _: _messages().__aiter__()
        self.client.websocket = mock_ws
        await self.client.listen()

    async def test_mob_eaten_retires_owned_mob(self):
        await self._feed({
            "type": "MOB_EATEN",
            "payload": {"eaterId": "predator_1", "targetId": "mob_eaten"},
        })
        self.assertNotIn("mob_eaten", self.client.mob_objects)

    async def test_mob_eaten_for_unowned_mob_is_harmless(self):
        await self._feed({
            "type": "MOB_EATEN",
            "payload": {"eaterId": "predator_1", "targetId": "not_mine"},
        })
        # Our owned mob is untouched; no crash for the unowned target.
        self.assertIn("mob_eaten", self.client.mob_objects)


class TestMobNotFoundRetirement(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = HexGenLifeClient("ws://mock:8765", "test_client")
        self.client.mob_objects["mob_ghost"] = Mob("mob_ghost", mob_type="prey")

    async def test_mob_not_found_retires_attributed_mob(self):
        async def _messages():
            yield json.dumps({"type": "ERROR", "payload": {
                "errorCode": "MOB_NOT_FOUND",
                "errorMessage": "Mob mob_ghost not found.",
            }})
        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda _: _messages().__aiter__()
        self.client.websocket = mock_ws

        await self.client.listen()

        self.assertNotIn("mob_ghost", self.client.mob_objects)

    async def test_non_not_found_error_does_not_retire(self):
        self.client._current_acting_mob = "mob_ghost"
        async def _messages():
            yield json.dumps({"type": "ERROR", "payload": {
                "errorCode": "NO_GRASS",
                "errorMessage": "No grass available.",
            }})
        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda _: _messages().__aiter__()
        self.client.websocket = mock_ws

        await self.client.listen()

        # A recoverable error must NOT retire the mob.
        self.assertIn("mob_ghost", self.client.mob_objects)


class TestStateManagerRemovalInsufficient(unittest.TestCase):
    """Locks in the ADD-3 fix: StateManager removal alone does not clean
    mob_objects (the dict autonomous_loop reads); retire_mob does."""

    def setUp(self):
        self.client = HexGenLifeClient("ws://mock:8765", "test_client")
        self.client.mob_objects["mob_x"] = Mob("mob_x", mob_type="prey")
        self.client.state_manager._state["mobs"]["mob_x"] = {"mob_id": "mob_x"}

    def test_state_manager_eaten_does_not_touch_mob_objects(self):
        self.client.state_manager._process_mob_eaten({"targetId": "mob_x"})
        # Removed from state...
        self.assertNotIn("mob_x", self.client.state_manager._state["mobs"])
        # ...but still in mob_objects — the loop would keep acting for it.
        self.assertIn("mob_x", self.client.mob_objects)

    def test_retire_mob_cleans_mob_objects(self):
        self.client.retire_mob("mob_x", reason="MOB_EATEN")
        self.assertNotIn("mob_x", self.client.mob_objects)


if __name__ == "__main__":
    unittest.main()
