"""MobManager — creates and queries mob records in the SQLite database."""
import json
import logging
import random
import sqlite3
import time
import uuid

from server.constants import (DEFAULT_MOB_PHYSICAL, DEFAULT_MOB_HEALTH_EXT,
                              DEFAULT_DECISION_TREE, DEFAULT_PREDATOR_DECISION_TREE,
                              PREDATOR_PHYSICAL_OVERRIDES)

logger = logging.getLogger("Server.MobManager")


def _staggered_starter_age(max_age: float) -> tuple[float, str]:
    """Pick a random starter age in [0, 0.5 * max_age] with matching life_stage.

    Spawning every starter at age 0 produces a synchronized age cohort that
    all reaches old age together (~tick 1000-1100 in observed runs), causing
    a catastrophic population collapse independent of predation. Staggering
    ages gives the starter population a realistic age pyramid: a mix of
    juveniles and adults at spawn, so reproduction and senescence overlap
    continuously rather than as cohort events.

    Range capped at 50% of max_age so no starter spawns as a senior — old
    age emerges naturally as the simulation runs.
    """
    age = random.uniform(0.0, max_age * 0.5)
    frac = age / max_age if max_age > 0 else 0.0
    if frac < 0.05:
        stage = "baby"
    elif frac < 0.15:
        stage = "juvenile"
    else:
        stage = "adult"
    return age, stage


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

        # Founding predators must spawn CLUSTERED, in prey range. Two reasons:
        # (1) predators only eat by hunting, so a seed dropped on a random tile
        # far from the herd starves before it finds prey; (2) scattered founders
        # never meet a mate, so the population can't breed and dies out (run 32:
        # 4/5 founders starved, the lone survivor lived to old age with 0
        # offspring). So: the FIRST seed predator anchors next to a live prey;
        # every later seed anchors on an already-placed predator — all founders
        # end up together in a prey-dense spot, able to feed AND pair. Bred
        # children ignore this (breed_mobs overrides their position to a parent).
        pos = None
        if mob_type == "predator":
            anchor = None
            # Cluster on an existing predator if one is already placed. No
            # is_active filter: a just-seeded predator (is_active still 0) is a
            # valid clustering anchor as soon as its row exists.
            cursor.execute(
                "SELECT m.position FROM mobs m "
                "LEFT JOIN mob_genes g ON m.mob_id = g.mob_id "
                "WHERE m.mob_type = 'predator' "
                "  AND (g.death IS NULL OR g.death = 0) "
                "  AND m.position IS NOT NULL "
                "ORDER BY RANDOM() LIMIT 1"
            )
            arow = cursor.fetchone()
            if arow and arow["position"]:
                anchor = arow["position"]
            else:
                # First founder: anchor next to a live prey so the whole cluster
                # forms in the herd.
                cursor.execute(
                    "SELECT m.position FROM mobs m "
                    "LEFT JOIN mob_genes g ON m.mob_id = g.mob_id "
                    "WHERE m.mob_type = 'prey' AND m.is_active = 1 "
                    "  AND (g.death IS NULL OR g.death = 0) "
                    "ORDER BY RANDOM() LIMIT 1"
                )
                prow = cursor.fetchone()
                if prow and prow["position"]:
                    anchor = prow["position"]
            if anchor:
                try:
                    apos = json.loads(anchor)
                    pos = {"x": float(apos["x"]) + random.uniform(-3.0, 3.0),
                           "y": float(apos["y"]) + random.uniform(-3.0, 3.0)}
                except (json.JSONDecodeError, TypeError, KeyError):
                    pos = None

        if pos is None:
            # Default (all prey, and predators when no live prey exist yet):
            # a random starting tile.
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
            (mob_id, mob_type, 0.0, None, False),
        )

        # mob_health — starters get a staggered age so the initial population
        # has a mixed age pyramid rather than a synchronized cohort. Bred
        # children are still created via ensure_client_mob but breed_mobs
        # then UPDATEs them back to age=0, life_stage='baby' so newborns
        # remain unaffected by this stagger.
        h = DEFAULT_MOB_HEALTH_EXT
        init_age, init_stage = _staggered_starter_age(h["max_age"])
        cursor.execute(
            """INSERT OR IGNORE INTO mob_health
               (mob_id, hunger, fat, health, age, energy, life_stage, birth_tick, max_age)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mob_id, 0.0, 0.0, 100.0, init_age,
             h["energy"], init_stage, h["birth_tick"], h["max_age"]),
        )
        if mob_type == "predator":
            cursor.execute(
                "UPDATE mob_health SET fat = 15.0, energy = 55.0 WHERE mob_id = ?",
                (mob_id,),
            )

        # mob_physical
        phys = dict(DEFAULT_MOB_PHYSICAL)
        if mob_type == "predator":
            phys.update(PREDATOR_PHYSICAL_OVERRIDES)
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
        brain_tree = DEFAULT_PREDATOR_DECISION_TREE if mob_type == "predator" else DEFAULT_DECISION_TREE
        cursor.execute(
            """INSERT OR IGNORE INTO mob_brain (mob_id, cognition_attributes, decision_tree, memory)
               VALUES (?, ?, ?, ?)""",
            (mob_id, json.dumps({}), json.dumps(brain_tree), json.dumps({})),
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
