"""MobInteractions — handles all mob action commands and metabolism."""
import json
import logging
import math
import random
import sqlite3
import time
import uuid

from server.constants import (
    DEFAULT_MOB_PHYSICAL, DEFAULT_MOB_HEALTH_EXT, DEFAULT_DECISION_TREE,
    HEX_RADIUS, pixel_to_axial_flat_top,
)

logger = logging.getLogger("Server.MobInteractions")

# Grass consumed per eat action
GRASS_PER_EAT = 5.0
# Energy gained per eat action (herbivore)
ENERGY_PER_EAT = 10.0
# Attack damage per hit
BASE_ATTACK_DAMAGE = 10.0
# Energy gained from eating a mob
ENERGY_FROM_MOB = 30.0
# Hunger increase per tick
HUNGER_PER_TICK = 1.0
# Fat consumed per tick (resting metabolism) — kept for reference
FAT_PER_TICK = 0.5
# Starvation thresholds
STARVATION_TIER1 = 30.0   # hunger >= 30 → 2 damage
STARVATION_TIER2 = 40.0   # hunger > 40  → 3 damage
# Aging cost per unit of age increase
ENERGY_PER_AGE_UNIT = 1.0
# Age increase per tick (default, overridden by mob_physical.aging_rate)
DEFAULT_AGING_RATE = 0.05
# Breeding energy cost
BREED_ENERGY_COST = 20.0
# Minimum energy to breed
MIN_BREED_ENERGY = 40.0


class MobInteractions:
    def __init__(self, server, db_conn: sqlite3.Connection, mob_manager):
        self.server = server
        self.db_conn = db_conn
        self.mob_manager = mob_manager
        # Tracks last move distance per mob_id for camouflage detection
        self.mob_last_move_dist: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_mob_row(self, mob_id: str) -> dict | None:
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT * FROM mobs WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def _get_position(self, mob_id: str) -> dict | None:
        row = self._get_mob_row(mob_id)
        if row is None:
            return None
        pos = row.get("position")
        if isinstance(pos, str):
            try:
                return json.loads(pos)
            except (json.JSONDecodeError, TypeError):
                return None
        return pos

    def _set_position(self, mob_id: str, x: float, y: float):
        cursor = self.db_conn.cursor()
        cursor.execute(
            "UPDATE mobs SET position = ? WHERE mob_id = ?",
            (json.dumps({"x": x, "y": y}), mob_id),
        )
        self.db_conn.commit()

    def _nearest_tile(self, x: float, y: float) -> dict | None:
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT *, ((centerX - ?) * (centerX - ?) + (centerY - ?) * (centerY - ?)) AS dist2 "
            "FROM hex_tiles ORDER BY dist2 LIMIT 1",
            (x, x, y, y),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def _record_interaction(self, mob_a: str, mob_b: str | None,
                             itype: str, outcome: str, details: dict | None = None):
        cursor = self.db_conn.cursor()
        cursor.execute(
            """INSERT INTO interaction_history
               (mob_a_id, mob_b_id, interaction_type, timestamp, details, outcome)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (mob_a, mob_b, itype, time.time(),
             json.dumps(details or {}), outcome),
        )
        self.db_conn.commit()

    # ------------------------------------------------------------------
    # LOOK
    # ------------------------------------------------------------------

    async def handle_look(self, payload: dict, websocket) -> None:
        mob_id = payload.get("mobId")
        if not mob_id or not self.mob_manager.mob_exists(mob_id):
            await self.server.send_error(websocket, "MOB_NOT_FOUND",
                                         f"Mob {mob_id} not found.")
            return

        pos = self._get_position(mob_id)
        if pos is None:
            await self.server.send_error(websocket, "NO_POSITION",
                                         f"Mob {mob_id} has no position.")
            return

        phys = self.mob_manager.get_mob_physical(mob_id)
        vision = phys.get("vision", 20.0)
        ox, oy = pos["x"], pos["y"]

        # Tiles within vision
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT * FROM hex_tiles WHERE "
            "(centerX - ?) * (centerX - ?) + (centerY - ?) * (centerY - ?) <= ? * ?",
            (ox, ox, oy, oy, vision, vision),
        )
        tiles = []
        for row in cursor.fetchall():
            r = dict(row)
            tiles.append({
                "hexId": str(r["id"]),
                "centerX": r["centerX"],
                "centerY": r["centerY"],
                "grass": r["Grass"],
                "water": r["Water"],
                "distance": math.sqrt((r["centerX"] - ox) ** 2 + (r["centerY"] - oy) ** 2),
            })

        # Mobs within vision (excluding self)
        cursor.execute(
            "SELECT * FROM mobs WHERE mob_id != ? AND is_active = 1",
            (mob_id,),
        )
        visible_mobs = []
        for row in cursor.fetchall():
            m = dict(row)
            m_pos = m.get("position")
            if isinstance(m_pos, str):
                try:
                    m_pos = json.loads(m_pos)
                except (json.JSONDecodeError, TypeError):
                    continue
            if m_pos is None:
                continue
            dx = m_pos["x"] - ox
            dy = m_pos["y"] - oy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > vision:
                continue

            # Camouflage detection
            t_phys = self.mob_manager.get_mob_physical(m["mob_id"])
            camouflage = t_phys.get("camouflage", 0.5)
            size = t_phys.get("size", 1.0)
            last_move = self.mob_last_move_dist.get(m["mob_id"], 0.0)
            detection = vision - camouflage * 10.0 + last_move * 0.5 + size * 2.0
            if detection < dist:
                continue

            visible_mobs.append({
                "mobId": m["mob_id"],
                "mob_type": m.get("mob_type", "prey"),
                "position": m_pos,
                "distance": dist,
                "alive": True,
            })

        # mob_self
        health = self.mob_manager.get_mob_health(mob_id)
        mob_self = {
            "mobId": mob_id,
            "position": pos,
            "hunger": health.get("hunger", 0.0),
            "fat": health.get("fat", 0.0),
            "energy": health.get("energy", 50.0),
            "health": health.get("health", 100.0),
        }

        import websockets
        try:
            await websocket.send(json.dumps({
                "type": "LOOK_RESULT",
                "payload": {
                    "tiles": tiles,
                    "mobs": visible_mobs,
                    "mob_self": mob_self,
                },
            }))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # MOVE_MOB
    # ------------------------------------------------------------------

    async def handle_move_mob(self, payload: dict, websocket) -> None:
        mob_id = payload.get("mobId")
        target = payload.get("targetLocation", {})
        tx = float(target.get("x", 0))
        ty = float(target.get("y", 0))

        if not mob_id or not self.mob_manager.mob_exists(mob_id):
            await self.server.send_error(websocket, "MOB_NOT_FOUND",
                                         f"Mob {mob_id} not found.")
            return

        pos = self._get_position(mob_id) or {"x": 0.0, "y": 0.0}
        ox, oy = pos["x"], pos["y"]
        dx, dy = tx - ox, ty - oy
        dist = math.sqrt(dx * dx + dy * dy)

        phys = self.mob_manager.get_mob_physical(mob_id)
        speed = phys.get("speed", 1.0)

        if dist <= speed or dist == 0:
            nx, ny = tx, ty
        else:
            nx = ox + dx / dist * speed
            ny = oy + dy / dist * speed

        # Clamp to integer coords as required by validator
        nx, ny = round(nx), round(ny)
        move_dist = math.sqrt((nx - ox) ** 2 + (ny - oy) ** 2)
        self.mob_last_move_dist[mob_id] = move_dist

        self._set_position(mob_id, float(nx), float(ny))

        # Ensure hex tiles exist around new position
        q, r = pixel_to_axial_flat_top(nx, ny, HEX_RADIUS)
        await self.server.ensure_hex_layer(q, r, radius=2)

        # Broadcast move to nearby clients
        await self.server.broadcast("MOB_MOVED", {
            "mobId": mob_id,
            "position": {"x": nx, "y": ny},
        })

    # ------------------------------------------------------------------
    # EAT_GRASS
    # ------------------------------------------------------------------

    async def handle_eat_grass(self, payload: dict, websocket) -> None:
        mob_id = payload.get("mobId")
        if not mob_id or not self.mob_manager.mob_exists(mob_id):
            await self.server.send_error(websocket, "MOB_NOT_FOUND",
                                         f"Mob {mob_id} not found.")
            return

        pos = self._get_position(mob_id) or {"x": 0.0, "y": 0.0}
        tile = self._nearest_tile(pos["x"], pos["y"])
        if tile is None or tile["Grass"] <= 0:
            await self.server.send_error(websocket, "NO_GRASS",
                                         "No grass available at current tile.")
            return

        phys = self.mob_manager.get_mob_physical(mob_id)
        diet_type = phys.get("diet_type", 0.0)  # 0=herbivore, 1=carnivore
        efficiency = 1.0 - diet_type * 0.7      # carnivore gets 30% efficiency

        grass_consumed = min(GRASS_PER_EAT, tile["Grass"])
        energy_gain = ENERGY_PER_EAT * efficiency

        cursor = self.db_conn.cursor()
        cursor.execute("SELECT energy, fat FROM mob_health WHERE mob_id = ?", (mob_id,))
        h = cursor.fetchone()
        cur_energy = h["energy"] if h else 50.0
        cur_fat = h["fat"] if h else 0.0

        new_energy = cur_energy + energy_gain
        # Fat accumulates from overflow above 80 at 5:1 ratio (spec 2.3)
        fat_gain = 0.0
        if new_energy > 80.0:
            overflow = new_energy - 80.0
            fat_gain = overflow / 5.0
            new_energy = 80.0
        new_energy = min(100.0, new_energy)
        new_fat = min(100.0, cur_fat + fat_gain)
        cursor.execute(
            "UPDATE hex_tiles SET Grass = MAX(0, Grass - ?) WHERE id = ?",
            (grass_consumed, tile["id"]),
        )
        cursor.execute(
            "UPDATE mob_health SET energy = ?, fat = ? WHERE mob_id = ?",
            (new_energy, new_fat, mob_id),
        )
        self.db_conn.commit()

        self._record_interaction(mob_id, None, "EAT_GRASS", "SUCCESS",
                                  {"grass_consumed": grass_consumed, "energy_gain": energy_gain})

        await self.server.broadcast("GRASS_EATEN", {
            "mobId": mob_id,
            "tileId": str(tile["id"]),
            "grassRemaining": tile["Grass"] - grass_consumed,
        })

    # ------------------------------------------------------------------
    # ATTACK_MOB
    # ------------------------------------------------------------------

    async def handle_attack_mob(self, payload: dict, websocket) -> None:
        mob_id = payload.get("mobId")
        target_id = payload.get("targetId")

        if not mob_id or not self.mob_manager.mob_exists(mob_id):
            await self.server.send_error(websocket, "MOB_NOT_FOUND",
                                         f"Mob {mob_id} not found.")
            return
        if not target_id or not self.mob_manager.mob_exists(target_id):
            await self.server.send_error(websocket, "TARGET_NOT_FOUND",
                                         f"Target {target_id} not found.")
            return

        phys = self.mob_manager.get_mob_physical(mob_id)
        t_phys = self.mob_manager.get_mob_physical(target_id)
        attack = phys.get("attack_power", 1.0)
        defense = t_phys.get("defense", 1.0)
        damage = max(0.0, attack * BASE_ATTACK_DAMAGE - defense * 2.0)

        cursor = self.db_conn.cursor()
        cursor.execute(
            "UPDATE mob_health SET health = MAX(0, health - ?) WHERE mob_id = ?",
            (damage, target_id),
        )
        self.db_conn.commit()

        # Check if target died
        health = self.mob_manager.get_mob_health(target_id)
        if health.get("health", 1.0) <= 0:
            cursor.execute(
                "UPDATE mob_genes SET death = ? WHERE mob_id = ?",
                (time.time(), target_id),
            )
            self.db_conn.commit()

        self._record_interaction(mob_id, target_id, "ATTACK", "HIT",
                                  {"damage": damage})

        await self.server.broadcast("MOB_ATTACKED", {
            "attackerId": mob_id,
            "targetId": target_id,
            "damage": damage,
        })

    # ------------------------------------------------------------------
    # EAT_MOB
    # ------------------------------------------------------------------

    async def handle_eat_mob(self, payload: dict, websocket) -> None:
        mob_id = payload.get("mobId")
        target_id = payload.get("targetId")

        if not mob_id or not self.mob_manager.mob_exists(mob_id):
            await self.server.send_error(websocket, "MOB_NOT_FOUND",
                                         f"Mob {mob_id} not found.")
            return
        if not target_id or not self.mob_manager.mob_exists(target_id):
            await self.server.send_error(websocket, "TARGET_NOT_FOUND",
                                         f"Target {target_id} not found.")
            return

        # Target must be dead
        t_genes = self.db_conn.cursor()
        t_genes.execute("SELECT death FROM mob_genes WHERE mob_id = ?", (target_id,))
        row = t_genes.fetchone()
        if row is None or row["death"] is None:
            await self.server.send_error(websocket, "TARGET_ALIVE",
                                         "Cannot eat a living mob.")
            return

        cursor = self.db_conn.cursor()
        cursor.execute(
            "UPDATE mob_health SET energy = MIN(100.0, energy + ?), fat = MIN(100.0, fat + ?) "
            "WHERE mob_id = ?",
            (ENERGY_FROM_MOB, ENERGY_FROM_MOB * 0.5, mob_id),
        )
        # Remove consumed mob
        cursor.execute("DELETE FROM mobs WHERE mob_id = ?", (target_id,))
        self.db_conn.commit()

        self._record_interaction(mob_id, target_id, "EAT_MOB", "SUCCESS")

        await self.server.broadcast("MOB_EATEN", {
            "eaterId": mob_id,
            "targetId": target_id,
        })

    # ------------------------------------------------------------------
    # BREED
    # ------------------------------------------------------------------

    async def handle_breed(self, payload: dict, websocket) -> None:
        mob_id = payload.get("mobId")
        target_id = payload.get("targetId")

        if not mob_id or not self.mob_manager.mob_exists(mob_id):
            await self.server.send_error(websocket, "MOB_NOT_FOUND",
                                         f"Mob {mob_id} not found.")
            return
        if not target_id or not self.mob_manager.mob_exists(target_id):
            await self.server.send_error(websocket, "TARGET_NOT_FOUND",
                                         f"Target {target_id} not found.")
            return

        child_id = self.breed_mobs(mob_id, target_id)
        if child_id is None:
            await self.server.send_error(websocket, "BREED_FAILED",
                                         "Breeding conditions not met.")
            return

        await self.server.broadcast("MOB_BRED", {
            "parentAId": mob_id,
            "parentBId": target_id,
            "childId": child_id,
        })

    def breed_mobs(self, parent_a_id: str, parent_b_id: str) -> str | None:
        """Synchronous breeding logic. Returns child mob_id or None."""
        h_a = self.mob_manager.get_mob_health(parent_a_id)
        h_b = self.mob_manager.get_mob_health(parent_b_id)

        if h_a.get("energy", 0) < MIN_BREED_ENERGY:
            return None
        if h_b.get("energy", 0) < MIN_BREED_ENERGY:
            return None
        if h_a.get("life_stage", "adult") != "adult":
            return None
        if h_b.get("life_stage", "adult") != "adult":
            return None

        p_a = self.mob_manager.get_mob_physical(parent_a_id)
        p_b = self.mob_manager.get_mob_physical(parent_b_id)

        # Inherit physical traits as average + small mutation
        child_phys = {}
        for key in DEFAULT_MOB_PHYSICAL:
            va = p_a.get(key, DEFAULT_MOB_PHYSICAL[key])
            vb = p_b.get(key, DEFAULT_MOB_PHYSICAL[key])
            avg = (va + vb) / 2.0
            mutation = random.uniform(-0.1, 0.1) * avg
            child_phys[key] = max(0.01, avg + mutation)

        # Determine mob type from parent A
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT mob_type FROM mobs WHERE mob_id = ?", (parent_a_id,))
        row = cursor.fetchone()
        mob_type = row["mob_type"] if row else "prey"

        # Generate child ID
        child_client_id = f"child_{uuid.uuid4().hex[:8]}"
        child_mob_id = self.mob_manager.ensure_client_mob(
            child_client_id, mob_type=mob_type, physical_overrides=child_phys
        )

        # Set child as baby at parent A's position
        pos = self._get_position(parent_a_id) or {"x": 0.0, "y": 0.0}
        cursor.execute(
            "UPDATE mobs SET position = ? WHERE mob_id = ?",
            (json.dumps(pos), child_mob_id),
        )
        cursor.execute(
            "UPDATE mob_health SET life_stage = 'baby', age = 0.0 WHERE mob_id = ?",
            (child_mob_id,),
        )

        # Record family tree
        cursor.execute(
            "UPDATE family_tree SET parent_a_id = ?, parent_b_id = ? WHERE mob_id = ?",
            (parent_a_id, parent_b_id, child_mob_id),
        )

        # Deduct energy from parents
        cursor.execute(
            "UPDATE mob_health SET energy = MAX(0, energy - ?) WHERE mob_id IN (?, ?)",
            (BREED_ENERGY_COST, parent_a_id, parent_b_id),
        )
        self.db_conn.commit()

        self._record_interaction(parent_a_id, parent_b_id, "BREED", "SUCCESS",
                                  {"child_id": child_mob_id})
        return child_mob_id

    # ------------------------------------------------------------------
    # METABOLISM (called each tick)
    # ------------------------------------------------------------------

    async def process_metabolism(self) -> None:
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT m.mob_id, m.mob_type, h.hunger, h.fat, h.health, h.energy, "
            "h.age, h.life_stage, h.birth_tick, h.max_age, "
            "p.metabolism_resting, p.aging_rate "
            "FROM mobs m "
            "JOIN mob_health h ON m.mob_id = h.mob_id "
            "JOIN mob_physical p ON m.mob_id = p.mob_id "
            "LEFT JOIN mob_genes g ON m.mob_id = g.mob_id "
            "WHERE g.death IS NULL OR g.death = 0"
        )
        rows = cursor.fetchall()

        for row in rows:
            mob_id = row["mob_id"]
            hunger = row["hunger"]
            fat = row["fat"]
            health = row["health"]
            energy = row["energy"]
            age = row["age"]
            life_stage = row["life_stage"] or "adult"
            max_age = row["max_age"] or 10000.0
            metabolism_resting = row["metabolism_resting"] or 0.5
            aging_rate = row["aging_rate"] or DEFAULT_AGING_RATE

            # Aging
            new_age = age + aging_rate
            new_energy = max(0.0, energy - aging_rate)

            # Life stage transitions
            if life_stage == "baby" and new_age >= max_age * 0.05:
                life_stage = "juvenile"
            elif life_stage == "juvenile" and new_age >= max_age * 0.15:
                life_stage = "adult"
            elif life_stage == "adult" and new_age >= max_age * 0.75:
                life_stage = "senior"

            # Fat burns to energy at 1:1 (spec 2.2); fat suppresses hunger (spec 2.1)
            new_fat = fat
            if new_fat > 0:
                burn = min(new_fat, metabolism_resting)
                new_fat = max(0.0, new_fat - burn)
                new_energy = min(100.0, new_energy + burn)  # 1:1 conversion
                new_hunger = hunger  # fat suppresses hunger increment (spec 2.1)
            else:
                new_hunger = min(50.0, hunger + HUNGER_PER_TICK)

            # Starvation damage (spec 2.5: first tier at hunger >= 30)
            damage = 0.0
            if new_hunger > STARVATION_TIER2:
                damage = 3.0
            elif new_hunger >= STARVATION_TIER1:
                damage = 2.0

            new_health = max(0.0, health - damage)

            # Old age death
            if new_age >= max_age:
                new_health = 0.0

            cursor.execute(
                "UPDATE mob_health SET hunger = ?, fat = ?, health = ?, energy = ?, "
                "age = ?, life_stage = ? WHERE mob_id = ?",
                (new_hunger, new_fat, new_health, new_energy,
                 new_age, life_stage, mob_id),
            )

            # Death check
            if new_health <= 0:
                cursor.execute(
                    "UPDATE mob_genes SET death = ? WHERE mob_id = ?",
                    (time.time(), mob_id),
                )
                logger.info(f"Mob {mob_id} died (health={new_health}, age={new_age})")

        self.db_conn.commit()
