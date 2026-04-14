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

logging.basicConfig(level=logging.INFO)

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

    # If hunger is high or fat/energy is low → first output (hunger check)
    if hunger > 5 or fat < 5 or energy < 10:
        next_node = outputs[0] if outputs else None
    else:
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)

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

    # Check if there's food nearby from LOOK data in memory
    look_data = memory.get("last_look", {})
    tiles = look_data.get("tiles", [])
    has_grass_nearby = any(t.get("grass", 0) > 0 for t in tiles)

    if (hunger > 3 or fat < 8) and has_grass_nearby:
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

    Emits a MOVE_MOB action.
    """
    look_data = memory.get("last_look", {})
    current_pos = mob_state.get("position", {"x": 0, "y": 0})
    cx, cy = current_pos.get("x", 0), current_pos.get("y", 0)

    # If we have a threat, move away from it
    threat = memory.get("threat")
    if threat:
        tx, ty = threat["position"]["x"], threat["position"]["y"]
        dx, dy = cx - tx, cy - ty
        dist = math.sqrt(dx * dx + dy * dy) or 1
        # Normalize and move away
        move_x = int(cx + (dx / dist) * 3)
        move_y = int(cy + (dy / dist) * 3)
        memory.pop("threat", None)
        return {"action": "MOVE_MOB", "payload": {
            "targetLocation": {"x": move_x, "y": move_y}
        }}

    # If hungry, move toward grass
    hunger = matrix[0] if len(matrix) > 0 else 0
    tiles = look_data.get("tiles", [])
    grass_tiles = [t for t in tiles if t.get("grass", 0) > 0 and t.get("distance", 0) > 0]

    if hunger > 3 and grass_tiles:
        closest_grass = min(grass_tiles, key=lambda t: t.get("distance", 999))
        move_x = int(closest_grass["centerX"])
        move_y = int(closest_grass["centerY"])
        return {"action": "MOVE_MOB", "payload": {
            "targetLocation": {"x": move_x, "y": move_y}
        }}

    # Otherwise wander randomly
    move_x = cx + random.randint(-3, 3)
    move_y = cy + random.randint(-3, 3)
    return {"action": "MOVE_MOB", "payload": {
        "targetLocation": {"x": int(move_x), "y": int(move_y)}
    }}


@register("action_eat")
def action_eat(matrix, memory, outputs, mob_state):
    """Emit EAT_GRASS command."""
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
               and m.get("distance", 999) < mob_state.get("vision", 10) * 0.5]

    if targets:
        closest = min(targets, key=lambda m: m.get("distance", 999))
        memory["attack_target"] = closest
        next_node = outputs[0] if outputs else None
    else:
        memory.pop("attack_target", None)
        next_node = outputs[1] if len(outputs) > 1 else (outputs[0] if outputs else None)

    return {"matrix": matrix, "next": next_node}


@register("action_attack")
def action_attack(matrix, memory, outputs, mob_state):
    """Emit ATTACK_MOB command targeting the mob stored in memory."""
    target = memory.get("attack_target")
    if not target:
        # No target, just wander
        return evaluate_movement(matrix, memory, outputs, mob_state)

    return {"action": "ATTACK_MOB", "payload": {
        "targetId": target["mobId"],
    }}


@register("evaluate_flee")
def evaluate_flee(matrix, memory, outputs, mob_state):
    """Move away from the nearest threat (stored in memory by evaluate_danger)."""
    return evaluate_movement(matrix, memory, outputs, mob_state)
