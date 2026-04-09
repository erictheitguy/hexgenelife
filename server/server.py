import asyncio
import json
import sqlite3
import datetime
import time
import websockets

class GameServer:
    def __init__(self, db_path="game_state.db"):
        self.db_path = db_path
        self.db_conn = None
        self.clients = set()
        self.action_queue = []
        self.tick_rate = 1.0  # 1 tick per second
        self._initialize_db()
        print("GameServer initialized. Database connection established.")

    def _initialize_db(self):
        """Initializes the SQLite database and necessary tables."""
        self.db_conn = sqlite3.connect(self.db_path)
        self.db_conn.row_factory = sqlite3.Row
        cursor = self.db_conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mobs (
                mob_id TEXT PRIMARY KEY,
                position TEXT,
                mob_type TEXT,
                generation INTEGER,
                timestamp REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mob_genes (
                mob_id TEXT,
                mobType TEXT,
                fitnessScore REAL,
                death REAL, -- Timestamp of death (NULL if not dead)
                expired BOOLEAN, -- Flag if gene has expired
                PRIMARY KEY (mob_id, mobType)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mob_health (
                mob_id TEXT PRIMARY KEY,
                hunger REAL,
                fat REAL,
                health REAL,
                age REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mob_brain (
                mob_id TEXT PRIMARY KEY,
                cognition_attributes TEXT
            )
        """)
        
        # Add HexTile mapping
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hex_tiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loc TEXT,
                centerXY TEXT,
                centerX INTEGER,
                centerY INTEGER,
                hexcp1 TEXT,
                hexcp2 TEXT,
                hexcp3 TEXT,
                hexcp4 TEXT,
                hexcp5 TEXT,
                hexcp6 TEXT,
                hexcp7 TEXT,
                Water REAL,
                Grass REAL,
                Created TEXT,
                Updated TEXT
            )
        """)
        
        # Populate at least 1 hexagon if empty
        cursor.execute("SELECT COUNT(*) FROM hex_tiles")
        if cursor.fetchone()[0] == 0:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute("""
                INSERT INTO hex_tiles (
                    loc, centerXY, centerX, centerY, 
                    hexcp1, hexcp2, hexcp3, hexcp4, hexcp5, hexcp6, hexcp7, 
                    Water, Grass, Created, Updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                json.dumps({"type": "Polygon", "coordinates": [[[0,0], [1,0], [1,1], [0,1], [-1,0], [-1,-1], [0,0]]]}),
                json.dumps([0, 0]), 0, 0,
                json.dumps([0,0]), json.dumps([1,0]), json.dumps([1,1]),
                json.dumps([0,1]), json.dumps([-1,0]), json.dumps([-1,-1]), json.dumps([0,0]),
                100.0, 100.0, now, now
            ))
            print("Populated default hex tile.")

        self.db_conn.commit()
        print(f"Database initialized at {self.db_path}")

    def _ensure_client_mob(self, client_id: str):
        """Phase 1 Requirement: Ensure client has an assigned mob."""
        if not self.db_conn: return
        cursor = self.db_conn.cursor()
        mob_id = f"mob_{client_id}"
        cursor.execute("SELECT 1 FROM mobs WHERE mob_id = ?", (mob_id,))
        if not cursor.fetchone():
            timestamp = self._get_current_timestamp()
            cursor.execute("""
                INSERT INTO mobs (mob_id, position, mob_type, generation, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (mob_id, json.dumps({"x":0, "y":0}), "default", 1, timestamp))
            cursor.execute("""
                INSERT INTO mob_genes (mob_id, mobType, fitnessScore, death, expired)
                VALUES (?, ?, ?, ?, ?)
            """, (mob_id, "default", 100.0, None, False))
            self.db_conn.commit()
            print(f"Created default mob {mob_id} for client {client_id}")

    def _validate_message(self, message: dict, command_type: str) -> bool:
        """Validates message structure against schema expectation."""
        required_fields = {
            "MOVE_MOB": ["mobId", "targetLocation"],
            "REQUEST_WORLD_STATE": ["clientId"]
        }
        
        # Convert potentially older field maps to test newer ones
        payload = message.get("payload", {})
        if not payload: 
            payload = message.get("data", {})
            
        if command_type in required_fields:
            for field in required_fields[command_type]:
                # check both camelCase and snake_case for backward compat while we migrate
                alt_field = "".join(['_'+c.lower() if c.isupper() else c for c in field]).lstrip('_')
                if field not in payload and alt_field not in payload:
                    print(f"Validation Error: Missing required field '{field}' for command type '{command_type}'.")
                    return False

        # Phase 1: Coordinate type validation for MOVE_MOB
        if command_type == "MOVE_MOB":
            target_loc = payload.get("targetLocation") or payload.get("target_location") or payload.get("new_pos")
            if target_loc:
                if not isinstance(target_loc, dict):
                    print(f"Validation Error: 'targetLocation' must be an object.")
                    return False
                x = target_loc.get("x")
                y = target_loc.get("y")
                # Strict integer check as per requirements
                if not isinstance(x, int) or not isinstance(y, int):
                    print(f"Validation Error: 'targetLocation' coordinates must be integers. Received x={type(x)}, y={type(y)}")
                    return False
        return True


    async def send_error(self, websocket, error_code: str, error_message: str):
        err_msg = json.dumps({
            "type": "ERROR",
            "payload": {
                "errorCode": error_code,
                "errorMessage": error_message
            }
        })
        try:
            await websocket.send(err_msg)
        except Exception:
            pass

    async def broadcast(self, message_type: str, payload: dict):
        if not self.clients:
            return
        msg = json.dumps({"type": message_type, "payload": payload})
        for client in self.clients:
            try:
                await client.send(msg)
            except Exception:
                pass

    async def ws_handler(self, websocket, path="/"):
        """Main connection handler."""
        self.clients.add(websocket)
        print(f"Client connected. Total clients: {len(self.clients)}")
        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                    command_type = message.get("type")
                    payload = message.get("payload", message.get("data", {}))
                    
                    # Ensure client mob logically based on ID
                    client_id = payload.get("clientId") or payload.get("client_id")
                    if client_id:
                        self._ensure_client_mob(client_id)

                    if not self._validate_message(message, command_type):
                        await self.send_error(websocket, "VALIDATION_FAILED", "Message schema validation failed.")
                        continue

                    self.action_queue.append({
                        "websocket": websocket,
                        "command_type": command_type,
                        "payload": payload
                    })
                except json.JSONDecodeError:
                    print("Error: Malformed JSON received.")
                    await self.send_error(websocket, "MALFORMED_JSON", "Invalid JSON payload.")
        except websockets.exceptions.ConnectionClosed:
            print("Client disconnected.")
        finally:
            self.clients.remove(websocket)

    async def _tick_loop(self):
        """Strict tick-based loop implementation."""
        print(f"Tick loop starting. Tick rate: {self.tick_rate}s")
        while True:
            await asyncio.sleep(self.tick_rate)
            if self.action_queue:
                queue_snapshot = self.action_queue[:]
                self.action_queue.clear()
                
                for action in queue_snapshot:
                    cmd = action["command_type"]
                    payload = action["payload"]
                    ws = action["websocket"]
                    
                    if cmd == "MOVE_MOB":
                        await self._handle_move_mob(payload)
                    elif cmd == "REQUEST_WORLD_STATE":
                        await self._handle_request_world_state(payload, ws)
                    else:
                        print(f"Unknown command queued: {cmd}")

            # Once all actions for the tick are done, broadcast TICK_COMPLETE
            await self.broadcast("TICK_COMPLETE", {"timestamp": self._get_current_timestamp()})

    async def _handle_move_mob(self, payload: dict):
        mob_id = payload.get("mobId") or payload.get("mob_id")
        target_loc = payload.get("targetLocation") or payload.get("new_pos")

        if not mob_id or not target_loc:
            return

        if not self._mob_exists(mob_id):
            print(f"Error: Mob {mob_id} does not exist.")
            return

        if not self.db_conn: return
        cursor = self.db_conn.cursor()
        timestamp = self._get_current_timestamp()
        
        cursor.execute("UPDATE mobs SET position = ?, timestamp = ? WHERE mob_id = ?", 
                       (json.dumps(target_loc), timestamp, mob_id))
        self.db_conn.commit()
        print(f"Updated mob {mob_id} position to {target_loc}.")
        
        await self.broadcast("MOB_UPDATE", {
            "mobId": mob_id,
            "health": {"hunger": 100, "fat": 0, "health": 100, "age": 0},
            "brain": {"updated": timestamp},
            "geneTraits": {"mobType": "default", "fitnessScore": 100, "death": None}
        })

    async def _handle_request_world_state(self, payload: dict, ws):
        client_id = payload.get("clientId") or payload.get("client_id")
        if not client_id: return
            
        if not self.db_conn: return
        cursor = self.db_conn.cursor()
        
        cursor.execute("SELECT * FROM mobs")
        mobs = [dict(row) for row in cursor.fetchall()]
            
        cursor.execute("SELECT * FROM hex_tiles")
        tiles = [dict(row) for row in cursor.fetchall()]

        try:
            await ws.send(json.dumps({
                "type": "WORLD_UPDATE",
                "payload": {
                    "mobs": mobs,
                    "tiles": tiles
                }
            }))
        except Exception as e:
            print(f"Failed to send world state: {e}")

    def _mob_exists(self, mob_id: str) -> bool:
        if not self.db_conn: return False
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT 1 FROM mobs WHERE mob_id = ?", (mob_id,))
        return cursor.fetchone() is not None

    def _get_current_timestamp(self) -> float:
        return time.time()

    def close(self):
        if self.db_conn:
            self.db_conn.close()
            print("Database connection closed.")

async def main():
    server = GameServer()
    # Run the tick loop explicitly in the background
    asyncio.create_task(server._tick_loop())
    
    # Start the WebSocket server using the new ws_handler
    async with websockets.serve(server.ws_handler, "localhost", 8765):
        print("WebSocket server started on ws://localhost:8765")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer shutting down.")
