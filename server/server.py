import asyncio
import json
import os
import sqlite3
import datetime
import time
import websockets
import math

# --- Phase 2 Constants & Hex Math ---
HEX_RADIUS = 5.0
HEX_CREATION_BROADCAST_RANGE = 100.0
DEFAULT_WATER = 5.0
DEFAULT_GRASS = 3.0

def flat_top_corner(center_x, center_y, size, i):
    angle_deg = 60 * i
    angle_rad = math.pi / 180 * angle_deg
    return [center_x + size * math.cos(angle_rad), center_y + size * math.sin(angle_rad)]

def get_hex_corners(center_x, center_y, size):
    corners = []
    for i in range(6):
        corners.append(flat_top_corner(center_x, center_y, size, i))
    corners.append(corners[0]) # close polygon
    return corners

def pixel_to_axial_flat_top(x, y, size):
    q = (2.0/3.0 * x) / size
    r = (-1.0/3.0 * x + math.sqrt(3)/3.0 * y) / size
    # axial rounding
    frac_q, frac_r = q, r
    frac_s = -frac_q - frac_r
    q = round(frac_q)
    r = round(frac_r)
    s = round(frac_s)
    q_diff = abs(q - frac_q)
    r_diff = abs(r - frac_r)
    s_diff = abs(s - frac_s)
    if q_diff > r_diff and q_diff > s_diff:
        q = -r - s
    elif r_diff > s_diff:
        r = -q - s
    return q, r

def axial_to_pixel_flat_top(q, r, size):
    x = size * 3.0/2.0 * q
    y = size * math.sqrt(3) * (r + q/2.0)
    return x, y

def point_in_polygon(x, y, polygon):
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if min(p1y, p2y) < y <= max(p1y, p2y):
            if x <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside
# ------------------------------------

# Default DB lives next to server.py so the path is stable regardless of CWD
_DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_state.db")

# Maximum actions a single client may queue per tick.
MAX_ACTIONS_PER_TICK = 3


class GameServer:
    def __init__(self, db_path=_DEFAULT_DB):
        self.db_path = db_path
        self.db_conn = None
        self.clients = set()
        self.action_queue = []          # list of {websocket, command_type, payload}
        self.tick_rate = 1.0            # seconds per tick
        self._client_action_counts = {}  # {websocket: int}  — reset each tick
        self._ws_to_mob = {}             # {websocket: mob_id}
        self._initialize_db()
        print("GameServer initialized. Database connection established.")

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    def _initialize_db(self):
        """Initialises the SQLite database and all required tables."""
        self.db_conn = sqlite3.connect(self.db_path)
        self.db_conn.row_factory = sqlite3.Row
        cursor = self.db_conn.cursor()

        # ---- mobs --------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mobs (
                mob_id TEXT PRIMARY KEY,
                position TEXT,
                mob_type TEXT,
                generation INTEGER,
                timestamp REAL
            )
        """)

        # ---- mob_genes ---------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mob_genes (
                mob_id TEXT,
                mobType TEXT,
                fitnessScore REAL,
                death REAL,          -- Timestamp of death (NULL if not dead)
                expired BOOLEAN,     -- Flag if gene has expired
                PRIMARY KEY (mob_id, mobType)
            )
        """)

        # ---- mob_health --------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mob_health (
                mob_id TEXT PRIMARY KEY,
                hunger REAL,
                fat REAL,
                health REAL,
                age REAL
            )
        """)

        # ---- mob_brain ---------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mob_brain (
                mob_id TEXT PRIMARY KEY,
                cognition_attributes TEXT
            )
        """)

        # ---- hex_tiles ---------------------------------------------------
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

        # ---- interaction_history (Gap #1) --------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interaction_history (
                interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                mob_a_id TEXT NOT NULL,
                mob_b_id TEXT,              -- NULL for single-mob events
                interaction_type TEXT NOT NULL, -- 'BREEDING' | 'ATTACK' | 'CONSUMPTION'
                timestamp REAL NOT NULL,
                details TEXT,               -- JSON blob with event-specific data
                outcome TEXT NOT NULL       -- 'SUCCESS' | 'FAILURE' | 'PARTIAL'
            )
        """)

        # ---- Seed at least 1 hex tile ------------------------------------
        cursor.execute("SELECT COUNT(*) FROM hex_tiles")
        if cursor.fetchone()[0] == 0:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cx, cy = 0.0, 0.0
            corners = get_hex_corners(cx, cy, HEX_RADIUS)
            loc_json = json.dumps({"type": "Polygon", "coordinates": [corners]})
            cx_y_json = json.dumps([cx, cy])
            
            cursor.execute("""
                INSERT INTO hex_tiles (
                    loc, centerXY, centerX, centerY,
                    hexcp1, hexcp2, hexcp3, hexcp4, hexcp5, hexcp6, hexcp7,
                    Water, Grass, Created, Updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                loc_json, cx_y_json, cx, cy,
                json.dumps(corners[0]), json.dumps(corners[1]), json.dumps(corners[2]),
                json.dumps(corners[3]), json.dumps(corners[4]), json.dumps(corners[5]), json.dumps(corners[6]),
                100.0, 100.0, now, now,
            ))
            print("Populated default hex tile.")

        self.db_conn.commit()
        print(f"Database initialized at {self.db_path}")

    # ------------------------------------------------------------------
    # Mob helpers
    # ------------------------------------------------------------------
    def _ensure_client_mob(self, client_id: str):
        """Ensure a mob + all sub-table rows exist for this client (Gap #2)."""
        if not self.db_conn:
            return
        cursor = self.db_conn.cursor()
        mob_id = f"mob_{client_id}"

        cursor.execute("SELECT 1 FROM mobs WHERE mob_id = ?", (mob_id,))
        if cursor.fetchone():
            return  # already exists

        timestamp = self._get_current_timestamp()

        cursor.execute("""
            INSERT INTO mobs (mob_id, position, mob_type, generation, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (mob_id, json.dumps({"x": 0, "y": 0}), "default", 1, timestamp))

        cursor.execute("""
            INSERT INTO mob_genes (mob_id, mobType, fitnessScore, death, expired)
            VALUES (?, ?, ?, ?, ?)
        """, (mob_id, "default", 100.0, None, False))

        # Gap #2 — insert into mob_health
        cursor.execute("""
            INSERT INTO mob_health (mob_id, hunger, fat, health, age)
            VALUES (?, ?, ?, ?, ?)
        """, (mob_id, 0.0, 0.0, 100.0, 0.0))

        # Gap #2 — insert into mob_brain
        cursor.execute("""
            INSERT INTO mob_brain (mob_id, cognition_attributes)
            VALUES (?, ?)
        """, (mob_id, json.dumps({})))

        self.db_conn.commit()
        print(f"Created mob {mob_id} (all tables) for client {client_id}")

    def _mob_exists(self, mob_id: str) -> bool:
        if not self.db_conn:
            return False
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT 1 FROM mobs WHERE mob_id = ?", (mob_id,))
        return cursor.fetchone() is not None

    def _get_mob_health(self, mob_id: str) -> dict:
        """Read real health values from DB (Gap #3)."""
        if not self.db_conn:
            return {"hunger": 0.0, "fat": 0.0, "health": 0.0, "age": 0.0}
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT hunger, fat, health, age FROM mob_health WHERE mob_id = ?",
            (mob_id,)
        )
        row = cursor.fetchone()
        if row:
            return {"hunger": row["hunger"], "fat": row["fat"],
                    "health": row["health"], "age": row["age"]}
        return {"hunger": 0.0, "fat": 0.0, "health": 0.0, "age": 0.0}

    def _get_current_timestamp(self) -> float:
        return time.time()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate_message(self, message: dict, command_type: str) -> bool:
        """Validates message structure against schema rules."""
        required_fields = {
            "MOVE_MOB": ["mobId", "targetLocation"],
            "REQUEST_WORLD_STATE": ["clientId"],
        }

        payload = message.get("payload", message.get("data", {}))

        if command_type in required_fields:
            for field in required_fields[command_type]:
                alt_field = "".join(
                    ["_" + c.lower() if c.isupper() else c for c in field]
                ).lstrip("_")
                if field not in payload and alt_field not in payload:
                    print(f"Validation Error: Missing '{field}' for '{command_type}'.")
                    return False

        # Strict integer coordinates for MOVE_MOB
        if command_type == "MOVE_MOB":
            target_loc = (
                payload.get("targetLocation")
                or payload.get("target_location")
                or payload.get("new_pos")
            )
            if target_loc:
                if not isinstance(target_loc, dict):
                    print("Validation Error: 'targetLocation' must be an object.")
                    return False
                x = target_loc.get("x")
                y = target_loc.get("y")
                if not isinstance(x, int) or not isinstance(y, int):
                    print(
                        f"Validation Error: Coordinates must be integers. "
                        f"Received x={type(x).__name__}, y={type(y).__name__}"
                    )
                    return False
        return True

    # ------------------------------------------------------------------
    # WebSocket helpers
    # ------------------------------------------------------------------
    async def send_error(self, websocket, error_code: str, error_message: str):
        err_msg = json.dumps({
            "type": "ERROR",
            "payload": {
                "errorCode": error_code,
                "errorMessage": error_message,
            },
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

    # ------------------------------------------------------------------
    # Connection handler
    # ------------------------------------------------------------------
    async def ws_handler(self, websocket, path="/"):
        """Main per-connection handler."""
        self.clients.add(websocket)
        self._client_action_counts[websocket] = 0
        print(f"Client connected. Total clients: {len(self.clients)}")
        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                    command_type = message.get("type")
                    payload = message.get("payload", message.get("data", {}))

                    # Resolve / create client mob
                    client_id = payload.get("clientId") or payload.get("client_id")
                    if client_id:
                        self._ensure_client_mob(client_id)
                        self._ws_to_mob[websocket] = f"mob_{client_id}"

                    if not self._validate_message(message, command_type):
                        await self.send_error(
                            websocket, "VALIDATION_FAILED",
                            "Message schema validation failed."
                        )
                        continue

                    # Gap #5 — per-tick action limit
                    count = self._client_action_counts.get(websocket, 0)
                    if count >= MAX_ACTIONS_PER_TICK:
                        await self.send_error(
                            websocket, "ACTION_LIMIT_EXCEEDED",
                            f"Maximum {MAX_ACTIONS_PER_TICK} actions allowed per tick."
                        )
                        continue

                    self._client_action_counts[websocket] = count + 1
                    self.action_queue.append({
                        "websocket": websocket,   # Gap #7 — carry ws reference
                        "command_type": command_type,
                        "payload": payload,
                    })

                except json.JSONDecodeError:
                    print("Error: Malformed JSON received.")
                    await self.send_error(
                        websocket, "MALFORMED_JSON", "Invalid JSON payload."
                    )
        except websockets.exceptions.ConnectionClosed:
            print("Client disconnected.")
        finally:
            self.clients.discard(websocket)
            self._client_action_counts.pop(websocket, None)
            self._ws_to_mob.pop(websocket, None)

    # ------------------------------------------------------------------
    # Tick loop
    # ------------------------------------------------------------------
    async def _tick_loop(self):
        """Strict tick-based loop — processes queued actions then broadcasts TICK_COMPLETE."""
        print(f"Tick loop starting. Tick rate: {self.tick_rate}s")
        while True:
            await asyncio.sleep(self.tick_rate)

            if self.action_queue:
                queue_snapshot = self.action_queue[:]
                self.action_queue.clear()

                for action in queue_snapshot:
                    cmd = action["command_type"]
                    payload = action["payload"]
                    ws = action["websocket"]   # Gap #7

                    if cmd == "MOVE_MOB":
                        await self._handle_move_mob(payload, ws)
                    elif cmd == "REQUEST_WORLD_STATE":
                        await self._handle_request_world_state(payload, ws)
                    else:
                        print(f"Unknown command queued: {cmd}")

            # Reset per-client action counts for next tick (Gap #5)
            for ws in list(self._client_action_counts):
                self._client_action_counts[ws] = 0

            await self.broadcast("TICK_COMPLETE", {"timestamp": self._get_current_timestamp()})

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------
    async def _handle_move_mob(self, payload: dict, websocket):
        """Process MOVE_MOB — update DB position and broadcast real health (Gap #3, #7)."""
        mob_id = payload.get("mobId") or payload.get("mob_id")
        target_loc = payload.get("targetLocation") or payload.get("new_pos")

        if not mob_id or not target_loc:
            await self.send_error(websocket, "INVALID_PAYLOAD",
                                  "mobId and targetLocation are required.")
            return

        if not self._mob_exists(mob_id):
            print(f"Error: Mob {mob_id} does not exist.")
            await self.send_error(websocket, "MOB_NOT_FOUND",
                                  f"Mob '{mob_id}' does not exist.")  # Gap #7
            return

        if not self.db_conn:
            return

        target_x, target_y = target_loc.get("x", 0), target_loc.get("y", 0)

        cursor = self.db_conn.cursor()
        
        # --- Phase 2: Dynamic Hex Generation ---
        cursor.execute("SELECT hexcp1, hexcp2, hexcp3, hexcp4, hexcp5, hexcp6 FROM hex_tiles")
        tiles = cursor.fetchall()
        point_inside = False
        for tile in tiles:
            poly = [
                json.loads(tile["hexcp1"]), json.loads(tile["hexcp2"]), json.loads(tile["hexcp3"]),
                json.loads(tile["hexcp4"]), json.loads(tile["hexcp5"]), json.loads(tile["hexcp6"])
            ]
            if point_in_polygon(target_x, target_y, poly):
                point_inside = True
                break
                
        if not point_inside:
            await self._create_adjacent_hex(target_x, target_y)
        # ---------------------------------------

        timestamp = self._get_current_timestamp()
        cursor.execute(
            "UPDATE mobs SET position = ?, timestamp = ? WHERE mob_id = ?",
            (json.dumps(target_loc), timestamp, mob_id),
        )
        self.db_conn.commit()
        print(f"Updated mob {mob_id} position to {target_loc}.")

        # Gap #3 — read actual health from DB
        health = self._get_mob_health(mob_id)

        # Gap #11 — fetch gene traits for complete broadcast
        cursor.execute(
            "SELECT mobType, fitnessScore, death FROM mob_genes WHERE mob_id = ?",
            (mob_id,)
        )
        gene_row = cursor.fetchone()
        gene_traits = (
            {"mobType": gene_row["mobType"],
             "fitnessScore": gene_row["fitnessScore"],
             "death": gene_row["death"]}
            if gene_row else {"mobType": "default", "fitnessScore": 0, "death": None}
        )

        await self.broadcast("MOB_UPDATE", {
            "mobId": mob_id,
            "health": health,
            "brain": {"updated": timestamp},
            "geneTraits": gene_traits,
        })

    async def _handle_request_world_state(self, payload: dict, ws):
        """Send WORLD_UPDATE with schema-compliant structure (Gap #11)."""
        client_id = payload.get("clientId") or payload.get("client_id")
        if not client_id:
            return
        if not self.db_conn:
            return

        cursor = self.db_conn.cursor()

        cursor.execute("SELECT * FROM mobs")
        mobs = [dict(row) for row in cursor.fetchall()]

        # Map hex_tiles rows to the documented WORLD_UPDATE schema shape
        cursor.execute("SELECT * FROM hex_tiles")
        tiles = []
        for row in cursor.fetchall():
            r = dict(row)
            tiles.append({
                "hexId": str(r["id"]),
                "tileData": {
                    "location": {
                        "centerX": r["centerX"],
                        "centerY": r["centerY"],
                    },
                    "resources": {
                        "water": r["Water"],
                        "grass": r["Grass"],
                    },
                    "updated": r["Updated"],
                },
            })

        try:
            await ws.send(json.dumps({
                "type": "WORLD_UPDATE",
                "payload": {
                    "mobs": mobs,
                    "tiles": tiles,   # now matches websocket_messages.json schema
                },
            }))
        except Exception as e:
            print(f"Failed to send world state: {e}")

    async def _create_adjacent_hex(self, mob_x, mob_y):
        cursor = self.db_conn.cursor()
        
        # 1. Determine which Hex cell this is using flat-top axial math
        q, r = pixel_to_axial_flat_top(mob_x, mob_y, HEX_RADIUS)
        cx, cy = axial_to_pixel_flat_top(q, r, HEX_RADIUS)
        
        # Guard: check if this hex already exists (by center threshold)
        cursor.execute("SELECT id, centerX, centerY FROM hex_tiles")
        for tile in cursor.fetchall():
            if abs(tile["centerX"] - cx) < 0.1 and abs(tile["centerY"] - cy) < 0.1:
                return # Already exists
                
        # 2. Get existing neighbours
        neighbour_qs = [(q+1, r), (q+1, r-1), (q, r-1), (q-1, r), (q-1, r+1), (q, r+1)]
        neighbour_centers = [axial_to_pixel_flat_top(nq, nr, HEX_RADIUS) for nq, nr in neighbour_qs]
        
        water_sum = 0.0
        grass_sum = 0.0
        n_count = 0
        
        cursor.execute("SELECT Water, Grass, centerX, centerY FROM hex_tiles")
        all_tiles = cursor.fetchall()
        for tile in all_tiles:
            for nx, ny in neighbour_centers:
                if abs(tile["centerX"] - nx) < 0.1 and abs(tile["centerY"] - ny) < 0.1:
                    water_sum += tile["Water"]
                    grass_sum += tile["Grass"]
                    n_count += 1
                    break 
                    
        if n_count > 0:
            new_water = water_sum / n_count
            new_grass = grass_sum / n_count
        else:
            new_water = DEFAULT_WATER
            new_grass = DEFAULT_GRASS
            
        corners = get_hex_corners(cx, cy, HEX_RADIUS)
        loc_json = json.dumps({"type": "Polygon", "coordinates": [corners]})
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        cursor.execute("""
            INSERT INTO hex_tiles (
                loc, centerXY, centerX, centerY,
                hexcp1, hexcp2, hexcp3, hexcp4, hexcp5, hexcp6, hexcp7,
                Water, Grass, Created, Updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            loc_json, json.dumps([cx, cy]), cx, cy,
            json.dumps(corners[0]), json.dumps(corners[1]), json.dumps(corners[2]),
            json.dumps(corners[3]), json.dumps(corners[4]), json.dumps(corners[5]), json.dumps(corners[6]),
            new_water, new_grass, now, now,
        ))
        
        new_hex_id = cursor.lastrowid
        self.db_conn.commit()
        print(f"Created new hex tile {new_hex_id} at ({cx}, {cy})")
        
        # 3. Broadcast HEX_CREATED to mobs within RANGE=100
        cursor.execute("SELECT mob_id, position FROM mobs")
        targets = set()
        for mob in cursor.fetchall():
            pos = json.loads(mob["position"])
            mx, my = pos.get("x", 0), pos.get("y", 0)
            dist = math.sqrt((mx - cx)**2 + (my - cy)**2)
            if dist <= HEX_CREATION_BROADCAST_RANGE:
                targets.add(mob["mob_id"])
                
        payload = {
            "hexId": str(new_hex_id),
            "tileData": {
                "location": {
                    "centerX": cx,
                    "centerY": cy
                },
                "corners": {
                    "hexcp1": corners[0],
                    "hexcp2": corners[1],
                    "hexcp3": corners[2],
                    "hexcp4": corners[3],
                    "hexcp5": corners[4],
                    "hexcp6": corners[5],
                    "hexcp7": corners[6]
                },
                "resources": {
                    "water": new_water,
                    "grass": new_grass
                },
                "created": now
            }
        }
        
        msg = json.dumps({"type": "HEX_CREATED", "payload": payload})
        for ws in self.clients:
            associated_mob = self._ws_to_mob.get(ws)
            # If the WS has an active mob and it's within range, send
            if associated_mob in targets:
                try:
                    await ws.send(msg)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def close(self):
        if self.db_conn:
            self.db_conn.close()
            print("Database connection closed.")


async def main():
    server = GameServer()
    asyncio.create_task(server._tick_loop())

    async with websockets.serve(server.ws_handler, "localhost", 8765):
        print("WebSocket server started on ws://localhost:8765")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer shutting down.")
