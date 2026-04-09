import unittest
import json
from unittest.mock import MagicMock, patch
import asyncio

# Import the class to be tested
from client.websocket_client import HexGenLifeClient, ClientState

class TestHexGenLifeClient(unittest.TestCase):

    def setUp(self):
        # Setup a mock URI and client instance for testing
        self.mock_uri = "ws://mock_server:8765"
        self.client = HexGenLifeClient(self.mock_uri)
        # Mock the asyncio loop for synchronous testing if needed, but for async tests, we'll use asyncio.run
        self.loop = asyncio.get_event_loop()
        # Manually set the loop for testing if necessary, or rely on asyncio.run

    @patch('client.websocket_client.asyncio.sleep', return_value=None)
    @patch('client.websocket_client.websockets.connect')
    async def test_connect_success(self, mock_connect, mock_sleep):
        """Test successful connection establishment."""
        mock_websocket = MagicMock()
        mock_websocket.open = True
        mock_connect.return_value.__aenter__.return_value = mock_websocket
        
        # Temporarily patch the receive_messages to prevent it from blocking indefinitely
        with patch.object(self.client, 'receive_messages', return_value=None):
            await self.client.connect()
        
        mock_connect.assert_called_once_with(self.mock_uri)
        mock_websocket.send.assert_not_called() # Should not send anything on connection only
        # Check if the connection was established (mock_websocket is set)
        self.assertIsNotNone(self.client.websocket)


    @patch('client.websocket_client.HexGenLifeClient.send_message')
    async def test_send_move_mob(self, mock_send_message):
        """Test that send_move_mob correctly calls send_message with the right payload."""
        mob_id = 5
        x, y = 15, 25
        await self.client.send_move_mob(mob_id, x, y)
        
        mock_send_message.assert_called_once_with("MOVE_MOB", {"mobId": mob_id, "targetLocation": {"x": x, "y": y}})

    @patch('client.websocket_client.HexGenLifeClient.send_message')
    async def test_send_request_world_state(self, mock_send_message):
        """Test that send_request_world_state correctly calls send_message with the right payload."""
        client_id = "test_client_id"
        await self.client.send_request_world_state(client_id)
        
        mock_send_message.assert_called_once_with("REQUEST_WORLD_STATE", {"clientId": client_id})

    # --- Test for State Management Logic (Simplified for this step) ---
    def test_state_update_mob_update(self):
        """Test the MOB_UPDATE handling updates the state correctly."""
        # Setup initial state
        initial_state = {"mobs": {}, "worldTiles": {}}
        self.client.state_manager.setState(initial_state)
        
        # Mock the incoming MOB_UPDATE data
        mob_id = 101
        mock_mob_update = {
            "type": "STATE",
            "MOB_UPDATE": {
                "mobId": mob_id,
                "health": {"hunger": 10.0, "fat": 5.0, "health": 90.0, "age": 100.0},
                "brain": {"updated": "2026-04-08T10:00:00Z"},
                "geneTraits": {"mobType": "A", "fitnessScore": 0.85, "death": None}
            }
        }
        
        # Manually call the handler (since we can't easily mock the websocket stream in this simple test)
        self.client.handle_incoming_message(mock_mob_update)
        
        # Assert state was updated
        final_state = self.client.get_client_state()
        self.assertIn(mob_id, final_state["mobs"])
        self.assertEqual(final_state["mobs"][mob_id]["health"]["health"], 90.0)
        self.assertEqual(final_state["mobs"][mob_id]["brain"]["updated"], "2026-04-08T10:00:00Z")


if __name__ == '__main__':
    # For running async tests from a script
    try:
        asyncio.run(unittest.main())
    except RuntimeError as e:
        if "cannot run non-main coroutine" in str(e):
            # Handle case where asyncio.run is called in an environment that already has a loop
            loop = asyncio.get_event_loop()
            loop.run_until_complete(unittest.main())
        else:
            raise