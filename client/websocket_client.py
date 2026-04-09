import asyncio
import websockets
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the WebSocket server address (to be configured)
SERVER_URI = "ws://localhost:8765" # Placeholder, this should be configurable

# Placeholder for HexGenLifeClient, assuming it needs to be defined or imported
class HexGenLifeClient:
    def __init__(self, uri):
        self.uri = uri
        self.websocket = None
        self.loop = asyncio.get_event_loop()
        self.state_manager = ClientState() # Initialize state manager here
        
    async def connect(self):
        """Establishes the WebSocket connection."""
        logging.info(f"Attempting to connect to {self.uri}...")
        try:
            self.websocket = await websockets.connect(self.uri)
            logging.info("WebSocket connection established.")
            # Start listening for messages in a separate task if necessary
            # For now, we just keep the connection open.
            return True
        except Exception as e:
            logging.error(f"Connection failed: {e}")
            return False

    async def send_message(self, message_type: str, payload: dict):
        """Sends a message to the server, handling serialization and connection status."""
        if self.websocket:
            message = {"type": message_type, "data": payload}
            try:
                await self.websocket.send(json.dumps(message))
                logging.info(f"Sent message type: {message_type}")
            except Exception as e:
                logging.error(f"Failed to send message {message_type}: {e}")
        else:
            logging.warning(f"WebSocket is not connected. Message type: {message_type} not sent.")

    async def send_move_mob(self, mob_id: str | int, x: float, y: float):
        """Sends a command to move a specific mob to coordinates (x, y)."""
        mob_id_str = str(mob_id)
        logging.info(f"Sending move command for mob {mob_id_str} to ({x}, {y})")
        # Adjusted payload to match test expectation: {"mobId": mob_id, "targetLocation": {"x": x, "y": y}}
        await self.send_message("MOVE_MOB", {"mobId": mob_id_str, "targetLocation": {"x": x, "y": y}})

    async def send_request_world_state(self, client_id: str):
        """Requests the current world state from the server."""
        logging.info(f"Requesting world state for client {client_id}")
        # Placeholder logic: send a request message type
        await self.send_message("REQUEST_WORLD_STATE", {"clientId": client_id})

    def start(self):
        """Starts the connection process in the event loop."""
        self.loop.run_until_complete(self.connect())

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
        # Removed: client_state = ClientState() - Instance creation moved to HexGenLifeClient

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
    
    def get_state_subscriber(self):
        """Returns a callback function to subscribe to state changes."""
        def state_callback(new_state):
            logging.info("State has been updated. Triggering rendering update.")
            # TODO: Signal the rendering component/state manager upon any state change
        return state_callback

    def handle_incoming_message(self, message: dict):
        """Delegates incoming messages to the state manager."""
        message_type = message.get("type")
        if message_type == "MOB_UPDATE":
            self._process_mob_update(message.get("data", {}))
        elif message_type == "WORLD_UPDATE":
            self._process_world_update(message.get("data", {}))
        else:
            logging.warning(f"Unknown message type received: {message_type}")

    def get_client_state(self) -> dict:
        """Retrieves the current state from the state manager."""
        return self.get_state()

    def _process_mob_update(self, mob_data: dict):
        """Processes a Mob Update message with nested health and gene information."""
        mob_id = mob_data.get("mob_id")
        
        # Semantic Clarification: MobGene.death is the timestamp when the mob died, 
        # while MobGene.expired is a boolean flag indicating if the gene has expired.
        
        health = mob_data.get("health", {})
        genes = mob_data.get("genes", [])
        
        logging.info(f"Processing Mob Update for {mob_id}. Health: {health}, Genes: {genes}")
        # TODO: Update local state with new mob and nested data
        # TODO: Update the UI/view with the new state
        pass
    
    def _process_world_update(self, world_data: dict):
        """Processes a World Update message with location and resource information."""
        location = world_data.get("location", {})
        resources = world_data.get("resources", {})
        
        logging.info(f"Processing World Update. Location: {location}, Resources: {resources}")
        # TODO: Update local map state
        # TODO: Update the UI/view with new world state
        pass

    def trigger_render_update(self):
        """Public method to be called by the main loop to signal the viewer to re-render."""
        logging.info("Client signaling viewer to re-render.")
        # In a real app, this would dispatch an event or call a specific viewer API.
        # For now, we log the signal.
        pass