"""
HexGenLife Sim Runner Skill
============================
Runs a full supervised simulation cycle:
  1. Start server (new game)
  2. Spawn prey clients
  3. Monitor DB/logs until prey start breeding
  4. Add predator clients
  5. Continue monitoring (max 30 min total)
  6. Kill server + clients
  7. Write a run report to Obsidian at Projects/HexGenLife/Runs/run-<N>.md

Debug improvements over original kiro version:
  - Hunger, energy, fat averages in every snapshot
  - EAT_GRASS and EAT_MOB event counts tracked each poll
  - ERROR/WARNING/Exception lines from server.log and client.log scanned each poll
  - Detected errors added as phase markers in real time
  - Server + client log tails actually included in Obsidian report
  - Phase marker when prey health drops critically low (<20)
  - Richer console output per poll (health/hunger/energy/fat + pred metrics)
  - Read-only DB connection to avoid locking live server
"""
import importlib.util
import json
import math
import os
import re
import signal
import sqlite3
import subprocess
import statistics
import sys
import time
from datetime import datetime

WORKSPACE      = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH        = os.path.join(WORKSPACE, "server", "game_state.db")
LOGS_DIR       = os.path.join(WORKSPACE, "logs")
SERVER_LOG     = os.path.join(LOGS_DIR, "server.log")
CLIENT_LOG     = os.path.join(LOGS_DIR, "client.log")
MAX_SECONDS    = 30 * 60
POLL_INTERVAL  = 10
# Radius (world units) used for the "still near start" prey-dispersal metric.
# Roughly 4 hex steps with HEX_RADIUS=5.0.
SPREAD_NEAR_RADIUS = 20.0

# ---------------------------------------------------------------------------
# Verdict thresholds
# ---------------------------------------------------------------------------
# A run is graded along three independent axes (see _build_report):
#   * mechanical    — did the simulation machinery run cleanly (ticks, no crashes)
#   * ecological    — is it a healthy, balanced ecosystem (survival, breeding, health)
#   * observability — are the clients/server reliable and quiet in the logs
# The overall verdict is the worst of the three. Tune these without touching logic.

# Number of trailing poll snapshots that define the "late run" window.
LATE_RUN_SNAPSHOTS = 3
# Late-run average prey health below this → ecological WARN (starving population).
LATE_RUN_PREY_HEALTH_WARN = 20.0
# Late-run average prey health below this → ecological FAIL (population doomed).
LATE_RUN_PREY_HEALTH_FAIL = 8.0

# Predator:prey alive-ratio thresholds (only when prey still alive).
PRED_PREY_RATIO_WARN = 1.0   # predators >= prey → top-heavy, unstable
PRED_PREY_RATIO_FAIL = 2.0   # predators dwarf prey → imminent prey collapse

# Population collapse: final prey dropped to this fraction of the peak (and the
# peak was a real bloom, i.e. >= COLLAPSE_MIN_PEAK) → ecological FAIL.
PREY_COLLAPSE_FRACTION = 0.20
COLLAPSE_MIN_PEAK = 5
# Runaway predator growth: predator peak exceeds start by this multiple → FAIL.
PRED_RUNAWAY_MULT = 4.0

# Per-error-code counts (parsed from client.log) considered excessive.
ERR_CODE_WARN = 25
ERR_CODE_FAIL = 150

# Client LOOK-timeout / reconnect counts over the whole run.
LOOK_TIMEOUT_WARN = 3
LOOK_TIMEOUT_FAIL = 20
RECONNECT_WARN = 1
RECONNECT_FAIL = 5
CONN_FAIL_WARN = 1
CONN_FAIL_FAIL = 10

# Verdict severity ordering helper.
_VERDICT_RANK = {"PASS": 0, "WARN": 1, "FAIL": 2}


def _worse(a: str, b: str) -> str:
    """Return the more severe of two verdict strings."""
    return a if _VERDICT_RANK[a] >= _VERDICT_RANK[b] else b

# Per-run state that persists across snapshots within a single run_sim() call.
# Reset at the top of run_sim() so back-to-back runs in the same process stay clean.
_run_state: dict = {
    "start_centroid": None,    # (x, y) — first observed centroid of alive prey
    "start_tile_count": None,  # initial hex_tiles row count
    "known_dead_predators": set(),  # mob_ids whose death we've already captured
    "predator_death_events": [],    # list of dicts; see _capture_predator_deaths
}

# Mirror of client/brain_registry.py ATTACK_RANGE — used to label whether
# prey were close enough to bite at the moment a predator died.
PREDATOR_ATTACK_RANGE = 3.0


# ---------------------------------------------------------------------------
# Skill loader helpers
# ---------------------------------------------------------------------------

def _load_skill(rel_path: str):
    # Dependency skills live under .codex/skills (and may be mirrored under
    # .claude/skills). Kiro is intentionally not consulted.
    candidates = [
        os.path.join(WORKSPACE, ".codex", "skills", rel_path),
        os.path.join(WORKSPACE, ".claude", "skills", rel_path),
    ]
    full = next((c for c in candidates if os.path.exists(c)), None)
    if not full:
        raise FileNotFoundError(f"Skill module not found for {rel_path}: {candidates}")
    spec = importlib.util.spec_from_file_location("_skill", full)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _db_connect():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _snapshot() -> dict:
    """Return a dict of key sim metrics from a read-only DB connection."""
    if not os.path.exists(DB_PATH):
        return {}
    try:
        conn = _db_connect()
        cur  = conn.cursor()

        def scalar(sql, params=()):
            cur.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row else 0

        def avg_min_max(sql, params=()):
            cur.execute(sql, params)
            row = cur.fetchone()
            if not row or row[0] is None:
                return 0.0, 0.0, 0.0
            return round(row[0], 2), round(row[1] or 0, 2), round(row[2] or 0, 2)

        prey_total = scalar("SELECT COUNT(*) FROM mobs WHERE mob_type='prey'")
        prey_alive = scalar(
            "SELECT COUNT(*) FROM mobs m JOIN mob_health h ON m.mob_id=h.mob_id "
            "WHERE m.mob_type='prey' AND h.health > 0"
        )
        pred_total = scalar("SELECT COUNT(*) FROM mobs WHERE mob_type='predator'")
        pred_alive = scalar(
            "SELECT COUNT(*) FROM mobs m JOIN mob_health h ON m.mob_id=h.mob_id "
            "WHERE m.mob_type='predator' AND h.health > 0"
        )
        prey_bred = scalar(
            "SELECT COUNT(*) FROM family_tree ft JOIN mobs m ON ft.mob_id=m.mob_id "
            "WHERE ft.parent_a_id IS NOT NULL AND m.mob_type='prey'"
        )
        pred_bred = scalar(
            "SELECT COUNT(*) FROM family_tree ft JOIN mobs m ON ft.mob_id=m.mob_id "
            "WHERE ft.parent_a_id IS NOT NULL AND m.mob_type='predator'"
        )
        prey_adult = scalar(
            "SELECT COUNT(*) FROM mobs m JOIN mob_health h ON m.mob_id=h.mob_id "
            "WHERE m.mob_type='prey' AND h.health > 0 AND h.life_stage IN ('adult', 'senior')"
        )
        pred_adult = scalar(
            "SELECT COUNT(*) FROM mobs m JOIN mob_health h ON m.mob_id=h.mob_id "
            "WHERE m.mob_type='predator' AND h.health > 0 AND h.life_stage IN ('adult', 'senior')"
        )
        cur.execute("SELECT value FROM server_state WHERE key='tick_num'")
        row = cur.fetchone()
        tick = int(row["value"]) if row else 0
        queue_depth = scalar("SELECT value FROM server_state WHERE key='queue_depth'") or 0
        deferred_actions = scalar("SELECT value FROM server_state WHERE key='deferred_actions'") or 0
        degraded_mode = scalar("SELECT value FROM server_state WHERE key='degraded_mode'") or 0

        prey_health  = avg_min_max(
            "SELECT AVG(h.health), MIN(h.health), MAX(h.health) FROM mob_health h "
            "JOIN mobs m ON h.mob_id=m.mob_id WHERE m.mob_type='prey'"
        )
        pred_health  = avg_min_max(
            "SELECT AVG(h.health), MIN(h.health), MAX(h.health) FROM mob_health h "
            "JOIN mobs m ON h.mob_id=m.mob_id WHERE m.mob_type='predator'"
        )
        # Alive-only averages for diagnostic signals
        prey_hunger  = avg_min_max(
            "SELECT AVG(h.hunger), MIN(h.hunger), MAX(h.hunger) FROM mob_health h "
            "JOIN mobs m ON h.mob_id=m.mob_id WHERE m.mob_type='prey' AND h.health > 0"
        )
        prey_energy  = avg_min_max(
            "SELECT AVG(h.energy), MIN(h.energy), MAX(h.energy) FROM mob_health h "
            "JOIN mobs m ON h.mob_id=m.mob_id WHERE m.mob_type='prey' AND h.health > 0"
        )
        prey_fat     = avg_min_max(
            "SELECT AVG(h.fat), MIN(h.fat), MAX(h.fat) FROM mob_health h "
            "JOIN mobs m ON h.mob_id=m.mob_id WHERE m.mob_type='prey' AND h.health > 0"
        )
        pred_hunger  = avg_min_max(
            "SELECT AVG(h.hunger), MIN(h.hunger), MAX(h.hunger) FROM mob_health h "
            "JOIN mobs m ON h.mob_id=m.mob_id WHERE m.mob_type='predator' AND h.health > 0"
        )
        pred_energy  = avg_min_max(
            "SELECT AVG(h.energy), MIN(h.energy), MAX(h.energy) FROM mob_health h "
            "JOIN mobs m ON h.mob_id=m.mob_id WHERE m.mob_type='predator' AND h.health > 0"
        )

        breed_events      = scalar("SELECT COUNT(*) FROM interaction_history WHERE interaction_type='BREED'")
        attack_events     = scalar("SELECT COUNT(*) FROM interaction_history WHERE interaction_type='ATTACK'")
        eat_grass_events  = scalar("SELECT COUNT(*) FROM interaction_history WHERE interaction_type='EAT_GRASS'")
        eat_mob_events    = scalar("SELECT COUNT(*) FROM interaction_history WHERE interaction_type='EAT_MOB'")

        # --- Strict breeding-capable adults (life_stage='adult' only, not senior) ---
        prey_adult_strict = scalar(
            "SELECT COUNT(*) FROM mobs m JOIN mob_health h ON m.mob_id=h.mob_id "
            "WHERE m.mob_type='prey' AND h.health > 0 AND h.life_stage='adult'"
        )
        prey_senior = scalar(
            "SELECT COUNT(*) FROM mobs m JOIN mob_health h ON m.mob_id=h.mob_id "
            "WHERE m.mob_type='prey' AND h.health > 0 AND h.life_stage='senior'"
        )
        pred_adult_strict = scalar(
            "SELECT COUNT(*) FROM mobs m JOIN mob_health h ON m.mob_id=h.mob_id "
            "WHERE m.mob_type='predator' AND h.health > 0 AND h.life_stage='adult'"
        )
        pred_senior = scalar(
            "SELECT COUNT(*) FROM mobs m JOIN mob_health h ON m.mob_id=h.mob_id "
            "WHERE m.mob_type='predator' AND h.health > 0 AND h.life_stage='senior'"
        )

        # --- pred_fat (symmetric with prey_fat) ---
        pred_fat = avg_min_max(
            "SELECT AVG(h.fat), MIN(h.fat), MAX(h.fat) FROM mob_health h "
            "JOIN mobs m ON h.mob_id=m.mob_id WHERE m.mob_type='predator' AND h.health > 0"
        )

        # --- Genetics: per-trait avg/min/max for each mob_type (alive only) ---
        TRAITS = ("speed", "vision", "attack_power", "defense", "camouflage", "aging_rate")
        genetics = {}
        for mob_type_g in ("prey", "predator"):
            for trait in TRAITS:
                cur.execute(
                    f"SELECT AVG(p.{trait}), MIN(p.{trait}), MAX(p.{trait}) "
                    f"FROM mob_physical p JOIN mobs m ON p.mob_id=m.mob_id "
                    f"JOIN mob_health h ON m.mob_id=h.mob_id "
                    f"WHERE m.mob_type=? AND h.health > 0",
                    (mob_type_g,)
                )
                r = cur.fetchone()
                prefix = f"{mob_type_g[0]}_{trait}"  # p_speed, p_vision, d_speed, etc.
                if r and r[0] is not None:
                    genetics[f"{prefix}_avg"] = round(r[0], 3)
                    genetics[f"{prefix}_min"] = round(r[1] or r[0], 3)
                    genetics[f"{prefix}_max"] = round(r[2] or r[0], 3)
                else:
                    genetics[f"{prefix}_avg"] = genetics[f"{prefix}_min"] = genetics[f"{prefix}_max"] = 0.0

        # --- Generation distribution ---
        cur.execute(
            "SELECT MAX(m.generation), AVG(m.generation) FROM mobs m "
            "JOIN mob_health h ON m.mob_id=h.mob_id "
            "WHERE m.mob_type='prey' AND h.health > 0"
        )
        r = cur.fetchone()
        prey_max_gen = int(r[0] or 0)
        prey_avg_gen = round(r[1] or 0.0, 2)
        cur.execute(
            "SELECT MAX(m.generation), AVG(m.generation) FROM mobs m "
            "JOIN mob_health h ON m.mob_id=h.mob_id "
            "WHERE m.mob_type='predator' AND h.health > 0"
        )
        r = cur.fetchone()
        pred_max_gen = int(r[0] or 0)
        pred_avg_gen = round(r[1] or 0.0, 2)

        # --- Grass supply ---
        cur.execute("SELECT SUM(Grass), AVG(Grass), COUNT(*) FROM hex_tiles")
        gr = cur.fetchone()
        grass_total    = round(float(gr[0] or 0), 1)
        grass_avg      = round(float(gr[1] or 0), 2)
        grass_depleted = scalar("SELECT COUNT(*) FROM hex_tiles WHERE Grass <= 0.5")

        # --- Tile generation: hex_tiles is grown by the server as mobs roam,
        #     so the count over time is a proxy for explored area. ---
        tiles_total = scalar("SELECT COUNT(*) FROM hex_tiles")
        if _run_state["start_tile_count"] is None and tiles_total > 0:
            _run_state["start_tile_count"] = tiles_total
        tiles_generated = tiles_total - (_run_state["start_tile_count"] or tiles_total)

        # --- Prey dispersal: are prey still clustered near where they spawned? ---
        # NOTE: do NOT filter by m.is_active = 1 — bred children are never marked
        # active (server.py only sets is_active for mob_{client_id}, not for
        # adopted children), so requiring it would silently drop them and the
        # spread metric would collapse to 0 once starter prey die off.
        cur.execute(
            "SELECT m.position FROM mobs m JOIN mob_health h ON m.mob_id=h.mob_id "
            "WHERE m.mob_type='prey' AND h.health > 0"
        )
        prey_positions: list[tuple[float, float]] = []
        for row in cur.fetchall():
            raw = row["position"]
            if raw is None:
                continue
            try:
                if isinstance(raw, str):
                    p = json.loads(raw)
                else:
                    p = raw
                prey_positions.append((float(p["x"]), float(p["y"])))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue

        if prey_positions:
            cx_now = sum(p[0] for p in prey_positions) / len(prey_positions)
            cy_now = sum(p[1] for p in prey_positions) / len(prey_positions)
        else:
            cx_now = cy_now = 0.0

        # Latch the starting centroid the first tick we see any live prey.
        if _run_state["start_centroid"] is None and prey_positions:
            _run_state["start_centroid"] = (cx_now, cy_now)

        start_cx, start_cy = _run_state["start_centroid"] or (cx_now, cy_now)

        if prey_positions:
            dists = [math.hypot(x - start_cx, y - start_cy) for x, y in prey_positions]
            prey_spread_avg = round(statistics.fmean(dists), 2)
            prey_spread_max = round(max(dists), 2)
            near_count      = sum(1 for d in dists if d <= SPREAD_NEAR_RADIUS)
            prey_near_start_pct = round(100.0 * near_count / len(dists), 1)
            centroid_drift  = round(math.hypot(cx_now - start_cx, cy_now - start_cy), 2)
        else:
            prey_spread_avg = 0.0
            prey_spread_max = 0.0
            prey_near_start_pct = 0.0
            centroid_drift = 0.0

        conn.close()
        snap = {
            "tick":             tick,
            "prey_total":       prey_total,
            "prey_alive":       prey_alive,
            "prey_bred":        prey_bred,
            "pred_total":       pred_total,
            "pred_alive":       pred_alive,
            "pred_bred":        pred_bred,
            "prey_adult":       prey_adult,
            "prey_adult_strict": prey_adult_strict,
            "prey_senior":      prey_senior,
            "pred_adult":       pred_adult,
            "pred_adult_strict": pred_adult_strict,
            "pred_senior":      pred_senior,
            "prey_health_avg":  prey_health[0],
            "prey_health_min":  prey_health[1],
            "prey_health_max":  prey_health[2],
            "pred_health_avg":  pred_health[0],
            "pred_health_min":  pred_health[1],
            "pred_health_max":  pred_health[2],
            "prey_hunger_avg":  prey_hunger[0],
            "prey_energy_avg":  prey_energy[0],
            "prey_fat_avg":     prey_fat[0],
            "pred_hunger_avg":  pred_hunger[0],
            "pred_energy_avg":  pred_energy[0],
            "pred_fat_avg":     pred_fat[0],
            "breed_events":     breed_events,
            "attack_events":    attack_events,
            "eat_grass_events": eat_grass_events,
            "eat_mob_events":   eat_mob_events,
            "queue_depth":      int(queue_depth),
            "deferred_actions": int(deferred_actions),
            "degraded_mode":    int(degraded_mode),
            "tiles_total":      int(tiles_total),
            "tiles_generated":  int(tiles_generated),
            "prey_centroid_x":  round(cx_now, 2),
            "prey_centroid_y":  round(cy_now, 2),
            "prey_centroid_drift":  centroid_drift,
            "prey_spread_avg":  prey_spread_avg,
            "prey_spread_max":  prey_spread_max,
            "prey_near_start_pct": prey_near_start_pct,
            "start_centroid_x": round(start_cx, 2),
            "start_centroid_y": round(start_cy, 2),
            "grass_total":      grass_total,
            "grass_avg":        grass_avg,
            "grass_depleted":   int(grass_depleted),
            "prey_max_gen":     prey_max_gen,
            "prey_avg_gen":     prey_avg_gen,
            "pred_max_gen":     pred_max_gen,
            "pred_avg_gen":     pred_avg_gen,
        }
        snap.update(genetics)
        return snap
    except Exception as e:
        print(f"[sim_runner] WARNING: snapshot failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Predator death diagnostic
# ---------------------------------------------------------------------------

def _capture_predator_deaths(current_tick: int) -> None:
    """Find newly-dead predators and snapshot the hunting context at their death.

    Each event records: predator id, vision used, last-known position, distance
    to nearest live prey, count of live prey within the predator's vision, and
    count within attack range. This tells us whether the predator died with
    food in sight (a hunting/AI problem) or with the world empty (an ecology
    problem).
    """
    if not os.path.exists(DB_PATH):
        return
    try:
        conn = _db_connect()
        cur = conn.cursor()

        cur.execute(
            "SELECT m.mob_id, m.position, g.death, "
            "       COALESCE(p.vision, 20.0) AS vision "
            "FROM mobs m "
            "JOIN mob_genes g ON m.mob_id = g.mob_id "
            "LEFT JOIN mob_physical p ON m.mob_id = p.mob_id "
            "WHERE m.mob_type = 'predator' "
            "  AND g.death IS NOT NULL AND g.death > 0"
        )
        dead_rows = cur.fetchall()

        known = _run_state["known_dead_predators"]
        new_dead = [r for r in dead_rows if r["mob_id"] not in known]
        if not new_dead:
            conn.close()
            return

        # See snapshot's prey query — bred children are not is_active=1, so the
        # ecological "live prey count" must omit that filter or we'll undercount.
        cur.execute(
            "SELECT m.position FROM mobs m JOIN mob_health h ON m.mob_id = h.mob_id "
            "WHERE m.mob_type = 'prey' AND h.health > 0"
        )
        prey_positions: list[tuple[float, float]] = []
        for r in cur.fetchall():
            raw = r["position"]
            try:
                p = json.loads(raw) if isinstance(raw, str) else raw
                prey_positions.append((float(p["x"]), float(p["y"])))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue

        for r in new_dead:
            try:
                raw = r["position"]
                p = json.loads(raw) if isinstance(raw, str) else raw
                px, py = float(p["x"]), float(p["y"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                known.add(r["mob_id"])
                continue

            vision = float(r["vision"] or 20.0)

            if prey_positions:
                dists = [math.hypot(qx - px, qy - py) for qx, qy in prey_positions]
                nearest = round(min(dists), 2)
                prey_in_vision = sum(1 for d in dists if d <= vision)
                prey_in_attack = sum(1 for d in dists if d <= PREDATOR_ATTACK_RANGE)
            else:
                nearest = None
                prey_in_vision = 0
                prey_in_attack = 0

            _run_state["predator_death_events"].append({
                "mob_id":               r["mob_id"],
                "tick":                 current_tick,
                "position":             (round(px, 2), round(py, 2)),
                "vision":               round(vision, 1),
                "nearest_prey_dist":    nearest,
                "prey_in_vision":       prey_in_vision,
                "prey_in_attack_range": prey_in_attack,
                "total_live_prey":      len(prey_positions),
            })
            known.add(r["mob_id"])

        conn.close()
    except Exception as e:
        print(f"[sim_runner] WARNING: predator-death capture failed: {e}")


# ---------------------------------------------------------------------------
# Log scanning
# ---------------------------------------------------------------------------

_log_positions: dict[str, int] = {}

def _scan_log_errors(log_path: str) -> list[str]:
    """Return new ERROR/CRITICAL/WARNING/Exception lines since last scan."""
    if not os.path.exists(log_path):
        return []
    pos = _log_positions.get(log_path, 0)
    try:
        with open(log_path, "r", errors="replace") as f:
            f.seek(pos)
            lines = f.readlines()
            _log_positions[log_path] = f.tell()
    except OSError:
        return []
    return [
        l.rstrip() for l in lines
        if re.search(r"ERROR|CRITICAL|WARNING|Exception|Traceback", l, re.IGNORECASE)
    ]


def _death_cause_tally() -> dict:
    """Parse server log for structured death lines and return cause counts."""
    tally = {"starvation": 0, "predation": 0, "old_age": 0, "unknown": 0}
    if not os.path.exists(SERVER_LOG):
        return tally
    cause_re = re.compile(r"died cause=(\S+)")
    try:
        with open(SERVER_LOG, "r", errors="replace") as f:
            for line in f:
                m = cause_re.search(line)
                if m:
                    cause = m.group(1).split()[0]  # strip trailing fields
                    if cause.startswith("predation"):
                        tally["predation"] += 1
                    elif cause.startswith("starvation"):
                        tally["starvation"] += 1
                    elif cause.startswith("old_age"):
                        tally["old_age"] += 1
                    else:
                        tally["unknown"] += 1
    except OSError:
        pass
    return tally


def _tail_log(log_path: str, n: int = 80) -> str:
    """Return last n lines of a log file as a single string."""
    if not os.path.exists(log_path):
        return "(log file not found)"
    try:
        with open(log_path, "r", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except OSError as e:
        return f"(error reading log: {e})"


def _client_reliability_stats() -> dict:
    stats = {"connection_failed": 0, "look_timeouts": 0, "forced_reconnect": 0}
    if not os.path.exists(CLIENT_LOG):
        return stats
    try:
        with open(CLIENT_LOG, "r", errors="replace") as f:
            for line in f:
                if "Connection failed:" in line:
                    stats["connection_failed"] += 1
                if "LOOK_RESULT timeout" in line:
                    stats["look_timeouts"] += 1
                if "forcing reconnect" in line.lower():
                    stats["forced_reconnect"] += 1
    except OSError:
        pass
    return stats


def _error_code_tally() -> dict:
    """Count server error codes seen in client.log.

    Every server ERROR is logged by the client's state manager as
    ``Server error [<CODE>]`` regardless of whether the client could attribute
    it to a specific Mob, so that line is the authoritative per-error signal —
    it includes the *unattributed* errors that never reach Mob.record_error
    (the client logs those only as "Could not attribute error <CODE>").
    Counting it means reliability grading sees the full error volume, not just
    the attributed subset (see ADD-1 in the 2026-06-15 fix plan).

    The older ``Action error recorded: <CODE>`` line is the attributed subset;
    we fall back to it only for logs that predate the ``Server error`` line, so
    no error is double-counted.
    """
    keys = ("MOB_NOT_FOUND", "TARGET_NOT_FOUND", "BREED_FAILED", "other")
    tally = {k: 0 for k in keys}
    fallback = {k: 0 for k in keys}
    if not os.path.exists(CLIENT_LOG):
        return tally
    server_re = re.compile(r"Server error \[([^\]]+)\]")
    action_re = re.compile(r"Action error recorded:\s+(\S+)")
    saw_server_line = False
    try:
        with open(CLIENT_LOG, "r", errors="replace") as f:
            for line in f:
                m = server_re.search(line)
                if m:
                    saw_server_line = True
                    code = m.group(1)
                    tally[code if code in tally else "other"] += 1
                    continue
                m = action_re.search(line)
                if m:
                    code = m.group(1)
                    fallback[code if code in fallback else "other"] += 1
    except OSError:
        pass
    return tally if saw_server_line else fallback


def _load_pressure_summary() -> str:
    """Call analyze_tick_metrics.summarize() on the server log and return a formatted block."""
    try:
        tool_path = os.path.join(WORKSPACE, "tools", "analyze_tick_metrics.py")
        if not os.path.exists(tool_path) or not os.path.exists(SERVER_LOG):
            return "(analyze_tick_metrics.py or server.log not found)"
        spec = importlib.util.spec_from_file_location("analyze_tick_metrics", tool_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        from pathlib import Path
        ticks = mod.parse_log(Path(SERVER_LOG))
        if not ticks:
            return "(no TICK-METRICS lines found in server.log)"
        s = mod.summarize(ticks)
        worst = f"#{s['worst_tick']}" if s["worst_tick"] is not None else "none"
        lines = [
            f"| Ticks analyzed | {s['tick_count']} |",
            f"| Ticks with rejections | {s['ticks_with_rejections']} |",
            f"| Degraded ticks | {s['degraded_ticks']} |",
            f"| Deeply-degraded ticks | {s['deeply_degraded_ticks']} |",
            f"| Worst tick | {worst} ({s['worst_tick_rejections']} rejections) |",
        ]
        total_rej = sum(s.get("total_rej_ws_cap", {}).values())
        total_def = sum(s.get("total_def_budget", {}).values())
        lines.append(f"| Total WS-cap rejections | {total_rej} |")
        lines.append(f"| Total budget deferrals | {total_def} |")
        return "| Metric | Value |\n|--------|-------|\n" + "\n".join(lines)
    except Exception as e:
        return f"(load pressure analysis failed: {e})"


def _performance_metrics() -> dict:
    """Parse server/client logs for lag and fall-behind indicators."""
    metrics = {
        "server_tick_samples": 0,
        "server_tick_ms_avg": 0.0,
        "server_tick_ms_p95": 0.0,
        "server_tick_ms_max": 0.0,
        "server_slow_tick_count": 0,
        "server_slow_tick_ms_max": 0.0,
        "server_action_limit_exceeded": 0,
        "client_tick_samples": 0,
        "client_tick_ms_avg": 0.0,
        "client_tick_ms_p95": 0.0,
        "client_tick_ms_max": 0.0,
        "client_look_ms_avg": 0.0,
        "client_look_ms_p95": 0.0,
        "client_look_ms_max": 0.0,
        "client_action_limit_exceeded": 0,
    }

    server_tick_ms = []
    slow_tick_ms = []
    client_tick_ms = []
    client_look_ms = []

    server_tick_re = re.compile(r"total=(\d+(?:\.\d+)?)ms")
    slow_tick_re = re.compile(r"Slow tick: (\d+(?:\.\d+)?)ms")
    client_tick_re = re.compile(r"\[TICK \d+\] total=(\d+(?:\.\d+)?)ms")
    client_look_re = re.compile(r"look=(\d+(?:\.\d+)?)ms")

    if os.path.exists(SERVER_LOG):
        try:
            with open(SERVER_LOG, "r", errors="replace") as f:
                for line in f:
                    if "[TICK " in line and " total=" in line:
                        m = server_tick_re.search(line)
                        if m:
                            server_tick_ms.append(float(m.group(1)))
                    if "Slow tick:" in line:
                        m = slow_tick_re.search(line)
                        if m:
                            slow_tick_ms.append(float(m.group(1)))
                    if "ACTION_LIMIT_EXCEEDED" in line:
                        metrics["server_action_limit_exceeded"] += 1
        except OSError:
            pass

    if os.path.exists(CLIENT_LOG):
        try:
            with open(CLIENT_LOG, "r", errors="replace") as f:
                for line in f:
                    if "[TICK " in line and " total=" in line:
                        mt = client_tick_re.search(line)
                        if mt:
                            client_tick_ms.append(float(mt.group(1)))
                        ml = client_look_re.search(line)
                        if ml:
                            client_look_ms.append(float(ml.group(1)))
                    if "ACTION_LIMIT_EXCEEDED" in line:
                        metrics["client_action_limit_exceeded"] += 1
        except OSError:
            pass

    def _fill(prefix: str, vals: list[float]):
        if not vals:
            return
        vals_sorted = sorted(vals)
        metrics[f"{prefix}_samples"] = len(vals_sorted)
        metrics[f"{prefix}_ms_avg"] = round(statistics.fmean(vals_sorted), 2)
        metrics[f"{prefix}_ms_max"] = round(vals_sorted[-1], 2)
        p95_idx = max(0, int(0.95 * (len(vals_sorted) - 1)))
        metrics[f"{prefix}_ms_p95"] = round(vals_sorted[p95_idx], 2)

    _fill("server_tick", server_tick_ms)
    _fill("client_tick", client_tick_ms)
    _fill("client_look", client_look_ms)

    metrics["server_slow_tick_count"] = len(slow_tick_ms)
    metrics["server_slow_tick_ms_max"] = round(max(slow_tick_ms), 2) if slow_tick_ms else 0.0

    return metrics



# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------

def _kill(pid: int):
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


# ---------------------------------------------------------------------------
# Obsidian report
# ---------------------------------------------------------------------------

def _next_run_number() -> int:
    result = subprocess.run(
        ["obsidian", "search", "query=run-", "path=Projects/HexGenLife/Runs", "limit=100"],
        capture_output=True, text=True
    )
    existing = [l.strip() for l in result.stdout.splitlines() if "run-" in l]
    nums = []
    for e in existing:
        base = os.path.basename(e).replace(".md", "")
        if base.startswith("run-"):
            try:
                nums.append(int(base[4:]))
            except ValueError:
                pass
    return max(nums, default=0) + 1


def _split_for_argv(text: str, limit: int = 60000) -> list[str]:
    """Split text into contiguous chunks that reassemble exactly, each well
    under the Linux single-argv byte cap (MAX_ARG_STRLEN ~128 KB). Breaks are
    preferred at newline boundaries so a chunk never splits a line (and thus
    never splits a multi-byte UTF-8 char, since '\\n' is a clean ASCII boundary).
    """
    parts: list[str] = []
    start, n = 0, len(text)
    while start < n:
        end = min(start + limit, n)
        if end < n:
            nl = text.rfind("\n", start, end)
            if nl > start:
                end = nl + 1  # keep the newline with this chunk
        parts.append(text[start:end])
        start = end
    return parts or [""]


def _write_obsidian_report(run_num: int, report: str):
    note_name = f"run-{run_num}"
    note_path = f"Projects/HexGenLife/Runs/{note_name}.md"
    # A full report can exceed the 128 KB single-argv limit, which makes
    # `obsidian create content=<report>` fail with E2BIG (errno 7). Write the
    # first chunk via create, then append the remainder chunk-by-chunk.
    chunks = _split_for_argv(report)
    subprocess.run(
        ["obsidian", "create", f"name={note_name}",
         f"path={note_path}", f"content={chunks[0]}", "silent", "overwrite"],
        capture_output=True, text=True
    )
    for chunk in chunks[1:]:
        subprocess.run(
            ["obsidian", "append", f"path={note_path}",
             f"content={chunk}", "inline"],
            capture_output=True, text=True
        )
    print(f"[sim_runner] Report written to Obsidian: {note_path}")


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def _build_report(
    run_num: int,
    timestamp: str,
    duration_s: float,
    snapshots: list[dict],
    phases: list[str],
    log_errors: list[str],
) -> str:
    final = snapshots[-1] if snapshots else {}
    first = snapshots[0] if snapshots else {}
    reliability = _client_reliability_stats()
    perf = _performance_metrics()
    death_tally = _death_cause_tally()
    err_tally = _error_code_tally()

    # Late-run prey health: average prey_health_avg over the trailing snapshots
    # where prey were still alive. None if prey were already extinct.
    late_snaps = [
        s for s in snapshots[-LATE_RUN_SNAPSHOTS:]
        if s.get("prey_alive", 0) > 0
    ]
    late_prey_health = (
        round(statistics.mean(s.get("prey_health_avg", 0) for s in late_snaps), 1)
        if late_snaps else None
    )

    issues = []
    recommendations = []

    grass_total    = final.get("grass_total", 0)
    grass_avg      = final.get("grass_avg", 0)
    grass_depleted = final.get("grass_depleted", 0)
    tiles_total    = final.get("tiles_total", 1) or 1

    if final.get("prey_alive", 0) == 0:
        issues.append("All prey died before the run ended.")
        total_deaths = sum(death_tally.values())
        if total_deaths > 0:
            top = max(death_tally, key=death_tally.get)
            if top == "predation":
                recommendations.append(
                    f"Primary kill cause: predation ({death_tally['predation']} / {total_deaths} deaths). "
                    "Consider reducing predator count, attack_power, or vision range."
                )
            elif top == "starvation":
                if grass_depleted > tiles_total * 0.3:
                    recommendations.append(
                        f"Primary kill cause: starvation ({death_tally['starvation']} / {total_deaths}) "
                        f"with {grass_depleted}/{tiles_total} tiles depleted — grass is scarce. "
                        "Increase DEFAULT_GRASS or slow grass consumption."
                    )
                else:
                    recommendations.append(
                        f"Primary kill cause: starvation ({death_tally['starvation']} / {total_deaths}) "
                        f"but grass supply is fine (avg {grass_avg:.1f}/tile, {grass_depleted} depleted). "
                        "Prey may not be finding grass — check grass_seek_move in brain_registry.py."
                    )
        else:
            recommendations.append(
                "Increase starting prey count or reduce metabolism rates "
                "(metabolism_active / metabolism_resting in constants.py)."
            )
    elif final.get("prey_alive", 0) < 2:
        issues.append("Prey population critically low at end of run.")
        recommendations.append("Tune prey energy gain from eating grass (EAT_GRASS reward).")

    # Explosion detection: population growing well beyond starting count with sustained degraded mode
    max_prey = max((s.get("prey_total", 0) for s in snapshots), default=0)
    start_prey = first.get("prey_total", 0) or 1
    degraded_ticks = sum(1 for s in snapshots if s.get("degraded_mode", 0) > 0)
    if max_prey > start_prey * 5 and degraded_ticks > len(snapshots) * 0.3:
        issues.append(
            f"Population explosion detected: prey peaked at {max_prey} "
            f"({max_prey/start_prey:.0f}× start) with server degraded for "
            f"{degraded_ticks}/{len(snapshots)} poll intervals."
        )
        recommendations.append(
            "Ecosystem is overwhelming the server. Tune breeding thresholds or "
            "predator pressure to limit population growth."
        )

    if final.get("prey_bred", 0) == 0:
        issues.append("No prey breeding occurred during the run.")
        if grass_depleted > tiles_total * 0.3:
            recommendations.append(
                f"No breeding and {grass_depleted}/{tiles_total} tiles depleted — grass is scarce. "
                "Increase DEFAULT_GRASS in constants.py."
            )
        else:
            recommendations.append(
                "Grass supply is adequate; lower the energy threshold for breeding "
                "(evaluate_breed_energy in brain_registry.py)."
            )

    if final.get("eat_grass_events", 0) == 0:
        issues.append("No EAT_GRASS events — prey may not be finding or eating grass.")
        recommendations.append(
            "Check grass_seek_move in brain_registry.py and DEFAULT_GRASS in constants.py."
        )

    if final.get("pred_total", 0) > 0:
        if final.get("pred_alive", 0) == 0:
            issues.append("All predators died before the run ended.")
            if death_tally.get("predation", 0) == 0:
                recommendations.append(
                    "No predation deaths recorded — predators may not be locating prey. "
                    "Check predator vision range (PREDATOR_PHYSICAL_OVERRIDES in constants.py) and hunt logic."
                )
            else:
                recommendations.append(
                    "Consider increasing predator attack_power or reducing prey defense."
                )
        if final.get("pred_bred", 0) == 0:
            issues.append("No predator breeding occurred.")
            recommendations.append(
                "Predators may be spending all energy hunting. "
                "Tune evaluate_breed_energy threshold for predators."
            )
        if final.get("eat_mob_events", 0) == 0:
            issues.append("No EAT_MOB events — predators aren't eating prey corpses.")
            recommendations.append(
                "Check predator eat_mob brain node and ensure predators can find dead prey."
            )
        # Hunt success rate
        attack_ev = final.get("attack_events", 0)
        eat_mob_ev = final.get("eat_mob_events", 0)
        if attack_ev > 0:
            hunt_success = round(100.0 * eat_mob_ev / attack_ev, 1)
            if hunt_success < 10:
                issues.append(
                    f"Hunt success rate very low ({hunt_success}% — {eat_mob_ev} kills / {attack_ev} attacks)."
                )
                recommendations.append(
                    "Predators are attacking but rarely killing. Consider increasing "
                    "attack_power or reducing prey health/defense."
                )

    if final.get("tick", 0) < 50:
        issues.append(f"Tick count very low ({final.get('tick', 0)}) — server may have stalled.")
        recommendations.append("Check server.log for errors. Ensure all clients connected successfully.")

    if log_errors:
        issues.append(f"{len(log_errors)} ERROR/WARNING lines detected in logs during run.")
        recommendations.append("See 'Log Errors' section below for details.")
    if reliability["connection_failed"] > 0 or reliability["look_timeouts"] > 0:
        issues.append(
            f"Client reliability issues detected: {reliability['connection_failed']} connection failures, "
            f"{reliability['look_timeouts']} LOOK timeouts."
        )
        recommendations.append(
            "Review websocket client reconnect handling and server socket capacity under load."
        )

    if perf.get("server_slow_tick_count", 0) > 0:
        issues.append(
            f"Server slow ticks detected: {perf['server_slow_tick_count']} "
            f"(max {perf['server_slow_tick_ms_max']}ms)."
        )
        recommendations.append(
            "Server is falling behind intermittently. Review tick budgets, expensive LOOK paths, "
            "and event broadcast volume under load."
        )

    if perf.get("client_tick_ms_p95", 0) >= 1000 or perf.get("client_look_ms_p95", 0) >= 1000:
        issues.append(
            f"Client tick latency high (p95 total={perf.get('client_tick_ms_p95', 0)}ms, "
            f"p95 look={perf.get('client_look_ms_p95', 0)}ms)."
        )
        recommendations.append(
            "Clients are falling behind the server tick loop. Increase LOOK staggering/throttle and "
            "reduce duplicate same-tick LOOK requests."
        )

    # --- Late-run prey health ---
    if late_prey_health is not None and late_prey_health < LATE_RUN_PREY_HEALTH_WARN:
        issues.append(
            f"Late-run prey health critically low (avg {late_prey_health} over last "
            f"{len(late_snaps)} polls, threshold {LATE_RUN_PREY_HEALTH_WARN})."
        )
        recommendations.append(
            "Prey are starving even where they survive. Increase EAT_GRASS energy reward "
            "or grass regrowth, or reduce prey metabolism."
        )

    # --- Predator/prey ratio (top-heavy ecosystem) ---
    prey_alive_f = final.get("prey_alive", 0)
    pred_alive_f = final.get("pred_alive", 0)
    pred_prey_ratio = (pred_alive_f / prey_alive_f) if prey_alive_f > 0 else None
    if pred_prey_ratio is not None and pred_prey_ratio >= PRED_PREY_RATIO_WARN:
        issues.append(
            f"Predator/prey ratio top-heavy: {pred_alive_f} predators vs {prey_alive_f} prey "
            f"(ratio {pred_prey_ratio:.1f})."
        )
        recommendations.append(
            "Too many predators per prey — reduce starting predators, predator vision, or "
            "predator breeding rate to keep the ecosystem stable."
        )

    # --- Population collapse (boom then crash) ---
    prey_peak = max((s.get("prey_alive", 0) for s in snapshots), default=0)
    if (prey_peak >= COLLAPSE_MIN_PEAK
            and prey_alive_f > 0
            and prey_alive_f <= prey_peak * PREY_COLLAPSE_FRACTION):
        issues.append(
            f"Prey population collapsed: peaked at {prey_peak}, ended at {prey_alive_f} "
            f"(<= {int(PREY_COLLAPSE_FRACTION * 100)}% of peak)."
        )
        recommendations.append(
            "Boom-bust crash with no recovery. Check grass regrowth rate vs herd size and "
            "predator pressure timing."
        )

    # --- Runaway predator growth ---
    start_pred = first.get("pred_total", 0) or 0
    pred_peak = max((s.get("pred_alive", 0) for s in snapshots), default=0)
    if start_pred > 0 and pred_peak >= start_pred * PRED_RUNAWAY_MULT:
        issues.append(
            f"Runaway predator growth: started {start_pred}, peaked at {pred_peak} "
            f"({pred_peak / start_pred:.0f}× start)."
        )
        recommendations.append(
            "Predators are out-breeding their prey supply. Raise the predator breeding energy "
            "threshold or shorten predator lifespan."
        )

    # --- Excessive server-rejected action error codes ---
    for code in ("MOB_NOT_FOUND", "TARGET_NOT_FOUND", "BREED_FAILED"):
        cnt = err_tally.get(code, 0)
        if cnt >= ERR_CODE_WARN:
            sev = "Excessive" if cnt >= ERR_CODE_FAIL else "Elevated"
            issues.append(f"{sev} {code} errors: {cnt} (client.log).")
            recommendations.append(
                f"High {code} count suggests clients act on stale state. Review the brain "
                "target-selection / LOOK freshness path in client/brain_registry.py."
            )

    if not issues:
        issues.append("No critical issues detected.")
        recommendations.append("Simulation appears healthy. Consider longer runs or larger worlds.")

    # -----------------------------------------------------------------------
    # Three-axis verdict (mechanical / ecological / observability)
    # Overall verdict is the worst of the three. See thresholds near top.
    # -----------------------------------------------------------------------
    prey_survived  = final.get("prey_alive", 0) > 0
    pred_present   = final.get("pred_total", 0) > 0
    pred_survived  = final.get("pred_alive", 0) > 0 if pred_present else True
    prey_bred_any  = final.get("prey_bred", 0) > 0
    pred_bred_any  = final.get("pred_bred", 0) > 0 if pred_present else True

    # -- Mechanical: did the simulation machinery run cleanly? --
    crash = any(re.search(r"Traceback|CRITICAL", l, re.IGNORECASE) for l in log_errors)
    mech_verdict = "PASS"
    mech_notes = []
    if not snapshots:
        mech_verdict, mech_notes = "FAIL", ["No snapshots captured — run never produced state."]
    else:
        if final.get("tick", 0) < 50:
            mech_verdict = _worse(mech_verdict, "FAIL")
            mech_notes.append(f"Server barely ticked ({final.get('tick', 0)} ticks) — likely stalled.")
        if crash:
            mech_verdict = _worse(mech_verdict, "FAIL")
            mech_notes.append("Traceback/CRITICAL found in logs.")
        if perf.get("server_slow_tick_count", 0) > 0:
            mech_verdict = _worse(mech_verdict, "WARN")
            mech_notes.append(f"{perf['server_slow_tick_count']} slow server ticks.")
        if log_errors and not crash:
            mech_verdict = _worse(mech_verdict, "WARN")
            mech_notes.append(f"{len(log_errors)} ERROR/WARNING log lines.")
    if not mech_notes:
        mech_notes.append("Server ticked cleanly with no crashes.")

    # -- Ecological: is it a healthy, balanced ecosystem? --
    eco_verdict = "PASS"
    eco_notes = []
    if not prey_survived:
        eco_verdict = _worse(eco_verdict, "FAIL")
        eco_notes.append("Prey went extinct.")
    if (prey_peak >= COLLAPSE_MIN_PEAK and prey_survived
            and prey_alive_f <= prey_peak * PREY_COLLAPSE_FRACTION):
        eco_verdict = _worse(eco_verdict, "FAIL")
        eco_notes.append(f"Prey population collapsed ({prey_peak}→{prey_alive_f}).")
    if pred_prey_ratio is not None and pred_prey_ratio >= PRED_PREY_RATIO_FAIL:
        eco_verdict = _worse(eco_verdict, "FAIL")
        eco_notes.append(f"Predators dwarf prey (ratio {pred_prey_ratio:.1f}).")
    elif pred_prey_ratio is not None and pred_prey_ratio >= PRED_PREY_RATIO_WARN:
        eco_verdict = _worse(eco_verdict, "WARN")
        eco_notes.append(f"Predator/prey ratio top-heavy ({pred_prey_ratio:.1f}).")
    if start_pred > 0 and pred_peak >= start_pred * PRED_RUNAWAY_MULT:
        eco_verdict = _worse(eco_verdict, "FAIL")
        eco_notes.append(f"Runaway predator growth ({start_pred}→{pred_peak}).")
    if late_prey_health is not None and late_prey_health < LATE_RUN_PREY_HEALTH_FAIL:
        eco_verdict = _worse(eco_verdict, "FAIL")
        eco_notes.append(f"Late-run prey health near-zero ({late_prey_health}).")
    elif late_prey_health is not None and late_prey_health < LATE_RUN_PREY_HEALTH_WARN:
        eco_verdict = _worse(eco_verdict, "WARN")
        eco_notes.append(f"Late-run prey health low ({late_prey_health}).")
    if prey_survived and not prey_bred_any:
        eco_verdict = _worse(eco_verdict, "WARN")
        eco_notes.append("No prey breeding occurred.")
    if pred_present and not pred_survived:
        eco_verdict = _worse(eco_verdict, "WARN")
        eco_notes.append("Predators went extinct.")
    if pred_present and pred_survived and not pred_bred_any:
        eco_verdict = _worse(eco_verdict, "WARN")
        eco_notes.append("No predator breeding occurred.")
    if not eco_notes:
        eco_notes.append("Prey and predators survived and bred in balance.")

    # -- Observability / reliability: are clients & logs clean? --
    obs_verdict = "PASS"
    obs_notes = []
    lt = reliability.get("look_timeouts", 0)
    rc = reliability.get("forced_reconnect", 0)
    cf = reliability.get("connection_failed", 0)
    if lt >= LOOK_TIMEOUT_FAIL:
        obs_verdict = _worse(obs_verdict, "FAIL"); obs_notes.append(f"{lt} LOOK timeouts.")
    elif lt >= LOOK_TIMEOUT_WARN:
        obs_verdict = _worse(obs_verdict, "WARN"); obs_notes.append(f"{lt} LOOK timeouts.")
    if rc >= RECONNECT_FAIL:
        obs_verdict = _worse(obs_verdict, "FAIL"); obs_notes.append(f"{rc} forced reconnects.")
    elif rc >= RECONNECT_WARN:
        obs_verdict = _worse(obs_verdict, "WARN"); obs_notes.append(f"{rc} forced reconnects.")
    if cf >= CONN_FAIL_FAIL:
        obs_verdict = _worse(obs_verdict, "FAIL"); obs_notes.append(f"{cf} connection failures.")
    elif cf >= CONN_FAIL_WARN:
        obs_verdict = _worse(obs_verdict, "WARN"); obs_notes.append(f"{cf} connection failures.")
    for code in ("MOB_NOT_FOUND", "TARGET_NOT_FOUND", "BREED_FAILED"):
        cnt = err_tally.get(code, 0)
        if cnt >= ERR_CODE_FAIL:
            obs_verdict = _worse(obs_verdict, "FAIL"); obs_notes.append(f"{cnt} {code}.")
        elif cnt >= ERR_CODE_WARN:
            obs_verdict = _worse(obs_verdict, "WARN"); obs_notes.append(f"{cnt} {code}.")
    if (perf.get("client_tick_ms_p95", 0) >= 1000
            or perf.get("client_look_ms_p95", 0) >= 1000):
        obs_verdict = _worse(obs_verdict, "WARN"); obs_notes.append("High client tick/LOOK latency (p95 ≥ 1s).")
    if not obs_notes:
        obs_notes.append("Clients reliable; logs quiet.")

    # -- Overall = worst of the three axes --
    verdict = _worse(_worse(mech_verdict, eco_verdict), obs_verdict)
    verdict_note = (
        f"mechanical={mech_verdict}, ecological={eco_verdict}, observability={obs_verdict}"
    )
    verdict_breakdown_md = (
        "| Axis | Verdict | Notes |\n"
        "|------|---------|-------|\n"
        f"| Mechanical | {mech_verdict} | {'; '.join(mech_notes)} |\n"
        f"| Ecological | {eco_verdict} | {'; '.join(eco_notes)} |\n"
        f"| Observability / Reliability | {obs_verdict} | {'; '.join(obs_notes)} |\n"
    )

    snap_hdr = (
        "| tick | prey_alive | prey_adult | prey_bred | pred_alive | pred_adult | pred_bred "
        "| prey_hp | prey_hunger | prey_energy | eat_grass | eat_mob | breed | attack "
        "| tiles | tiles_new | spread_avg | spread_max | near_start_% | drift "
        "| q_depth | deferred | degraded |\n"
        "|------|-----------|-----------|-----------|-----------|-----------|-----------|--------|-------------|-------------|-----------|---------|-------|--------|-------|-----------|------------|------------|--------------|-------|---------|----------|----------|\n"
    )
    snap_rows = ""
    for s in snapshots:
        snap_rows += (
            f"| {s.get('tick',0)} "
            f"| {s.get('prey_alive',0)} "
            f"| {s.get('prey_adult',0)} "
            f"| {s.get('prey_bred',0)} "
            f"| {s.get('pred_alive',0)} "
            f"| {s.get('pred_adult',0)} "
            f"| {s.get('pred_bred',0)} "
            f"| {s.get('prey_health_avg',0):.1f} "
            f"| {s.get('prey_hunger_avg',0):.1f} "
            f"| {s.get('prey_energy_avg',0):.1f} "
            f"| {s.get('eat_grass_events',0)} "
            f"| {s.get('eat_mob_events',0)} "
            f"| {s.get('breed_events',0)} "
            f"| {s.get('attack_events',0)} "
            f"| {s.get('tiles_total',0)} "
            f"| {s.get('tiles_generated',0)} "
            f"| {s.get('prey_spread_avg',0):.1f} "
            f"| {s.get('prey_spread_max',0):.1f} "
            f"| {s.get('prey_near_start_pct',0):.1f} "
            f"| {s.get('prey_centroid_drift',0):.1f} "
            f"| {s.get('queue_depth',0)} "
            f"| {s.get('deferred_actions',0)} "
            f"| {s.get('degraded_mode',0)} |\n"
        )

    issues_md = "\n".join(f"- {i}" for i in issues)
    recs_md   = "\n".join(f"- {r}" for r in recommendations)
    phases_md = "\n".join(f"- {p}" for p in phases)

    log_err_section = ""
    if log_errors:
        log_err_section = (
            "\n## Log Errors Detected During Run\n\n"
            "```\n" + "\n".join(log_errors[-60:]) + "\n```\n"
        )

    # Predator death context — only rendered if at least one predator died.
    pred_death_section = ""
    death_events = _run_state.get("predator_death_events", [])
    if death_events:
        in_sight = sum(1 for e in death_events if (e["prey_in_vision"] or 0) > 0)
        in_attack = sum(1 for e in death_events if (e["prey_in_attack_range"] or 0) > 0)
        no_prey  = sum(1 for e in death_events if not e["total_live_prey"])
        rows = "\n".join(
            f"| {e['mob_id']} | {e['tick']} | ({e['position'][0]}, {e['position'][1]}) "
            f"| {e['vision']} "
            f"| {'-' if e['nearest_prey_dist'] is None else e['nearest_prey_dist']} "
            f"| {e['prey_in_vision']} | {e['prey_in_attack_range']} | {e['total_live_prey']} |"
            for e in death_events
        )
        pred_death_section = f"""
## Predator Deaths

**{len(death_events)}** predators died during the run. Of those:
- **{in_sight}** had at least one live prey within vision at the moment of death
- **{in_attack}** had prey within attack range ({PREDATOR_ATTACK_RANGE} units)
- **{no_prey}** died with **no live prey anywhere in the world**

| predator_id | tick (poll) | position | vision | nearest_prey_dist | prey_in_vision | prey_in_attack_range | total_live_prey |
|-------------|-------------|----------|--------|-------------------|----------------|----------------------|-----------------|
{rows}
"""

    server_tail = _tail_log(SERVER_LOG, 80)
    client_tail = _tail_log(CLIENT_LOG, 80)

    # --- Genetics section ---
    TRAIT_LABELS = {
        "speed": "Speed", "vision": "Vision", "attack_power": "Attack",
        "defense": "Defense", "camouflage": "Camouflage", "aging_rate": "Aging rate",
    }
    genetics_rows_prey = ""
    genetics_rows_pred = ""
    for trait, label in TRAIT_LABELS.items():
        f_avg = final.get(f"p_{trait}_avg", 0)
        f_min = final.get(f"p_{trait}_min", 0)
        f_max = final.get(f"p_{trait}_max", 0)
        i_avg = first.get(f"p_{trait}_avg", f_avg)
        drift = round(f_avg - i_avg, 3) if i_avg else 0
        genetics_rows_prey += (
            f"| {label} | {f_min} | {f_avg} | {f_max} | {drift:+.3f} |\n"
        )
        f_avg = final.get(f"d_{trait}_avg", 0)
        f_min = final.get(f"d_{trait}_min", 0)
        f_max = final.get(f"d_{trait}_max", 0)
        i_avg = first.get(f"d_{trait}_avg", f_avg)
        drift = round(f_avg - i_avg, 3) if i_avg else 0
        genetics_rows_pred += (
            f"| {label} | {f_min} | {f_avg} | {f_max} | {drift:+.3f} |\n"
        )

    load_pressure = _load_pressure_summary()

    genetics_section = f"""
## Genetics (final snapshot, alive mobs only)

### Prey traits

| Trait | Min | Avg | Max | Drift (vs start) |
|-------|-----|-----|-----|-----------------|
{genetics_rows_prey}
Generation: avg={final.get('prey_avg_gen', 0)} max={final.get('prey_max_gen', 0)}

### Predator traits

| Trait | Min | Avg | Max | Drift (vs start) |
|-------|-----|-----|-----|-----------------|
{genetics_rows_pred}
Generation: avg={final.get('pred_avg_gen', 0)} max={final.get('pred_max_gen', 0)}
"""

    # --- Death-cause tally ---
    total_deaths = sum(death_tally.values())
    death_section = f"""
## Death Cause Tally

| Cause | Count |
|-------|-------|
| Predation | {death_tally['predation']} |
| Starvation | {death_tally['starvation']} |
| Old age | {death_tally['old_age']} |
| Unknown | {death_tally['unknown']} |
| **Total** | **{total_deaths}** |

Grass at end: total={grass_total} avg/tile={grass_avg} depleted_tiles={grass_depleted}/{tiles_total}
"""

    # --- Hunt success rate ---
    attack_ev  = final.get("attack_events", 0)
    eat_mob_ev = final.get("eat_mob_events", 0)
    hunt_pct   = round(100.0 * eat_mob_ev / attack_ev, 1) if attack_ev > 0 else 0.0

    return f"""---
tags: [hexgenlife, sim-run]
run: {run_num}
timestamp: {timestamp}
duration_seconds: {round(duration_s)}
verdict: {verdict}
verdict_mechanical: {mech_verdict}
verdict_ecological: {eco_verdict}
verdict_observability: {obs_verdict}
---

# HexGenLife Sim Run {run_num}

**Date:** {timestamp}
**Duration:** {round(duration_s / 60, 1)} min
**Verdict:** {verdict} — {verdict_note}

## Verdict Breakdown

{verdict_breakdown_md}

## Phases

{phases_md}

## Metrics Snapshots

{snap_hdr}{snap_rows}

## Final State

| Metric | Value |
|--------|-------|
| Ticks completed | {final.get('tick', 0)} |
| Prey alive | {final.get('prey_alive', 0)} / {final.get('prey_total', 0)} |
| Prey breeding-capable adults | {final.get('prey_adult_strict', 0)} |
| Prey seniors (non-breeding) | {final.get('prey_senior', 0)} |
| Prey bred (born in-sim) | {final.get('prey_bred', 0)} |
| Prey max generation | {final.get('prey_max_gen', 0)} |
| Predators alive | {final.get('pred_alive', 0)} / {final.get('pred_total', 0)} |
| Predator breeding-capable adults | {final.get('pred_adult_strict', 0)} |
| Predator seniors (non-breeding) | {final.get('pred_senior', 0)} |
| Predators bred | {final.get('pred_bred', 0)} |
| Predator max generation | {final.get('pred_max_gen', 0)} |
| Hunt success rate | {hunt_pct}% ({eat_mob_ev} kills / {attack_ev} attacks) |
| Prey health avg/min/max | {final.get('prey_health_avg', 0)} / {final.get('prey_health_min', 0)} / {final.get('prey_health_max', 0)} |
| Prey health late-run avg (last {LATE_RUN_SNAPSHOTS} polls) | {late_prey_health if late_prey_health is not None else 'n/a (prey extinct)'} |
| Predator/prey alive ratio | {f'{pred_prey_ratio:.2f}' if pred_prey_ratio is not None else 'n/a'} |
| Prey hunger avg | {final.get('prey_hunger_avg', 0)} |
| Prey energy avg | {final.get('prey_energy_avg', 0)} |
| Prey fat avg | {final.get('prey_fat_avg', 0)} |
| Predator health avg/min/max | {final.get('pred_health_avg', 0)} / {final.get('pred_health_min', 0)} / {final.get('pred_health_max', 0)} |
| Predator hunger avg | {final.get('pred_hunger_avg', 0)} |
| Predator energy avg | {final.get('pred_energy_avg', 0)} |
| Predator fat avg | {final.get('pred_fat_avg', 0)} |
| Grass total / avg / depleted | {grass_total} / {grass_avg} / {grass_depleted} tiles |
| Client connection failures | {reliability.get('connection_failed', 0)} |
| Client LOOK timeouts | {reliability.get('look_timeouts', 0)} |
| Client forced reconnects | {reliability.get('forced_reconnect', 0)} |
| Action errors: MOB_NOT_FOUND | {err_tally.get('MOB_NOT_FOUND', 0)} |
| Action errors: TARGET_NOT_FOUND | {err_tally.get('TARGET_NOT_FOUND', 0)} |
| Action errors: BREED_FAILED | {err_tally.get('BREED_FAILED', 0)} |
| Action errors: other | {err_tally.get('other', 0)} |
| Server tick samples (log) | {perf.get('server_tick_samples', 0)} |
| Server tick ms avg / p95 / max | {perf.get('server_tick_ms_avg', 0)} / {perf.get('server_tick_ms_p95', 0)} / {perf.get('server_tick_ms_max', 0)} |
| Server slow ticks / max slow ms | {perf.get('server_slow_tick_count', 0)} / {perf.get('server_slow_tick_ms_max', 0)} |
| Server ACTION_LIMIT_EXCEEDED (log) | {perf.get('server_action_limit_exceeded', 0)} |
| Client tick samples (log) | {perf.get('client_tick_samples', 0)} |
| Client tick ms avg / p95 / max | {perf.get('client_tick_ms_avg', 0)} / {perf.get('client_tick_ms_p95', 0)} / {perf.get('client_tick_ms_max', 0)} |
| Client LOOK ms avg / p95 / max | {perf.get('client_look_ms_avg', 0)} / {perf.get('client_look_ms_p95', 0)} / {perf.get('client_look_ms_max', 0)} |
| Client ACTION_LIMIT_EXCEEDED (log) | {perf.get('client_action_limit_exceeded', 0)} |
| Server queue depth (final) | {final.get('queue_depth', 0)} |
| Server deferred actions (final) | {final.get('deferred_actions', 0)} |
| Server degraded mode (final) | {final.get('degraded_mode', 0)} |
| EAT_GRASS events | {final.get('eat_grass_events', 0)} |
| EAT_MOB events | {final.get('eat_mob_events', 0)} |
| BREED events | {final.get('breed_events', 0)} |
| ATTACK events | {final.get('attack_events', 0)} |
| Hex tiles total (final) | {final.get('tiles_total', 0)} |
| Hex tiles generated during run | {final.get('tiles_generated', 0)} |
| Prey starting centroid | ({final.get('start_centroid_x', 0)}, {final.get('start_centroid_y', 0)}) |
| Prey current centroid | ({final.get('prey_centroid_x', 0)}, {final.get('prey_centroid_y', 0)}) |
| Prey centroid drift (world units) | {final.get('prey_centroid_drift', 0)} |
| Prey avg distance from start (final) | {final.get('prey_spread_avg', 0)} |
| Prey max distance from start (final) | {final.get('prey_spread_max', 0)} |
| Prey within {int(SPREAD_NEAR_RADIUS)} units of start (final) | {final.get('prey_near_start_pct', 0)}% |

## Issues Found

{issues_md}

## Recommendations

{recs_md}

## Load / Backpressure (analyze_tick_metrics)

{load_pressure}
{genetics_section}{death_section}{pred_death_section}{log_err_section}
## Server Log (last 80 lines)

```
{server_tail}
```

## Client Log (last 80 lines)

```
{client_tail}
```
"""


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_sim(
    prey: int = 5,
    predators: int = 2,
    max_seconds: int = MAX_SECONDS,
    prey_breed_threshold: int = 1,
):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[sim_runner] Starting sim run at {timestamp}")

    # Reset per-run state so a fresh run starts with a clean centroid + tile baseline.
    _run_state["start_centroid"] = None
    _run_state["start_tile_count"] = None
    _run_state["known_dead_predators"] = set()
    _run_state["predator_death_events"] = []

    server_skill = _load_skill("hexgenlife-server/server_skill.py")
    client_skill = _load_skill("hexgenlife-client/client_skill.py")

    phases:    list[str]  = []
    snapshots: list[dict] = []
    pids:      list[int]  = []
    all_log_errors: list[str] = []

    # 1. Start server
    server_pid = server_skill.start_server(mode="new")
    pids.append(server_pid)
    phases.append(f"Server started (PID {server_pid})")
    print(f"[sim_runner] Waiting 3s for server to initialise...")
    time.sleep(3)

    # Prime scan positions so we only catch errors produced after startup
    _scan_log_errors(SERVER_LOG)
    _scan_log_errors(CLIENT_LOG)

    # 2. Spawn prey
    client_skill.start_clients(mode="new", prey=prey, predators=0)
    phases.append(f"Spawned {prey} prey clients")
    print(f"[sim_runner] Prey clients launched. Monitoring every {POLL_INTERVAL}s...")

    predators_added         = False
    health_critical_noted   = False
    first_eat_noted         = False
    first_prey_adult_noted  = False
    first_pred_adult_noted  = False
    start_time              = time.time()
    last_snap_tick          = -1
    stall_count             = 0       # consecutive polls with no tick advance

    while True:
        elapsed = time.time() - start_time
        if elapsed >= max_seconds:
            phases.append(f"Max time ({max_seconds}s) reached — stopping")
            print("[sim_runner] Time limit reached.")
            break

        time.sleep(POLL_INTERVAL)

        # Scan for new log errors
        for log_path, label in ((SERVER_LOG, "server"), (CLIENT_LOG, "client")):
            errs = _scan_log_errors(log_path)
            if errs:
                all_log_errors.extend(errs)
                phases.append(
                    f"Log errors in {label}.log at tick ~{last_snap_tick}: {errs[0][:80]}"
                )
                for e in errs[:3]:
                    print(f"[sim_runner] LOG {label.upper()}: {e}")

        snap = _snapshot()
        if not snap:
            continue

        # Capture any newly-dead predators with their hunting context.
        _capture_predator_deaths(snap.get("tick", 0))

        # Stall detection: warn if tick doesn't advance across 3 consecutive polls
        if snap.get("tick", 0) == last_snap_tick and last_snap_tick >= 0:
            stall_count += 1
            if stall_count == 3:
                phases.append(
                    f"WARNING: tick stalled at {last_snap_tick} for {stall_count * POLL_INTERVAL}s — server may be hung"
                )
                print(f"[sim_runner] WARNING: tick stalled at {last_snap_tick} for {stall_count * POLL_INTERVAL}s")
        else:
            stall_count = 0

        # Record snapshot only when tick advances
        if snap.get("tick", 0) != last_snap_tick:
            snapshots.append(snap)
            last_snap_tick = snap.get("tick", 0)
            pred_str = ""
            if snap.get("pred_total", 0) > 0:
                pred_str = (
                    f" | pred {snap['pred_alive']}/{snap['pred_total']} "
                    f"adult={snap.get('pred_adult', 0)} "
                    f"hp={snap['pred_health_avg']:.0f} "
                    f"hunger={snap['pred_hunger_avg']:.0f} "
                    f"energy={snap['pred_energy_avg']:.0f}"
                )
            print(
                f"[sim_runner] tick={snap['tick']:4d} "
                f"prey={snap['prey_alive']}/{snap['prey_total']} "
                f"adult={snap.get('prey_adult', 0)} bred={snap['prey_bred']} "
                f"hp={snap['prey_health_avg']:.1f} "
                f"hunger={snap['prey_hunger_avg']:.1f} "
                f"energy={snap['prey_energy_avg']:.1f} "
                f"fat={snap['prey_fat_avg']:.1f} "
                f"eat_grass={snap['eat_grass_events']} "
                f"breed={snap['breed_events']} "
                f"tiles={snap.get('tiles_total', 0)}(+{snap.get('tiles_generated', 0)}) "
                f"spread={snap.get('prey_spread_avg', 0):.1f}/max{snap.get('prey_spread_max', 0):.1f} "
                f"near={snap.get('prey_near_start_pct', 0):.0f}% "
                f"drift={snap.get('prey_centroid_drift', 0):.1f}"
                f"{pred_str}"
            )

        # Phase: first grass eating
        if not first_eat_noted and snap.get("eat_grass_events", 0) > 0:
            phases.append(f"First EAT_GRASS recorded at tick {snap['tick']}")
            first_eat_noted = True

        # Phase: first prey reach adulthood (can now breed)
        if not first_prey_adult_noted and snap.get("prey_adult", 0) > 0:
            phases.append(
                f"First prey reached adulthood at tick {snap['tick']} "
                f"({snap['prey_adult']} adults of {snap['prey_alive']} alive)"
            )
            print(f"[sim_runner] First prey adults at tick {snap['tick']} — breeding now possible.")
            first_prey_adult_noted = True

        # Phase: first predators reach adulthood
        if (not first_pred_adult_noted and snap.get("pred_total", 0) > 0
                and snap.get("pred_adult", 0) > 0):
            phases.append(
                f"First predators reached adulthood at tick {snap['tick']} "
                f"({snap['pred_adult']} adults of {snap['pred_alive']} alive)"
            )
            print(f"[sim_runner] First predator adults at tick {snap['tick']} — predators can now breed.")
            first_pred_adult_noted = True

        # Phase: critically low prey health
        if (not health_critical_noted
                and snap.get("prey_alive", 0) > 0
                and snap.get("prey_health_avg", 100.0) < 20.0):
            phases.append(
                f"WARNING: prey avg health critically low "
                f"({snap['prey_health_avg']:.1f}) at tick {snap['tick']}"
            )
            health_critical_noted = True

        # Early exit: all prey dead
        if snap.get("prey_total", 0) > 0 and snap.get("prey_alive", 0) == 0:
            phases.append("All prey died — ending early")
            print("[sim_runner] All prey dead. Ending early.")
            break

        # Add predators once prey start breeding
        if not predators_added and snap.get("prey_bred", 0) >= prey_breed_threshold:
            print(f"[sim_runner] Prey breeding detected ({snap['prey_bred']} born). Adding predators...")
            client_skill.start_clients(mode="new", prey=0, predators=predators)
            phases.append(f"Added {predators} predator clients at tick {snap['tick']}")
            predators_added = True

    duration = time.time() - start_time

    # 3. Kill server and clients
    print("[sim_runner] Terminating server and clients...")
    for pid in pids:
        _kill(pid)
    subprocess.run(["pkill", "-f", "websocket_client"], capture_output=True)
    subprocess.run(["pkill", "-f", "server.server"],    capture_output=True)
    phases.append("Server and clients terminated")
    time.sleep(1)

    # 4. Build and write report
    run_num = _next_run_number()
    report  = _build_report(run_num, timestamp, duration, snapshots, phases, all_log_errors)
    _write_obsidian_report(run_num, report)
    print(f"[sim_runner] Done. Run #{run_num} report saved.")
    return run_num


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HexGenLife sim runner")
    parser.add_argument("--prey",            type=int, default=5)
    parser.add_argument("--predators",       type=int, default=2)
    parser.add_argument("--max-minutes",     type=int, default=30)
    parser.add_argument("--breed-threshold", type=int, default=1,
                        help="Number of bred prey before predators are added")
    args = parser.parse_args()
    run_sim(
        prey=args.prey,
        predators=args.predators,
        max_seconds=args.max_minutes * 60,
        prey_breed_threshold=args.breed_threshold,
    )
