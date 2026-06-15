"""
Tests for COR-3 — structured server→client error attribution.

The server now emits structured fields (mobId/targetId/commandType) in ERROR
payloads, and the client prefers payload["mobId"] over the legacy regex parse
and over self._current_acting_mob.

Run from the project root:
    .venv/bin/python -m pytest tests/test_error_attribution.py -v
"""
import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock

from client.websocket_client import HexGenLifeClient
from client.mob import Mob
from server.server import GameServer


# ---------------------------------------------------------------------------
# Client: structured-field attribution wins over legacy fallbacks
# ---------------------------------------------------------------------------
class TestStructuredAttribution(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = HexGenLifeClient("ws://mock:8765", "test_client")
        # The mob the error SHOULD attribute to.
        self.target_mob = Mob("mob_target", mob_type="prey")
        self.client.mob_objects["mob_target"] = self.target_mob
        # A different mob that is "currently acting" — proves structured field wins.
        self.other_mob = Mob("mob_other", mob_type="prey")
        self.client.mob_objects["mob_other"] = self.other_mob
        self.client._current_acting_mob = "mob_other"

    async def _deliver_error(self, payload: dict):
        async def _messages():
            yield json.dumps({"type": "ERROR", "payload": payload})

        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda _: _messages().__aiter__()
        self.client.websocket = mock_ws
        await self.client.listen()

    async def _assert_attributed_to_target(self, error_code: str, extra: dict | None = None):
        payload = {
            "errorCode": error_code,
            "errorMessage": "irrelevant human text",
            "mobId": "mob_target",
            "commandType": "ATTACK_MOB",
        }
        if extra:
            payload.update(extra)
        await self._deliver_error(payload)
        # The error must land on the structured target, NOT the acting mob.
        self.assertEqual(
            self.target_mob.brain.memory.get("last_error", {}).get("code"),
            error_code,
        )
        self.assertIsNone(self.other_mob.brain.memory.get("last_error"))

    async def test_breed_failed_attributes_to_structured_mob(self):
        await self._assert_attributed_to_target(
            "BREED_FAILED", {"commandType": "BREED_MOB", "targetId": "mob_mate"})

    async def test_mob_not_found_attributes_to_structured_mob(self):
        # Use a message naming a DIFFERENT mob to prove structured field wins
        # over the legacy regex parse too.
        await self._deliver_error({
            "errorCode": "MOB_NOT_FOUND",
            "errorMessage": "Mob mob_other not found.",
            "mobId": "mob_target",
            "commandType": "ATTACK_MOB",
        })
        self.assertEqual(
            self.target_mob.brain.memory.get("last_error", {}).get("code"),
            "MOB_NOT_FOUND",
        )
        # mob_target should have been retired (server no longer knows it).
        self.assertNotIn("mob_target", self.client.mob_objects)
        # The acting mob must NOT have received the error.
        self.assertIsNone(self.other_mob.brain.memory.get("last_error"))

    async def test_target_not_found_attributes_to_structured_mob(self):
        await self._assert_attributed_to_target(
            "TARGET_NOT_FOUND", {"targetId": "mob_ghost"})

    async def test_server_busy_attributes_to_structured_mob(self):
        await self._assert_attributed_to_target(
            "SERVER_BUSY", {"retryAfterMs": 500})
        self.assertGreaterEqual(self.client._throttle_ticks, 1)

    async def test_action_limit_exceeded_attributes_to_structured_mob(self):
        await self._assert_attributed_to_target("ACTION_LIMIT_EXCEEDED")
        self.assertGreaterEqual(self.client._throttle_ticks, 1)

    async def test_structured_command_type_used_when_no_local_action(self):
        """When no local last_sent_action exists, the recorded action context
        falls back to the server's commandType/targetId."""
        await self._deliver_error({
            "errorCode": "TARGET_NOT_FOUND",
            "errorMessage": "Target mob_ghost not found.",
            "mobId": "mob_target",
            "commandType": "EAT_MOB",
            "targetId": "mob_ghost",
        })
        err = self.target_mob.brain.memory.get("last_error")
        self.assertIsNotNone(err)
        self.assertEqual(err["action"]["type"], "EAT_MOB")
        self.assertEqual(err["action"]["payload"]["targetId"], "mob_ghost")


# ---------------------------------------------------------------------------
# Client: legacy fallbacks still work when no structured mobId is present
# ---------------------------------------------------------------------------
class TestLegacyFallback(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = HexGenLifeClient("ws://mock:8765", "test_client")
        self.mob = Mob("mob_legacy", mob_type="prey")
        self.client.mob_objects["mob_legacy"] = self.mob

    async def _deliver_error(self, payload: dict):
        async def _messages():
            yield json.dumps({"type": "ERROR", "payload": payload})

        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda _: _messages().__aiter__()
        self.client.websocket = mock_ws
        await self.client.listen()

    async def test_legacy_regex_parse_when_no_structured_field(self):
        """No payload["mobId"] → fall back to regex parse of the message."""
        self.client._current_acting_mob = "mob_someone_else"
        await self._deliver_error({
            "errorCode": "MOB_NOT_FOUND",
            "errorMessage": "Mob mob_legacy not found.",
        })
        self.assertEqual(
            self.mob.brain.memory.get("last_error", {}).get("code"),
            "MOB_NOT_FOUND",
        )

    async def test_legacy_current_acting_mob_when_no_field_no_match(self):
        """No structured field and no regex match → fall back to acting mob."""
        self.client._current_acting_mob = "mob_legacy"
        self.client._last_sent_action["mob_legacy"] = {"type": "EAT_GRASS", "payload": {}}
        await self._deliver_error({
            "errorCode": "NO_GRASS",
            "errorMessage": "No grass available at current tile.",
        })
        err = self.mob.brain.memory.get("last_error")
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], "NO_GRASS")
        self.assertEqual(err["action"]["type"], "EAT_GRASS")


# ---------------------------------------------------------------------------
# Server: representative handler emits structured fields
# ---------------------------------------------------------------------------
DB_PATH = "test_error_attribution.db"


def _cleanup(path: str):
    for _ in range(3):
        try:
            if os.path.exists(path):
                os.remove(path)
            break
        except PermissionError:
            import time
            time.sleep(0.1)


class TestServerEmitsStructuredFields(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)
        self.server._ensure_client_mob("attacker")

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    def _capture_error(self, mock_ws):
        """Return the parsed ERROR payload sent to the mock websocket."""
        for call_args in mock_ws.send.call_args_list:
            msg = json.loads(call_args[0][0])
            if msg.get("type") == "ERROR":
                return msg["payload"]
        return None

    async def test_attack_nonexistent_target_carries_command_type(self):
        mock_ws = AsyncMock()
        await self.server._handle_attack_mob(
            {"mobId": "mob_attacker", "targetId": "mob_does_not_exist"},
            mock_ws,
        )
        payload = self._capture_error(mock_ws)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["errorCode"], "TARGET_NOT_FOUND")
        self.assertEqual(payload["commandType"], "ATTACK_MOB")
        self.assertEqual(payload["mobId"], "mob_attacker")
        self.assertEqual(payload["targetId"], "mob_does_not_exist")
        # Human-readable text is preserved (backward compatible).
        self.assertIn("errorMessage", payload)

    async def test_breed_failed_carries_structured_fields(self):
        # Create a second mob so both exist (so we reach BREED_FAILED, not
        # TARGET_NOT_FOUND). Drop energy below the breed threshold so breeding
        # deterministically fails.
        self.server._ensure_client_mob("mate")
        cursor = self.server.db_conn.cursor()
        cursor.execute(
            "UPDATE mob_health SET energy = 0 WHERE mob_id IN ('mob_attacker', 'mob_mate')"
        )
        self.server.db_conn.commit()
        mock_ws = AsyncMock()
        await self.server._handle_breed(
            {"mobId": "mob_attacker", "targetId": "mob_mate"},
            mock_ws,
        )
        payload = self._capture_error(mock_ws)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["errorCode"], "BREED_FAILED")
        self.assertEqual(payload["commandType"], "BREED_MOB")
        self.assertEqual(payload["mobId"], "mob_attacker")
        self.assertEqual(payload["targetId"], "mob_mate")


if __name__ == "__main__":
    unittest.main()
