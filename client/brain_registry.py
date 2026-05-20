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
# Herd instinct is suppressed when the mob's local tile grass falls below this value.
# Prevents cluster pull from overriding the need to disperse when the shared area is depleted.
GRASS_HERD_SUPPRESS_THRESHOLD = 2.0
# Minimum grass value on a tile for it to count as a seek target.
# Tiles below this are ignored when computing the grass movement vector,
# preventing tiny residual grass from anchoring mobs to a depleted area.
GRASS_SEEK_MIN = 1.0

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
    visible_mobs = look_data.get("mobs", [])
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

    # If we have a threat, move away from it
    threat = memory.get("threat")
    if threat:
        tx, ty = threat["position"]["x"], threat["position"]["y"]
        dx, dy = cx - tx, cy - ty
        dist = math.sqrt(dx * dx + dy * dy) or 1
        move_x = int(cx + (dx / dist) * 3)
        move_y = int(cy + (dy / dist) * 3)
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
    visible_mobs = look_data.get("mobs", [])

    # Grass level at the mob's current position (nearest visible tile)
    local_grass = 0.0
    if tiles:
        nearest_tile = min(tiles, key=lambda t: t.get("distance", 999))
        local_grass = nearest_tile.get("grass", 0.0)

    # Suppress herd when local grass is depleted — mob must disperse to find food
    if local_grass < GRASS_HERD_SUPPRESS_THRESHOLD:
        herd = 0.0

    # --- Grass vector: toward highest-grass visible tile above seek minimum ---
    gvx, gvy = 0.0, 0.0
    if tiles:
        best = max(tiles, key=lambda t: t.get("grass", 0))
        if best.get("grass", 0) > GRASS_SEEK_MIN:
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
        last_prey = memory.get("last_prey_pos")
        pursue_steps = memory.get("pursue_steps", 0)
        if last_prey and pursue_steps > 0:
            tx, ty = last_prey["x"], last_prey["y"]
            dx, dy = tx - cx, ty - cy
            dist = math.sqrt(dx*dx + dy*dy) or 1
            if dist >= 2.0:
                memory["pursue_steps"] = pursue_steps - 1
                move_x = int(cx + (dx/dist) * wander_dist)
                move_y = int(cy + (dy/dist) * wander_dist)
                return {"action": "MOVE_MOB", "payload": {
                    "targetLocation": {"x": move_x, "y": move_y}
                }}
            else:
                memory.pop("last_prey_pos", None)
                memory["pursue_steps"] = 0

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
        bx = gvx * (1.0 - herd) + hvx * herd
        by = gvy * (1.0 - herd) + hvy * herd
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
    """Emit EAT_GRASS if standing on a grass tile, otherwise move to the nearest grass tile center."""
    look_data = memory.get("last_look", {})
    tiles = look_data.get("tiles", [])
    grass_tiles = [t for t in tiles if t.get("grass", 0) > 0]

    if not grass_tiles:
        # No grass visible — wander to find some
        return evaluate_movement(matrix, memory, outputs, mob_state)

    nearest = min(grass_tiles, key=lambda t: t.get("distance", 999))

    # Move toward the grass tile center until within inradius (4.33).
    # This ensures the mob is standing on the grass tile before eating.
    if nearest.get("distance", 999) > 4.33:
        return {"action": "MOVE_MOB", "payload": {
            "targetLocation": {"x": int(nearest["centerX"]), "y": int(nearest["centerY"])}
        }}

    return {"action": "EAT_GRASS", "payload": {}}


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
    """
    look_data = memory.get("last_look", {})
    visible_mobs = look_data.get("mobs", [])
    mob_type = mob_state.get("mob_type", "predator")

    targets = [m for m in visible_mobs
               if m.get("mob_type") == "prey"
               and m.get("alive", True)
               and m.get("distance", 999) < mob_state.get("vision", 15)]

    if targets:
        closest = min(targets, key=lambda m: m.get("distance", 999))
        memory["attack_target"] = closest
        memory["target_in_range"] = closest.get("distance", 999) <= ATTACK_RANGE
        memory["last_prey_pos"] = dict(closest["position"])
        memory["pursue_steps"] = 20
        next_node = outputs[0] if outputs else None
    else:
        memory.pop("attack_target", None)
        memory.pop("target_in_range", None)
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)

    return {"matrix": matrix, "next": next_node}


@register("action_attack")
def action_attack(matrix, memory, outputs, mob_state):
    """Emit ATTACK_MOB command targeting the mob stored in memory."""
    target = memory.get("attack_target")
    if not target:
        # No target, just wander
        return evaluate_movement(matrix, memory, outputs, mob_state)

    # If NOT in range, move toward the target instead of attacking
    if not memory.get("target_in_range"):
        tx, ty = target["position"]["x"], target["position"]["y"]
        logger.debug(f"Target {target['mobId']} out of range. Moving toward ({tx}, {ty})")
        return {"action": "MOVE_MOB", "payload": {
            "targetLocation": {"x": int(tx), "y": int(ty)}
        }}

    return {"action": "ATTACK_MOB", "payload": {
        "targetId": target["mobId"],
    }}


@register("evaluate_eat_carcass")
def evaluate_eat_carcass(matrix, memory, outputs, mob_state):
    """Predator: check for dead prey nearby and eat if found.

    Routes to first output (action_eat_mob) if a dead prey is within ATTACK_RANGE.
    Routes to second output (evaluate_hunt) otherwise.
    """
    look_data = memory.get("last_look", {})
    visible_mobs = look_data.get("mobs", [])

    dead_prey = [m for m in visible_mobs
                 if m.get("mob_type") == "prey"
                 and not m.get("alive", True)
                 and m.get("distance", 999) <= ATTACK_RANGE]

    if dead_prey:
        closest = min(dead_prey, key=lambda m: m.get("distance", 999))
        memory["eat_target"] = closest
        next_node = outputs[0] if outputs else None
    else:
        memory.pop("eat_target", None)
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)

    return {"matrix": matrix, "next": next_node}


@register("action_eat_mob")
def action_eat_mob(matrix, memory, outputs, mob_state):
    """Emit EAT_MOB targeting the dead prey stored in memory by evaluate_eat_carcass."""
    target = memory.get("eat_target")
    if not target:
        return evaluate_movement(matrix, memory, outputs, mob_state)

    if target.get("distance", 999) > ATTACK_RANGE:
        tx, ty = target["position"]["x"], target["position"]["y"]
        return {"action": "MOVE_MOB", "payload": {
            "targetLocation": {"x": int(tx), "y": int(ty)}
        }}

    memory.pop("eat_target", None)
    return {"action": "EAT_MOB", "payload": {"targetId": target["mobId"]}}


@register("evaluate_flee")
def evaluate_flee(matrix, memory, outputs, mob_state):
    """Move away from the nearest threat (stored in memory by evaluate_danger)."""
    return evaluate_movement(matrix, memory, outputs, mob_state)


@register("evaluate_breed_energy")
def evaluate_breed_energy(matrix, memory, outputs, mob_state):
    """Gate breeding path — check energy and life stage.

    Routes to first output (find_partner) if energy >= 70 and life_stage == "adult".
    Routes to second output (evaluate_danger_check) otherwise.
    Passes matrix through unchanged.
    """
    energy = mob_state.get("energy", 0)
    life_stage = mob_state.get("life_stage", "")
    health = mob_state.get("health", 100)

    # Require energy >= 45 (above server MIN_BREED_ENERGY=40; energy caps at 50 from eating)
    # Also require health >= 80 so injured mobs don't breed
    if energy >= 45 and life_stage == "adult" and health >= 80:
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

    # 2.4 — filter candidates
    my_type = mob_state.get("mob_type", "")
    vision = mob_state.get("vision", 10.0)
    candidates = [
        m for m in mobs
        if m.get("mob_type") == my_type
        and m.get("alive") is True
        and m.get("distance", float("inf")) <= vision
    ]

    # 2.5 — no candidates
    if not candidates:
        memory.pop("breed_target", None)
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)
        return {"matrix": matrix, "next": next_node}

    # 2.6 — store closest candidate, route to first output
    closest = min(candidates, key=lambda m: m.get("distance", float("inf")))
    memory["breed_target"] = closest
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

    if target["distance"] <= ATTACK_RANGE:
        memory.pop("breed_target", None)
        return {"action": "BREED_MOB", "payload": {"targetId": target["mobId"]}}
    else:
        tp = target["position"]
        return {"action": "MOVE_MOB", "payload": {"targetLocation": {"x": int(tp["x"]), "y": int(tp["y"])}}}
