import asyncio
import websockets
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the WebSocket server address (to be configured)
SERVER_URI = "ws://localhost:8765" # Placeholder, this should be configurable

# --- Phase 3: State Management and Incoming Message Handling ---
class ClientState:
    """Simple Observable Pattern State Manager for the client."""
    def __init__(self):
        self._state = {
            "mobs": {},  # {mobId: {health: {...}, brain: {...}, geneTraits: {...}}}
            "worldTiles": {} # {hexId: {location: {...}, resources: {...}}}
        }
        # Define expected initial structure for better type hinting/clarity
        self._initial_state_structure = {
            "mobs": {
                "health": {"hunger": 0.0, "fat": 0.0, "health": 100.0, "age": 0.0},
                "brain": {"updated": None},
                "geneTraits": {"mobType": "Unknown", "fitnessScore": 0.0, "death": None}
            },
            "worldTiles": {
                "location": {"centerX": 0.0, "centerY": 0.0},
                "resources": {"water": 0.0, "grass": 0.0}
            }
        }
        self._state.update(self._initial_state_structure)
        self._subscribers = []
    def subscribe(self, callback):
        """Adds a callback function to be called on state changes."""
        self._subscribers.append(callback)
    def setState(self, new_state: dict):
        """Updates the state and notifies all subscribers."""
        self._state.update(new_state)
        for callback in self._subscribers:
            callback(self._state)
    def get_state(self):
        """Returns a copy of the current state."""
        return self._state.copy()

    # Initialize state manager
    client_state = ClientState()

    def handle_incoming_message(self, data: dict):
        """Handles incoming messages based on the message type."""
        msg_type = data.get("type")
        payload = data.get("payload", {})

        if msg_type == "STATE":
            if "MOB_UPDATE" in data:
                logging.info(f"Handling MOB_UPDATE for mobId: {payload.get('mobId')}")
                # TODO: Implement state update logic using Observable Pattern
                mob_id = payload.get("mobId")
                mob_update_data = payload.get("health", {})
                brain_data = payload.get("brain", {})
                gene_data = payload.get("geneTraits", {})

                if mob_id is not None:
                    current_mobs = self.state_manager.get_state()["mobs"]
                    current_mobs[mob_id] = {
                        "health": mob_update_data,
                        "brain": brain_data,
                        "geneTraits": gene_data
                    }
                    self.state_manager.setState({"mobs": current_mobs})

            elif "WORLD_UPDATE" in data:
                logging.info(f"Handling WORLD_UPDATE for hexId: {payload.get('hexId')}")
                # TODO: Implement state update logic using Observable Pattern
                hex_id = payload.get("hexId")
                tile_data = payload.get("tileData", {})

                if hex_id is not None:
                    current_tiles = self.state_manager.get_state()["worldTiles"]
                    current_tiles[hex_id] = {
                        "location": tile_data.get("location", {}),
                        "resources": tile_data.get("resources", {})
                    }
                    self.state_manager.setState({"worldTiles": current_tiles})

        elif msg_type == "COMMAND":
            if "MOVE_MOB" in data:
                logging.info(f"Handling MOVE_MOB command for mobId: {payload.get('mobId')} to ({payload.get('targetLocation', {}).get('x')}, {payload.get('targetLocation', {}).get('y')})")
                # Outgoing message logic is handled by send_move_mob
                pass
            elif "REQUEST_WORLD_STATE" in data:
                logging.info(f"Handling REQUEST_WORLD_STATE for clientId: {payload.get('clientId')}")
                # Outgoing message logic is handled by send_request_world_state
                pass
        else:
            logging.warning(f"Unknown message type received: {msg_type}")

    def get_state_subscriber(self):
        """Returns a callback function to subscribe to state changes."""
        def state_callback(new_state):
            logging.info("State has been updated. Triggering rendering update.")
            # TODO: Signal the rendering component/state manager upon any state change
        return state_callback

    def get_client_state(self):
        return self.state_manager.get_state()

    def trigger_render_update(self):
        """Public method to be called by the main loop to signal the viewer to re-render."""
        logging.info("Client signaling viewer to re-render.")
        # In a real app, this would dispatch an event or call a specific viewer API.
        # For now, we log the signal.
        pass

    async def send_message(self, message_type: str, payload: dict):
        """Sends a structured message to the server."""
        if self.websocket and self.websocket.open:
            message = {
                "type": message_type,
                "payload": payload
            }
            try:
                await self.websocket.send(json.dumps(message))
                logging.info(f"Sent message type: {message_type}")
            except Exception as e:
                logging.error(f"Failed to send message {message_type}: {e}")
        else:
            logging.warning("WebSocket is not connected. Message not sent.")

    async def send_move_mob(self, mob_id: int, x: int, y: int):
        """Composes and sends a MOVE_MOB message."""
        payload = {
            "mobId": mob_id,
            "targetLocation": {
                "x": x,
                "y": y
            }
        }
        await self.send_message("MOVE_MOB", payload)

    async def send_request_world_state(self, client_id: str):
        """Composes and sends a REQUEST_WORLD_STATE message."""
        payload = {
            "clientId": client_id
        }
        await self.send_message("REQUEST_WORLD_STATE", payload)

    def start(self):
        """Starts the connection process in the event loop."""
        try:
            self.loop.run_until_complete(self.connect())
        except KeyboardInterrupt:
            logging.info("Client stopped by user (KeyboardInterrupt).")
        finally:
            logging.info("Client shutting down.")

if __name__ == "__main__":
    client = HexGenLifeClient(SERVER_URI)
    client.start()
    
    # --- Simulation of the main application loop calling render updates ---
    # In a real application, this would be managed by the GUI framework's main loop.
    print("--- Simulating main loop running state update checks ---")
    
    # Simulate a state update received by the client (for testing the subscription path)
    test_mob_update = {
        "type": "STATE",
        "MOB_UPDATE": {
            "mobId": 1,
            "health": {"hunger": 50.0, "fat": 10.0, "health": 80.0, "age": 500.0},
            "brain": {"updated": "2026-04-08T11:00:00Z"},
            "geneTraits": {"mobType": "B", "fitnessScore": 0.5, "death": None}
        }
    }
    client.handle_incoming_message(test_mob_update)
    
    client.trigger_render_update()
    print("--- Simulation finished ---")