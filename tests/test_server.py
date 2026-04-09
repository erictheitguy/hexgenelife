import unittest
from unittest.mock import MagicMock, patch
import json
import os

# Adjust import based on actual structure. Assuming server.py is in the server directory.
from server.server import GameServer

class TestGameServer(unittest.TestCase):

    def setUp(self):
        # Setup a temporary in-memory database path for testing
        self.test_db_path = "test_game_state.db"
        self.server = GameServer(db_path=self.test_db_path)
        # Ensure the test DB file is cleaned up before and after tests
        for _ in range(3): # Retry up to 3 times to remove the file
            if os.path.exists(self.test_db_path):
                try:
                    os.remove(self.test_db_path)
                    break
                except PermissionError:
                    # File is locked, wait and retry
                    import time
                    time.sleep(0.1)
            else:
                break

    def tearDown(self):
        # Clean up the test database file
        for _ in range(3): # Retry up to 3 times to remove the file
            if os.path.exists(self.test_db_path):
                try:
                    os.remove(self.test_db_path)
                    break
                except PermissionError:
                    # File is locked, wait and retry
                    import time
                    time.sleep(0.1)
            else:
                break

    def test_initialize_db(self):
        # Test if initialization creates the DB file and tables (basic check)
        self.assertTrue(os.path.exists(self.test_db_path))
        self.assertIsNotNone(self.server.db_conn)

    @patch.object(GameServer, '_handle_move_mob')
    @patch.object(GameServer, '_handle_request_world_state')
    def test_receive_message_move_mob(self, mock_handle_request, mock_handle_move):
        """Test receiving a MOVE_MOB message correctly routes to _handle_move_mob."""
        test_message = json.dumps({"type": "MOVE_MOB", "data": {"mob_id": "m1", "new_pos": "1,2"}})
        self.server.receive_message(test_message)
        mock_handle_move.assert_called_once()
        mock_handle_request.assert_not_called()

    @patch.object(GameServer, '_handle_move_mob')
    @patch.object(GameServer, '_handle_request_world_state')
    def test_receive_message_request_world_state(self, mock_handle_request, mock_handle_move):
        """Test receiving a REQUEST_WORLD_STATE message correctly routes to _handle_request_world_state."""
        test_message = json.dumps({"type": "REQUEST_WORLD_STATE", "data": {"client_id": "c1", "scope": "world"}})
        self.server.receive_message(test_message)
        mock_handle_request.assert_called_once()
        mock_handle_move.assert_not_called()

    def test_receive_message_invalid_json(self):
        """Test handling of malformed JSON."""
        self.server.receive_message("{'type': 'INVALID'") # Invalid JSON structure
        # In a real scenario, we would check for printed error or exception handling.
        # For this test, we just ensure it doesn't crash.

    @patch('server.server.GameServer._initialize_db')
    def test_initialization_sets_up_db(self, mock_init_db):
        """Test that initialization calls the DB setup."""
        GameServer(db_path=self.test_db_path)
        mock_init_db.assert_called_once()


if __name__ == '__main__':
    unittest.main()