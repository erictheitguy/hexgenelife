# create random amount of mob

import datetime
from pymongo import *
import random
import string
import theory.create_hex

# =============================================================================
# TRAIT SYSTEM FOUNDATION - Phase 1
# =============================================================================

# Trait definitions with types, ranges, and inheritance modes
TRAIT_TYPES = {
    "speed": {
        "description": "Movement speed",
        "min": 1,
        "max": 10,
        "default": 5,
        "inherit_mode": "additive",  # additive, dominant, recessive
        "mutation_rate": 0.05,  # ±5% per generation
        "mutation_variance": 0.1  # ±10% additional variance
    },
    "size": {
        "description": "Physical size (affects resource consumption)",
        "min": 1,
        "max": 10,
        "default": 5,
        "inherit_mode": "additive",
        "mutation_rate": 0.05,
        "mutation_variance": 0.1
    },
    "strength": {
        "description": "Physical strength (affects combat, carrying)",
        "min": 1,
        "max": 10,
        "default": 5,
        "inherit_mode": "additive",
        "mutation_rate": 0.05,
        "mutation_variance": 0.1
    },
    "camouflage": {
        "description": "Blending into environment (prey advantage)",
        "min": 1,
        "max": 10,
        "default": 5,
        "inherit_mode": "additive",
        "mutation_rate": 0.08,
        "mutation_variance": 0.15
    },
    "hunting_skill": {
        "description": "Ability to catch prey (predator advantage)",
        "min": 1,
        "max": 10,
        "default": 5,
        "inherit_mode": "additive",
        "mutation_rate": 0.05,
        "mutation_variance": 0.1
    },
    "tracking_range": {
        "description": "Detection radius for targets",
        "min": 1,
        "max": 50,
        "default": 15,
        "inherit_mode": "additive",
        "mutation_rate": 0.05,
        "mutation_variance": 0.1
    },
    "reproduction_rate": {
        "description": "Frequency of reproduction attempts",
        "min": 1,
        "max": 10,
        "default": 5,
        "inherit_mode": "additive",
        "mutation_rate": 0.05,
        "mutation_variance": 0.1
    },
    "metabolism_rate": {
        "description": "Energy consumption rate (higher = faster burning)",
        "min": 1,
        "max": 10,
        "default": 5,
        "inherit_mode": "additive",
        "mutation_rate": 0.05,
        "mutation_variance": 0.1
    }
}

# Inheritance mode definitions
INHERITANCE_MODES = {
    "additive": "Both parents contribute equally to offspring traits",
    "dominant": "One parent's traits dominate (simplified: first parent)",
    "recessive": "Traits only expressed if both parents have them (simplified: average)"
}

# Inheritance modes with descriptions
INHERITANCE_MODES_DESC = {
    "additive": "Both parents contribute equally",
    "dominant": "Dominant traits from parents",
    "recessive": "Recessive traits only when both parents carry them"
}

def id_generator(id_size=8, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(id_size))

client = MongoClient('candygram', 27017)
db_map = client.map
hex_tiles_collection = db_map.hex_tiles
db_mob = client.mob
mob_info_collection = db_mob.grasseater

# =============================================================================
# EXTENDED MOB SCHEMA
# =============================================================================
# New fields added:
# - mob_type: "prey" | "predator" | "grass_eater"
# - generation: integer tracking evolutionary generation
# - parent_ids: array of parent mob IDs (up to 2)
# - genome: object with base trait values (genetic code)
# - actual_traits: object with modified trait values (post-mutation)
# - fitness_score: survival/reproduction metric

number_to_create = 5


for i in range(1, number_to_create):
    # Determine mob type based on generation (generation 0 = grass_eater, gen 1+ can be prey/predator)
    if i == 1:
        mob_type = "grass_eater"
    else:
        # Randomly assign prey or predator for generations 1+
        mob_type = random.choice(["prey", "predator"])
    
    # get random starting location
    total_hexes = hex_tiles_collection.find().count()
    random_tile_number = random.randint(0, (total_hexes - 1))
    random_tile = hex_tiles_collection.find().skip(random_tile_number).limit(-1)

    # we should offset these some random point inside random hexagon
    # to help remove chances of creating two on top of each other
    rand_diff1 = random.randint(-5, 5)
    rand_diff2 = random.randint(-5, 5)
    mx = random_tile[0]["centerX"]
    my = random_tile[0]["centerY"]

    # in case we insert on edge hex
    theory.create_hex.create_surrounding_hex(mx, my, 10)

    mx += rand_diff1
    my += rand_diff2

    # starting value for hunger, energy, fat will change once mob born and it starts to live
    # really only determine its starting actions

    rand_hunger = random.randint(0, 100)
    hunger = rand_hunger  # value 0 through 100


    rand_energy = random.randint(0, 100)
    energy = rand_energy  # value 0 through 100

    rand_fat = random.randint(0, 100)
    fat = rand_fat  # value 0 through 100

    size = 1  # size determines how much grass we remove each bite

    # age well how old it is...
    age = 0
    # eyesight determines how far away it can look for food and mobs
    # higher the better
    rand_eyesight = random.randint(0, 30)
    eyesight = rand_eyesight  # value 0 through 30
    if eyesight < 10:
        rand_eyesight = random.randint(0, 30)
        eyesight = (eyesight + rand_eyesight) / 2  # lets give it slightly better chance

    # herd instinct determines its need to find others like itself
    # also how close it feels it needs to be
    rand_herd_instinct = random.randint(0, 100)
    mob_herd_instinct = rand_herd_instinct  # value 0 through 100

    # =============================================================================
    # TRAIT SYSTEM INITIALIZATION
    # =============================================================================
    
    # Generate base genome (genetic code)
    genome = {}
    actual_traits = {}
    
    # For first generation, generate completely random traits
    if i == 1:
        parent_ids = []
        generation = 0
        # Generate base genome values
        for trait_name, trait_info in TRAIT_TYPES.items():
            genome[trait_name] = random.randint(trait_info["min"], trait_info["max"])
        
        # Apply initial mutation (first generation gets slight mutation)
        for trait_name in genome:
            if random.random() < TRAIT_TYPES[trait_name]["mutation_rate"]:
                mutation = random.uniform(-TRAIT_TYPES[trait_name]["mutation_variance"], 
                                           TRAIT_TYPES[trait_name]["mutation_variance"])
                genome[trait_name] = max(TRAIT_TYPES[trait_name]["min"], 
                                        min(TRAIT_TYPES[trait_name]["max"],
                                            int(genome[trait_name] + mutation)))
        
        # Copy genome to actual_traits (no modification yet)
        actual_traits = dict(genome)
        
    else:
        # For non-first generation, create simple parent references
        # In future versions, this will properly track parents
        parent_ids = [id_generator(6), id_generator(6)]  # Placeholder parent IDs
        
        generation = random.randint(1, 10)  # Fake generation counter
        
        # For now, generate traits similarly to first generation
        # In future, this will use inherit_traits() function
        for trait_name, trait_info in TRAIT_TYPES.items():
            genome[trait_name] = random.randint(trait_info["min"], trait_info["max"])
        
        # Apply mutations
        for trait_name in genome:
            if random.random() < TRAIT_TYPES[trait_name]["mutation_rate"]:
                mutation = random.uniform(-TRAIT_TYPES[trait_name]["mutation_variance"], 
                                           TRAIT_TYPES[trait_name]["mutation_variance"])
                genome[trait_name] = max(TRAIT_TYPES[trait_name]["min"], 
                                        min(TRAIT_TYPES[trait_name]["max"],
                                            int(genome[trait_name] + mutation)))
        
        # Copy genome to actual_traits
        actual_traits = dict(genome)
    
    # Calculate initial fitness score (simple: based on trait diversity)
    fitness_score = sum(actual_traits.values()) / len(actual_traits)

    # Convert mob_type string to schema format
    mob_type_schema = {
        "grass_eater": "grass_eater",
        "prey": "prey",
        "predator": "predator"
    }.get(mob_type, "grass_eater")

    new_mob = {
        "mob_id": id_generator(),
        "mXY": [mx, my],
        "mX": mx,
        "mY": my,
        "hunger": hunger,
        "energy": energy,
        "fat": fat,
        "size": size,
        "eyesight": eyesight,
        "mob_type": mob_type_schema,
        "mob_herd": mob_herd_instinct,
        "age": age,
        "generation": generation,
        "parent_ids": parent_ids,
        "genome": genome,
        "actual_traits": actual_traits,
        "fitness_score": fitness_score,
        "Created": datetime.datetime.utcnow()
    }

    mob_id = mob_info_collection.insert(new_mob)
    print(f"Mob {mob_id}: Type={mob_type}, Gen={generation}, Fitness={fitness_score:.2f}")
    print(f"  Genome: {genome}")
    print(f"  Traits: {actual_traits}")

print("\n=== Trait System Initialization Complete ===")
print(f"Added {number_to_create - 1} mobs with genetic traits")
print("Available traits:")
for trait_name, trait_info in TRAIT_TYPES.items():
    print(f"  - {trait_name}: {trait_info['description']} (range: {trait_info['min']}-{trait_info['max']})")
print("\nInheritance modes:")
for mode, desc in INHERITANCE_MODES.items():
    print(f"  - {mode}: {desc}")