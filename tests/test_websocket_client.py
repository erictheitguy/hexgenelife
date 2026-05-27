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

    def test_initial_state_has_brain_functions_key(self):
        """Initial ClientState must have an empty brain_functions dict."""
        s = self.state.get_state()
        self.assertIn("brain_functions", s)
        self.assertIsInstance(s["brain_functions"], dict)
        self.assertEqual(len(s["brain_functions"]), 0)

    def test_process_brain_functions_list_stores_by_id(self):
        """BRAIN_FUNCTIONS_LIST payload must be cached keyed by function_id."""
        msg = {
            "type": "BRAIN_FUNCTIONS_LIST",
            "payload": {
                "functions": [
                    {"function_id": "evaluate_state", "function_name": "Evaluate State",
                     "description": "Root node", "input_schema": None, "output_schema": None, "version": 1},
                    {"function_id": "evaluate_hunger", "function_name": "Evaluate Hunger",
                     "description": "Hunger gate", "input_schema": None, "output_schema": None, "version": 1},
                ]
            }
        }
        self.state.handle_incoming_message(msg)
        s = self.state.get_state()
        self.assertIn("evaluate_state", s["brain_functions"])
        self.assertIn("evaluate_hunger", s["brain_functions"])
        self.assertEqual(s["brain_functions"]["evaluate_state"]["function_name"], "Evaluate State")

    def test_get_brain_function_returns_cached_entry(self):
        """get_brain_function must return the stored metadata dict."""
        self.state._state["brain_functions"]["evaluate_danger"] = {
            "function_id": "evaluate_danger", "version": 2
        }
        result = self.state.get_brain_function("evaluate_danger")
        self.assertIsNotNone(result)
        self.assertEqual(result["version"], 2)

    def test_get_brain_function_returns_none_for_unknown(self):
        """get_brain_function must return None for a function_id not yet fetched."""
        self.assertIsNone(self.state.get_brain_function("nonexistent_fn"))


# ---------------------------------------------------------------------------
# ClientState semantic broadcast event tests (synchronous)
# ---------------------------------------------------------------------------
class TestClientStateSemanticEvents(unittest.TestCase):

    def setUp(self):
        self.state = ClientState()
        self.state._state["mobs"]["mob_1"] = {
            "mob_id": "mob_1",
            "position": {"x": 0, "y": 0},
            "health": {"hunger": 0, "fat": 0, "health": 80.0, "age": 0},
        }
        # Tile stored in WORLD_UPDATE shape (string hex key)
        self.state._state["worldTiles"]["5"] = {
            "hexId": "5",
            "tileData": {
                "location": {"centerX": 10, "centerY": 10},
                "resources": {"water": 50.0, "grass": 20.0},
            },
        }

    def test_mob_moved_patches_position(self):
        msg = {"type": "MOB_MOVED", "payload": {"mobId": "mob_1", "position": {"x": 3, "y": 7}}}
        self.state.handle_incoming_message(msg)
        pos = self.state.get_state()["mobs"]["mob_1"]["position"]
        self.assertEqual(pos["x"], 3)
        self.assertEqual(pos["y"], 7)

    def test_mob_moved_stubs_unknown_mob(self):
        msg = {"type": "MOB_MOVED", "payload": {"mobId": "new_mob", "position": {"x": 1, "y": 2}}}
        self.state.handle_incoming_message(msg)
        s = self.state.get_state()
        self.assertIn("new_mob", s["mobs"])
        self.assertEqual(s["mobs"]["new_mob"]["position"]["x"], 1)

    def test_grass_eaten_patches_tile_resources(self):
        msg = {"type": "GRASS_EATEN", "payload": {"mobId": "mob_1", "tileId": "5", "grassRemaining": 12.0}}
        self.state.handle_incoming_message(msg)
        grass = self.state.get_state()["worldTiles"]["5"]["tileData"]["resources"]["grass"]
        self.assertEqual(grass, 12.0)

    def test_mob_attacked_decrements_target_health(self):
        msg = {"type": "MOB_ATTACKED", "payload": {"attackerId": "other", "targetId": "mob_1", "damage": 15.0}}
        self.state.handle_incoming_message(msg)
        health = self.state.get_state()["mobs"]["mob_1"]["health"]["health"]
        self.assertEqual(health, 65.0)

    def test_mob_attacked_health_floors_at_zero(self):
        self.state._state["mobs"]["mob_1"]["health"]["health"] = 5.0
        msg = {"type": "MOB_ATTACKED", "payload": {"attackerId": "other", "targetId": "mob_1", "damage": 50.0}}
        self.state.handle_incoming_message(msg)
        health = self.state.get_state()["mobs"]["mob_1"]["health"]["health"]
        self.assertEqual(health, 0.0)

    def test_mob_eaten_removes_target_from_state(self):
        msg = {"type": "MOB_EATEN", "payload": {"eaterId": "predator_1", "targetId": "mob_1"}}
        self.state.handle_incoming_message(msg)
        self.assertNotIn("mob_1", self.state.get_state()["mobs"])

    def test_mob_bred_adds_child_stub(self):
        msg = {"type": "MOB_BRED", "payload": {"parentAId": "mob_1", "parentBId": "mob_2", "childId": "child_1"}}
        self.state.handle_incoming_message(msg)
        self.assertIn("child_1", self.state.get_state()["mobs"])

    def test_event_sequence_move_then_grass_eaten(self):
        """Position and grass state should both reflect incremental updates."""
        self.state.handle_incoming_message(
            {"type": "MOB_MOVED", "payload": {"mobId": "mob_1", "position": {"x": 5, "y": 5}}}
        )
        self.state.handle_incoming_message(
            {"type": "GRASS_EATEN", "payload": {"mobId": "mob_1", "tileId": "5", "grassRemaining": 0.0}}
        )
        s = self.state.get_state()
        self.assertEqual(s["mobs"]["mob_1"]["position"]["x"], 5)
        self.assertEqual(s["worldTiles"]["5"]["tileData"]["resources"]["grass"], 0.0)


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

    # --- send_request_brain_functions ------------------------------------
    async def test_send_request_brain_functions_sends_correct_type(self):
        """send_request_brain_functions must send REQUEST_BRAIN_FUNCTIONS."""
        mock_ws = AsyncMock()
        self.client.websocket = mock_ws
        await self.client.send_request_brain_functions()
        mock_ws.send.assert_awaited_once()
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "REQUEST_BRAIN_FUNCTIONS")

    async def test_listen_routes_brain_functions_list_to_state(self):
        """BRAIN_FUNCTIONS_LIST received in listen() must be stored in ClientState."""
        payload = {
            "functions": [
                {"function_id": "evaluate_flee", "function_name": "Evaluate Flee",
                 "description": "Flee logic", "input_schema": None, "output_schema": None, "version": 1},
            ]
        }

        async def _messages():
            yield json.dumps({"type": "BRAIN_FUNCTIONS_LIST", "payload": payload})

        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda _: _messages().__aiter__()
        self.client.websocket = mock_ws

        await self.client.listen()

        cached = self.client.state_manager.get_brain_function("evaluate_flee")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["function_name"], "Evaluate Flee")

    # --- send_message no-op when not connected ----------------------------
    async def test_send_message_no_crash_when_disconnected(self):
        self.client.websocket = None
        # Should log a warning but not raise
        await self.client.send_message("MOVE_MOB", {"mobId": "m1", "targetLocation": {"x": 0, "y": 0}})

    async def test_send_message_failure_sets_force_reconnect(self):
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = OSError("send failed")
        self.client.websocket = mock_ws
        await self.client.send_message("LOOK", {"mobId": "m1"})
        self.assertTrue(self.client._force_reconnect.is_set())

    # --- LOOK in-flight guard ---------------------------------------------
    def test_should_send_look_blocked_when_in_flight(self):
        """Stale perception forces wants_look=True, but in-flight guard suppresses send."""
        self.client._stale_perception["mob_x"] = True
        self.client._look_in_flight.add("mob_x")
        self.assertFalse(self.client._should_send_look("mob_x", tick_num=1))

    def test_should_send_look_allowed_when_not_in_flight(self):
        """Stale perception with no in-flight LOOK should send."""
        self.client._stale_perception["mob_x"] = True
        self.assertTrue(self.client._should_send_look("mob_x", tick_num=1))

    async def test_listen_look_result_clears_in_flight_and_stale(self):
        """LOOK_RESULT must clear both _look_in_flight and _stale_perception for the mob."""
        from client.mob import Mob

        mob_id = f"mob_{self.client_id}"
        self.client.mob_objects[mob_id] = Mob(mob_id, mob_type="prey")
        self.client._look_events[mob_id] = asyncio.Event()
        self.client._look_in_flight.add(mob_id)
        self.client._stale_perception[mob_id] = True

        async def _messages():
            yield json.dumps({
                "type": "LOOK_RESULT",
                "payload": {"mob_self": {"mobId": mob_id}}
            })

        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda _: _messages().__aiter__()
        self.client.websocket = mock_ws

        await self.client.listen()

        self.assertNotIn(mob_id, self.client._look_in_flight)
        self.assertFalse(self.client._stale_perception[mob_id])

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

        # At least one LOOK should have been sent (first phase of tick cycle)
        self.assertTrue(mock_ws.send.called)
        sent = json.loads(mock_ws.send.call_args_list[0][0][0])
        self.assertEqual(sent["type"], "LOOK")

    async def test_autonomous_loop_forces_reconnect_on_look_timeout_streak(self):
        from client.mob import Mob
        async def _timeout_wait_for(coro, timeout):
            coro.close()
            raise asyncio.TimeoutError

        mock_ws = AsyncMock()
        self.client.websocket = mock_ws
        self.client.connection_state = "CONNECTED"
        self.client._base_look_stride = 1
        self.client.mob_objects["mob_test_client_1"] = Mob("mob_test_client_1", mob_type="prey")
        self.client._look_events["mob_test_client_1"] = asyncio.Event()
        self.client._look_timeout_streak["mob_test_client_1"] = 2
        with patch("client.websocket_client.asyncio.wait_for", side_effect=_timeout_wait_for):
            self.client.tick_event.set()
            task = asyncio.create_task(self.client.autonomous_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            self.assertTrue(self.client._force_reconnect.is_set())


# ---------------------------------------------------------------------------
# Error feedback attribution tests
# ---------------------------------------------------------------------------
class TestErrorFeedback(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        from client.mob import Mob
        self.client = HexGenLifeClient("ws://mock:8765", "test_client")
        self.mob = Mob("mob_err", mob_type="prey")
        self.client.mob_objects["mob_err"] = self.mob

    async def test_error_attributed_to_current_acting_mob(self):
        """ERROR received while mob_err is acting is recorded in its brain memory."""
        self.client._current_acting_mob = "mob_err"
        self.client._last_sent_action["mob_err"] = {"type": "EAT_GRASS", "payload": {}}

        async def _messages():
            yield json.dumps({"type": "ERROR", "payload": {
                "errorCode": "NO_GRASS", "errorMessage": "No grass available."
            }})

        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda _: _messages().__aiter__()
        self.client.websocket = mock_ws

        await self.client.listen()

        err = self.mob.brain.memory.get("last_error")
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], "NO_GRASS")
        self.assertEqual(err["action"]["type"], "EAT_GRASS")

    async def test_error_attributed_by_mob_id_in_message(self):
        """'Mob X not found' messages are attributed to mob X even when a different mob is acting."""
        self.client._current_acting_mob = "mob_other"  # different from mob_err

        async def _messages():
            yield json.dumps({"type": "ERROR", "payload": {
                "errorCode": "MOB_NOT_FOUND", "errorMessage": "Mob mob_err not found."
            }})

        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda _: _messages().__aiter__()
        self.client.websocket = mock_ws

        await self.client.listen()

        err = self.mob.brain.memory.get("last_error")
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], "MOB_NOT_FOUND")

    def test_record_error_writes_code_and_action_to_memory(self):
        """Mob.record_error() persists error code and action context into brain memory."""
        self.mob.record_error("ACTION_LIMIT_EXCEEDED", {"type": "MOVE_MOB", "payload": {}})
        err = self.mob.brain.memory.get("last_error")
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], "ACTION_LIMIT_EXCEEDED")
        self.assertEqual(err["action"]["type"], "MOVE_MOB")

    def test_record_error_accepts_none_action(self):
        """record_error with no action context should still record the error code."""
        self.mob.record_error("VALIDATION_FAILED", None)
        err = self.mob.brain.memory.get("last_error")
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], "VALIDATION_FAILED")
        self.assertIsNone(err["action"])

    async def test_unattributable_error_does_not_raise(self):
        """ERROR for an unknown mob is handled gracefully (logs a warning, no crash)."""
        self.client._current_acting_mob = None  # nothing acting

        async def _messages():
            yield json.dumps({"type": "ERROR", "payload": {
                "errorCode": "DB_ERROR", "errorMessage": "Internal error."
            }})

        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda _: _messages().__aiter__()
        self.client.websocket = mock_ws

        await self.client.listen()  # Should not raise

    def test_server_busy_applies_client_throttle(self):
        self.client._throttle_ticks = 0
        self.client._handle_error_feedback({"errorCode": "SERVER_BUSY", "errorMessage": "queue full"})
        self.assertGreaterEqual(self.client._throttle_ticks, 1)


if __name__ == "__main__":
    unittest.main()
