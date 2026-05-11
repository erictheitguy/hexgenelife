import asyncio
import websockets
import json
import logging
import random
import sys
import time

from client.mob import Mob

import os

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

def _configure_logging(level_name: str = "DEBUG"):
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(LOGS_DIR, "client.log")),
            logging.StreamHandler()
        ]
    )

_configure_logging(os.environ.get("LOG_LEVEL", "DEBUG"))
logger = logging.getLogger("ClientManager")

# Define the WebSocket server address
SERVER_URI = "ws://localhost:8765"

class HexGenLifeClient:
    def __init__(self, uri, client_id, mob_ids=None):
        self.uri = uri
        self.client_id = client_id
        self.mob_ids = mob_ids or []
        self.websocket = None
        self.state_manager = ClientState()
        self.tick_event = asyncio.Event()
        self.all_mobs_dead_event = asyncio.Event()
        # Phase 4.5 — managed Mob objects
        self.mob_objects: dict[str, Mob] = {}  # {mob_id: Mob}
        self._look_events: dict[str, asyncio.Event] = {}  # {mob_id: Event}


    async def connect(self):
        """Establishes the WebSocket connection."""
        logger.info(f"[{self.client_id}] Attempting to connect to {self.uri}...")
        try:
            self.websocket = await websockets.connect(self.uri)
            logger.info(f"[{self.client_id}] WebSocket connection established.")
            return True
        except Exception as e:
            logger.error(f"[{self.client_id}] Connection failed: {e}")
            return False

    async def listen(self):
        """Listens for incoming messages and updates client state."""
        try:
            async for raw_message in self.websocket:
                message = json.loads(raw_message)
                msg_type = message.get("type")
                
                if msg_type == "TICK_COMPLETE":
                    logger.debug(f"[{self.client_id}] Tick complete received.")
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
                elif msg_type == "MOB_BRED":
                    payload = message.get("payload", {})
                    child_id = payload.get("childId")
                    parent_a_id = payload.get("parentAId")
                    # Only the client that owns the parent adopts the child
                    if child_id and parent_a_id in self.mob_objects and child_id not in self.mob_objects:
                        child_mob = Mob(child_id)
                        self.mob_objects[child_id] = child_mob
                        self._look_events[child_id] = asyncio.Event()
                        logger.info(f"[{self.client_id}] Adopted child mob {child_id} (parent={parent_a_id})")
                else:
                    self.state_manager.handle_incoming_message(message)
                    # Update mob objects with MOB_UPDATE data
                    if msg_type == "MOB_UPDATE":
                        payload = message.get("payload", {})
                        upd_mob_id = payload.get("mobId", "")
                        if upd_mob_id in self.mob_objects:
                            self.mob_objects[upd_mob_id].update_state(payload)
                    elif msg_type == "WORLD_UPDATE":
                        payload = message.get("payload", {})
                        for mob_data in payload.get("mobs", []):
                            m_id = mob_data.get("mobId") or mob_data.get("mob_id")
                            if m_id in self.mob_objects:
                                self.mob_objects[m_id].update_state(mob_data)
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"[{self.client_id}] Connection closed by server.")

    async def autonomous_loop(self):
        """Orchestrates autonomous actions synchronized with server ticks.

        Phase 4.5: Uses Mob objects with brain-driven decision making.
        Each tick: LOOK → brain thinks → send resulting action.
        Falls back to random movement if brain produces no action.
        """
        logger.info(f"[{self.client_id}] Starting autonomous loop.")

        # Ensure at least the primary Mob object exists for this client
        target_mobs = self.mob_ids if self.mob_ids else [f"mob_{self.client_id}"]
        for mob_id in target_mobs:
            if mob_id not in self.mob_objects:
                self.mob_objects[mob_id] = Mob(mob_id)
                self._look_events[mob_id] = asyncio.Event()

        tick_num = 0
        while True:
            await self.tick_event.wait()
            self.tick_event.clear()
            tick_start = time.perf_counter()
            tick_num += 1

            # Filter for alive mobs
            alive_mobs = [m_id for m_id, m in self.mob_objects.items() if not m.is_dead]
            
            if not alive_mobs:
                logger.info(f"[{self.client_id}] All mobs are dead. Terminating autonomous loop.")
                self.all_mobs_dead_event.set()
                break

            t_look_total = 0.0
            t_brain_total = 0.0
            t_action_total = 0.0

            for mob_id in alive_mobs:
                mob = self.mob_objects[mob_id]
                mob.reset_tick()

                # Step 1: Send LOOK command
                t0 = time.perf_counter()
                await self.send_message("LOOK", {"mobId": mob_id})

                # Wait briefly for LOOK_RESULT (with timeout)
                look_evt = self._look_events.get(mob_id)
                if look_evt:
                    look_evt.clear()
                    try:
                        await asyncio.wait_for(look_evt.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        logger.warning(f"[{self.client_id}] LOOK_RESULT timeout for {mob_id}")
                        mob._awaiting_look = False  # proceed with stale look data
                t_look_total += time.perf_counter() - t0

                # Step 2: Brain thinks and produces an action
                if mob.is_dead:
                    logger.info(f"[{self.client_id}] Mob {mob_id} died after LOOK. Skipping brain action.")
                    continue

                t0 = time.perf_counter()
                action = mob.get_tick_action()
                t_brain_total += time.perf_counter() - t0

                t0 = time.perf_counter()
                if action and "action" in action:
                    action_type = action["action"]
                    action_payload = action.get("payload", {})
                    action_payload["mobId"] = mob_id
                    await self.send_message(action_type, action_payload)
                    logger.debug(f"[{self.client_id}] Brain action for {mob_id}: {action_type}")
                else:
                    # Fallback: random movement
                    target_x = random.randint(-10, 10)
                    target_y = random.randint(-10, 10)
                    await self.send_move_mob(mob_id, target_x, target_y)
                t_action_total += time.perf_counter() - t0

            t_total = time.perf_counter() - tick_start
            logger.debug(
                f"[{self.client_id}][TICK {tick_num}] total={t_total*1000:.1f}ms  "
                f"look={t_look_total*1000:.1f}ms  brain={t_brain_total*1000:.1f}ms  "
                f"action_send={t_action_total*1000:.1f}ms  mobs={len(alive_mobs)}"
            )



    async def send_message(self, message_type: str, payload: dict):
        """Sends a message to the server, handling serialization and connection status."""
        if self.websocket:
            # Ensure clientId is in the payload for server verification/assignment
            payload["clientId"] = self.client_id
            message = {"type": message_type, "payload": payload}
            try:
                await self.websocket.send(json.dumps(message))
                logger.debug(f"[{self.client_id}] Sent message type: {message_type}")
            except Exception as e:
                logger.error(f"[{self.client_id}] Failed to send message {message_type}: {e}")
        else:
            logger.warning(f"[{self.client_id}] WebSocket is not connected. Message type: {message_type} not sent.")

    async def send_move_mob(self, mob_id: str | int, x: int, y: int):
        """Sends a command to move a specific mob with integer coordinates."""
        logger.debug(f"[{self.client_id}] Moving mob {mob_id} to ({x}, {y})")
        await self.send_message("MOVE_MOB", {
            "mobId": str(mob_id), 
            "targetLocation": {"x": int(x), "y": int(y)}
        })


    async def send_request_world_state(self):
        """Requests the current world state from the server."""
        logger.debug(f"[{self.client_id}] Requesting world state.")
        await self.send_message("REQUEST_WORLD_STATE", {"clientId": self.client_id})

    async def run(self):
        """Main entry point for the client logic with auto-reconnect."""
        base_delay = 1
        max_delay = 30
        backoff_factor = 2
        delay = base_delay
        
        loop_task = asyncio.create_task(self.autonomous_loop())
        
        while not self.all_mobs_dead_event.is_set():
            if await self.connect():
                # Initial request to ensure mob is created and state is synced
                delay = base_delay
                await self.send_request_world_state()
                
                # Listen blocks until connection drops or all mobs die
                listen_task = asyncio.create_task(self.listen())
                death_wait_task = asyncio.create_task(self.all_mobs_dead_event.wait())
                
                # Wait for either connection to close or all mobs to die
                done, pending = await asyncio.wait(
                    [listen_task, death_wait_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                
                if self.all_mobs_dead_event.is_set():
                    logger.info(f"[{self.client_id}] Termination signal received: All mobs are dead.")
                    # Cancel listen task if it's still running
                    if not listen_task.done():
                        listen_task.cancel()
                    break
                else:
                    # Connection closed unexpectedly
                    logger.warning(f"[{self.client_id}] Connection lost. Reconnecting in {delay} seconds...")
                    await asyncio.sleep(delay)
                    delay = min(max_delay, delay * backoff_factor)
            else:
                logger.info(f"[{self.client_id}] Failed to connect. Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
                delay = min(max_delay, delay * backoff_factor)

        # Cleanup
        if self.websocket:
            await self.websocket.close()
        if not loop_task.done():
            loop_task.cancel()
        logger.info(f"[{self.client_id}] Client manager terminated.")


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
            logger.info("State has been updated. Triggering rendering update.")
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
            logger.warning(f"Server error [{code}]: {msg}")
        elif message_type == "HEX_CREATED":
            self._process_hex_created(payload)
        elif message_type == "LOOK_RESULT":
            self._process_look_result(payload)
        elif message_type == "TICK_COMPLETE":
            pass  # handled in listen() via tick_event
        elif message_type in ("MOB_MOVED", "GRASS_EATEN", "MOB_ATTACKED", "MOB_EATEN", "MOB_BRED"):
            pass  # informational broadcasts — handled in HexGenLifeClient.listen()
        else:
            logger.warning(f"Unknown message type received: {message_type}")

    def get_client_state(self) -> dict:
        """Retrieves the current state from the state manager."""
        return self.get_state()

    def _process_mob_update(self, mob_data: dict):
        """Processes a Mob Update message."""
        mob_id = mob_data.get("mobId") or mob_data.get("mob_id")
        if mob_id:
            self._state["mobs"][mob_id] = mob_data
            logger.debug(f"Updated state for mob {mob_id}")
    
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

        logger.debug(f"Processed world snapshot: {len(mobs)} mobs, {len(tiles)} tiles.")

    def _process_hex_created(self, payload: dict):
        hex_id = payload.get("hexId")
        tile_data = payload.get("tileData")
        if hex_id and tile_data:
            self._state["worldTiles"][hex_id] = tile_data
            loc = tile_data.get("location", {})
            cx = loc.get("centerX", "?")
            cy = loc.get("centerY", "?")
            logger.debug(f"HEX_CREATED: new tile {hex_id} at ({cx}, {cy})")

    def _process_look_result(self, payload: dict):
        """Process LOOK_RESULT — store visible tiles/mobs in state."""
        mob_self = payload.get("mob_self", {})
        mob_id = mob_self.get("mobId", "")
        if mob_id:
            self._state.setdefault("look_results", {})[mob_id] = payload
            logger.debug(
                f"LOOK_RESULT for {mob_id}: "
                f"{len(payload.get('tiles', []))} tiles, "
                f"{len(payload.get('mobs', []))} mobs visible"
            )

    def trigger_render_update(self):
        """Public method to be called by the main loop to signal the viewer to re-render."""
        logger.info("Client signaling viewer to re-render.")
        pass

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("client_ids", nargs="*", default=["client_1"])
    parser.add_argument("--mobs", nargs="*", help="Specific mob IDs to manage")
    parser.add_argument("--log-level", default=None,
                        choices=["debug", "info", "warning"],
                        help="Override log level (env LOG_LEVEL also accepted)")
    args = parser.parse_args()

    if args.log_level:
        _configure_logging(args.log_level)
    
    logger.info(f"Starting clients: {args.client_ids}, managing mobs: {args.mobs}")
    
    tasks = []
    for cid in args.client_ids:
        client = HexGenLifeClient(SERVER_URI, cid, mob_ids=args.mobs)
        tasks.append(client.run())
        
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Shutting down clients.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass