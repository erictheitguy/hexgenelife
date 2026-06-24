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
    attack_size_factor,
)

logger = logging.getLogger("Server.MobInteractions")

# Grass consumed per eat action
GRASS_PER_EAT = 5.0
# Energy gained per eat action (herbivore)
ENERGY_PER_EAT = 10.0
# Energy spent per MOVE: superlinear in the distance actually moved this tick
# and scaled by mass: cost = MOVE_ENERGY_COST * mass * move_dist**2. Small
# steps are cheap; moving at full speed costs disproportionately more, so
# resting/short moves conserve energy. Movement is still capped at the mob's
# speed per tick (see handle_move_mob), so this penalises how much of that
# per-tick budget is spent, not raw map distance.
MOVE_ENERGY_COST = 0.2
# Attack damage per hit
BASE_ATTACK_DAMAGE = 10.0
# Energy spent by attacker per attack action
ATTACK_ENERGY_COST = 2.5
# Energy gained per EAT_MOB bite. Raised (20→32) as part of boosting nutrition
# per kill: committed-flee prey are hard to catch (~6-7 kills/120 ticks no matter
# the predator count), so the few kills predators DO land must pay off enough to
# sustain a small BREEDING population and to feed several predators sharing one
# carcass.
ENERGY_FROM_MOB = 32.0
# Fat gained per EAT_MOB bite. Raised (13→26) so a single kill takes a predator
# past the breeding fat threshold (25) — fat suppresses hunger and gates
# reproduction, so richer meat lets a low kill rate support a breeding group.
FAT_FROM_MOB = 26.0
# Fat level above which gains from eating are halved (satiation curve)
FAT_SATIATION_THRESHOLD = 40.0
# Carcass meat pool: stored in dead mob's mob_health.fat. Floored at this
# value on death so even a starved prey carcass yields a baseline meal.
# Biologically: this represents body muscle mass, which doesn't depend on
# stored fat reserves. Raised 80→110 so each kill yields more total meat
# (~6-7 bites), enough to feed several predators well from one carcass.
CARCASS_MEAT_BASE = 110.0
# Meat consumed from the carcass per EAT_MOB bite.
BITE_MEAT_DRAIN = 18.0
# Carcass is removed when its remaining meat drops at or below this — the
# point at which only bones/scraps are left.
MIN_MEAT_LEFT = 5.0
# Hunger increase per tick
HUNGER_PER_TICK = 1.0
# Fat consumed per tick (resting metabolism) — kept for reference
FAT_PER_TICK = 0.5
# Energy threshold below which hunger increases when fat is depleted
HUNGER_ENERGY_THRESHOLD = 60.0
# Starvation thresholds
STARVATION_TIER1 = 30.0   # hunger >= 30 → 2 damage
STARVATION_TIER2 = 40.0   # hunger > 40  → 3 damage
# Predator-specific sustain adjustments
PREDATOR_STARVATION_TIER1 = 35.0
PREDATOR_STARVATION_TIER2 = 45.0
# Predators burn calories faster than prey — active hunting is metabolically
# expensive. Without this, well-fed predators experience zero mortality and
# the population grows without bound until prey collapse (Run-25 showed
# 0 predator deaths across 30 minutes). 1.4 makes predators starve about
# twice as fast as prey when food is scarce.
PREDATOR_HUNGER_PER_TICK = 1.4
PREDATOR_ATTACK_ENERGY_COST = 1.8
CARCASS_STALE_SECONDS = 60.0
# Aging cost per unit of age increase
ENERGY_PER_AGE_UNIT = 1.0
# Age increase per tick (default, overridden by mob_physical.aging_rate)
DEFAULT_AGING_RATE = 0.125
# Breeding energy cost (prey)
BREED_ENERGY_COST = 20.0
# Minimum energy to breed (prey)
MIN_BREED_ENERGY = 40.0
# Predators pay more to breed and require deeper reserves — apex predators
# breed slowly in nature and we want the population to grow only when prey
# is abundant.
BREED_ENERGY_COST_PREDATOR = 40.0
MIN_BREED_ENERGY_PREDATOR = 65.0


def _is_breedable_health(health: dict) -> bool:
    return (
        health.get("life_stage", "adult") == "adult"
        and health.get("energy", 0.0) >= MIN_BREED_ENERGY
        and health.get("health", 0.0) >= 80.0
    )


class MobInteractions:
    def __init__(self, server, db_conn: sqlite3.Connection, mob_manager):
        self.server = server
        self.db_conn = db_conn
        self.mob_manager = mob_manager
        # Tracks last move distance per mob_id for camouflage detection
        self.mob_last_move_dist: dict[str, float] = {}
        self._interaction_buffer: list[tuple] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_mob_row(self, mob_id: str) -> dict | None:
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT * FROM mobs WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def _apply_carcass_meat(self, mob_id: str) -> None:
        """Ensure a freshly-killed mob's carcass has at least CARCASS_MEAT_BASE
        meat, stored in mob_health.fat. Called from every death code path so a
        single carcass can sustain multiple bites and feed multiple predators.
        Uses MAX so a well-fed prey's carcass keeps its higher fat (bigger meal)
        while a starved prey still yields the baseline."""
        cursor = self.db_conn.cursor()
        cursor.execute(
            "UPDATE mob_health SET fat = MAX(fat, ?) WHERE mob_id = ?",
            (CARCASS_MEAT_BASE, mob_id),
        )

    def _offspring_count(self, mob_id: str) -> int:
        cursor = self.db_conn.cursor()
        return cursor.execute(
            "SELECT COUNT(*) FROM family_tree WHERE parent_a_id=? OR parent_b_id=?",
            (mob_id, mob_id),
        ).fetchone()[0]

    def _live_fitness_score(self, health: dict, offspring_count: int = 0) -> float:
        if not _is_breedable_health(health):
            return 0.0
        energy_quality = min(1.0, health.get("energy", 0.0) / 100.0)
        health_quality = min(1.0, health.get("health", 0.0) / 100.0)
        return round(max(0.0001, energy_quality * health_quality * (1 + offspring_count)), 4)

    def _finalize_death(self, mob_id: str, death_ts: float) -> float:
        cursor = self.db_conn.cursor()
        cursor.execute(
            "UPDATE mob_genes SET death = ? WHERE mob_id = ? AND (death IS NULL OR death = 0)",
            (death_ts, mob_id),
        )
        self._apply_carcass_meat(mob_id)
        if hasattr(self.server, "remove_from_spatial_index"):
            self.server.remove_from_spatial_index(mob_id)
        row = cursor.execute(
            "SELECT COALESCE(fitnessScore, 0.0) AS fitnessScore FROM mob_genes WHERE mob_id = ?",
            (mob_id,),
        ).fetchone()
        return row["fitnessScore"] if row else 0.0

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
        if hasattr(self.server, "update_spatial_index"):
            self.server.update_spatial_index(mob_id, {"x": x, "y": y})

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
        self._interaction_buffer.append(
            (mob_a, mob_b, itype, time.time(), json.dumps(details or {}), outcome)
        )
        if len(self._interaction_buffer) >= 100:
            self.flush_interactions()

    def flush_interactions(self):
        if not self._interaction_buffer:
            return
        cursor = self.db_conn.cursor()
        cursor.executemany(
            """INSERT INTO interaction_history
               (mob_a_id, mob_b_id, interaction_type, timestamp, details, outcome)
               VALUES (?, ?, ?, ?, ?, ?)""",
            self._interaction_buffer,
        )
        self.db_conn.commit()
        self._interaction_buffer.clear()

    # ------------------------------------------------------------------
    # LOOK
    # ------------------------------------------------------------------

    async def handle_look(self, payload: dict, websocket) -> None:
        mob_id = payload.get("mobId")
        if not mob_id or not self.mob_manager.mob_exists(mob_id):
            await self.server.send_error(websocket, "MOB_NOT_FOUND",
                                         f"Mob {mob_id} not found.",
                                         {"mobId": mob_id, "commandType": "LOOK"})
            return

        pos = self._get_position(mob_id)
        if pos is None:
            await self.server.send_error(websocket, "NO_POSITION",
                                         f"Mob {mob_id} has no position.",
                                         {"mobId": mob_id, "commandType": "LOOK"})
            return

        phys = self.mob_manager.get_mob_physical(mob_id)
        vision = phys.get("vision", 20.0)
        ox, oy = pos["x"], pos["y"]

        # Tiles within vision. The BETWEEN clauses let SQLite use
        # idx_hex_tiles_cx_cy to narrow to the bounding box; the quadratic
        # check then filters the box corners off.
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT * FROM hex_tiles "
            "WHERE centerX BETWEEN ? AND ? "
            "  AND centerY BETWEEN ? AND ? "
            "  AND (centerX - ?) * (centerX - ?) + (centerY - ?) * (centerY - ?) <= ? * ?",
            (ox - vision, ox + vision, oy - vision, oy + vision,
             ox, ox, oy, oy, vision, vision),
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

        # Mobs within vision (excluding self) — include recently dead so predators can eat carcasses
        nearby_ids = None
        if hasattr(self.server, "get_nearby_mob_ids"):
            nearby_ids = self.server.get_nearby_mob_ids(ox, oy, vision)
        if nearby_ids is not None:
            nearby_ids.discard(mob_id)
        # Join mob_physical so camouflage/size come back on the same row —
        # avoids N per-mob SELECTs inside the detection loop below.
        if nearby_ids is None:
            cursor.execute(
                "SELECT m.*, g.death, COALESCE(g.fitnessScore, 0.0) AS fitnessScore, "
                "       COALESCE(p.camouflage, 0.5) AS camouflage, "
                "       COALESCE(p.size, 1.0) AS size, "
                "       COALESCE(h.life_stage, 'adult') AS life_stage, "
                "       COALESCE(h.energy, 0.0) AS energy "
                "FROM mobs m "
                "LEFT JOIN mob_genes g ON m.mob_id = g.mob_id "
                "LEFT JOIN mob_physical p ON m.mob_id = p.mob_id "
                "LEFT JOIN mob_health h ON m.mob_id = h.mob_id "
                "WHERE m.mob_id != ? AND m.is_active = 1",
                (mob_id,),
            )
            rows = cursor.fetchall()
        elif not nearby_ids:
            rows = []
        else:
            ph = ",".join("?" for _ in nearby_ids)
            params = tuple(nearby_ids)
            cursor.execute(
                f"SELECT m.*, g.death, COALESCE(g.fitnessScore, 0.0) AS fitnessScore, "
                f"       COALESCE(p.camouflage, 0.5) AS camouflage, "
                f"       COALESCE(p.size, 1.0) AS size, "
                f"       COALESCE(h.life_stage, 'adult') AS life_stage, "
                f"       COALESCE(h.energy, 0.0) AS energy "
                f"FROM mobs m "
                f"LEFT JOIN mob_genes g ON m.mob_id = g.mob_id "
                f"LEFT JOIN mob_physical p ON m.mob_id = p.mob_id "
                f"LEFT JOIN mob_health h ON m.mob_id = h.mob_id "
                f"WHERE m.mob_id IN ({ph}) AND m.is_active = 1",
                params,
            )
            rows = cursor.fetchall()
        visible_mobs = []
        for row in rows:
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

            is_dead = bool(m.get("death"))

            # Dead mobs don't use camouflage — always visible as carcasses.
            # camouflage/size were already joined in above; no per-mob SELECT.
            if not is_dead:
                camouflage = m["camouflage"]
                size = m["size"]
                last_move = self.mob_last_move_dist.get(m["mob_id"], 0.0)
                detection = vision - camouflage * 10.0 + last_move * 0.5 + size * 2.0
                if detection < dist:
                    continue

            visible_mobs.append({
                "mobId": m["mob_id"],
                "mob_type": m.get("mob_type", "prey"),
                "position": m_pos,
                "distance": dist,
                "alive": not is_dead,
                "life_stage": m.get("life_stage") or "adult",
                "energy": m.get("energy", 0.0),
                "fitnessScore": m.get("fitnessScore", 0.0) or 0.0,
            })

        # mob_self
        health = self.mob_manager.get_mob_health(mob_id)
        phys = self.mob_manager.get_mob_physical(mob_id)
        mob_self = {
            "mobId": mob_id,
            "position": pos,
            "hunger": health.get("hunger", 0.0),
            "fat": health.get("fat", 0.0),
            "energy": health.get("energy", 50.0),
            "health": health.get("health", 100.0),
            "life_stage": health.get("life_stage", "adult"),
            "herd": phys.get("herd", 0.5),
            "vision": phys.get("vision", 20.0),
        }
        genes = self.db_conn.cursor()
        genes.execute("SELECT COALESCE(fitnessScore, 0.0) AS fitnessScore FROM mob_genes WHERE mob_id = ?", (mob_id,))
        gene_row = genes.fetchone()
        mob_self["fitnessScore"] = gene_row["fitnessScore"] if gene_row else 0.0

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
                                         f"Mob {mob_id} not found.",
                                         {"mobId": mob_id, "commandType": "MOVE_MOB"})
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

        # Movement costs energy, superlinear in distance moved and scaled by
        # mass: small steps are cheap, full-speed moves cost disproportionately
        # more. (move_dist is already capped at the mob's speed.)
        if move_dist > 0:
            mass = phys.get("mass", 1.0)
            move_cost = MOVE_ENERGY_COST * mass * (move_dist ** 2)
            cursor = self.db_conn.cursor()
            cursor.execute(
                "UPDATE mob_health SET energy = MAX(0, energy - ?) WHERE mob_id = ?",
                (move_cost, mob_id),
            )
            self.db_conn.commit()

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
                                         f"Mob {mob_id} not found.",
                                         {"mobId": mob_id, "commandType": "EAT_GRASS"})
            return

        pos = self._get_position(mob_id) or {"x": 0.0, "y": 0.0}
        tile = self._nearest_tile(pos["x"], pos["y"])
        if tile is None or tile["Grass"] <= 0:
            await self.server.send_error(websocket, "NO_GRASS",
                                         "No grass available at current tile.",
                                         {"mobId": mob_id, "commandType": "EAT_GRASS"})
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
        # Fat accumulates from overflow above 50 at 1:1 ratio
        fat_gain = 0.0
        if new_energy > 50.0:
            overflow = new_energy - 50.0
            fat_gain = overflow
            new_energy = 50.0
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
                                         f"Mob {mob_id} not found.",
                                         {"mobId": mob_id, "targetId": target_id,
                                          "commandType": "ATTACK_MOB"})
            return
        if not target_id or not self.mob_manager.mob_exists(target_id):
            await self.server.send_error(websocket, "TARGET_NOT_FOUND",
                                         f"Target {target_id} not found.",
                                         {"mobId": mob_id, "targetId": target_id,
                                          "commandType": "ATTACK_MOB"})
            return

        # A corpse stays is_active=1 for several ticks so predators can eat the
        # carcass, so mob_exists() still returns true. Bail out before applying
        # any damage if the target is already dead — otherwise every subsequent
        # attack would re-run the death block (rewriting the death timestamp,
        # recomputing fitness, re-applying carcass meat and re-logging the
        # death), corrupting death-cause telemetry. Predators should route to
        # EAT_MOB instead.
        t_genes = self.db_conn.cursor()
        t_genes.execute("SELECT death FROM mob_genes WHERE mob_id = ?", (target_id,))
        death_row = t_genes.fetchone()
        if death_row is not None and death_row["death"]:
            await self.server.send_error(websocket, "TARGET_ALREADY_DEAD",
                                         f"Target {target_id} is already dead.",
                                         {"mobId": mob_id, "targetId": target_id,
                                          "commandType": "ATTACK_MOB"})
            return

        phys = self.mob_manager.get_mob_physical(mob_id)
        t_phys = self.mob_manager.get_mob_physical(target_id)
        attack = phys.get("attack_power", 1.0)
        defense = t_phys.get("defense", 1.0)
        damage = max(0.0, attack * BASE_ATTACK_DAMAGE - defense * 2.0)

        # Scale damage by size-class mismatch. A baby predator can attempt to
        # attack an adult prey, but its damage is a small fraction of normal —
        # it'll exhaust its energy without bringing the target down. Lets the
        # size constraint be emergent (any mob can try anything) rather than a
        # hard brain-side rule.
        attacker_health = self.mob_manager.get_mob_health(mob_id)
        target_health = self.mob_manager.get_mob_health(target_id)
        size_factor = attack_size_factor(
            attacker_health.get("life_stage", "adult"),
            target_health.get("life_stage", "adult"),
        )
        damage *= size_factor

        cursor = self.db_conn.cursor()
        cursor.execute(
            "UPDATE mob_health SET health = MAX(0, health - ?) WHERE mob_id = ?",
            (damage, target_id),
        )
        attack_cost = PREDATOR_ATTACK_ENERGY_COST if self._get_mob_row(mob_id).get("mob_type") == "predator" else ATTACK_ENERGY_COST
        cursor.execute(
            "UPDATE mob_health SET energy = MAX(0, energy - ?) WHERE mob_id = ?",
            (attack_cost, mob_id),
        )
        self.db_conn.commit()

        # Check if target died
        health = self.mob_manager.get_mob_health(target_id)
        if health.get("health", 1.0) <= 0:
            now = time.time()
            fitness = self._finalize_death(target_id, now)
            # Keep is_active=1 briefly so predators can see and eat the carcass;
            # metabolism loop will set is_active=0 after it's been eaten or times out.
            self.db_conn.commit()
            logger.info(
                f"Mob {target_id} died cause=predation killer={mob_id} "
                f"fitness={fitness}"
            )

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
                                         f"Mob {mob_id} not found.",
                                         {"mobId": mob_id, "targetId": target_id,
                                          "commandType": "EAT_MOB"})
            return
        if not target_id or not self.mob_manager.mob_exists(target_id):
            await self.server.send_error(websocket, "TARGET_NOT_FOUND",
                                         f"Target {target_id} not found.",
                                         {"mobId": mob_id, "targetId": target_id,
                                          "commandType": "EAT_MOB"})
            return

        # Target must be dead
        t_genes = self.db_conn.cursor()
        t_genes.execute("SELECT death FROM mob_genes WHERE mob_id = ?", (target_id,))
        row = t_genes.fetchone()
        if row is None or not row["death"]:
            await self.server.send_error(websocket, "TARGET_NOT_DEAD",
                                         "Cannot eat a living mob.",
                                         {"mobId": mob_id, "targetId": target_id,
                                          "commandType": "EAT_MOB"})
            return

        cursor = self.db_conn.cursor()
        cursor.execute("SELECT fat FROM mob_health WHERE mob_id = ?", (mob_id,))
        h = cursor.fetchone()
        cur_fat = h["fat"] if h else 0.0

        # Carcass meat is stored on the target's mob_health.fat. Death paths
        # floor it to CARCASS_MEAT_BASE; this read uses MAX as a safety net
        # in case a test or alternate code path set the death timestamp
        # without going through _apply_carcass_meat.
        cursor.execute("SELECT fat FROM mob_health WHERE mob_id = ?", (target_id,))
        t_row = cursor.fetchone()
        target_meat = max(t_row["fat"] if t_row else 0.0, 0.0)

        if target_meat <= 0.0:
            # Empty carcass (scavenged or stale) — clean up without nutrition.
            cursor.execute("DELETE FROM mobs WHERE mob_id = ?", (target_id,))
            self.db_conn.commit()
            if hasattr(self.server, "remove_from_spatial_index"):
                self.server.remove_from_spatial_index(target_id)
            await self.server.send_error(websocket, "CARCASS_EMPTY",
                                         "Carcass has no meat left.",
                                         {"mobId": mob_id, "targetId": target_id,
                                          "commandType": "EAT_MOB"})
            return

        # One bite removes BITE_MEAT_DRAIN from the carcass (or all that's left
        # if the carcass is nearly bones). The predator's per-bite gain stays
        # the same regardless — a small bite still nourishes a small predator.
        bite_drained = min(BITE_MEAT_DRAIN, target_meat)
        new_target_meat = target_meat - bite_drained

        # Satiation curve: halve fat gains when predator is already well-fed.
        fat_gain = FAT_FROM_MOB * 0.5 if cur_fat > FAT_SATIATION_THRESHOLD else FAT_FROM_MOB

        cursor.execute(
            "UPDATE mob_health SET energy = MIN(100.0, energy + ?), fat = MIN(100.0, fat + ?) "
            "WHERE mob_id = ?",
            (ENERGY_FROM_MOB, fat_gain, mob_id),
        )

        if new_target_meat <= MIN_MEAT_LEFT:
            # Carcass picked clean — remove it.
            cursor.execute("DELETE FROM mobs WHERE mob_id = ?", (target_id,))
            self.db_conn.commit()
            if hasattr(self.server, "remove_from_spatial_index"):
                self.server.remove_from_spatial_index(target_id)
        else:
            # Carcass still has meat — leave it for the next bite/predator.
            cursor.execute(
                "UPDATE mob_health SET fat = ? WHERE mob_id = ?",
                (new_target_meat, target_id),
            )
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
                                         f"Mob {mob_id} not found.",
                                         {"mobId": mob_id, "targetId": target_id,
                                          "commandType": "BREED_MOB"})
            return
        if not target_id or not self.mob_manager.mob_exists(target_id):
            await self.server.send_error(websocket, "TARGET_NOT_FOUND",
                                         f"Target {target_id} not found.",
                                         {"mobId": mob_id, "targetId": target_id,
                                          "commandType": "BREED_MOB"})
            return

        child_id = self.breed_mobs(mob_id, target_id)
        if child_id is None:
            await self.server.send_error(websocket, "BREED_FAILED",
                                         "Breeding conditions not met.",
                                         {"mobId": mob_id, "targetId": target_id,
                                          "commandType": "BREED_MOB"})
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

        # Determine mob type and parent generations up front.
        cursor = self.db_conn.cursor()
        cursor.execute(
            "SELECT mob_type, generation FROM mobs WHERE mob_id = ?", (parent_a_id,)
        )
        row = cursor.fetchone()
        mob_type = row["mob_type"] if row else "prey"
        gen_a = row["generation"] if row else 0
        cursor.execute("SELECT generation FROM mobs WHERE mob_id = ?", (parent_b_id,))
        row_b = cursor.fetchone()
        gen_b = row_b["generation"] if row_b else 0
        child_generation = max(gen_a, gen_b) + 1

        breed_cost = BREED_ENERGY_COST_PREDATOR if mob_type == "predator" else BREED_ENERGY_COST

        if not _is_breedable_health(h_a):
            return None
        if not _is_breedable_health(h_b):
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

        # Generate child ID
        child_client_id = f"child_{uuid.uuid4().hex[:8]}"
        child_mob_id = self.mob_manager.ensure_client_mob(
            child_client_id, mob_type=mob_type, physical_overrides=child_phys
        )

        # Set child as baby at parent A's position, and mark it active so the
        # LOOK query (which filters WHERE is_active = 1) returns it to other
        # mobs.  is_active is normally set when a WebSocket client first sends
        # a message for mob_{client_id}; the parent client adopts this child
        # but never triggers that path, so without this update the child would
        # be invisible to predators and prey alike for its entire life.
        pos = self._get_position(parent_a_id) or {"x": 0.0, "y": 0.0}
        cursor.execute(
            "UPDATE mobs SET position = ?, is_active = 1, generation = ? WHERE mob_id = ?",
            (json.dumps(pos), child_generation, child_mob_id),
        )
        cursor.execute(
            "UPDATE mob_health SET life_stage = 'baby', age = 0.0, hunger = 0.0, fat = 20.0, energy = 50.0 WHERE mob_id = ?",
            (child_mob_id,),
        )

        # Record family tree
        cursor.execute(
            "UPDATE family_tree SET parent_a_id = ?, parent_b_id = ? WHERE mob_id = ?",
            (parent_a_id, parent_b_id, child_mob_id),
        )

        # Deduct energy from parents (predator-specific cost applied if relevant)
        cursor.execute(
            "UPDATE mob_health SET energy = MAX(0, energy - ?) WHERE mob_id IN (?, ?)",
            (breed_cost, parent_a_id, parent_b_id),
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

            # Fat burns to energy at 1:1 (spec 2.2); fat suppresses and reduces hunger (spec 2.1)
            new_fat = fat
            if new_fat > 0:
                burn = min(new_fat, metabolism_resting)
                new_fat = max(0.0, new_fat - burn)
                new_energy = min(100.0, new_energy + burn)  # 1:1 conversion
                # Fat satisfies hunger — decrease it while reserves exist
                new_hunger = max(0.0, hunger - burn)
            elif new_energy < HUNGER_ENERGY_THRESHOLD:
                # No fat and energy is low — hunger increases
                hunger_gain = PREDATOR_HUNGER_PER_TICK if row["mob_type"] == "predator" else HUNGER_PER_TICK
                new_hunger = min(50.0, hunger + hunger_gain)
            else:
                # No fat but energy is sufficient — hunger holds steady
                new_hunger = hunger

            # Starvation damage (spec 2.5: first tier at hunger >= 30)
            damage = 0.0
            if row["mob_type"] == "predator":
                if new_hunger > PREDATOR_STARVATION_TIER2:
                    damage = 2.5
                elif new_hunger >= PREDATOR_STARVATION_TIER1:
                    damage = 1.5
            else:
                if new_hunger > STARVATION_TIER2:
                    damage = 3.0
                elif new_hunger >= STARVATION_TIER1:
                    damage = 2.0

            new_health = max(0.0, health - damage)

            # HP recovery when well-fed (hunger < 5, no starvation damage)
            if new_hunger < 5 and damage == 0.0:
                new_health = min(100.0, new_health + 0.5)

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
                now_ts = time.time()
                fitness = self._finalize_death(mob_id, now_ts)
                if new_age >= max_age:
                    cause = f"old_age age={new_age:.1f}/{max_age:.1f}"
                elif damage > 0:
                    cause = f"starvation hunger={new_hunger:.1f}"
                else:
                    cause = "unknown"
                logger.info(
                    f"Mob {mob_id} died cause={cause} health={new_health:.1f} "
                    f"fitness={fitness}"
                )
            else:
                offspring_count = self._offspring_count(mob_id)
                fitness = self._live_fitness_score({
                    "life_stage": life_stage,
                    "energy": new_energy,
                    "health": new_health,
                }, offspring_count)
                cursor.execute(
                    "UPDATE mob_genes SET fitnessScore = ? WHERE mob_id = ?",
                    (fitness, mob_id),
                )

        self.db_conn.commit()
        self.flush_interactions()

        # Clean up stale carcasses (dead > 30s and not yet eaten)
        stale_cutoff = time.time() - CARCASS_STALE_SECONDS
        cursor = self.db_conn.cursor()
        cursor.execute(
            "UPDATE mobs SET is_active = 0 "
            "WHERE mob_id IN ("
            "  SELECT m.mob_id FROM mobs m "
            "  JOIN mob_genes g ON m.mob_id = g.mob_id "
            "  WHERE g.death > 0 AND g.death < ? AND m.is_active = 1"
            ")",
            (stale_cutoff,),
        )
        self.db_conn.commit()
