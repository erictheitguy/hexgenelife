import sqlite3
import json

class DBReader:
    def __init__(self, db_path):
        self.db_path = f"file:{db_path}?mode=ro"
        self.conn = sqlite3.connect(self.db_path, uri=True, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def get_world_state(self):
        """Returns dict containing 'tiles' and 'mobs'"""
        cursor = self.conn.cursor()
        
        # Load Tiles — handle both schemas (with and without Updated column)
        try:
            cursor.execute("SELECT id, Water, Grass, centerX, centerY, Updated, hexcp1, hexcp2, hexcp3, hexcp4, hexcp5, hexcp6 FROM hex_tiles")
            has_updated = True
        except Exception:
            cursor.execute("SELECT id, Water, Grass, centerX, centerY, hexcp1, hexcp2, hexcp3, hexcp4, hexcp5, hexcp6 FROM hex_tiles")
            has_updated = False

        tiles = []
        for row in cursor.fetchall():
            try:
                poly = [
                    json.loads(row["hexcp1"]), json.loads(row["hexcp2"]), json.loads(row["hexcp3"]),
                    json.loads(row["hexcp4"]), json.loads(row["hexcp5"]), json.loads(row["hexcp6"])
                ]
                tiles.append({
                    "id": row["id"],
                    "water": row["Water"],
                    "grass": row["Grass"],
                    "centerX": row["centerX"] if "centerX" in row.keys() else 0,
                    "centerY": row["centerY"] if "centerY" in row.keys() else 0,
                    "updated": row["Updated"] if has_updated else None,
                    "polygon": poly
                })
            except Exception:
                pass
                
        # Load Mobs — use a simpler query that works with minimal schemas
        try:
            cursor.execute("""
                SELECT m.mob_id, m.position, m.mob_type, m.generation, m.species_id, m.is_active,
                       h.hunger, h.fat, h.energy, h.health, h.age, h.life_stage,
                       g.fitnessScore,
                       s.name as species_name
                FROM mobs m
                JOIN mob_health h ON m.mob_id = h.mob_id
                LEFT JOIN mob_genes g ON m.mob_id = g.mob_id
                LEFT JOIN species s ON m.species_id = s.species_id
                WHERE h.health > 0
            """)
        except Exception:
            # Fallback for minimal test schemas
            cursor.execute("""
                SELECT m.mob_id, m.position, m.mob_type,
                       h.health
                FROM mobs m
                JOIN mob_health h ON m.mob_id = h.mob_id
                WHERE h.health > 0
            """)

        mobs = []
        for row in cursor.fetchall():
            try:
                pos = json.loads(row["position"])
                keys = row.keys()
                mobs.append({
                    "id": row["mob_id"],
                    "x": pos.get("x", 0),
                    "y": pos.get("y", 0),
                    "type": row["mob_type"],
                    "generation": row["generation"] if "generation" in keys else None,
                    "species_id": row["species_id"] if "species_id" in keys else None,
                    "species_name": row["species_name"] if "species_name" in keys else "Unknown",
                    "health": row["health"],
                    "hunger": row["hunger"] if "hunger" in keys else 0,
                    "fat": row["fat"] if "fat" in keys else 0,
                    "energy": row["energy"] if "energy" in keys else 0,
                    "life_stage": row["life_stage"] if "life_stage" in keys else "unknown",
                    "age": row["age"] if "age" in keys else 0,
                    "fitness": row["fitnessScore"] if "fitnessScore" in keys else 0,
                    "is_active": row["is_active"] if "is_active" in keys else 0,
                    "size": 1.0,  # default; overridden below if mob_physical available
                })
            except Exception:
                pass

        # Enrich mobs with size from mob_physical
        try:
            cursor.execute("SELECT mob_id, size FROM mob_physical")
            size_map = {row["mob_id"]: row["size"] for row in cursor.fetchall()}
            for mob in mobs:
                if mob["id"] in size_map:
                    mob["size"] = size_map[mob["id"]]
        except Exception:
            pass
                
        return {"tiles": tiles, "mobs": mobs}

    def get_server_tick(self) -> int:
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM server_state WHERE key = 'tick_num'")
            row = cursor.fetchone()
            return int(row["value"]) if row else 0
        except Exception:
            return 0

    def get_mob_lineage(self, mob_id, max_depth=4):
        """Return a BFS ancestry chain as a list of dicts, ordered by depth.

        Each entry: {mob_id, parent_a_id, parent_b_id, species_id, depth}.
        Returns None if mob_id has no family_tree record (founder mob).
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT parent_a_id, parent_b_id, species_id FROM family_tree WHERE mob_id = ?",
                (mob_id,)
            )
            if cursor.fetchone() is None:
                return None
        except Exception:
            return None

        visited: set = set()
        chain: list = []
        queue: list = [(mob_id, 0)]
        while queue:
            current_id, depth = queue.pop(0)
            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT parent_a_id, parent_b_id, species_id FROM family_tree WHERE mob_id = ?",
                    (current_id,)
                )
                row = cursor.fetchone()
            except Exception:
                row = None
            parent_a = row["parent_a_id"] if row else None
            parent_b = row["parent_b_id"] if row else None
            species = row["species_id"] if row else None
            chain.append({
                "mob_id": current_id,
                "parent_a_id": parent_a,
                "parent_b_id": parent_b,
                "species_id": species,
                "depth": depth,
            })
            if depth < max_depth:
                if parent_a:
                    queue.append((parent_a, depth + 1))
                if parent_b:
                    queue.append((parent_b, depth + 1))
        return chain

    def get_mob_brain(self, mob_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT decision_tree FROM mob_brain WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row["decision_tree"])
            except Exception:
                return None
        return None

    def get_brain_functions(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT function_name, description FROM brain_functions")
        funcs = []
        for row in cursor.fetchall():
            funcs.append({"name": row["function_name"], "description": row["description"]})
        return funcs
        
    def close(self):
        self.conn.close()
