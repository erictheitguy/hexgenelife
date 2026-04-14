import asyncio
import json
import os
import sqlite3
import datetime
import time
import websockets
import math
import random

# --- Phase 2 Constants & Hex Math ---
HEX_RADIUS = 5.0
HEX_CREATION_BROADCAST_RANGE = 100.0
DEFAULT_WATER = 5.0
DEFAULT_GRASS = 3.0

# --- Phase 4.1 Mob defaults ---
DEFAULT_MOB_PHYSICAL = {
    "size": 1.0,
    "speed": 1.0,
    "mass": 1.0,
    "vision": 10.0,
    "metabolism_active": 1.0,
    "metabolism_resting": 0.2,
    "diet_type": 0.0,        # 0.0 = herbivore, 1.0 = carnivore
    "attack_power": 1.0,
    "defense": 1.0,
    "camouflage": 0.5,       # 0.0 = fully visible, 1.0 = fully hidden
}
DEFAULT_MOB_HEALTH_EXT = {
    "energy": 50.0,
    "life_stage": "adult",   # baby | juvenile | adult | senior
    "birth_tick": 0.0,
    "max_age": 10000.0,
}
# Default starter decision tree — simple eat-or-wander
DEFAULT_DECISION_TREE = {
    "root": "evaluate_state",
    "nodes": {
        "evaluate_state": {
            "function": "evaluate_state",
            "outputs": ["evaluate_hunger", "evaluate_movement"]
        },
        "evaluate_hunger": {
            "function": "evaluate_hunger",
            "outputs": ["action_eat", "evaluate_movement"]
        },
        "evaluate_movement": {
            "function": "evaluate_movement",
            "outputs": []
        },
        "action_eat": {
            "function": "action_eat",
            "outputs": []
        }
    }
}

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
        self._mob_last_move_dist = {}    # {mob_id: float} — Phase 4.2 movement tracking
        self._mobs_acted_this_tick = set() # Phase 4.3: track which mobs performed actions
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
                species_id TEXT,
                generation INTEGER,
                timestamp REAL
            )
        """)
        
        # Ensure species_id exists if table was already created
        try:
            cursor.execute("ALTER TABLE mobs ADD COLUMN species_id TEXT")
        except sqlite3.OperationalError:
            pass # column already exists

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

        # ---- species -----------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS species (
                species_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mean_traits TEXT,    -- JSON blob
                member_count INTEGER DEFAULT 0
            )
        """)

        # ---- family_tree -------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS family_tree (
                mob_id TEXT PRIMARY KEY,
                parent_a_id TEXT,
                parent_b_id TEXT,
                species_id TEXT,
                timestamp REAL
            )
        """)

        # ---- mob_health (extended Phase 4.1) ----------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mob_health (
                mob_id TEXT PRIMARY KEY,
                hunger REAL,
                fat REAL,
                health REAL,
                age REAL,
                energy REAL DEFAULT 50.0,
                life_stage TEXT DEFAULT 'adult',
                birth_tick REAL DEFAULT 0.0,
                max_age REAL DEFAULT 10000.0
            )
        """)

        # ---- mob_brain (extended Phase 4.1) ------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mob_brain (
                mob_id TEXT PRIMARY KEY,
                cognition_attributes TEXT,
                decision_tree TEXT,
                memory TEXT
            )
        """)

        # ---- mob_physical (Phase 4.1) ------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mob_physical (
                mob_id TEXT PRIMARY KEY,
                size REAL DEFAULT 1.0,
                speed REAL DEFAULT 1.0,
                mass REAL DEFAULT 1.0,
                vision REAL DEFAULT 10.0,
                metabolism_active REAL DEFAULT 1.0,
                metabolism_resting REAL DEFAULT 0.2,
                diet_type REAL DEFAULT 0.0,
                attack_power REAL DEFAULT 1.0,
                defense REAL DEFAULT 1.0,
                camouflage REAL DEFAULT 0.5
            )
        """)

        # ---- brain_functions (Phase 4.1) ---------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS brain_functions (
                function_id TEXT PRIMARY KEY,
                function_name TEXT NOT NULL,
                function_code TEXT NOT NULL,
                description TEXT,
                input_schema TEXT,
                output_schema TEXT,
                version INTEGER DEFAULT 1,
                created TEXT,
                updated TEXT
            )
        """)

        # Seed starter brain functions if table is empty
        cursor.execute("SELECT COUNT(*) FROM brain_functions")
        if cursor.fetchone()[0] == 0:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            starter_functions = [
                ("evaluate_state", "Evaluate State", "evaluate_state",
                 "Root node: builds input matrix from mob state (hunger, fat, energy, health).",
                 json.dumps({"inputs": ["hunger", "fat", "energy", "health"]}),
                 json.dumps({"output": "matrix"}), 1, now, now),
                ("evaluate_hunger", "Evaluate Hunger", "evaluate_hunger",
                 "Checks hunger/fat levels, routes to eat or continue.",
                 json.dumps({"inputs": ["matrix"]}),
                 json.dumps({"output": "matrix_or_action"}), 1, now, now),
                ("evaluate_danger", "Evaluate Danger", "evaluate_danger",
                 "Uses LOOK_RESULT to check for nearby predators.",
                 json.dumps({"inputs": ["matrix", "look_result"]}),
                 json.dumps({"output": "matrix_or_action"}), 1, now, now),
                ("evaluate_movement", "Evaluate Movement", "evaluate_movement",
                 "Decides direction to move (toward food, away from danger, or wander).",
                 json.dumps({"inputs": ["matrix", "memory"]}),
                 json.dumps({"output": "action"}), 1, now, now),
                ("action_eat", "Action Eat Grass", "action_eat",
                 "Emits EAT_GRASS command to the server.",
                 json.dumps({"inputs": ["matrix"]}),
                 json.dumps({"output": "server_command"}), 1, now, now),
                ("action_move", "Action Move", "action_move",
                 "Emits MOVE_MOB command with calculated target.",
                 json.dumps({"inputs": ["matrix", "memory"]}),
                 json.dumps({"output": "server_command"}), 1, now, now),
                ("action_look", "Action Look", "action_look",
                 "Emits LOOK command to observe surroundings.",
                 json.dumps({"inputs": []}),
                 json.dumps({"output": "server_command"}), 1, now, now),
            ]
            cursor.executemany("""
                INSERT INTO brain_functions
                    (function_id, function_name, function_code, description,
                     input_schema, output_schema, version, created, updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, starter_functions)
            print("Seeded starter brain functions.")

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
    def _ensure_client_mob(self, client_id: str, mob_type: str = "prey",
                           physical_overrides: dict | None = None):
        """Ensure a mob + all sub-table rows exist for this client.

        Phase 4.1: now also populates mob_physical and extended mob_health /
        mob_brain columns.  ``mob_type`` defaults to 'prey'; pass 'predator'
        to create a carnivore with adjusted defaults.
        """
        if not self.db_conn:
            return
        cursor = self.db_conn.cursor()
        mob_id = f"mob_{client_id}"

        cursor.execute("SELECT 1 FROM mobs WHERE mob_id = ?", (mob_id,))
        if cursor.fetchone():
            return  # already exists

        timestamp = self._get_current_timestamp()

        # --- Derive physical defaults based on mob_type ---
        phys = dict(DEFAULT_MOB_PHYSICAL)
        if mob_type == "predator":
            phys.update({
                "diet_type": 1.0,
                "speed": 1.5,
                "attack_power": 3.0,
                "defense": 1.5,
                "vision": 15.0,
                "metabolism_active": 1.5,
                "camouflage": 0.6,
            })
        elif mob_type == "prey":
            phys.update({
                "camouflage": 0.7,   # prey tend to be better at hiding
                "speed": 1.3,        # prey are fast to flee
                "defense": 1.2,
            })
        if physical_overrides:
            phys.update(physical_overrides)

        cursor.execute("""
            INSERT INTO mobs (mob_id, position, mob_type, generation, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (mob_id, json.dumps({"x": 0, "y": 0}), mob_type, 1, timestamp))

        cursor.execute("""
            INSERT INTO mob_genes (mob_id, mobType, fitnessScore, death, expired)
            VALUES (?, ?, ?, ?, ?)
        """, (mob_id, mob_type, 100.0, None, False))

        # mob_health — now includes Phase 4.1 extended columns
        health_ext = dict(DEFAULT_MOB_HEALTH_EXT)
        health_ext["birth_tick"] = timestamp
        cursor.execute("""
            INSERT INTO mob_health
                (mob_id, hunger, fat, health, age,
                 energy, life_stage, birth_tick, max_age)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (mob_id, 0.0, 10.0, 100.0, 0.0,
              health_ext["energy"], health_ext["life_stage"],
              health_ext["birth_tick"], health_ext["max_age"]))

        # mob_brain — now includes decision_tree and memory
        cursor.execute("""
            INSERT INTO mob_brain (mob_id, cognition_attributes, decision_tree, memory)
            VALUES (?, ?, ?, ?)
        """, (mob_id, json.dumps({}),
              json.dumps(DEFAULT_DECISION_TREE),
              json.dumps({})))

        # mob_physical (Phase 4.1)
        cursor.execute("""
            INSERT INTO mob_physical
                (mob_id, size, speed, mass, vision,
                 metabolism_active, metabolism_resting,
                 diet_type, attack_power, defense, camouflage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (mob_id, phys["size"], phys["speed"], phys["mass"],
              phys["vision"], phys["metabolism_active"],
              phys["metabolism_resting"], phys["diet_type"],
              phys["attack_power"], phys["defense"], phys["camouflage"]))

        self.db_conn.commit()
        print(f"Created mob {mob_id} (all tables, type={mob_type}) for client {client_id}")
        
        # Phase 4.10: Classify as founder species
        self._classify_mob(mob_id)

    def _mob_exists(self, mob_id: str) -> bool:
        if not self.db_conn:
            return False
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT 1 FROM mobs WHERE mob_id = ?", (mob_id,))
        return cursor.fetchone() is not None

    def _get_mob_health(self, mob_id: str) -> dict:
        """Read all health values from DB including Phase 4.1 extensions."""
        defaults = {"hunger": 0.0, "fat": 0.0, "health": 0.0, "age": 0.0,
                    "energy": 0.0, "life_stage": "adult",
                    "birth_tick": 0.0, "max_age": 10000.0}
        if not self.db_conn:
            return defaults
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT hunger, fat, health, age, energy, life_stage, birth_tick, max_age "
            "FROM mob_health WHERE mob_id = ?",
            (mob_id,)
        )
        row = cursor.fetchone()
        if row:
            return {"hunger": row["hunger"], "fat": row["fat"],
                    "health": row["health"], "age": row["age"],
                    "energy": row["energy"], "life_stage": row["life_stage"],
                    "birth_tick": row["birth_tick"], "max_age": row["max_age"]}
        return defaults

    def _get_mob_physical(self, mob_id: str) -> dict:
        """Read physical attributes from DB (Phase 4.1)."""
        defaults = dict(DEFAULT_MOB_PHYSICAL)
        if not self.db_conn:
            return defaults
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT size, speed, mass, vision, metabolism_active, "
            "metabolism_resting, diet_type, attack_power, defense, camouflage "
            "FROM mob_physical WHERE mob_id = ?",
            (mob_id,)
        )
        row = cursor.fetchone()
        if row:
            return {k: row[k] for k in defaults}
        return defaults

    def _get_current_timestamp(self) -> float:
        return time.time()

    # ------------------------------------------------------------------
    # Phase 4.10 — Taxonomy Logic
    # ------------------------------------------------------------------
    def _generate_latin_name(self, is_founder=False) -> str:
        prefixes = ["Velo", "Herbi", "Carni", "Aqua", "Terra", "Avia", "Grandis", "Parvus", "Ferox", "Mitis"]
        suffixes = ["saurus", "raptor", "vagus", "phagus", "don", "therium", "pteryx", "pus", "cola", "mimus"]
        
        name = random.choice(prefixes) + random.choice(suffixes)
        if is_founder:
            name = f"Primus {name}"
        return name

    def _classify_mob(self, mob_id: str, parent_species_id: str = None):
        """Classifies a mob into a species based on trait Z-score."""
        if not self.db_conn:
            return None
        cursor = self.db_conn.cursor()
        
        phys = self._get_mob_physical(mob_id)
        traits = ["vision", "camouflage", "size", "mass", "speed", "diet_type", 
                  "attack_power", "defense", "metabolism_active", "metabolism_resting"]
        
        current_trait_vector = {t: phys.get(t, 0) for t in traits}
        
        new_species = False
        if not parent_species_id:
            new_species = True
        else:
            cursor.execute("SELECT mean_traits FROM species WHERE species_id = ?", (parent_species_id,))
            row = cursor.fetchone()
            if not row:
                new_species = True
            else:
                mean_traits = json.loads(row["mean_traits"])
                dist_sq = 0
                for t in traits:
                    val = current_trait_vector[t]
                    mean = mean_traits.get(t, val)
                    # Use a fixed std_dev typical for our trait ranges (0.1)
                    diff = (val - mean) / 0.1
                    dist_sq += diff * diff
                
                dist = math.sqrt(dist_sq)
                if dist > 3.0: # SPECIES_THRESHOLD (lenient as per user request)
                    new_species = True
        
        if new_species:
            species_id = f"sp_{int(time.time()*1000)}_{random.randint(0,999)}"
            name = self._generate_latin_name(is_founder=(parent_species_id is None))
            cursor.execute("""
                INSERT INTO species (species_id, name, mean_traits, member_count)
                VALUES (?, ?, ?, ?)
            """, (species_id, name, json.dumps(current_trait_vector), 1))
        else:
            species_id = parent_species_id
            cursor.execute("SELECT mean_traits, member_count FROM species WHERE species_id = ?", (species_id,))
            row = cursor.fetchone()
            if row:
                mean_traits = json.loads(row["mean_traits"])
                count = row["member_count"]
                new_count = count + 1
                new_means = {t: (mean_traits[t] * count + current_trait_vector[t]) / new_count for t in traits}
                cursor.execute("""
                    UPDATE species SET mean_traits = ?, member_count = ? WHERE species_id = ?
                """, (json.dumps(new_means), new_count, species_id))
            
        cursor.execute("UPDATE mobs SET species_id = ? WHERE mob_id = ?", (species_id, mob_id))
        self.db_conn.commit()
        return species_id

    def _get_species_info(self, mob_id: str) -> dict:
        """Fetch species ID and name for a specific mob."""
        if not self.db_conn:
            return {}
        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT s.species_id, s.name 
            FROM species s
            JOIN mobs m ON m.species_id = s.species_id
            WHERE m.mob_id = ?
        """, (mob_id,))
        row = cursor.fetchone()
        if row:
            return {"speciesId": row["species_id"], "speciesName": row["name"]}
        return {}

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate_message(self, message: dict, command_type: str) -> bool:
        """Validates message structure against schema rules."""
        required_fields = {
            "MOVE_MOB": ["mobId", "targetLocation"],
            "REQUEST_WORLD_STATE": ["clientId"],
            "LOOK": ["mobId"],
            "EAT_GRASS": ["mobId"],
            "ATTACK_MOB": ["mobId", "targetId"],
            "EAT_MOB": ["mobId", "targetId"],
            "BREED": ["mobId", "targetId"],
            "REQUEST_BRAIN_FUNCTIONS": [],
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
                    elif cmd == "LOOK":
                        await self._handle_look(payload, ws)
                    elif cmd == "EAT_GRASS":
                        await self._handle_eat_grass(payload, ws)
                    elif cmd == "ATTACK_MOB":
                        await self._handle_attack_mob(payload, ws)
                    elif cmd == "EAT_MOB":
                        await self._handle_eat_mob(payload, ws)
                    elif cmd == "BREED":
                        await self._handle_breed(payload, ws)
                    elif cmd == "REQUEST_BRAIN_FUNCTIONS":
                        await self._handle_request_brain_functions(payload, ws)
                    else:
                        print(f"Unknown command queued: {cmd}")

            # Phase 4.3: Process metabolism for all mobs
            await self._process_metabolism()

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

        # Phase 4.3: Energy check
        health = self._get_mob_health(mob_id)
        phys = self._get_mob_physical(mob_id)
        target_x, target_y = target_loc.get("x", 0), target_loc.get("y", 0)
        
        # Calculate distance for energy cost
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT position FROM mobs WHERE mob_id = ?", (mob_id,))
        old_pos_json = cursor.fetchone()["position"]
        old_pos = json.loads(old_pos_json)
        dx = target_x - old_pos.get("x", 0)
        dy = target_y - old_pos.get("y", 0)
        dist = math.sqrt(dx*dx + dy*dy)
        
        energy_cost = phys["mass"] * dist * 0.1
        if health["energy"] < energy_cost:
            await self.send_error(websocket, "INSUFFICIENT_ENERGY", 
                                  f"Required: {energy_cost:.1f}, Current: {health['energy']:.1f}")
            return
            
        self._mobs_acted_this_tick.add(mob_id)
        
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

        # --- Phase 4.2: Track movement distance for visibility penalty ---
        cursor.execute("SELECT position FROM mobs WHERE mob_id = ?", (mob_id,))
        old_pos_row = cursor.fetchone()
        if old_pos_row:
            old_pos = json.loads(old_pos_row["position"])
            dx = target_x - old_pos.get("x", 0)
            dy = target_y - old_pos.get("y", 0)
            move_dist = math.sqrt(dx * dx + dy * dy)
            self._mob_last_move_dist[mob_id] = move_dist
        else:
            self._mob_last_move_dist[mob_id] = 0.0

        timestamp = self._get_current_timestamp()
        cursor.execute(
            "UPDATE mobs SET position = ?, timestamp = ? WHERE mob_id = ?",
            (json.dumps(target_loc), timestamp, mob_id),
        )
        self.db_conn.commit()
        print(f"Updated mob {mob_id} position to {target_loc}.")

        # Deduct energy
        cursor.execute("UPDATE mob_health SET energy = energy - ? WHERE mob_id = ?", (energy_cost, mob_id))
        self.db_conn.commit()

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

        physical = self._get_mob_physical(mob_id)

        await self.broadcast("MOB_UPDATE", {
            "mobId": mob_id,
            "health": health,
            "physical": physical,
            "species": self._get_species_info(mob_id),
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

        # Build enriched mob list with health + physical data (Phase 4.1)
        cursor.execute("SELECT * FROM mobs")
        raw_mobs = cursor.fetchall()
        mobs = []
        for m in raw_mobs:
            mob_dict = dict(m)
            mob_id = m["mob_id"]
            mob_dict["health"] = self._get_mob_health(mob_id)
            mob_dict["physical"] = self._get_mob_physical(mob_id)
            mob_dict["species"] = self._get_species_info(mob_id)
            mobs.append(mob_dict)

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

    # ------------------------------------------------------------------
    # Phase 4.2 — LOOK handler
    # ------------------------------------------------------------------
    async def _handle_look(self, payload: dict, websocket):
        """Process LOOK — return visible tiles and mobs based on vision/camouflage.

        Visibility formula for other mobs:
            detection_score = observer.vision
                              - target.camouflage * CAMOUFLAGE_WEIGHT
                              + target.recent_speed_penalty * SPEED_PENALTY_WEIGHT
                              + target.size * SIZE_VISIBILITY_WEIGHT
        If detection_score > DETECTION_THRESHOLD the target mob is visible.
        """
        CAMOUFLAGE_WEIGHT = 10.0
        SPEED_PENALTY_WEIGHT = 0.5
        SIZE_VISIBILITY_WEIGHT = 2.0
        DETECTION_THRESHOLD = 5.0

        mob_id = payload.get("mobId") or payload.get("mob_id")
        if not mob_id or not self._mob_exists(mob_id):
            await self.send_error(websocket, "MOB_NOT_FOUND",
                                  f"Mob '{mob_id}' does not exist.")
            return

        cursor = self.db_conn.cursor()

        # --- Observer state ---
        cursor.execute("SELECT position FROM mobs WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        obs_pos = json.loads(row["position"])
        obs_x, obs_y = obs_pos.get("x", 0), obs_pos.get("y", 0)

        obs_phys = self._get_mob_physical(mob_id)
        vision_range = obs_phys["vision"]

        # Phase 4.3: Energy check
        health_state = self._get_mob_health(mob_id)
        energy_cost = 1.0
        if health_state["energy"] < energy_cost:
            await self.send_error(websocket, "INSUFFICIENT_ENERGY", "LOOK requires 1 energy.")
            return
        
        self._mobs_acted_this_tick.add(mob_id)
        cursor.execute("UPDATE mob_health SET energy = energy - ? WHERE mob_id = ?", (energy_cost, mob_id))
        self.db_conn.commit()

        # --- Visible tiles ---
        cursor.execute("SELECT id, centerX, centerY, Water, Grass FROM hex_tiles")
        visible_tiles = []
        for tile in cursor.fetchall():
            dx = tile["centerX"] - obs_x
            dy = tile["centerY"] - obs_y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= vision_range:
                visible_tiles.append({
                    "hexId": str(tile["id"]),
                    "centerX": tile["centerX"],
                    "centerY": tile["centerY"],
                    "water": tile["Water"],
                    "grass": tile["Grass"],
                    "distance": round(dist, 2),
                })

        # --- Visible mobs ---
        cursor.execute("SELECT mob_id, position, mob_type FROM mobs")
        visible_mobs = []
        for m in cursor.fetchall():
            if m["mob_id"] == mob_id:
                continue  # don't list self
            m_pos = json.loads(m["position"])
            mx, my = m_pos.get("x", 0), m_pos.get("y", 0)
            dx = mx - obs_x
            dy = my - obs_y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > vision_range:
                continue  # out of range entirely

            # Visibility check
            t_phys = self._get_mob_physical(m["mob_id"])
            recent_move = self._mob_last_move_dist.get(m["mob_id"], 0.0)

            detection_score = (
                obs_phys["vision"]
                - t_phys["camouflage"] * CAMOUFLAGE_WEIGHT
                + recent_move * SPEED_PENALTY_WEIGHT
                + t_phys["size"] * SIZE_VISIBILITY_WEIGHT
            )

            if detection_score > DETECTION_THRESHOLD:
                # Check if target is alive
                cursor2 = self.db_conn.cursor()
                cursor2.execute(
                    "SELECT death FROM mob_genes WHERE mob_id = ?",
                    (m["mob_id"],)
                )
                gene_row = cursor2.fetchone()
                is_alive = gene_row is None or gene_row["death"] is None

                visible_mobs.append({
                    "mobId": m["mob_id"],
                    "position": m_pos,
                    "mob_type": m["mob_type"],
                    "size": t_phys["size"],
                    "distance": round(dist, 2),
                    "alive": is_alive,
                })

        # --- Self state summary ---
        mob_health = self._get_mob_health(mob_id)

        result = {
            "tiles": visible_tiles,
            "mobs": visible_mobs,
            "mob_self": {
                "mobId": mob_id,
                "position": obs_pos,
                "hunger": mob_health["hunger"],
                "fat": mob_health["fat"],
                "energy": mob_health["energy"],
                "health": mob_health["health"],
                "life_stage": mob_health["life_stage"],
            },
        }

        try:
            await websocket.send(json.dumps({
                "type": "LOOK_RESULT",
                "payload": result,
            }))
        except Exception as e:
            print(f"Failed to send LOOK_RESULT: {e}")

    # ------------------------------------------------------------------
    # Phase 4.3 — EAT_GRASS handler
    # ------------------------------------------------------------------
    async def _handle_eat_grass(self, payload: dict, websocket):
        """Process EAT_GRASS — mob eats grass from its current tile.

        Efficiency scales with diet_type spectrum:
            grass_nutrition = base_amount * (1.0 - diet_type * 0.7)
        Pure herbivore (0.0) gets 100% efficiency.
        Pure carnivore (1.0) gets only 30% efficiency.
        """
        BASE_GRASS_CONSUMED = 5.0  # how much grass is consumed from tile
        BASE_FAT_GAIN = 3.0       # base fat gained

        mob_id = payload.get("mobId") or payload.get("mob_id")
        if not mob_id or not self._mob_exists(mob_id):
            await self.send_error(websocket, "MOB_NOT_FOUND",
                                  f"Mob '{mob_id}' does not exist.")
            return

        cursor = self.db_conn.cursor()

        # Get mob position
        cursor.execute("SELECT position FROM mobs WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        mob_pos = json.loads(row["position"])
        mob_x, mob_y = mob_pos.get("x", 0), mob_pos.get("y", 0)

        # Find the tile the mob is standing on
        cursor.execute(
            "SELECT id, Water, Grass, hexcp1, hexcp2, hexcp3, hexcp4, hexcp5, hexcp6 "
            "FROM hex_tiles"
        )
        standing_tile = None
        for tile in cursor.fetchall():
            poly = [
                json.loads(tile["hexcp1"]), json.loads(tile["hexcp2"]),
                json.loads(tile["hexcp3"]), json.loads(tile["hexcp4"]),
                json.loads(tile["hexcp5"]), json.loads(tile["hexcp6"]),
            ]
            if point_in_polygon(mob_x, mob_y, poly):
                standing_tile = tile
                break

        if standing_tile is None:
            await self.send_error(websocket, "NO_TILE",
                                  "Mob is not standing on any tile.")
            return

        if standing_tile["Grass"] <= 0:
            await self.send_error(websocket, "NO_GRASS",
                                  "No grass available on this tile.")
            return

        # Calculate consumption
        phys = self._get_mob_physical(mob_id)
        
        # Phase 4.3: Energy check
        health = self._get_mob_health(mob_id)
        energy_cost = 2.0
        if health["energy"] < energy_cost:
            await self.send_error(websocket, "INSUFFICIENT_ENERGY", "EAT_GRASS requires 2 energy.")
            return
        
        diet_type = phys["diet_type"]  # 0.0 = herbivore, 1.0 = carnivore
        efficiency = 1.0 - diet_type * 0.7

        actual_consumed = min(BASE_GRASS_CONSUMED, standing_tile["Grass"])
        fat_gain = actual_consumed * (BASE_FAT_GAIN / BASE_GRASS_CONSUMED) * efficiency

        # Update tile grass
        new_grass = standing_tile["Grass"] - actual_consumed
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute(
            "UPDATE hex_tiles SET Grass = ?, Updated = ? WHERE id = ?",
            (new_grass, now, standing_tile["id"]),
        )

        # Update mob health — increase fat, decrease hunger, deduct energy
        health = self._get_mob_health(mob_id)
        new_fat = health["fat"] + fat_gain
        new_hunger = max(0.0, health["hunger"] - fat_gain * 2)
        new_energy = health["energy"] - energy_cost
        cursor.execute(
            "UPDATE mob_health SET fat = ?, hunger = ?, energy = ? WHERE mob_id = ?",
            (new_fat, new_hunger, new_energy, mob_id),
        )
        self.db_conn.commit()
        
        self._mobs_acted_this_tick.add(mob_id)

        print(f"Mob {mob_id} ate {actual_consumed:.1f} grass "
              f"(efficiency={efficiency:.1%}, fat+={fat_gain:.1f})")

        # Broadcast updated health
        updated_health = self._get_mob_health(mob_id)
        await self.broadcast("MOB_UPDATE", {
            "mobId": mob_id,
            "health": updated_health,
            "physical": phys,
            "brain": {"updated": self._get_current_timestamp()},
            "geneTraits": {},
        })

    # ------------------------------------------------------------------
    # Phase 4.6 — ATTACK_MOB handler
    # ------------------------------------------------------------------
    async def _handle_attack_mob(self, payload: dict, websocket):
        """Process ATTACK_MOB — attacker damages target mob.
        
        Formula: damage = (attacker.size * 10.0) / (target.size * 2.0)
        """
        mob_id = payload.get("mobId") or payload.get("mob_id")
        target_id = payload.get("targetId") or payload.get("target_id")
        
        if not self._mob_exists(mob_id) or not self._mob_exists(target_id):
            await self.send_error(websocket, "MOB_NOT_FOUND", "Attacker or target not found.")
            return

        # Distance check — must be close to attack
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT position FROM mobs WHERE mob_id = ?", (mob_id,))
        p1 = json.loads(cursor.fetchone()["position"])
        cursor.execute("SELECT position FROM mobs WHERE mob_id = ?", (target_id,))
        p2 = json.loads(cursor.fetchone()["position"])
        dist = math.sqrt((p1["x"]-p2["x"])**2 + (p1["y"]-p2["y"])**2)
        
        IF_DISTANCE = 3.0 # Attack range
        if dist > IF_DISTANCE:
            await self.send_error(websocket, "OUT_OF_RANGE", f"Target is too far ({dist:.1f} > {IF_DISTANCE})")
            return

        # Energy check
        health_att = self._get_mob_health(mob_id)
        energy_cost = 5.0
        if health_att["energy"] < energy_cost:
            await self.send_error(websocket, "INSUFFICIENT_ENERGY", "ATTACK_MOB requires 5 energy.")
            return

        # Calculate damage
        att_phys = self._get_mob_physical(mob_id)
        tar_phys = self._get_mob_physical(target_id)
        
        damage = (att_phys["size"] * 10.0) / (tar_phys["size"] * 2.0)
        damage = max(1.0, damage) # Minimum 1 damage
        
        # Apply damage
        cursor.execute("UPDATE mob_health SET health = health - ? WHERE mob_id = ?", (damage, target_id))
        cursor.execute("UPDATE mob_health SET energy = energy - ? WHERE mob_id = ?", (energy_cost, mob_id))
        self.db_conn.commit()
        
        self._mobs_acted_this_tick.add(mob_id)
        print(f"Mob {mob_id} attacked {target_id} for {damage:.1f} damage.")

        # Broadcast updates
        await self.broadcast("MOB_UPDATE", {
            "mobId": target_id,
            "health": self._get_mob_health(target_id),
            "physical": tar_phys,
            "brain": {"updated": self._get_current_timestamp()},
            "geneTraits": {},
        })
        await self.broadcast("MOB_UPDATE", {
            "mobId": mob_id,
            "health": self._get_mob_health(mob_id),
            "physical": att_phys,
            "brain": {"updated": self._get_current_timestamp()},
            "geneTraits": {},
        })

    # ------------------------------------------------------------------
    # Phase 4.7 — EAT_MOB handler
    # ------------------------------------------------------------------
    async def _handle_eat_mob(self, payload: dict, websocket):
        """Process EAT_MOB — carnivore consumes a dead mob.
        
        Efficiency scales with diet_type (1.0 = carnivore).
        """
        mob_id = payload.get("mobId") or payload.get("mob_id")
        target_id = payload.get("targetId") or payload.get("target_id")
        
        if not self._mob_exists(mob_id) or not self._mob_exists(target_id):
            await self.send_error(websocket, "MOB_NOT_FOUND", "Attacker or target not found.")
            return

        # Target must be dead
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT death FROM mob_genes WHERE mob_id = ?", (target_id,))
        gene_row = cursor.fetchone()
        if not gene_row or gene_row["death"] is None:
            await self.send_error(websocket, "TARGET_NOT_DEAD", "Can only eat dead mobs.")
            return

        # Position check
        cursor.execute("SELECT position FROM mobs WHERE mob_id = ?", (mob_id,))
        p1 = json.loads(cursor.fetchone()["position"])
        cursor.execute("SELECT position FROM mobs WHERE mob_id = ?", (target_id,))
        p2 = json.loads(cursor.fetchone()["position"])
        dist = math.sqrt((p1["x"]-p2["x"])**2 + (p1["y"]-p2["y"])**2)
        if dist > 3.0:
            await self.send_error(websocket, "OUT_OF_RANGE", "Carcass is too far.")
            return

        # Energy check
        health = self._get_mob_health(mob_id)
        energy_cost = 3.0
        if health["energy"] < energy_cost:
            await self.send_error(websocket, "INSUFFICIENT_ENERGY", "EAT_MOB requires 3 energy.")
            return

        # Calculate nutrition
        phys = self._get_mob_physical(mob_id)
        tar_phys = self._get_mob_physical(target_id)
        diet_type = phys["diet_type"] # 1.0 = carnivore
        efficiency = 0.3 + diet_type * 0.7 # Herbivores get 30% from meat, carnivores 100%
        
        fat_gain = tar_phys["size"] * 20.0 * efficiency
        
        # Update mob
        new_fat = health["fat"] + fat_gain
        new_hunger = max(0.0, health["hunger"] - fat_gain * 3)
        new_energy = health["energy"] - energy_cost
        
        cursor.execute(
            "UPDATE mob_health SET fat = ?, hunger = ?, energy = ? WHERE mob_id = ?",
            (new_fat, new_hunger, new_energy, mob_id),
        )
        # Remove the carcass? Or reduce its nutrition? For now just remove to keep simple.
        cursor.execute("DELETE FROM mobs WHERE mob_id = ?", (target_id,))
        cursor.execute("DELETE FROM mob_health WHERE mob_id = ?", (target_id,))
        cursor.execute("DELETE FROM mob_physical WHERE mob_id = ?", (target_id,))
        cursor.execute("DELETE FROM mob_brain WHERE mob_id = ?", (target_id,))
        cursor.execute("DELETE FROM mob_genes WHERE mob_id = ?", (target_id,))
        self.db_conn.commit()
        
        self._mobs_acted_this_tick.add(mob_id)
        print(f"Mob {mob_id} consumed carcass of {target_id} (fat+={fat_gain:.1f})")

        await self.broadcast("MOB_UPDATE", {
            "mobId": mob_id,
            "health": self._get_mob_health(mob_id),
            "physical": phys,
            "brain": {"updated": self._get_current_timestamp()},
            "geneTraits": {},
        })
        # Notify clients that carcass is gone
        await self.broadcast("MOB_DELETED", {"mobId": target_id})

    # ------------------------------------------------------------------
    # Phase 4.4 — REQUEST_BRAIN_FUNCTIONS handler
    # ------------------------------------------------------------------
    async def _handle_request_brain_functions(self, payload: dict, websocket):
        """Process REQUEST_BRAIN_FUNCTIONS — return all available brain functions from DB."""
        if not self.db_conn:
            return
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT * FROM brain_functions")
        rows = cursor.fetchall()
        
        functions = []
        for row in rows:
            functions.append({
                "function_id": row["function_id"],
                "function_name": row["function_name"],
                "description": row["description"],
                "input_schema": json.loads(row["input_schema"]) if row["input_schema"] else None,
                "output_schema": json.loads(row["output_schema"]) if row["output_schema"] else None,
                "version": row["version"],
            })
            
        try:
            await websocket.send(json.dumps({
                "type": "BRAIN_FUNCTIONS_LIST",
                "payload": {"functions": functions}
            }))
        except Exception as e:
            print(f"Failed to send BRAIN_FUNCTIONS_LIST: {e}")

    # ------------------------------------------------------------------
    # Phase 4.3 — Metabolism Processing
    # ------------------------------------------------------------------
    async def _process_metabolism(self):
        """Update hunger, energy, fat, and health for all mobs each tick."""
        if not self.db_conn:
            return
        cursor = self.db_conn.cursor()
        
        cursor.execute("SELECT mob_id FROM mobs")
        mobs = cursor.fetchall()
        
        now = self._get_current_timestamp()
        
        for row in mobs:
            mob_id = row["mob_id"]
            
            # Check if mob is alive
            cursor.execute("SELECT death FROM mob_genes WHERE mob_id = ?", (mob_id,))
            gene_row = cursor.fetchone()
            if gene_row and gene_row["death"] is not None:
                continue # Skip dead mobs
                
            health = self._get_mob_health(mob_id)
            phys = self._get_mob_physical(mob_id)
            
            new_health = health["health"] # Initialize new_health
            
            # 1. Base hunger increase
            new_hunger = health["hunger"] + 0.1
            
            # 1b. Phase 4.8 — Aging and Life Stages
            new_age = health["age"] + 1
            current_stage = health["life_stage"]
            new_stage = current_stage
            
            # Transition boundaries
            INFANT_LIMIT = 50
            ADULT_LIMIT = 500
            MAX_AGE = 1000
            
            if new_age < INFANT_LIMIT:
                new_stage = "infant"
            elif new_age < ADULT_LIMIT:
                new_stage = "adult"
            else:
                new_stage = "elder"
                
            # Growth for infants
            new_size = phys["size"]
            if new_stage == "infant":
                new_size = min(1.0, phys["size"] + 0.01) # grow size
                
            # Elder decay
            if new_stage == "elder":
                new_health -= 0.2 # Natural aging damage
            
            # Max age death
            if new_age > MAX_AGE:
                new_health = 0
            
            # --- Restoration of Fat -> Energy conversion logic ---
            # Rate depends on activity (Phase 4.3)
            acted = mob_id in self._mobs_acted_this_tick
            met_rate = phys["metabolism_active"] if acted else phys["metabolism_resting"]
            
            # Target energy burn to keep metabolism running
            # If energy is low, burn fat to replenish it
            fat_to_burn = 0.5 # Per tick baseline
            actual_fat_burned = min(health["fat"], fat_to_burn)
            energy_gained = actual_fat_burned * met_rate
            
            new_fat = health["fat"] - actual_fat_burned
            new_energy = health["energy"] + energy_gained
            
            # Cap energy at 100.0
            new_energy = min(new_energy, 100.0)
            
            # 3. Starvation branch
            if new_energy <= 0 and new_fat <= 0:
                new_health -= 1.0 # Starvation damage per tick
            
            # 4. Natural health regeneration if energy and fat are good
            if new_energy > 50 and new_fat > 10 and new_health < 100:
                new_health = min(100.0, new_health + 0.5)

            # 5. Death check
            if new_health <= 0:
                print(f"Mob {mob_id} has died of starvation/exhaustion/age.")
                cursor.execute("UPDATE mob_genes SET death = ? WHERE mob_id = ?", (now, mob_id))
            
            cursor.execute("""
                UPDATE mob_health 
                SET hunger = ?, fat = ?, energy = ?, health = ?, life_stage = ?, age = ?
                WHERE mob_id = ?
            """, (new_hunger, new_fat, new_energy, new_health, new_stage, new_age, mob_id))
            
            if new_size != phys["size"]:
                cursor.execute("UPDATE mob_physical SET size = ? WHERE mob_id = ?", (new_size, mob_id))
            
        self.db_conn.commit()
        self._mobs_acted_this_tick.clear()

    # ------------------------------------------------------------------
    # Phase 4.9 — BREED handler
    # ------------------------------------------------------------------
    async def _handle_breed(self, payload: dict, websocket):
        """Process BREED — two adult mobs create an infant offspring.
        
        Genetic crossover: offspring inherits average of parent traits + mutation.
        """
        mob_id = payload.get("mobId") or payload.get("mob_id")
        target_id = payload.get("targetId") or payload.get("target_id")
        
        if mob_id == target_id:
            return

        if not self._mob_exists(mob_id) or not self._mob_exists(target_id):
            await self.send_error(websocket, "MOB_NOT_FOUND", "Parents not found.")
            return

        h1 = self._get_mob_health(mob_id)
        h2 = self._get_mob_health(target_id)
        
        if h1["life_stage"] != "adult" or h2["life_stage"] != "adult":
            await self.send_error(websocket, "NOT_MATURE", "Both parents must be in adult stage.")
            return
            
        if h1["energy"] < 50 or h2["energy"] < 50:
            await self.send_error(websocket, "INSUFFICIENT_ENERGY", "Breeding requires 50 energy.")
            return

        # Distance check
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT position FROM mobs WHERE mob_id = ?", (mob_id,))
        p1 = json.loads(cursor.fetchone()["position"])
        cursor.execute("SELECT position FROM mobs WHERE mob_id = ?", (target_id,))
        p2 = json.loads(cursor.fetchone()["position"])
        dist = math.sqrt((p1["x"]-p2["x"])**2 + (p1["y"]-p2["y"])**2)
        if dist > 3.0:
            await self.send_error(websocket, "OUT_OF_RANGE", "Parents too far apart.")
            return

        # Deduct energy
        cursor.execute("UPDATE mob_health SET energy = energy - 50 WHERE mob_id = ?", (mob_id,))
        cursor.execute("UPDATE mob_health SET energy = energy - 50 WHERE mob_id = ?", (target_id,))
        
        # Inherit traits
        p1_phys = self._get_mob_physical(mob_id)
        p2_phys = self._get_mob_physical(target_id)
        
        cursor.execute("SELECT mob_type FROM mobs WHERE mob_id = ?", (mob_id,))
        p1_type = cursor.fetchone()["mob_type"]
        
        def crossover(a, b):
            mute = random.uniform(-0.1, 0.1)
            return max(0.01, (a + b) / 2.0 + mute)
            
        child_id = f"mob_child_{int(time.time()*1000)}"
        
        # Insert new mob
        now = self._get_current_timestamp()
        cursor.execute(
            "INSERT INTO mobs (mob_id, position, mob_type, timestamp) VALUES (?, ?, ?, ?)",
            (child_id, json.dumps(p1), p1_type, now)
        )
        cursor.execute(
            "INSERT INTO mob_health (mob_id, hunger, fat, energy, health, life_stage, age) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (child_id, 0.0, 5.0, 50.0, 100.0, "infant", 0)
        )
        cursor.execute(
            "INSERT INTO mob_physical (mob_id, vision, camouflage, size, mass, diet_type, metabolism_active, metabolism_resting) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (child_id, 
             crossover(p1_phys["vision"], p2_phys["vision"]),
             crossover(p1_phys["camouflage"], p2_phys["camouflage"]),
             0.1, # infant size
             crossover(p1_phys["mass"], p2_phys["mass"]),
             crossover(p1_phys["diet_type"], p2_phys["diet_type"]),
             crossover(p1_phys["metabolism_active"], p2_phys["metabolism_active"]),
             crossover(p1_phys["metabolism_resting"], p2_phys["metabolism_resting"])
            )
        )
        # Inherit brain (simple copy from p1 for now)
        cursor.execute("SELECT decision_tree, memory, cognition_attributes FROM mob_brain WHERE mob_id = ?", (mob_id,))
        brain_data = cursor.fetchone()
        cursor.execute(
            "INSERT INTO mob_brain (mob_id, decision_tree, memory, cognition_attributes) VALUES (?, ?, ?, ?)",
            (child_id, brain_data["decision_tree"], brain_data["memory"], brain_data["cognition_attributes"])
        )
        # Inherit genes (simple copy from p1)
        cursor.execute("SELECT mobType, fitnessScore FROM mob_genes WHERE mob_id = ?", (mob_id,))
        gene_data = cursor.fetchone()
        cursor.execute(
            "INSERT INTO mob_genes (mob_id, mobType, fitnessScore, death) VALUES (?, ?, ?, ?)",
            (child_id, gene_data["mobType"], gene_data["fitnessScore"], None)
        )
        
        self.db_conn.commit()
        print(f"Offspring {child_id} created between {mob_id} and {target_id}.")
        
        # Phase 4.10: Lineage & Classification
        cursor.execute("SELECT species_id FROM mobs WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        parent_species_id = row["species_id"] if row else None
        
        species_id = self._classify_mob(child_id, parent_species_id)
        
        cursor.execute("""
            INSERT INTO family_tree (mob_id, parent_a_id, parent_b_id, species_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (child_id, mob_id, target_id, species_id, now))
        self.db_conn.commit()
        
        # Broadcast new mob
        await self.broadcast("MOB_CREATED", {
            "mobId": child_id,
            "position": p1,
            "mob_type": p1_type,
            "health": self._get_mob_health(child_id),
            "physical": self._get_mob_physical(child_id),
            "species": self._get_species_info(child_id),
        })

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
