"""
Phase 4.4 — Brain Function Registry.

Maps function_id strings (from the brain_functions DB table) to callable
Python functions.  Each function has the signature:

    def func(matrix, memory, outputs, mob_state) -> dict

The return dict must contain either:
    {"action": "MOVE_MOB", "payload": {...}}   — emit a server command
    {"matrix": [...], "next": "node_id"}       — pass matrix to next node
    {"matrix": [...], "next": None}            — terminal, no action
"""
import math
import random
import logging

# Configure logging
logger = logging.getLogger("BrainRegistry")

ATTACK_RANGE = 3.0
CARCASS_LOCK_TICKS = 4
CARCASS_TARGET_COOLDOWN_TICKS = 5
# Mirror of server.mob_interactions.MIN_BREED_ENERGY — if these drift,
# the brain may pick partners the server rejects with BREED_FAILED.
MIN_BREED_ENERGY = 40.0
# Ticks a partner is skipped after a BREED_FAILED against them.
BREED_FAIL_COOLDOWN_TICKS = 5
# Ticks a predator stays committed to a specific attacked prey before
# reconsidering — refreshed on each ATTACK_MOB emitted against the same target.
PREDATOR_FOCUS_TICKS = 12
# Hard cap on consecutive attacks against the same focused prey before the
# predator gives up and lets evaluate_attack_target re-pick. Prevents a single
# elusive prey from exhausting the predator while others are nearby.
PREDATOR_FOCUS_MAX_ATTACKS = 8
# A different visible prey must be at least this much closer than the focused
# prey before the predator switches targets. Set high so a predator commits to
# running ONE prey down to the kill: in a dense fleeing swarm a freshly-spooked
# prey is almost always a bit closer than the one we just wounded, and a low
# ratio made predators spread single hits across the whole herd and kill nothing
# (observed: 2 attacks / 0 kills across a run). Only abandon the focused prey if
# another is >4x closer (i.e. the focused one has effectively escaped).
PREDATOR_SWITCH_RATIO = 4.0
# When a predator has no visible prey and no last_prey_pos memory, distances
# beyond this from origin trigger a homeward wander bias instead of random.
PREDATOR_EDGE_RADIUS = 25.0
FLEE_MIN_PERSISTENCE_TICKS = 6
FLEE_STEP_MULTIPLIER = 3.0

# Size-class preference for predator targeting.  Mirrors server's
# LIFE_STAGE_RANK so the brain can decline futile fights — the server still
# processes attacks against any visible mob (with reduced damage), but the
# brain won't *choose* a target it can't realistically bring down before
# exhausting its energy.  Baby predators that find no same-or-smaller prey
# drop through to evaluate_movement and wait for a parent kill instead.
_BRAIN_LIFE_STAGE_RANK = {
    "baby": 0,
    "infant": 1,
    "juvenile": 2,
    "adult": 3,
    "senior": 3,
}


def _brain_stage_rank(stage) -> int:
    return _BRAIN_LIFE_STAGE_RANK.get(stage or "adult", 3)
# Herd instinct is suppressed when the mob's local tile grass falls below this value.
# Prevents cluster pull from overriding the need to disperse when the shared area is depleted.
GRASS_HERD_SUPPRESS_THRESHOLD = 2.0
# Minimum grass value on a tile for it to count as a seek target.
# Tiles below this are ignored when computing the grass movement vector,
# preventing tiny residual grass from anchoring mobs to a depleted area.
GRASS_SEEK_MIN = 1.0
# Minimum grass on the server-nearest tile before the client emits EAT_GRASS.
GRASS_EAT_FLOOR = GRASS_SEEK_MIN


def _visible_mobs(memory):
    look_data = memory.get("last_look", {})
    if not isinstance(look_data, dict):
        return []
    mobs = look_data.get("mobs", [])
    return mobs if isinstance(mobs, list) else []


def _visible_mob_by_id(memory, mob_id):
    return next((m for m in _visible_mobs(memory) if m.get("mobId") == mob_id), None)


def _tick_cooldowns(memory, key):
    cooldowns = memory.get(key)
    if not cooldowns:
        return set()
    for target_id in list(cooldowns):
        cooldowns[target_id] -= 1
        if cooldowns[target_id] <= 0:
            cooldowns.pop(target_id, None)
    if not cooldowns:
        memory.pop(key, None)
        return set()
    return set(cooldowns)


def _set_cooldown(memory, key, target_id, ticks):
    if target_id:
        memory.setdefault(key, {})[target_id] = ticks

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_FUNCTION_REGISTRY: dict[str, callable] = {}


def register(func_id: str):
    """Decorator to register a brain function."""
    def decorator(fn):
        _FUNCTION_REGISTRY[func_id] = fn
        return fn
    return decorator


def get_function(func_id: str):
    """Look up a registered brain function by ID."""
    return _FUNCTION_REGISTRY.get(func_id)


def list_functions() -> list[str]:
    """Return all registered function IDs."""
    return list(_FUNCTION_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Starter brain functions (Phase 4.4)
# ---------------------------------------------------------------------------

@register("evaluate_state")
def evaluate_state(matrix, memory, outputs, mob_state):
    """Root node — builds input matrix from mob's current state.

    Output matrix: [hunger, fat, energy, health]
    Routes to first output if any state is critical, else second.
    """
    hunger = mob_state.get("hunger", 0)
    fat = mob_state.get("fat", 0)
    energy = mob_state.get("energy", 0)
    health = mob_state.get("health", 100)

    state_matrix = [hunger, fat, energy, health]

    # Always check danger first — flee takes priority over all other behavior.
    next_node = outputs[0] if outputs else None

    return {"matrix": state_matrix, "next": next_node}


@register("evaluate_hunger")
def evaluate_hunger(matrix, memory, outputs, mob_state):
    """Check hunger/fat levels. Routes to eat action or movement.

    matrix[0] = hunger, matrix[1] = fat
    If hunger > 3 or fat < 8 → eat (first output)
    Otherwise → continue to movement (second output)
    """
    hunger = matrix[0] if len(matrix) > 0 else 0
    fat = matrix[1] if len(matrix) > 1 else 0

    look_data = memory.get("last_look", {})
    tiles = look_data.get("tiles", [])
    current_tile = min(tiles, key=lambda t: t.get("distance", 999), default=None)
    if current_tile and current_tile.get("distance", 999) > 5.0:
        current_tile = None
    
    physical = mob_state.get("physical", {})
    graze_threshold = physical.get("graze_threshold", 5.0)

    if hunger > 3 or fat < 20:
        # Route to eat — action_eat will move toward grass if not already on a grass tile
        next_node = outputs[0] if outputs else None
    else:
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)

    return {"matrix": matrix, "next": next_node}


@register("evaluate_danger")
def evaluate_danger(matrix, memory, outputs, mob_state):
    """Evaluate nearby threats from LOOK data.

    If a predator is visible and close, flee (first output).
    Otherwise continue (second output).
    """
    look_data = memory.get("last_look", {})
    visible_mobs = _visible_mobs(memory)
    mob_type = mob_state.get("mob_type", "prey")

    # Prey should be wary of predators
    threats = []
    if mob_type == "prey":
        threats = [m for m in visible_mobs
                   if m.get("mob_type") == "predator"
                   and m.get("alive", True)
                   and m.get("distance", 999) < mob_state.get("vision", 10)]

    if threats:
        # Store closest threat in memory for flee logic
        closest = min(threats, key=lambda m: m.get("distance", 999))
        memory["threat"] = closest
        next_node = outputs[0] if outputs else None
    else:
        memory.pop("threat", None)
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)

    return {"matrix": matrix, "next": next_node}


@register("evaluate_movement")
def evaluate_movement(matrix, memory, outputs, mob_state):
    """Decide where to move — toward food, away from danger, or wander.

    Wander vector is a blend of:
      - grass vector: toward the best visible tile with grass > GRASS_SEEK_MIN
      - herd vector: toward centroid of visible same-type mobs (scaled by herd metric)

    Herd instinct is suppressed when the mob's local tile grass is below
    GRASS_HERD_SUPPRESS_THRESHOLD, forcing dispersal rather than cluster pull.
    When both vectors are zero (depleted area, no cluster) the mob takes a
    persistent random wander direction to explore for new grass.
    """
    look_data = memory.get("last_look", {})
    current_pos = mob_state.get("position", {"x": 0, "y": 0})
    if isinstance(current_pos, str):
        import json
        current_pos = json.loads(current_pos)
    cx, cy = current_pos.get("x", 0), current_pos.get("y", 0)

    # If we have a threat, flee — and COMMIT to the escape heading for several
    # ticks. The server caps movement at the mob's own speed/tick, so a prey
    # that holds a straight outward line keeps a constant gap from an
    # equal-speed predator and slips away, while prey that graze or jitter get
    # caught. Persisting the heading (graze_dir + wander_steps) lets a subset
    # of prey disperse to a refuge and survive the predator peak — the escape
    # valve that keeps the boom-bust cycle from going one-way extinct.
    threat = memory.get("threat")
    if threat:
        _phys = mob_state.get("physical", {})
        _persistence = _phys.get("persistence", 5.0)
        _speed = _phys.get("speed", 1.0)
        tx, ty = threat["position"]["x"], threat["position"]["y"]
        dx, dy = cx - tx, cy - ty
        dist = math.sqrt(dx * dx + dy * dy) or 1
        fx, fy = dx / dist, dy / dist
        memory["graze_dir_x"], memory["graze_dir_y"] = fx, fy
        memory["wander_steps"] = int(max(_persistence, FLEE_MIN_PERSISTENCE_TICKS))
        step = max(3.0, _speed * FLEE_STEP_MULTIPLIER)
        move_x = int(cx + fx * step)
        move_y = int(cy + fy * step)
        memory.pop("threat", None)
        return {"action": "MOVE_MOB", "payload": {
            "targetLocation": {"x": move_x, "y": move_y}
        }}

    physical = mob_state.get("physical", {})
    wander_dist = physical.get("wander_dist", 3.0)
    persistence = physical.get("persistence", 5.0)
    hunger = mob_state.get("hunger", matrix[0] if matrix else 0)
    # Suppress herd instinct when starving — survival overrides social behavior
    herd = 0.0 if hunger >= 30 else mob_state.get("herd", physical.get("herd", 0.5))
    # Move faster when starving
    if hunger >= 30:
        wander_dist = max(wander_dist, physical.get("speed", 1.0) * 5.0)
    mob_type = mob_state.get("mob_type", "prey")

    tiles = look_data.get("tiles", [])
    visible_mobs = _visible_mobs(memory)

    # Grass level at the mob's current position (nearest visible tile)
    local_grass = 0.0
    if tiles:
        nearest_tile = min(tiles, key=lambda t: t.get("distance", 999))
        local_grass = nearest_tile.get("grass", 0.0)

    # When local grass is depleted the herd should MIGRATE toward fresh grass
    # together, not scatter: soften (don't kill) cohesion so the grass vector
    # leads the move "out" toward grazing while the mob still stays loosely with
    # the group. The per-mob herd value sets the baseline grass-vs-cohesion
    # balance; this only tilts it toward foraging when there's nothing to eat
    # underfoot. Emergent result: a few prey heading for ungrazed tiles pull the
    # rest along via the (reduced but live) cohesion vector.
    depleted_local_grass = local_grass < GRASS_HERD_SUPPRESS_THRESHOLD
    if depleted_local_grass:
        herd *= 0.5

    # --- Grass vector: toward highest-grass visible tile above seek minimum ---
    gvx, gvy = 0.0, 0.0
    if tiles:
        best = max(tiles, key=lambda t: t.get("grass", 0))
        if best.get("grass", 0) >= GRASS_SEEK_MIN:
            dx, dy = best["centerX"] - cx, best["centerY"] - cy
            d = math.sqrt(dx*dx + dy*dy) or 1
            gvx, gvy = dx/d, dy/d

    # --- Herd vector: toward centroid of visible same-type mobs ---
    hvx, hvy = 0.0, 0.0
    same_type = [m for m in visible_mobs if m.get("mob_type") == mob_type]
    if same_type and herd > 0:
        avg_x = sum(m["position"]["x"] for m in same_type) / len(same_type)
        avg_y = sum(m["position"]["y"] for m in same_type) / len(same_type)
        dx, dy = avg_x - cx, avg_y - cy
        d = math.sqrt(dx*dx + dy*dy) or 1
        hvx, hvy = dx/d, dy/d

    # Predators: skip grass seeking; pursue last known prey position instead
    if mob_type == "predator":
        gvx, gvy = 0.0, 0.0
        # If we have a live focus_target but lost last_prey_pos (e.g. cleared
        # by reaching the spot), bias movement back toward the last known
        # focus position so the predator continues searching for that prey.
        focus = memory.get("focus_target")
        if focus and focus.get("ticks_remaining", 0) > 0 and not memory.get("last_prey_pos"):
            memory["last_prey_pos"] = dict(focus["position"])
            memory["pursue_steps"] = max(memory.get("pursue_steps", 0), 20)
        last_prey = memory.get("last_prey_pos")
        pursue_steps = memory.get("pursue_steps", 0)
        if last_prey and pursue_steps > 0:
            tx, ty = last_prey["x"], last_prey["y"]
            dx, dy = tx - cx, ty - cy
            dist = math.sqrt(dx*dx + dy*dy) or 1
            if dist >= 2.0:
                memory["pursue_steps"] = pursue_steps - 1
                speed = physical.get("speed", 1.5)
                # Active pursuit: stride 3× speed so the predator can actually
                # close on prey that's flagged in vision but past attack range.
                # Run-23 showed predator_4 dying with 8 prey at 9 units away —
                # the previous 2× stride couldn't catch them.
                step = max(wander_dist, speed * 3)
                move_x = int(cx + (dx/dist) * step)
                move_y = int(cy + (dy/dist) * step)
                return {"action": "MOVE_MOB", "payload": {
                    "targetLocation": {"x": move_x, "y": move_y}
                }}
            else:
                memory.pop("last_prey_pos", None)
                memory["pursue_steps"] = 0
        elif last_prey:
            # Active pursuit exhausted — keep a passive directional bias toward
            # the last known prey area until we get close enough to clear it.
            tx, ty = last_prey["x"], last_prey["y"]
            dx, dy = tx - cx, ty - cy
            dist = math.sqrt(dx*dx + dy*dy) or 1
            if dist >= 5.0:
                gvx, gvy = dx/dist, dy/dist
            else:
                memory.pop("last_prey_pos", None)
        else:
            # No prey signal. A baby/juvenile predator is a poor hunter, so it
            # tags along with the nearest visible ADULT predator to scavenge
            # that adult's kills until it matures. (LOOK carries other mobs'
            # mob_type + life_stage.)
            self_stage = mob_state.get("life_stage", "adult")
            if _brain_stage_rank(self_stage) < 3:
                adults = [m for m in visible_mobs
                          if m.get("mob_type") == "predator"
                          and m.get("alive", True)
                          and _brain_stage_rank(m.get("life_stage", "adult")) >= 3
                          and m.get("distance", 0) > 0]
                if adults:
                    nearest_adult = min(adults, key=lambda m: m.get("distance", 999))
                    ax = nearest_adult["position"]["x"]
                    ay = nearest_adult["position"]["y"]
                    ddx, ddy = ax - cx, ay - cy
                    dd = math.sqrt(ddx*ddx + ddy*ddy) or 1
                    # Trail at a small following gap rather than stacking on the
                    # adult, so the cub is on hand when the adult makes a kill.
                    if dd > 3.0:
                        gvx, gvy = ddx/dd, ddy/dd
            # No adult to follow either — if we've wandered to the map edge,
            # bias back toward origin (spawn region, where prey are likely)
            # instead of doubling down on a random outward direction.
            if gvx == 0 and gvy == 0:
                dist_from_origin = math.sqrt(cx*cx + cy*cy)
                if dist_from_origin > PREDATOR_EDGE_RADIUS:
                    d = dist_from_origin or 1
                    gvx, gvy = -cx/d, -cy/d

    # --- Blend vectors: grass weighted by (1-herd), herd weighted by herd ---
    # If no usable grass and herd is suppressed, fall back to persistent wander
    if gvx == 0 and gvy == 0 and hvx == 0 and hvy == 0:
        # Pure wander with persistence
        wander_steps = memory.get("wander_steps", 0)
        graze_dir_x = memory.get("graze_dir_x")
        graze_dir_y = memory.get("graze_dir_y")
        if graze_dir_x is None or wander_steps <= 0:
            angle = random.uniform(0, 2 * math.pi)
            graze_dir_x = math.cos(angle)
            graze_dir_y = math.sin(angle)
            memory["graze_dir_x"] = graze_dir_x
            memory["graze_dir_y"] = graze_dir_y
            memory["wander_steps"] = int(persistence)
        else:
            memory["wander_steps"] = wander_steps - 1
        bx, by = graze_dir_x, graze_dir_y
    else:
        grass_weight = 1.0 - herd
        herd_weight = herd
        if depleted_local_grass and (gvx != 0 or gvy != 0):
            grass_weight = max(grass_weight, 0.85)
            herd_weight = min(herd_weight, 0.15)
        bx = gvx * grass_weight + hvx * herd_weight
        by = gvy * grass_weight + hvy * herd_weight
        # Normalize blend
        bd = math.sqrt(bx*bx + by*by) or 1
        bx, by = bx/bd, by/bd
        memory["graze_dir_x"] = bx
        memory["graze_dir_y"] = by
        memory["wander_steps"] = int(persistence)

    move_x = int(cx + bx * wander_dist)
    move_y = int(cy + by * wander_dist)
    return {"action": "MOVE_MOB", "payload": {
        "targetLocation": {"x": move_x, "y": move_y}
    }}


@register("action_eat")
def action_eat(matrix, memory, outputs, mob_state):
    """Emit EAT_GRASS if the server-nearest tile has viable grass; otherwise move to grass.

    The server's EAT_GRASS handler picks the single tile whose center is
    closest to the mob's position and rejects with NO_GRASS if its grass is 0.
    Mirroring that predicate here prevents the brain from emitting EAT_GRASS
    when a closer (but bare) tile would be chosen server-side.
    """
    look_data = memory.get("last_look", {})
    tiles = look_data.get("tiles", [])

    # No LOOK data — fall through to a speculative EAT.
    if not tiles:
        return {"action": "EAT_GRASS", "payload": {}}

    server_nearest = min(tiles, key=lambda t: t.get("distance", 999))
    if server_nearest.get("grass", 0) >= GRASS_EAT_FLOOR:
        return {"action": "EAT_GRASS", "payload": {}}

    grass_tiles = [t for t in tiles if t.get("grass", 0) >= GRASS_EAT_FLOOR]
    if not grass_tiles:
        return evaluate_movement(matrix, memory, outputs, mob_state)

    nearest_grass = max(grass_tiles, key=lambda t: (t.get("grass", 0), -t.get("distance", 999)))
    return {"action": "MOVE_MOB", "payload": {
        "targetLocation": {"x": int(nearest_grass["centerX"]), "y": int(nearest_grass["centerY"])}
    }}


@register("action_move")
def action_move(matrix, memory, outputs, mob_state):
    """Emit MOVE_MOB command — delegates to evaluate_movement logic."""
    return evaluate_movement(matrix, memory, outputs, mob_state)


@register("action_look")
def action_look(matrix, memory, outputs, mob_state):
    """Emit LOOK command."""
    return {"action": "LOOK", "payload": {}}


@register("evaluate_attack_target")
def evaluate_attack_target(matrix, memory, outputs, mob_state):
    """Predator: evaluate if there's a viable attack target nearby.

    If prey is visible and close enough → attack (first output).
    Otherwise → continue (second output).

    Honors memory["focus_target"] set by action_attack: a previously-attacked
    prey is preferred over closer alternatives unless another prey is at least
    PREDATOR_SWITCH_RATIO closer.  Focus expires after PREDATOR_FOCUS_TICKS
    without a refresh, or PREDATOR_FOCUS_MAX_ATTACKS consecutive attacks
    without a kill.  When the focused prey is out of vision but focus is still
    live, last_prey_pos is repopulated so evaluate_movement continues pursuit.
    """
    visible_mobs = _visible_mobs(memory)

    # Decay focus each tick. action_attack refreshes ticks_remaining whenever
    # an attack is actually emitted against the focused mob.
    focus = memory.get("focus_target")
    if focus:
        focus["ticks_remaining"] = focus.get("ticks_remaining", 0) - 1
        if (focus["ticks_remaining"] <= 0
                or focus.get("consecutive_attacks", 0) >= PREDATOR_FOCUS_MAX_ATTACKS):
            memory.pop("focus_target", None)
            focus = None

    # If we have a recent carcass target, don't thrash back into hunt routing.
    if memory.get("carcass_lock_ticks", 0) > 0 and memory.get("eat_target"):
        memory["carcass_lock_ticks"] = memory.get("carcass_lock_ticks", 0) - 1
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)
        return {"matrix": matrix, "next": next_node}

    # Visible prey within vision range.  Size-class is enforced TWICE:
    #   1. Server-side: attacks on larger prey deal exponentially reduced
    #      damage (a baby vs adult is ~6%).  Allowed by the world.
    #   2. Brain-side (here): we filter to same-or-smaller targets so the
    #      brain won't *choose* a futile fight that would exhaust energy.
    # If no viable target exists we drop through to evaluate_movement —
    # better to wander and wait for a parent kill than starve in a chase.
    self_rank = _brain_stage_rank(mob_state.get("life_stage", "adult"))
    in_sight = [m for m in visible_mobs
                if m.get("mob_type") == "prey"
                and m.get("alive", True)
                and m.get("distance", 999) < mob_state.get("vision", 15)]
    targets = [m for m in in_sight
               if _brain_stage_rank(m.get("life_stage", "adult")) <= self_rank]

    if not targets:
        memory.pop("attack_target", None)
        memory.pop("target_in_range", None)
        # No prey is a viable *attack* target (any in sight are a larger
        # size-class), but if we can see prey at all we should hold near it —
        # loiter to scavenge a kill or pick off a straggler rather than
        # wandering off. Anchor pursuit to the focused prey's last spot, else
        # the nearest visible prey, so evaluate_movement heads toward / holds
        # near it instead of reverting to random wander.
        anchor = None
        if focus and focus.get("ticks_remaining", 0) > 2:
            anchor = dict(focus["position"])
        elif in_sight:
            nearest_seen = min(in_sight, key=lambda m: m.get("distance", 999))
            anchor = dict(nearest_seen["position"])
        if anchor:
            memory["last_prey_pos"] = anchor
            memory["pursue_steps"] = max(memory.get("pursue_steps", 0), 20)
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)
        return {"matrix": matrix, "next": next_node}

    chosen = None
    if focus:
        focused = next((m for m in targets if m.get("mobId") == focus["mobId"]), None)
        if focused:
            closest = min(targets, key=lambda m: m.get("distance", 999))
            focused_dist = focused.get("distance", 999)
            closest_dist = closest.get("distance", 999)
            # Stick with the focused prey unless another is clearly closer.
            if closest is focused or closest_dist * PREDATOR_SWITCH_RATIO >= focused_dist:
                chosen = focused
            else:
                # A much closer prey came into view — abandon focus and switch.
                memory.pop("focus_target", None)
                focus = None
                chosen = closest
    if chosen is None:
        chosen = min(targets, key=lambda m: m.get("distance", 999))

    memory["attack_target"] = chosen
    in_range = chosen.get("distance", 999) <= ATTACK_RANGE
    memory["target_in_range"] = in_range
    memory["last_prey_pos"] = dict(chosen["position"])
    memory["pursue_steps"] = 80
    # Commit to THIS prey while closing. Focus normally starts on the first
    # landed attack, but with attack-only-in-range a predator may chase for many
    # ticks before it can strike — and in a dense prey field, re-picking the
    # nearest target every tick makes it zig-zag and never close (observed: a
    # whole run with 0 attacks). Set/refresh focus now so the predator runs down
    # one prey instead of the swarm. (consecutive_attacks stays 0 until an actual
    # hit, so the anti-exhaustion cap only counts landed blows.)
    cur_focus = memory.get("focus_target")
    if cur_focus and cur_focus.get("mobId") == chosen.get("mobId"):
        cur_focus["ticks_remaining"] = PREDATOR_FOCUS_TICKS
        cur_focus["position"] = dict(chosen["position"])
    else:
        memory["focus_target"] = {
            "mobId": chosen.get("mobId"),
            "position": dict(chosen["position"]),
            "ticks_remaining": PREDATOR_FOCUS_TICKS,
            "consecutive_attacks": 0,
        }
    if in_range:
        # In reach — attack. Energy is only spent on blows that land.
        next_node = outputs[0] if outputs else None
    else:
        # Out of reach — a lazy, energy-conserving predator doesn't swing at
        # nothing. Close the gap via evaluate_movement (which pursues
        # last_prey_pos), then attack once in range.
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)
    return {"matrix": matrix, "next": next_node}


@register("action_attack")
def action_attack(matrix, memory, outputs, mob_state):
    """Emit ATTACK_MOB against the prey stored in memory.

    evaluate_attack_target only routes here when the target is within
    ATTACK_RANGE — predators conserve energy by closing distance rather than
    swinging from afar (each hit costs energy and many hunts fail).
    evaluate_eat_carcass handles moving to and eating the resulting carcass.

    Also refreshes memory["focus_target"] so the predator stays committed to
    this prey through brief vision loss but bails after too many attacks
    without a kill (anti-exhaustion).
    """
    target = memory.get("attack_target")
    if not target:
        return evaluate_movement(matrix, memory, outputs, mob_state)

    target_id = target["mobId"]
    current = _visible_mob_by_id(memory, target_id)
    if current is None:
        memory.pop("attack_target", None)
        memory.pop("target_in_range", None)
        focus = memory.get("focus_target")
        if focus and focus.get("mobId") == target_id:
            focus["ticks_remaining"] = min(focus.get("ticks_remaining", 0), 2)
        return evaluate_movement(matrix, memory, outputs, mob_state)
    if not current.get("alive", True):
        memory.pop("attack_target", None)
        memory.pop("target_in_range", None)
        memory["eat_target"] = current
        memory["carcass_lock_ticks"] = CARCASS_LOCK_TICKS
        return evaluate_eat_carcass(matrix, memory, ["action_eat_mob", "evaluate_movement"], mob_state)
    if current.get("mob_type") != "prey" or current.get("distance", 999) > ATTACK_RANGE:
        memory["attack_target"] = current
        memory["target_in_range"] = False
        return evaluate_movement(matrix, memory, outputs, mob_state)

    target = current
    target_pos = dict(target.get("position", {"x": 0, "y": 0}))
    focus = memory.get("focus_target")
    if focus and focus.get("mobId") == target_id:
        focus["ticks_remaining"] = PREDATOR_FOCUS_TICKS
        focus["consecutive_attacks"] = focus.get("consecutive_attacks", 0) + 1
        focus["position"] = target_pos
    else:
        memory["focus_target"] = {
            "mobId": target_id,
            "position": target_pos,
            "ticks_remaining": PREDATOR_FOCUS_TICKS,
            "consecutive_attacks": 1,
        }

    return {"action": "ATTACK_MOB", "payload": {"targetId": target_id}}


@register("evaluate_eat_carcass")
def evaluate_eat_carcass(matrix, memory, outputs, mob_state):
    """Predator: check for dead prey nearby and eat if found.

    Routes to first output (action_eat_mob) if a dead prey is within ATTACK_RANGE.
    Routes to second output (evaluate_hunt) otherwise.
    """
    visible_mobs = _visible_mobs(memory)
    cooldown_ids = _tick_cooldowns(memory, "carcass_cooldown")

    # Detect any visible dead prey — action_eat_mob handles moving to it
    dead_prey = [m for m in visible_mobs
                 if m.get("mob_type") == "prey"
                 and not m.get("alive", True)
                 and m.get("mobId") not in cooldown_ids]

    if dead_prey:
        closest = min(dead_prey, key=lambda m: m.get("distance", 999))
        memory["eat_target"] = closest
        memory["carcass_lock_ticks"] = CARCASS_LOCK_TICKS
        memory["last_prey_pos"] = dict(closest["position"])
        next_node = outputs[0] if outputs else None
    else:
        memory.pop("eat_target", None)
        memory["carcass_lock_ticks"] = 0
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)

    return {"matrix": matrix, "next": next_node}


@register("action_eat_mob")
def action_eat_mob(matrix, memory, outputs, mob_state):
    """Emit EAT_MOB targeting the dead prey stored in memory by evaluate_eat_carcass."""
    target = memory.get("eat_target")
    if not target:
        return evaluate_movement(matrix, memory, outputs, mob_state)

    target_id = target.get("mobId")
    current = _visible_mob_by_id(memory, target_id)
    if (current is None
            or current.get("mob_type") != "prey"
            or current.get("alive", True)):
        memory.pop("eat_target", None)
        memory["carcass_lock_ticks"] = 0
        _set_cooldown(memory, "carcass_cooldown", target_id, CARCASS_TARGET_COOLDOWN_TICKS)
        return evaluate_movement(matrix, memory, outputs, mob_state)

    target = current
    # Give a little tolerance to improve consume conversion after a kill.
    eat_range = ATTACK_RANGE + 1.0
    if target.get("distance", 999) > eat_range:
        tx, ty = target["position"]["x"], target["position"]["y"]
        return {"action": "MOVE_MOB", "payload": {
            "targetLocation": {"x": int(tx), "y": int(ty)}
        }}

    memory.pop("eat_target", None)
    memory["carcass_lock_ticks"] = 0
    return {"action": "EAT_MOB", "payload": {"targetId": target["mobId"]}}


@register("evaluate_flee")
def evaluate_flee(matrix, memory, outputs, mob_state):
    """Move away from the nearest threat (stored in memory by evaluate_danger)."""
    return evaluate_movement(matrix, memory, outputs, mob_state)


@register("evaluate_breed_energy")
def evaluate_breed_energy(matrix, memory, outputs, mob_state):
    """Gate breeding path using live fitness when available.

    Routes to first output (find_partner) when the mob is potentially
    breedable. find_partner and the server remain authoritative.
    Passes matrix through unchanged.
    """
    energy = mob_state.get("energy", 0)
    life_stage = mob_state.get("life_stage", "")
    health = mob_state.get("health", 100)
    fitness = mob_state.get("fitnessScore")
    if fitness is not None:
        can_breed = fitness > 0.0
    else:
        can_breed = energy >= MIN_BREED_ENERGY and health >= 80 and life_stage == "adult"

    if can_breed:
        next_node = outputs[0] if outputs else None
    else:
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)

    return {"matrix": matrix, "next": next_node}


@register("find_partner")
def find_partner(matrix, memory, outputs, mob_state):
    """Scan LOOK data for the closest visible, alive, same-type mob.

    Routes to first output (action_breed) if a partner is found and stores
    it in memory["breed_target"].  Routes to second output (evaluate_movement)
    if no suitable partner exists or the caller is not an adult.
    Passes matrix through unchanged.
    """
    # 2.2 — short-circuit if not adult
    if mob_state.get("life_stage", "") != "adult":
        memory.pop("breed_target", None)
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)
        return {"matrix": matrix, "next": next_node}

    # 2.3 — read LOOK data, handle missing keys gracefully
    last_look = memory.get("last_look", {})
    mobs = last_look.get("mobs", []) if isinstance(last_look, dict) else []

    cooldown_ids = _tick_cooldowns(memory, "breed_cooldown")

    # 2.4 — filter candidates using the live server-side fitness gate.
    my_type = mob_state.get("mob_type", "")
    vision = mob_state.get("vision", 10.0)
    candidates = [
        m for m in mobs
        if m.get("mob_type") == my_type
        and m.get("alive") is True
        and m.get("distance", float("inf")) <= vision
        and m.get("mobId") not in cooldown_ids
        and m.get("fitnessScore", 0.0) > 0.0
    ]

    # 2.5 — no candidates
    if not candidates:
        memory.pop("breed_target", None)
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)
        return {"matrix": matrix, "next": next_node}

    # 2.6 — store best candidate, route to first output
    best = max(candidates, key=lambda m: (m.get("fitnessScore", 0.0), -m.get("distance", float("inf"))))
    memory["breed_target"] = best
    next_node = outputs[0] if outputs else None
    return {"matrix": matrix, "next": next_node}


@register("action_breed")
def action_breed(matrix, memory, outputs, mob_state):
    """Emit BREED_MOB if partner is within ATTACK_RANGE, else move toward partner.

    Falls back to evaluate_movement if no breed_target is stored in memory.
    Clears memory["breed_target"] after emitting BREED_MOB.
    """
    target = memory.get("breed_target")

    # No target — fall back to movement logic
    if target is None:
        return evaluate_movement(matrix, memory, outputs, mob_state)

    target_id = target.get("mobId")
    current = _visible_mob_by_id(memory, target_id)
    if (current is None
            or current.get("alive") is not True
            or current.get("mob_type") != mob_state.get("mob_type")
            or current.get("fitnessScore", 0.0) <= 0.0):
        memory.pop("breed_target", None)
        if current is None:
            _set_cooldown(memory, "breed_cooldown", target_id, 1)
        return evaluate_movement(matrix, memory, outputs, mob_state)

    if current.get("distance", float("inf")) <= ATTACK_RANGE:
        memory.pop("breed_target", None)
        return {"action": "BREED_MOB", "payload": {"targetId": current["mobId"]}}
    else:
        memory["breed_target"] = current
        tp = current["position"]
        return {"action": "MOVE_MOB", "payload": {"targetLocation": {"x": int(tp["x"]), "y": int(tp["y"])}}}
