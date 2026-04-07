"""
Shared database connection module for hexgenlife project using SQLite3.
This ensures a single SQLite connection and proper connection pooling.
"""
import sqlite3
import os

DB_NAME = "hexgenlife.db"

# Global database connection instance
_conn = None

def get_db_connection():
    """Returns the singleton SQLite connection."""
    global _conn
    if _conn is None:
        try:
            _conn = sqlite3.connect(DB_NAME)
            _conn.row_factory = sqlite3.Row  # Allows access to columns by name
            print(f"SQLite database connection established: {DB_NAME}")
            _initialize_schema()
        except sqlite3.Error as e:
            print(f"SQLite connection error: {e}")
            _conn = None
            raise
    return _conn

def _initialize_schema():
    """Creates all necessary tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- Hex Tiles Collection Schema ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hex_tiles (
        _id TEXT PRIMARY KEY,
        loc TEXT,
        centerX REAL,
        centerY REAL,
        centerXY TEXT,
        Water INTEGER,
        Grass INTEGER,
        Created TEXT,
        updated TEXT
    );
    """)

    # --- Hex Centers Collection Schema ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hex_tiles_center (
        centerX REAL,
        centerY REAL,
        centerXY TEXT,
        hex_id TEXT,
        PRIMARY KEY (centerX, centerY),
        FOREIGN KEY (hex_id) REFERENCES hex_tiles(_id)
    );
    """)

    # --- Mob Collection Schema (Simplified based on attachment) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mob_collection (
        mob_id TEXT PRIMARY KEY,
        mX REAL,
        mY REAL,
        mXY TEXT,
        mob_type TEXT,
        mob_herd INTEGER,
        age INTEGER,
        generation INTEGER,
        parent_ids TEXT,
        genome TEXT,
        actual_traits TEXT,
        fitness_score REAL,
        Created TEXT,
        Updated TEXT
    );
    """)

    # --- Mob Health Schema (Simplified based on MobSchema.md) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mob_health (
        mob_id TEXT PRIMARY KEY,
        Hunger REAL,
        Fat REAL,
        Health REAL,
        Age REAL,
        Updated TEXT,
        FOREIGN KEY (mob_id) REFERENCES mob_collection(mob_id)
    );
    """)

    conn.commit()
    print("Database schema initialized successfully.")

def get_hex_tiles():
    """Return hex_tiles table reference."""
    conn = get_db_connection()
    return conn.execute("SELECT * FROM hex_tiles").fetchall()

def get_hex_tiles_center():
    """Return hex_tiles_center table reference."""
    conn = get_db_connection()
    return conn.execute("SELECT * FROM hex_tiles_center").fetchall()

def get_grass_eater_collection():
    """Return grass_eater_collection table reference."""
    conn = get_db_connection()
    return conn.execute("SELECT * FROM mob_collection WHERE mob_type = 'grass_eater'").fetchall()

def close_connections():
    """Close the SQLite connection."""
    global _conn
    if _conn:
        _conn.close()
        _conn = None
        print("SQLite connection closed.")

def find_hex_tile(centerX, centerY):
    """Returns a single hex tile row based on center coordinates."""
    conn = get_db_connection()
    cursor = conn.execute(
        "SELECT * FROM hex_tiles WHERE centerX = ? AND centerY = ?",
        (centerX, centerY)
    )
    return cursor.fetchone()

def find_hex_tiles_in_bounds(x_min, x_max, y_min, y_max):
    """Returns a list of hex tile rows within the specified bounding box."""
    conn = get_db_connection()
    cursor = conn.execute(
        "SELECT * FROM hex_tiles WHERE centerX >= ? AND centerX <= ? AND centerY >= ? AND centerY <= ?",
        (x_min, x_max, y_min, y_max)
    )
    return cursor.fetchall()

def find_mob_by_id(mob_id):
    """Returns a single mob row by its ID."""
    conn = get_db_connection()
    cursor = conn.execute("SELECT * FROM mob_collection WHERE mob_id = ?", (mob_id,))
    return cursor.fetchone()

def count_all_hex_tiles():
    """Returns the total count of hex tiles in the database."""
    conn = get_db_connection()
    cursor = conn.execute("SELECT COUNT(*) FROM hex_tiles")
    return cursor.fetchone()[0]

def get_random_hex_tile(offset):
    """Returns a random hex tile by skipping a given offset."""
    conn = get_db_connection()
    cursor = conn.execute(
        "SELECT * FROM hex_tiles ORDER BY RANDOM() LIMIT 1 OFFSET ?",
        (offset,)
    )
    return cursor.fetchone()

def update_mob_values(mob_id, **kwargs):
    """Updates multiple mob fields using arithmetic operations (e.g., $inc simulation)."""
    conn = get_db_connection()
    set_clauses = []
    params = []
    for key, value in kwargs.items():
        if key in ['Hunger', 'Fat', 'Health']:
            # Simulate $inc logic for these fields
            set_clauses.append(f"{key} = {key} + {value}")
            params.append(value)
        elif key in ['Updated']:
            set_clauses.append(f"{key} = datetime('now')")
        else:
            # For other fields, assume direct set operation if needed, or handle as per specific logic
            set_clauses.append(f"{key} = ?", value)
            params.append(value)

    if not set_clauses:
        return None

    set_sql = ", ".join(set_clauses)
    params.append(mob_id)
    
    update_query = f"UPDATE mob_collection SET {set_sql} WHERE mob_id = ?"
    cursor = conn.execute(update_query, tuple(params))
    conn.commit()
    return cursor.rowcount > 0

def insert_hex_tile(data):
    """Inserts a new hex tile record and returns its new ID."""
    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO hex_tiles (loc, centerX, centerY, centerXY, Water, Grass, Created, updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (data['loc'], data['centerX'], data['centerY'], data['centerXY'], data['Water'], data['Grass'], data['Created'], data['updated'])
    )
    conn.commit()
    return cursor.lastrowid

def insert_mob(data):
    """Inserts a new mob record and returns its new ID."""
    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO mob_collection (mob_id, mX, mY, mXY, mob_type, mob_herd, age, generation, parent_ids, genome, actual_traits, fitness_score, Created, Updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data['mob_id'], data['mX'], data['mY'], data['mXY'], data['mob_type'], data['mob_herd'], data['age'], data['generation'], data['parent_ids'], data['genome'], data['actual_traits'], data['fitness_score'], data['Created'], data['Updated']
        )
    )
    conn.commit()
    return cursor.lastrowid
