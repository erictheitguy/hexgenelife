import sqlite3
import datetime
import json
import logging
from server.constants import HEX_RADIUS, get_hex_corners, pixel_to_axial_flat_top, axial_to_pixel_flat_top

logger = logging.getLogger("Server.Database")

class DatabaseInitializer:
    @staticmethod
    def initialize_db(db_conn: sqlite3.Connection):
        """Initialises the SQLite database and all required tables."""
        db_conn.row_factory = sqlite3.Row
        cursor = db_conn.cursor()

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
        
        try:
            cursor.execute("ALTER TABLE mobs ADD COLUMN species_id TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE mobs ADD COLUMN is_active BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        # ---- mob_genes ---------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mob_genes (
                mob_id TEXT,
                mobType TEXT,
                fitnessScore REAL,
                death REAL,
                expired BOOLEAN,
                PRIMARY KEY (mob_id, mobType)
            )
        """)

        # ---- species -----------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS species (
                species_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mean_traits TEXT,
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

        # ---- mob_health --------------------------------------------------
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

        # ---- mob_brain ---------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mob_brain (
                mob_id TEXT PRIMARY KEY,
                cognition_attributes TEXT,
                decision_tree TEXT,
                memory TEXT
            )
        """)

        # ---- mob_physical ------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mob_physical (
                mob_id TEXT PRIMARY KEY,
                size REAL DEFAULT 1.0,
                speed REAL DEFAULT 1.0,
                mass REAL DEFAULT 1.0,
                vision REAL DEFAULT 10.0,
                metabolism_active REAL DEFAULT 1.5,
                metabolism_resting REAL DEFAULT 0.5,
                diet_type REAL DEFAULT 0.0,
                attack_power REAL DEFAULT 1.0,
                defense REAL DEFAULT 1.0,
                camouflage REAL DEFAULT 0.5,
                graze_threshold REAL DEFAULT 5.0,
                wander_dist REAL DEFAULT 3.0,
                persistence REAL DEFAULT 5.0,
                aging_rate REAL DEFAULT 0.05
            )
        """)
        
        for col, col_type, default_val in [
            ("graze_threshold", "REAL", "5.0"),
            ("wander_dist", "REAL", "3.0"),
            ("persistence", "REAL", "5.0"),
            ("aging_rate", "REAL", "0.05"),
            ("herd", "REAL", "0.5"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE mob_physical ADD COLUMN {col} {col_type} DEFAULT {default_val}")
            except sqlite3.OperationalError:
                pass

        # ---- brain_functions ---------------------------------------------
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
            logger.info("Seeded starter brain functions.")

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
                Updated TEXT,
                q INTEGER,
                r INTEGER
            )
        """)

        for col in ["q", "r"]:
            try:
                cursor.execute(f"ALTER TABLE hex_tiles ADD COLUMN {col} INTEGER")
            except sqlite3.OperationalError:
                pass

        # Indexes for bounding-box LOOK queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hex_tiles_cx_cy ON hex_tiles (centerX, centerY)")

        # Generated columns for mob position so bounding-box queries can use an index.
        # SQLite generated columns require SQLite 3.31+.
        try:
            cursor.execute(
                "ALTER TABLE mobs ADD COLUMN pos_x REAL GENERATED ALWAYS AS "
                "(CAST(json_extract(position, '$.x') AS REAL)) VIRTUAL"
            )
        except sqlite3.OperationalError:
            pass  # already exists or SQLite too old
        try:
            cursor.execute(
                "ALTER TABLE mobs ADD COLUMN pos_y REAL GENERATED ALWAYS AS "
                "(CAST(json_extract(position, '$.y') AS REAL)) VIRTUAL"
            )
        except sqlite3.OperationalError:
            pass
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mobs_pos ON mobs (pos_x, pos_y)")

        cursor.execute("SELECT id, centerX, centerY FROM hex_tiles WHERE q IS NULL OR r IS NULL")
        missing = cursor.fetchall()
        if missing:
            updates = []
            for row in missing:
                t_q, t_r = pixel_to_axial_flat_top(row["centerX"], row["centerY"], HEX_RADIUS)
                updates.append((t_q, t_r, row["id"]))
            cursor.executemany("UPDATE hex_tiles SET q = ?, r = ? WHERE id = ?", updates)
            logger.info(f"Migrated {len(updates)} hex tiles with q, r coordinates.")

        # ---- server_state -----------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cursor.execute(
            "INSERT OR IGNORE INTO server_state (key, value) VALUES ('tick_num', '0')"
        )

        # ---- interaction_history --------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interaction_history (
                interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                mob_a_id TEXT NOT NULL,
                mob_b_id TEXT,
                interaction_type TEXT NOT NULL,
                timestamp REAL NOT NULL,
                details TEXT,
                outcome TEXT NOT NULL
            )
        """)

        # ---- Seed initial hex tiles (radius 5) ---------------------------
        cursor.execute("SELECT COUNT(*) FROM hex_tiles")
        if cursor.fetchone()[0] == 0:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            initial_tiles = []
            radius = 5
            for q in range(-radius, radius + 1):
                for r in range(max(-radius, -q - radius), min(radius, -q + radius) + 1):
                    cx, cy = axial_to_pixel_flat_top(q, r, HEX_RADIUS)
                    corners = get_hex_corners(cx, cy, HEX_RADIUS)
                    loc_json = json.dumps({"type": "Polygon", "coordinates": [corners]})
                    initial_tiles.append((
                        loc_json, json.dumps([cx, cy]), cx, cy,
                        json.dumps(corners[0]), json.dumps(corners[1]), json.dumps(corners[2]),
                        json.dumps(corners[3]), json.dumps(corners[4]), json.dumps(corners[5]), json.dumps(corners[6]),
                        100.0, 100.0, now, now, q, r
                    ))
            
            cursor.executemany("""
                INSERT INTO hex_tiles (
                    loc, centerXY, centerX, centerY,
                    hexcp1, hexcp2, hexcp3, hexcp4, hexcp5, hexcp6, hexcp7,
                    Water, Grass, Created, Updated, q, r
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, initial_tiles)
            logger.info(f"Populated {len(initial_tiles)} initial hex tiles (radius {radius}).")

        db_conn.commit()
