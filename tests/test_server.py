"""
Tests for server/server.py — GameServer class.

Run from the project root:
    python -m pytest tests/test_server.py -v
"""
import asyncio
import contextlib
import json
import os
import sqlite3
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import server.server as server_mod

from server.server import GameServer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
DB_PATH = "test_game_state_server.db"


def _cleanup(path: str):
    for _ in range(3):
        try:
            if os.path.exists(path):
                os.remove(path)
            break
        except PermissionError:
            import time
            time.sleep(0.1)


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------
class TestGameServerInit(unittest.TestCase):
    """Database initialisation tests (synchronous)."""

    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    def test_db_file_created(self):
        """DB file must exist after initialisation."""
        self.assertTrue(os.path.exists(DB_PATH))

    def test_db_connection_open(self):
        """db_conn must be set and usable."""
        self.assertIsNotNone(self.server.db_conn)
        cursor = self.server.db_conn.cursor()
        cursor.execute("SELECT 1")
        self.assertEqual(cursor.fetchone()[0], 1)

    def test_tables_created(self):
        """All required tables must exist."""
        cursor = self.server.db_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        required = {"mobs", "mob_genes", "mob_health", "mob_brain",
                    "hex_tiles", "interaction_history"}
        self.assertTrue(required.issubset(tables),
                        f"Missing tables: {required - tables}")

    def test_at_least_one_hex_tile(self):
        """DB must have at least 1 hex tile after initialisation."""
        cursor = self.server.db_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM hex_tiles")
        self.assertGreater(cursor.fetchone()[0], 0)


class TestEnsureClientMob(unittest.TestCase):
    """Tests for _ensure_client_mob."""

    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    def test_creates_mob_rows_in_all_tables(self):
        """Mob creation must insert rows in mobs, mob_genes, mob_health, mob_brain."""
        self.server._ensure_client_mob("testclient")
        cursor = self.server.db_conn.cursor()
        mob_id = "mob_testclient"

        cursor.execute("SELECT 1 FROM mobs WHERE mob_id = ?", (mob_id,))
        self.assertIsNotNone(cursor.fetchone(), "Row missing in mobs")

        cursor.execute("SELECT 1 FROM mob_genes WHERE mob_id = ?", (mob_id,))
        self.assertIsNotNone(cursor.fetchone(), "Row missing in mob_genes")

        cursor.execute("SELECT 1 FROM mob_health WHERE mob_id = ?", (mob_id,))
        self.assertIsNotNone(cursor.fetchone(), "Row missing in mob_health")

        cursor.execute("SELECT 1 FROM mob_brain WHERE mob_id = ?", (mob_id,))
        self.assertIsNotNone(cursor.fetchone(), "Row missing in mob_brain")

    def test_no_duplicate_mob_creation(self):
        """Calling _ensure_client_mob twice must not raise or duplicate."""
        self.server._ensure_client_mob("dup_client")
        self.server._ensure_client_mob("dup_client")
        cursor = self.server.db_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM mobs WHERE mob_id = 'mob_dup_client'")
        self.assertEqual(cursor.fetchone()[0], 1)


class TestValidateMessage(unittest.TestCase):
    """Tests for _validate_message."""

    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    def _make_move(self, x, y, mob_id="mob1"):
        return {
            "type": "MOVE_MOB",
            "payload": {
                "mobId": mob_id,
                "targetLocation": {"x": x, "y": y},
            },
        }

    def test_valid_move_mob_integer_coords(self):
        msg = self._make_move(3, -5)
        self.assertTrue(self.server._validate_message(msg, "MOVE_MOB"))

    def test_invalid_move_mob_float_coords(self):
        msg = self._make_move(1.5, 2.7)
        self.assertFalse(self.server._validate_message(msg, "MOVE_MOB"))

    def test_invalid_move_mob_missing_mob_id(self):
        msg = {"type": "MOVE_MOB", "payload": {"targetLocation": {"x": 1, "y": 2}}}
        self.assertFalse(self.server._validate_message(msg, "MOVE_MOB"))

    def test_valid_request_world_state(self):
        msg = {"type": "REQUEST_WORLD_STATE", "payload": {"clientId": "c1"}}
        self.assertTrue(self.server._validate_message(msg, "REQUEST_WORLD_STATE"))

    def test_invalid_request_world_state_missing_client_id(self):
        msg = {"type": "REQUEST_WORLD_STATE", "payload": {}}
        self.assertFalse(self.server._validate_message(msg, "REQUEST_WORLD_STATE"))


class TestMobExists(unittest.TestCase):
    """Tests for _mob_exists."""

    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    def test_returns_false_for_unknown(self):
        self.assertFalse(self.server._mob_exists("nonexistent_mob"))

    def test_returns_true_after_creation(self):
        self.server._ensure_client_mob("known")
        self.assertTrue(self.server._mob_exists("mob_known"))


class TestAsyncHandlers(unittest.IsolatedAsyncioTestCase):
    """Async tests for WebSocket handlers."""

    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    async def test_send_error_sends_json(self):
        mock_ws = AsyncMock()
        await self.server.send_error(mock_ws, "TEST_CODE", "Test error.")
        mock_ws.send.assert_awaited_once()
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "ERROR")
        self.assertEqual(sent["payload"]["errorCode"], "TEST_CODE")

    async def test_ws_handler_malformed_json(self):
        """ws_handler must send ERROR and continue on bad JSON."""
        mock_ws = AsyncMock()
        mock_ws.__aiter__ = AsyncMock(return_value=iter(["not valid json"]))
        mock_ws.__anext__ = AsyncMock(side_effect=["{bad", StopAsyncIteration()])

        # Feed one bad message then close
        async def aiter_side_effect():
            yield "not valid json"

        mock_ws.__aiter__ = lambda self: aiter_side_effect().__aiter__()

        with patch.object(self.server, "send_error", new_callable=AsyncMock) as mock_err:
            await self.server.ws_handler(mock_ws)
            mock_err.assert_awaited()

    async def test_handle_move_mob_updates_position(self):
        """_handle_move_mob must update position in DB."""
        self.server._ensure_client_mob("mover")
        mob_id = "mob_mover"
        # Fix starting position so test is deterministic
        cursor = self.server.db_conn.cursor()
        cursor.execute("UPDATE mobs SET position = ? WHERE mob_id = ?",
                       (json.dumps({"x": 0, "y": 0}), mob_id))
        self.server.db_conn.commit()

        mock_ws = AsyncMock()
        await self.server._handle_move_mob(
            {"mobId": mob_id, "targetLocation": {"x": 5, "y": 7}}, mock_ws
        )
        cursor.execute("SELECT position FROM mobs WHERE mob_id = ?", (mob_id,))
        pos = json.loads(cursor.fetchone()[0])
        # Mob moves the full requested distance regardless of energy
        self.assertAlmostEqual(pos["x"], 5.0, places=1)
        self.assertAlmostEqual(pos["y"], 7.0, places=1)

    async def test_handle_move_mob_error_on_unknown_mob(self):
        """_handle_move_mob must reply with ERROR when mob doesn't exist."""
        mock_ws = AsyncMock()
        with patch.object(self.server, "send_error", new_callable=AsyncMock) as mock_err:
            await self.server._handle_move_mob(
                {"mobId": "ghost", "targetLocation": {"x": 0, "y": 0}}, mock_ws
            )
            mock_err.assert_awaited_once()

    async def test_handle_request_world_state(self):
        """_handle_request_world_state must send WORLD_UPDATE with documented shape."""
        mock_ws = AsyncMock()
        await self.server._handle_request_world_state({"clientId": "c1"}, mock_ws)
        mock_ws.send.assert_awaited_once()
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "WORLD_UPDATE")
        payload = sent["payload"]
        self.assertIn("mobs", payload)
        self.assertIn("tiles", payload)

    async def test_ws_handler_enqueues_into_inbound_queue(self):
        """Incoming validated commands should be queued into inbound_queue."""
        self.server._ensure_client_mob("qclient")
        msg = json.dumps({"type": "LOOK", "payload": {"mobId": "mob_qclient", "clientId": "qclient"}})

        async def _messages():
            yield msg

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda _: _messages().__aiter__()
        await self.server.ws_handler(mock_ws)
        self.assertGreaterEqual(self.server.inbound_queue.qsize(), 1)

    async def test_tick_loop_respects_look_budget(self):
        """LOOK processing should be capped per simulation tick."""
        self.server._ensure_client_mob("looker")
        ws = AsyncMock()
        for _ in range(4):
            await self.server.inbound_queue.put({
                "websocket": ws,
                "command_type": "LOOK",
                "payload": {"mobId": "mob_looker", "clientId": "looker"},
            })
        self.server.tick_rate = 0.01
        with patch.object(server_mod, "MAX_LOOKS_PER_SIM_TICK", 1), patch.object(server_mod, "MAX_ACTIONS_PER_SIM_TICK", 2):
            task = asyncio.create_task(self.server._tick_loop())
            await asyncio.sleep(0.04)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self.assertLessEqual(self.server._last_tick_stats.get("processed_look", 99), 1)
        self.assertGreaterEqual(self.server._last_tick_stats.get("deferred", 0), 1)


class TestDynamicWorldExpansion(unittest.IsolatedAsyncioTestCase):
    """Async tests for Phase 2 dynamic hex creation."""
    
    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    async def test_dynamic_hex_created_on_move(self):
        self.server._ensure_client_mob("explorer")
        mob_id = "mob_explorer"
        mock_ws = AsyncMock()
        self.server.clients.add(mock_ws)
        self.server._ws_to_mob[mock_ws] = mob_id
        
        # Move near the target so that it receives the broadcast
        cursor = self.server.db_conn.cursor()
        cursor.execute("UPDATE mobs SET position = ? WHERE mob_id = ?", (json.dumps({"x": 80, "y": 80}), mob_id))
        self.server.db_conn.commit()
        
        # Determine current hex count
        cursor.execute("SELECT COUNT(*) FROM hex_tiles")
        initial_count = cursor.fetchone()[0]
        
        # Move far enough to spawn a new hex (e.g. x=100, y=100)
        await self.server._handle_move_mob({"mobId": mob_id, "targetLocation": {"x": 100, "y": 100}}, mock_ws)
        
        # Hex length should be initial + 19 (for radius 2 layer)
        cursor.execute("SELECT COUNT(*) FROM hex_tiles")
        new_count = cursor.fetchone()[0]
        self.assertGreater(new_count, initial_count)
        
        # The new hex should have default resources because no neighbours exist at 100, 100
        cursor.execute("SELECT Water, Grass FROM hex_tiles ORDER BY id DESC LIMIT 1")
        new_hex = cursor.fetchone()
        self.assertEqual(new_hex["Water"], 5.0)
        self.assertEqual(new_hex["Grass"], 3.0)
        
        # Verify the broadcast was sent (multiple messages possible now)
        sent_msgs = [json.loads(call[0][0]) for call in mock_ws.send.call_args_list]
        hex_created_msgs = [m for m in sent_msgs if m["type"] == "HEX_CREATED"]
        self.assertGreaterEqual(len(hex_created_msgs), 1)

    async def test_broadcast_range_limited(self):
        """Test HEX_CREATED is sent to clients within 100 units, but not to those outside."""
        self.server._ensure_client_mob("close")
        self.server._ensure_client_mob("far")
        
        # Update their positions: "close" at 90,90, "far" at 500,500
        cursor = self.server.db_conn.cursor()
        cursor.execute("UPDATE mobs SET position = ? WHERE mob_id = ?", (json.dumps({"x": 90, "y": 90}), "mob_close"))
        cursor.execute("UPDATE mobs SET position = ? WHERE mob_id = ?", (json.dumps({"x": 500, "y": 500}), "mob_far"))
        self.server.db_conn.commit()
        
        ws_close = AsyncMock()
        ws_far = AsyncMock()
        self.server.clients.add(ws_close)
        self.server.clients.add(ws_far)
        self.server._ws_to_mob[ws_close] = "mob_close"
        self.server._ws_to_mob[ws_far] = "mob_far"
        
        # Explicitly trigger creating a hex at 100, 100
        await self.server._create_adjacent_hex(100, 100)
        
        # Check broadcasts
        sent_close = [json.loads(call[0][0]) for call in ws_close.send.call_args_list]
        self.assertTrue(any(m["type"] == "HEX_CREATED" for m in sent_close))
        
        sent_far = [json.loads(call[0][0]) for call in ws_far.send.call_args_list]
        self.assertFalse(any(m["type"] == "HEX_CREATED" for m in sent_far))

if __name__ == "__main__":
    unittest.main()
