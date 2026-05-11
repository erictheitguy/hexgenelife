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
    "aging_rate": 0.25,
    "herd": 0.5,          # 0.0 = solitary, 1.0 = strong herd instinct
}
DEFAULT_MOB_HEALTH_EXT = {
    "energy": 50.0,
    "life_stage": "adult",   # baby | juvenile | adult | senior
    "birth_tick": 0.0,
    "max_age": 500.0,
}
# Default starter decision tree — full prey tree with breeding path
DEFAULT_DECISION_TREE = {
    "root": "evaluate_state",
    "nodes": {
        "evaluate_state": {
            "function": "evaluate_state",
            "outputs": ["evaluate_hunger", "evaluate_breed_energy"]
        },
        "evaluate_hunger": {
            "function": "evaluate_hunger",
            "outputs": ["action_eat", "evaluate_breed_energy"]
        },
        "evaluate_breed_energy": {
            "function": "evaluate_breed_energy",
            "outputs": ["find_partner", "evaluate_danger_check"]
        },
        "find_partner": {
            "function": "find_partner",
            "outputs": ["action_breed", "evaluate_movement"]
        },
        "action_breed": {
            "function": "action_breed",
            "outputs": []
        },
        "evaluate_danger_check": {
            "function": "evaluate_danger",
            "outputs": ["evaluate_flee", "evaluate_movement"]
        },
        "evaluate_flee": {
            "function": "evaluate_flee",
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
            "outputs": ["evaluate_hunger_pred", "evaluate_eat_carcass"]
        },
        "evaluate_hunger_pred": {
            "function": "evaluate_hunger",
            "outputs": ["evaluate_eat_carcass", "evaluate_eat_carcass"]
        },
        "evaluate_eat_carcass": {
            "function": "evaluate_eat_carcass",
            "outputs": ["action_eat_mob", "evaluate_breed_energy"]
        },
        "action_eat_mob": {
            "function": "action_eat_mob",
            "outputs": []
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
