# Viewer Placeholder
# This file will serve as the entry point or main component for the HexGenLife viewer.
# It is intended to subscribe to state changes from the HexGenLifeClient.

import logging
# Assume HexGenLifeClient is imported from the client module
# from client.websocket_client import HexGenLifeClient 

logging.basicConfig(level=logging.INFO)

class HexGenLifeViewer:
    def __init__(self, client: HexGenLifeClient):
        self.client = client
        self.current_state = {}
        logging.info("HexGenLifeViewer initialized.")

    def start_listening(self):
        """Starts the process of listening for client state updates."""
        # In a real application, this would set up timers or event listeners 
        # to call self.update_view() when the client signals a change.
        logging.info("Viewer is now listening for state updates from the client.")
        # Example: self.client.state_manager.subscribe(self.update_view)

    def update_view(self, new_state: dict):
        """
        This method is called by the client when state changes.
        This is where the actual rendering logic (e.g., updating Pygame/GUI) would reside.
        """
        self.current_state = new_state
        logging.info(f"VIEWER RENDER: Received new state. Mobs: {len(new_state.get('mobs', {}))}, Tiles: {len(new_state.get('worldTiles', {}))}")
        # TODO: Implement actual rendering logic here using the new_state data.

if __name__ == '__main__':
    print("--- Viewer Placeholder Execution ---")
    # Mock client for standalone test
    class MockClient:
        def trigger_render_update(self):
            print(">>> MOCK: Client signaled a render update <<<")
            # Simulate state change for testing the update_view method
            mock_state = {"mobs": {1: {"health": {"health": 95.0}, "brain": {"updated": "now"}}, "worldTiles": {1: {"location": {"centerX": 10.0, "centerY": 10.0}, "resources": {"water": 1.0, "grass": 0.5}}}}
            print(">>> MOCK: State update simulated <<<")
            
    mock_client = MockClient()
    viewer = HexGenLifeViewer(mock_client)
    viewer.start_listening()
    
    # Simulate the client calling the viewer's update method
    viewer.update_view(mock_state)
    print("--- Viewer Placeholder Finished ---")