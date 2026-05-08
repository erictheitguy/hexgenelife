"""MobManager — creates and queries mob records in the SQLite database."""
import json
import logging
import random
import sqlite3
import time
import uuid

from server.constants import DEFAULT_MOB_PHYSICAL, DEFAULT_MOB_HEALTH_EXT, DEFAULT_DECISION_TREE

logger = logging.getLogger("Server.MobManager")


class MobManager:
    def __init__(self, db_conn: sqlite3.Connection):
        self.db_conn = db_conn

    # ------------------------------------------------------------------
    # Existence / lookup
    # ------------------------------------------------------------------

    def mob_exists(self, mob_id: str) -> bool:
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT 1 FROM mobs WHERE mob_id = ?", (mob_id,))
        return cursor.fetchone() is not None

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def ensure_client_mob(
        self,
        client_id: str,
        mob_type: str = "prey",
        physical_overrides: dict | None = None,
    ) -> str:
        """Create a mob for *client_id* if it doesn't exist. Returns mob_id."""
        mob_id = f"mob_{client_id}"
        if self.mob_exists(mob_id):
            return mob_id

        cursor = self.db_conn.cursor()

        # Pick a random starting tile
        cursor.execute("SELECT centerX, centerY FROM hex_tiles ORDER BY RANDOM() LIMIT 1")
        row = cursor.fetchone()
        if row:
            pos = {"x": float(row["centerX"]), "y": float(row["centerY"])}
        else:
            pos = {"x": 0.0, "y": 0.0}

        now = time.time()
        species_id = f"species_{mob_type}_default"

        cursor.execute(
            """INSERT OR IGNORE INTO mobs
               (mob_id, position, mob_type, species_id, generation, timestamp, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (mob_id, json.dumps(pos), mob_type, species_id, 0, now, 0),
        )

        # mob_genes
        cursor.execute(
            """INSERT OR IGNORE INTO mob_genes (mob_id, mobType, fitnessScore, death, expired)
               VALUES (?, ?, ?, ?, ?)""",
            (mob_id, mob_type, 0.0, 0.0, False),
        )

        # mob_health
        h = DEFAULT_MOB_HEALTH_EXT
        cursor.execute(
            """INSERT OR IGNORE INTO mob_health
               (mob_id, hunger, fat, health, age, energy, life_stage, birth_tick, max_age)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mob_id, 0.0, 0.0, 100.0, 0.0,
             h["energy"], "baby", h["birth_tick"], h["max_age"]),
        )

        # mob_physical
        phys = dict(DEFAULT_MOB_PHYSICAL)
        if mob_type == "predator":
            phys.update({"diet_type": 1.0, "attack_power": 3.0, "speed": 1.5, "vision": 25.0})
        if physical_overrides:
            phys.update(physical_overrides)

        cursor.execute(
            """INSERT OR IGNORE INTO mob_physical
               (mob_id, size, speed, mass, vision, metabolism_active, metabolism_resting,
                diet_type, attack_power, defense, camouflage,
                graze_threshold, wander_dist, persistence, aging_rate, herd)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mob_id,
             phys["size"], phys["speed"], phys["mass"], phys["vision"],
             phys["metabolism_active"], phys["metabolism_resting"],
             phys["diet_type"], phys["attack_power"], phys["defense"], phys["camouflage"],
             phys["graze_threshold"], phys["wander_dist"], phys["persistence"],
             phys["aging_rate"], phys.get("herd", 0.5)),
        )

        # mob_brain
        cursor.execute(
            """INSERT OR IGNORE INTO mob_brain (mob_id, cognition_attributes, decision_tree, memory)
               VALUES (?, ?, ?, ?)""",
            (mob_id, json.dumps({}), json.dumps(DEFAULT_DECISION_TREE), json.dumps({})),
        )

        # species (ensure exists)
        cursor.execute(
            """INSERT OR IGNORE INTO species (species_id, name, mean_traits, member_count)
               VALUES (?, ?, ?, ?)""",
            (species_id, f"{mob_type.capitalize()} Default", json.dumps(phys), 0),
        )
        cursor.execute(
            "UPDATE species SET member_count = member_count + 1 WHERE species_id = ?",
            (species_id,),
        )

        # family_tree
        cursor.execute(
            """INSERT OR IGNORE INTO family_tree
               (mob_id, parent_a_id, parent_b_id, species_id, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (mob_id, None, None, species_id, now),
        )

        self.db_conn.commit()
        logger.info(f"Created mob {mob_id} (type={mob_type})")
        return mob_id

    # ------------------------------------------------------------------
    # Getters
    # ------------------------------------------------------------------

    def get_mob_health(self, mob_id: str) -> dict:
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT * FROM mob_health WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        if row is None:
            return {}
        return dict(row)

    def get_mob_physical(self, mob_id: str) -> dict:
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT * FROM mob_physical WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        if row is None:
            return dict(DEFAULT_MOB_PHYSICAL)
        return dict(row)

    def get_mob_brain(self, mob_id: str) -> dict:
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT * FROM mob_brain WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        if row is None:
            return {"decision_tree": DEFAULT_DECISION_TREE, "memory": {}}
        d = dict(row)
        for key in ("cognition_attributes", "decision_tree", "memory"):
            if isinstance(d.get(key), str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    d[key] = {}
        return d

    def get_species_info(self, mob_id: str) -> dict:
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT species_id FROM mobs WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        if row is None or not row["species_id"]:
            return {}
        cursor.execute("SELECT * FROM species WHERE species_id = ?", (row["species_id"],))
        s = cursor.fetchone()
        if s is None:
            return {}
        d = dict(s)
        if isinstance(d.get("mean_traits"), str):
            try:
                d["mean_traits"] = json.loads(d["mean_traits"])
            except (json.JSONDecodeError, TypeError):
                d["mean_traits"] = {}
        return d

    def classify_mob(self, mob_id: str, parent_species_id: str | None = None) -> str:
        """Assign or return a species_id for mob_id. Simple implementation."""
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT mob_type, species_id FROM mobs WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        if row is None:
            return ""
        if row["species_id"]:
            return row["species_id"]

        mob_type = row["mob_type"] or "prey"
        species_id = parent_species_id or f"species_{mob_type}_default"
        cursor.execute(
            "UPDATE mobs SET species_id = ? WHERE mob_id = ?", (species_id, mob_id)
        )
        self.db_conn.commit()
        return species_id
