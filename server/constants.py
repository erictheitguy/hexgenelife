import os
import math

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

# --- Phase 2 Constants & Hex Math ---
HEX_RADIUS = 5.0
HEX_CREATION_BROADCAST_RANGE = 100.0
DEFAULT_WATER = 5.0
DEFAULT_GRASS = 3.0
ATTACK_RANGE = 3.0


# --- Phase 4.1 Mob defaults ---
DEFAULT_MOB_PHYSICAL = {
    "size": 1.0,
    "speed": 1.0,
    "mass": 1.0,
    "vision": 20.0,
    "metabolism_active": 1.5,
    "metabolism_resting": 0.5,
    "diet_type": 0.0,        # 0.0 = herbivore, 1.0 = carnivore
    "attack_power": 1.0,
    "defense": 1.0,
    "camouflage": 0.5,       # 0.0 = fully visible, 1.0 = fully hidden
    "graze_threshold": 5.0,
    "wander_dist": 3.0,
    "persistence": 5.0,
    "aging_rate": 0.125,
    "herd": 0.5,          # 0.0 = solitary, 1.0 = strong herd instinct
}
DEFAULT_MOB_HEALTH_EXT = {
    "energy": 50.0,
    "life_stage": "adult",   # baby | juvenile | adult | senior
    "birth_tick": 0.0,
    "max_age": 500.0,
}

# Predator-specific physical overrides — these are the *actual* tuning surface
# for predator balance.  DEFAULT_MOB_PHYSICAL applies to prey; predators get
# these values merged on top before any per-spawn physical_overrides are applied.
PREDATOR_PHYSICAL_OVERRIDES = {
    "diet_type": 1.0,
    "attack_power": 3.2,
    "speed": 1.6,
    "vision": 26.0,
    "aging_rate": 0.3,
    "metabolism_resting": 0.35,
}

# --- Size class by life stage ---
# Used by attack damage scaling: a mob attacking a target of higher size
# class deals exponentially reduced damage (a baby predator clawing at an
# adult deer can keep trying, but it'll exhaust its energy long before the
# target's health drops meaningfully). senior collapses to adult — size
# doesn't shrink with age in this model.
LIFE_STAGE_RANK = {
    "baby": 0,
    "infant": 1,
    "juvenile": 2,
    "adult": 3,
    "senior": 3,
}

# Per-rank-gap damage multiplier when attacker is smaller than target.
# Gap of 1 → 0.4×, gap of 2 → 0.16×, gap of 3 (baby vs adult) → 0.064×.
SIZE_GAP_DAMAGE_FALLOFF = 0.4


def life_stage_rank(stage) -> int:
    return LIFE_STAGE_RANK.get(stage or "adult", 3)


def attack_size_factor(attacker_stage, target_stage) -> float:
    """Damage multiplier reflecting attacker vs target size class.

    Returns 1.0 when attacker is at least as large as target (no penalty);
    falls off exponentially when attacker is smaller, so a baby attacking an
    adult inflicts ~6% of normal damage. This expresses the size mismatch as
    a physics property of the world rather than a brain rule — any mob can
    try to attack any other, but the attempt won't always be productive.
    """
    gap = life_stage_rank(target_stage) - life_stage_rank(attacker_stage)
    if gap <= 0:
        return 1.0
    return SIZE_GAP_DAMAGE_FALLOFF ** gap
# Default starter decision tree — full prey tree with breeding path
DEFAULT_DECISION_TREE = {
    "root": "evaluate_state",
    "nodes": {
        "evaluate_state": {
            "function": "evaluate_state",
            "outputs": ["evaluate_danger_check", "evaluate_hunger"]
        },
        "evaluate_danger_check": {
            "function": "evaluate_danger",
            "outputs": ["evaluate_flee", "evaluate_hunger"]
        },
        "evaluate_flee": {
            "function": "evaluate_flee",
            "outputs": []
        },
        "evaluate_hunger": {
            "function": "evaluate_hunger",
            "outputs": ["action_eat", "evaluate_breed_energy"]
        },
        "evaluate_breed_energy": {
            "function": "evaluate_breed_energy",
            "outputs": ["find_partner", "evaluate_movement"]
        },
        "find_partner": {
            "function": "find_partner",
            "outputs": ["action_breed", "evaluate_movement"]
        },
        "action_breed": {
            "function": "action_breed",
            "outputs": []
        },
        "evaluate_movement": {
            "function": "evaluate_movement",
            "outputs": []
        },
        "action_eat": {
            "function": "action_eat",
            "outputs": []
        }
    }
}

DEFAULT_PREDATOR_DECISION_TREE = {
    "root": "evaluate_state",
    "nodes": {
        "evaluate_state": {
            "function": "evaluate_state",
            "outputs": ["evaluate_eat_carcass", "evaluate_eat_carcass"]
        },
        "evaluate_eat_carcass": {
            "function": "evaluate_eat_carcass",
            "outputs": ["action_eat_mob", "evaluate_hunger_pred"]
        },
        "action_eat_mob": {
            "function": "action_eat_mob",
            "outputs": []
        },
        "evaluate_hunger_pred": {
            "function": "evaluate_hunger",
            "outputs": ["evaluate_hunt", "evaluate_breed_energy"]
        },
        "evaluate_breed_energy": {
            "function": "evaluate_breed_energy",
            "outputs": ["find_partner", "evaluate_hunt"]
        },
        "evaluate_hunt": {
            "function": "evaluate_attack_target",
            "outputs": ["action_attack", "evaluate_movement"]
        },
        "find_partner": {
            "function": "find_partner",
            "outputs": ["action_breed", "evaluate_hunt"]
        },
        "action_breed": {
            "function": "action_breed",
            "outputs": []
        },
        "evaluate_movement": {
            "function": "evaluate_movement",
            "outputs": []
        },
        "action_attack": {
            "function": "action_attack",
            "outputs": []
        },
    }
}

def flat_top_corner(center_x, center_y, size, i):
    angle_deg = 60 * i
    angle_rad = math.pi / 180 * angle_deg
    return [center_x + size * math.cos(angle_rad), center_y + size * math.sin(angle_rad)]

def get_hex_corners(center_x, center_y, size):
    corners = []
    for i in range(6):
        corners.append(flat_top_corner(center_x, center_y, size, i))
    corners.append(corners[0]) # close polygon
    return corners

def pixel_to_axial_flat_top(x, y, size):
    q = (2.0/3.0 * x) / size
    r = (-1.0/3.0 * x + math.sqrt(3)/3.0 * y) / size
    # axial rounding
    frac_q, frac_r = q, r
    frac_s = -frac_q - frac_r
    q = round(frac_q)
    r = round(frac_r)
    s = round(frac_s)
    q_diff = abs(q - frac_q)
    r_diff = abs(r - frac_r)
    s_diff = abs(s - frac_s)
    if q_diff > r_diff and q_diff > s_diff:
        q = -r - s
    elif r_diff > s_diff:
        r = -q - s
    return q, r

def axial_to_pixel_flat_top(q, r, size):
    x = size * 3.0/2.0 * q
    y = size * math.sqrt(3) * (r + q/2.0)
    return x, y

def point_in_polygon(x, y, polygon):
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if min(p1y, p2y) < y <= max(p1y, p2y):
            if x <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside
