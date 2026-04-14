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
        
        # Load Tiles
        cursor.execute("SELECT id, Water, Grass, centerX, centerY, Updated, hexcp1, hexcp2, hexcp3, hexcp4, hexcp5, hexcp6 FROM hex_tiles")
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
                    "centerX": row["centerX"],
                    "centerY": row["centerY"],
                    "updated": row["Updated"],
                    "polygon": poly
                })
            except Exception:
                pass
                
        # Load Mobs
        cursor.execute("""
            SELECT m.mob_id, m.position, m.mob_type, m.generation, m.species_id,
                   h.hunger, h.fat, h.health, h.age,
                   g.fitnessScore,
                   s.name as species_name
            FROM mobs m
            JOIN mob_health h ON m.mob_id = h.mob_id
            LEFT JOIN mob_genes g ON m.mob_id = g.mob_id
            LEFT JOIN species s ON m.species_id = s.species_id
            WHERE h.health > 0
        """)
        mobs = []
        for row in cursor.fetchall():
            try:
                pos = json.loads(row["position"])
                mobs.append({
                    "id": row["mob_id"],
                    "x": pos.get("x", 0),
                    "y": pos.get("y", 0),
                    "type": row["mob_type"],
                    "generation": row["generation"],
                    "species_id": row["species_id"],
                    "species_name": row["species_name"] or "Unknown",
                    "health": row["health"],
                    "hunger": row["hunger"],
                    "fat": row["fat"],
                    "age": row["age"],
                    "fitness": row["fitnessScore"]
                })
            except Exception:
                pass
                
        return {"tiles": tiles, "mobs": mobs}
        
    def close(self):
        self.conn.close()
