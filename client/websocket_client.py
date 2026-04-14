import asyncio
import websockets
import json
import logging
import random
import sys

from client.mob import Mob

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the WebSocket server address
SERVER_URI = "ws://localhost:8765"

class HexGenLifeClient:
    def __init__(self, uri, client_id):
        self.uri = uri
        self.client_id = client_id
        self.websocket = None
        self.state_manager = ClientState()
        self.tick_event = asyncio.Event()
        # Phase 4.5 — managed Mob objects
        self.mob_objects: dict[str, Mob] = {}  # {mob_id: Mob}
        self._look_events: dict[str, asyncio.Event] = {}  # {mob_id: Event}

    async def connect(self):
        """Establishes the WebSocket connection."""
        logging.info(f"[{self.client_id}] Attempting to connect to {self.uri}...")
        try:
            self.websocket = await websockets.connect(self.uri)
            logging.info(f"[{self.client_id}] WebSocket connection established.")
            return True
        except Exception as e:
            logging.error(f"[{self.client_id}] Connection failed: {e}")
            return False

    async def listen(self):
        """Listens for incoming messages and updates client state."""
        try:
            async for raw_message in self.websocket:
                message = json.loads(raw_message)
                msg_type = message.get("type")
                
                if msg_type == "TICK_COMPLETE":
                    logging.info(f"[{self.client_id}] Tick complete received.")
                    self.tick_event.set()
                elif msg_type == "LOOK_RESULT":
                    # Phase 4.5 — feed LOOK data to the mob's brain
                    payload = message.get("payload", {})
                    mob_self = payload.get("mob_self", {})
                    look_mob_id = mob_self.get("mobId", "")
                    if look_mob_id in self.mob_objects:
                        self.mob_objects[look_mob_id].store_look_result(payload)
                        self.mob_objects[look_mob_id].update_state({
                            "health": mob_self,
                        })
                    evt = self._look_events.get(look_mob_id)
                    if evt:
                        evt.set()
                    self.state_manager.handle_incoming_message(message)
                else:
                    self.state_manager.handle_incoming_message(message)
                    # Update mob objects with MOB_UPDATE data
                    if msg_type == "MOB_UPDATE":
                        payload = message.get("payload", {})
                        upd_mob_id = payload.get("mobId", "")
                        if upd_mob_id in self.mob_objects:
                            self.mob_objects[upd_mob_id].update_state(payload)
        except websockets.exceptions.ConnectionClosed:
            logging.warning(f"[{self.client_id}] Connection closed by server.")

    async def autonomous_loop(self):
        """Orchestrates autonomous actions synchronized with server ticks.

        Phase 4.5: Uses Mob objects with brain-driven decision making.
        Each tick: LOOK → brain thinks → send resulting action.
        Falls back to random movement if brain produces no action.
        """
        logging.info(f"[{self.client_id}] Starting autonomous loop.")

        # Ensure a Mob object exists for this client
        mob_id = f"mob_{self.client_id}"
        if mob_id not in self.mob_objects:
            self.mob_objects[mob_id] = Mob(mob_id)
            self._look_events[mob_id] = asyncio.Event()

        while True:
            await self.tick_event.wait()
            self.tick_event.clear()

            mob = self.mob_objects[mob_id]
            mob.reset_tick()

            # Step 1: Send LOOK command
            await self.send_message("LOOK", {"mobId": mob_id})

            # Wait briefly for LOOK_RESULT (with timeout)
            look_evt = self._look_events[mob_id]
            look_evt.clear()
            try:
                await asyncio.wait_for(look_evt.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                logging.warning(f"[{self.client_id}] LOOK_RESULT timeout")

            # Step 2: Brain thinks and produces an action
            action = mob.get_tick_action()

            if action and "action" in action:
                action_type = action["action"]
                action_payload = action.get("payload", {})
                action_payload["mobId"] = mob_id
                await self.send_message(action_type, action_payload)
                logging.info(f"[{self.client_id}] Brain action: {action_type}")
            else:
                # Fallback: random movement
                target_x = random.randint(-10, 10)
                target_y = random.randint(-10, 10)
                await self.send_move_mob(mob_id, target_x, target_y)


    async def send_message(self, message_type: str, payload: dict):
        """Sends a message to the server, handling serialization and connection status."""
        if self.websocket:
            # Ensure clientId is in the payload for server verification/assignment
            payload["clientId"] = self.client_id
            message = {"type": message_type, "payload": payload}
            try:
                await self.websocket.send(json.dumps(message))
                logging.debug(f"[{self.client_id}] Sent message type: {message_type}")
            except Exception as e:
                logging.error(f"[{self.client_id}] Failed to send message {message_type}: {e}")
        else:
            logging.warning(f"[{self.client_id}] WebSocket is not connected. Message type: {message_type} not sent.")

    async def send_move_mob(self, mob_id: str | int, x: int, y: int):
        """Sends a command to move a specific mob with integer coordinates."""
        logging.info(f"[{self.client_id}] Moving mob {mob_id} to ({x}, {y})")
        await self.send_message("MOVE_MOB", {
            "mobId": str(mob_id), 
            "targetLocation": {"x": int(x), "y": int(y)}
        })


    async def send_request_world_state(self):
        """Requests the current world state from the server."""
        logging.info(f"[{self.client_id}] Requesting world state.")
        await self.send_message("REQUEST_WORLD_STATE", {"clientId": self.client_id})

    async def run(self):
        """Main entry point for the client logic with auto-reconnect."""
        base_delay = 1
        max_delay = 30
        backoff_factor = 2
        delay = base_delay
        
        loop_task = asyncio.create_task(self.autonomous_loop())
        
        while True:
            if await self.connect():
                # Initial request to ensure mob is created and state is synced
                delay = base_delay
                await self.send_request_world_state()
                
                # Listen blocks until connection drops
                await self.listen()
                logging.warning(f"[{self.client_id}] Listen loop ended. Connection closed unexpectedly.")
                
            logging.info(f"[{self.client_id}] Reconnecting in {delay} seconds...")
            await asyncio.sleep(delay)
            delay = min(max_delay, delay * backoff_factor)

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
        # Server sends data under 'payload' per websocket_messages.json
        payload = message.get("payload", message.get("data", {}))
        if message_type == "MOB_UPDATE":
            self._process_mob_update(payload)
        elif message_type == "WORLD_UPDATE":
            self._process_world_update(payload)
        elif message_type == "ERROR":  # Gap #6 — handle server error responses
            code = payload.get("errorCode", "UNKNOWN")
            msg = payload.get("errorMessage", "")
            logging.warning(f"Server error [{code}]: {msg}")
        elif message_type == "HEX_CREATED":
            self._process_hex_created(payload)
        elif message_type == "LOOK_RESULT":
            self._process_look_result(payload)
        elif message_type == "TICK_COMPLETE":
            pass  # handled in listen() via tick_event
        else:
            logging.warning(f"Unknown message type received: {message_type}")

    def get_client_state(self) -> dict:
        """Retrieves the current state from the state manager."""
        return self.get_state()

    def _process_mob_update(self, mob_data: dict):
        """Processes a Mob Update message."""
        mob_id = mob_data.get("mobId") or mob_data.get("mob_id")
        if mob_id:
            self._state["mobs"][mob_id] = mob_data
            logging.info(f"Updated state for mob {mob_id}")
    
    def _process_world_update(self, world_data: dict):
        """Processes a World Update message (snapshot).
        
        Accepts either the documented hexId/tileData shape (from server) or
        raw row dicts (legacy / test fixtures).
        """
        mobs = world_data.get("mobs", [])
        tiles = world_data.get("tiles", [])

        for mob in mobs:
            mob_id = mob.get("mob_id") or mob.get("mobId")
            if mob_id:
                self._state["mobs"][mob_id] = mob

        for tile in tiles:
            # Documented schema: {hexId, tileData: {location, resources, updated}}
            if "hexId" in tile:
                tile_id = tile["hexId"]
            else:
                tile_id = tile.get("id")
            if tile_id is not None:
                self._state["worldTiles"][tile_id] = tile

        logging.info(f"Processed world snapshot: {len(mobs)} mobs, {len(tiles)} tiles.")

    def _process_hex_created(self, payload: dict):
        hex_id = payload.get("hexId")
        tile_data = payload.get("tileData")
        if hex_id and tile_data:
            self._state["worldTiles"][hex_id] = tile_data
            loc = tile_data.get("location", {})
            cx = loc.get("centerX", "?")
            cy = loc.get("centerY", "?")
            logging.info(f"HEX_CREATED: new tile {hex_id} at ({cx}, {cy})")

    def _process_look_result(self, payload: dict):
        """Process LOOK_RESULT — store visible tiles/mobs in state."""
        mob_self = payload.get("mob_self", {})
        mob_id = mob_self.get("mobId", "")
        if mob_id:
            self._state.setdefault("look_results", {})[mob_id] = payload
            logging.info(
                f"LOOK_RESULT for {mob_id}: "
                f"{len(payload.get('tiles', []))} tiles, "
                f"{len(payload.get('mobs', []))} mobs visible"
            )

    def trigger_render_update(self):
        """Public method to be called by the main loop to signal the viewer to re-render."""
        logging.info("Client signaling viewer to re-render.")
        pass

async def main():
    # Accept client IDs from command line arguments
    client_ids = sys.argv[1:]
    if not client_ids:
        client_ids = ["client_1"]
    
    logging.info(f"Starting clients: {client_ids}")
    
    tasks = []
    for cid in client_ids:
        client = HexGenLifeClient(SERVER_URI, cid)
        tasks.append(client.run())
        
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logging.info("Shutting down clients.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass