"""
Tests for client/websocket_client.py — HexGenLifeClient + ClientState.

Run from the project root:
    python -m pytest tests/test_websocket_client.py -v
"""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, call

from client.websocket_client import HexGenLifeClient, ClientState


# ---------------------------------------------------------------------------
# ClientState tests (synchronous)
# ---------------------------------------------------------------------------
class TestClientState(unittest.TestCase):

    def setUp(self):
        self.state = ClientState()

    def test_initial_state_has_required_keys(self):
        s = self.state.get_state()
        self.assertIn("mobs", s)
        self.assertIn("worldTiles", s)

    def test_set_state_updates_and_notifies(self):
        notified = []
        self.state.subscribe(lambda s: notified.append(s))
        self.state.setState({"mobs": {"m1": {"health": 50}}})
        self.assertEqual(len(notified), 1)

    def test_process_mob_update(self):
        mob_data = {
            "mobId": "mob_abc",
            "health": {"hunger": 10, "fat": 5, "health": 90, "age": 10}
        }
        self.state._process_mob_update(mob_data)
        s = self.state.get_state()
        self.assertIn("mob_abc", s["mobs"])
        self.assertEqual(s["mobs"]["mob_abc"]["health"]["health"], 90)

    def test_process_world_update(self):
        world_data = {
            "mobs": [{"mob_id": "m1", "position": "{\"x\":0,\"y\":0}"}],
            "tiles": [{"id": 1, "centerX": 0, "centerY": 0}]
        }
        self.state._process_world_update(world_data)
        s = self.state.get_state()
        self.assertIn("m1", s["mobs"])
        self.assertIn(1, s["worldTiles"])

    def test_handle_incoming_mob_update(self):
        msg = {
            "type": "MOB_UPDATE",
            "payload": {
                "mobId": "m2",
                "health": {"hunger": 0, "fat": 0, "health": 100, "age": 0},
                "brain": {"updated": None},
                "geneTraits": {"mobType": "default", "fitnessScore": 100, "death": None}
            }
        }
        self.state.handle_incoming_message(msg)
        s = self.state.get_state()
        self.assertIn("m2", s["mobs"])

    def test_handle_incoming_world_update(self):
        msg = {
            "type": "WORLD_UPDATE",
            "payload": {
                "mobs": [],
                "tiles": [{"id": 42, "centerX": 10, "centerY": 20}]
            }
        }
        self.state.handle_incoming_message(msg)
        s = self.state.get_state()
        self.assertIn(42, s["worldTiles"])

    def test_handle_incoming_error_logged(self):
        """ERROR messages should be handled without raising."""
        msg = {
            "type": "ERROR",
            "payload": {"errorCode": "TEST", "errorMessage": "Something failed"}
        }
        # Should not raise
        self.state.handle_incoming_message(msg)


# ---------------------------------------------------------------------------
# HexGenLifeClient async tests
# ---------------------------------------------------------------------------
class TestHexGenLifeClientAsync(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.uri = "ws://mock:8765"
        self.client_id = "test_client_1"
        self.client = HexGenLifeClient(self.uri, self.client_id)

    # --- connect -----------------------------------------------------------
    @patch("client.websocket_client.websockets.connect", new_callable=AsyncMock)
    async def test_connect_success(self, mock_connect):
        mock_ws = AsyncMock()
        mock_connect.return_value = mock_ws
        result = await self.client.connect()
        self.assertTrue(result)
        self.assertIs(self.client.websocket, mock_ws)

    @patch("client.websocket_client.websockets.connect", side_effect=OSError("refused"))
    async def test_connect_failure_returns_false(self, _mock_connect):
        result = await self.client.connect()
        self.assertFalse(result)

    # --- send_move_mob -----------------------------------------------------
    async def test_send_move_mob_integer_coords(self):
        mock_ws = AsyncMock()
        self.client.websocket = mock_ws

        await self.client.send_move_mob("mob_1", 3, -7)

        mock_ws.send.assert_awaited_once()
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "MOVE_MOB")
        loc = sent["payload"]["targetLocation"]
        self.assertIsInstance(loc["x"], int)
        self.assertIsInstance(loc["y"], int)
        self.assertEqual(loc["x"], 3)
        self.assertEqual(loc["y"], -7)

    async def test_send_move_mob_mob_id_is_string(self):
        """mobId must be serialised as a string even if passed as int."""
        mock_ws = AsyncMock()
        self.client.websocket = mock_ws
        await self.client.send_move_mob(42, 0, 0)
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertIsInstance(sent["payload"]["mobId"], str)

    # --- send_request_world_state -----------------------------------------
    async def test_send_request_world_state(self):
        mock_ws = AsyncMock()
        self.client.websocket = mock_ws
        await self.client.send_request_world_state()
        mock_ws.send.assert_awaited_once()
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "REQUEST_WORLD_STATE")
        self.assertIn("clientId", sent["payload"])

    # --- send_message no-op when not connected ----------------------------
    async def test_send_message_no_crash_when_disconnected(self):
        self.client.websocket = None
        # Should log a warning but not raise
        await self.client.send_message("MOVE_MOB", {"mobId": "m1", "targetLocation": {"x": 0, "y": 0}})

    # --- listen ------------------------------------------------------------
    async def test_listen_sets_tick_event_on_tick_complete(self):
        async def _messages():
            yield json.dumps({"type": "TICK_COMPLETE", "payload": {}})

        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda _: _messages().__aiter__()
        self.client.websocket = mock_ws

        self.assertFalse(self.client.tick_event.is_set())
        await self.client.listen()
        self.assertTrue(self.client.tick_event.is_set())

    async def test_listen_delegates_other_messages_to_state(self):
        mob_update = json.dumps({
            "type": "MOB_UPDATE",
            "payload": {
                "mobId": "m99",
                "health": {"hunger": 0, "fat": 0, "health": 100, "age": 0},
                "brain": {"updated": None},
                "geneTraits": {"mobType": "default", "fitnessScore": 100, "death": None}
            }
        })

        async def _messages():
            yield mob_update

        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda _: _messages().__aiter__()
        self.client.websocket = mock_ws

        await self.client.listen()
        s = self.client.state_manager.get_state()
        self.assertIn("m99", s["mobs"])

    # --- autonomous_loop --------------------------------------------------
    async def test_autonomous_loop_sends_move_after_tick(self):
        mock_ws = AsyncMock()
        self.client.websocket = mock_ws
        self.client.tick_event.set()   # Pre-fire one tick

        async def _cancel_after_one():
            await asyncio.sleep(0.05)
            raise asyncio.CancelledError

        task = asyncio.create_task(self.client.autonomous_loop())
        cancel_task = asyncio.create_task(_cancel_after_one())
        try:
            await asyncio.gather(task, cancel_task)
        except asyncio.CancelledError:
            task.cancel()

        # At least one MOVE_MOB should have been sent
        self.assertTrue(mock_ws.send.called)
        sent = json.loads(mock_ws.send.call_args_list[0][0][0])
        self.assertEqual(sent["type"], "MOVE_MOB")


if __name__ == "__main__":
    unittest.main()