# =============================================================================
# TRAIT MANAGER CORE FUNCTIONS
# =============================================================================
# Core trait management functions for the ecological simulation trait system.
# Implements inheritance, mutation, fitness calculation, and trait resolution.
# =============================================================================

import random
import sys
import os

# Handle both direct execution and module import
if __name__ == "__main__":
    # When run directly, we need to import from the parent theory package
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from trait_definitions import (
        TRAIT_TYPES, 
        INHERITANCE_MODES, 
        INHERITANCE_MODES_DESC,
        get_trait_config,
        get_inheritance_mode,
        validate_trait_value
    )
else:
    # Normal module import when used as part of the package
    from .trait_definitions import (
        TRAIT_TYPES, 
        INHERITANCE_MODES, 
        INHERITANCE_MODES_DESC,
        get_trait_config,
        get_inheritance_mode,
        validate_trait_value
    )

# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def inherit_traits(parent1, parent2, trait_name, mode="additive"):
    """
    Combine parent genes to produce offspring trait value.
    
    This function implements the inheritance logic based on the specified mode.
    It takes trait values from both parents and combines them according to the
    inheritance mode rules.
    
    Args:
        parent1: Dictionary containing parent 1's trait values and metadata
        parent2: Dictionary containing parent 2's trait values and metadata
        trait_name: Name of the trait to inherit (e.g., "speed", "size")
        mode: Inheritance mode ("additive", "dominant", "recessive")
        
    Returns:
        Integer or float: Combined trait value for offspring
        
    Example:
        >>> parent1 = {"speed": 8, "actual_traits": {"speed": 8}}
        >>> parent2 = {"speed": 4, "actual_traits": {"speed": 4}}
        >>> inherit_traits(parent1, parent2, "speed", "additive")
        6.0
    """
    # Ensure both parents have the trait
    if trait_name not in parent1 or trait_name not in parent2:
        raise ValueError(f"Trait '{trait_name}' not found in one or both parents")
    
    parent1_value = parent1[trait_name]
    parent2_value = parent2[trait_name]
    
    # Get inheritance mode configuration
    mode_config = get_inheritance_mode(mode)
    formula = mode_config["formula"]
    
    # Calculate based on inheritance mode
    if mode == "additive":
        # Both parents contribute equally
        offspring_value = (parent1_value + parent2_value) / 2
    elif mode == "dominant":
        # First parent's traits dominate (weighted 70% parent1, 30% parent2)
        offspring_value = parent1_value + (parent2_value - parent1_value) * 0.3
    elif mode == "recessive":
        # Second parent's traits dominate (weighted 70% parent2, 30% parent1)
        offspring_value = parent2_value + (parent1_value - parent2_value) * 0.3
    else:
        raise ValueError(f"Unknown inheritance mode: {mode}")
    
    # Round to nearest integer (traits are discrete)
    return int(round(offspring_value))


def mutate(genome, mutation_rate=0.05, trait_name=None):
    """
    Apply random mutations to a genome or individual trait.
    
    Mutations are probabilistic and unpredictable, enabling natural genetic variation.
    Each mutation is random with no deterministic seed, allowing for natural diversity.
    
    Args:
        genome: Dictionary containing trait values to mutate
        mutation_rate: Probability of mutation per trait (0.0 to 1.0)
        trait_name: Optional specific trait to mutate (if None, mutates all traits)
        
    Returns:
        Dictionary: Mutated genome with updated trait values
        
    Example:
        >>> genome = {"speed": 5, "size": 3, "strength": 7}
        >>> mutated_genome = mutate(genome, mutation_rate=0.1)
        >>> print(mutated_genome)
        {'speed': 4, 'size': 3, 'strength': 7}  # speed mutated
    """
    # Create a copy of the genome to avoid mutating the original
    mutated_genome = dict(genome)
    
    # Determine which traits to mutate
    traits_to_mutate = [trait_name] if trait_name else list(genome.keys())
    
    for trait_name in traits_to_mutate:
        # Check if trait exists and get its configuration
        if trait_name not in mutated_genome:
            continue
            
        trait_config = get_trait_config(trait_name)
        
        # Check if mutation should occur (random, no deterministic seed)
        if random.random() < trait_config["mutation_rate"]:
            # Apply mutation with variance range
            mutation_value = random.uniform(
                -trait_config["mutation_variance"], 
                trait_config["mutation_variance"]
            )
            
            # Apply mutation to trait value
            new_value = mutated_genome[trait_name] + mutation_value
            
            # Clamp to valid range
            mutated_genome[trait_name] = max(
                trait_config["min"], 
                min(trait_config["max"], int(new_value))
            )
    
    return mutated_genome


def calculate_fitness(mob, survival_metrics=None):
    """
    Compute fitness score for a mob based on traits and survival metrics.
    
    Fitness represents the overall survival and reproductive potential of a mob.
    Higher fitness scores indicate better adaptation to the environment.
    
    Args:
        mob: Dictionary containing mob data including actual_traits
        survival_metrics: Optional dictionary with survival metrics:
            - "alive": Boolean indicating if mob is currently alive
            - "age": Integer age of the mob
            - "reproduced": Boolean if mob has reproduced
            - "offspring_count": Integer number of offspring produced
            - "survival_time": Integer number of time steps survived
            If None, default survival metrics are used.
            
    Returns:
        Float: Fitness score (higher = better)
        
    Example:
        >>> mob = {"actual_traits": {"speed": 8, "hunting_skill": 7, "strength": 6}}
        >>> fitness = calculate_fitness(mob)
        >>> print(fitness)
        7.0
    """
    # Default survival metrics if not provided
    if survival_metrics is None:
        survival_metrics = {
            "alive": True,
            "age": 0,
            "reproduced": False,
            "offspring_count": 0,
            "survival_time": 0
        }
    
    # Get actual traits
    actual_traits = mob.get("actual_traits", {})
    
    # Base fitness from average trait values
    if not actual_traits:
        return 0.0
    
    avg_trait_value = sum(actual_traits.values()) / len(actual_traits)
    
    # Survival bonus
    survival_bonus = 0
    if survival_metrics.get("alive", False):
        survival_bonus = 1.0
    if survival_metrics.get("age", 0) > 5:
        survival_bonus += 0.1  # Bonus for surviving past initial period
    if survival_metrics.get("survival_time", 0) > 10:
        survival_bonus += 0.2  # Bonus for long survival
    
    # Reproduction bonus
    reproduction_bonus = 0
    if survival_metrics.get("reproduced", False):
        reproduction_bonus = 2.0
    offspring_count = survival_metrics.get("offspring_count", 0)
    if offspring_count > 0:
        reproduction_bonus += offspring_count * 0.5
    
    # Calculate final fitness score
    fitness = (avg_trait_value + survival_bonus + reproduction_bonus)
    
    # Normalize to 0-100 scale
    fitness = min(100.0, max(0.0, fitness * 10))
    
    return round(fitness, 2)


def get_trait_value(genome, mode, trait_name):
    """
    Resolve the final trait value for a mob by combining genome and inheritance mode.
    
    This function combines the genetic code (genome) with the inheritance mode
    to determine the actual expressed trait value. In a full implementation,
    this would also account for environmental factors and epigenetic modifications.
    
    Args:
        genome: Dictionary containing the genetic code (base trait values)
        mode: Inheritance mode to use ("additive", "dominant", "recessive")
        trait_name: Name of the trait to resolve
        
    Returns:
        Integer or float: Resolved trait value
        
    Example:
        >>> genome = {"speed": 5.5, "size": 3.5}
        >>> trait_value = get_trait_value(genome, "additive", "speed")
        >>> print(trait_value)
        6
    """
    # Get trait configuration
    trait_config = get_trait_config(trait_name)
    
    # Get the base value from genome
    base_value = genome.get(trait_name, trait_config["default"])
    
    # For a single mob (no parents), the genome value is the final value
    # Inheritance mode is already accounted for in the genome
    resolved_value = base_value
    
    # Clamp to valid range
    resolved_value = max(
        trait_config["min"], 
        min(trait_config["max"], int(round(resolved_value)))
    )
    
    return resolved_value


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_trait_bounds(trait_name):
    """
    Get minimum and maximum bounds for a trait.
    
    Args:
        trait_name: Name of the trait
        
    Returns:
        Tuple: (min_value, max_value)
        
    Example:
        >>> get_trait_bounds("speed")
        (1, 10)
    """
    trait_config = get_trait_config(trait_name)
    return trait_config["min"], trait_config["max"]


def get_default_trait_value(trait_name):
    """
    Get the default value for a trait.
    
    Args:
        trait_name: Name of the trait
        
    Returns:
        Integer: Default trait value
        
    Example:
        >>> get_default_trait_value("speed")
        5
    """
    trait_config = get_trait_config(trait_name)
    return trait_config["default"]


def get_mutation_rate(trait_name):
    """
    Get the mutation rate for a specific trait.
    
    Args:
        trait_name: Name of the trait
        
    Returns:
        Float: Mutation probability (0.0 to 1.0)
        
    Example:
        >>> get_mutation_rate("speed")
        0.05
    """
    trait_config = get_trait_config(trait_name)
    return trait_config["mutation_rate"]


def get_mutation_variance(trait_name):
    """
    Get the mutation variance for a specific trait.
    
    Args:
        trait_name: Name of the trait
        
    Returns:
        Float: Maximum mutation deviation
        
    Example:
        >>> get_mutation_variance("speed")
        0.1
    """
    trait_config = get_trait_config(trait_name)
    return trait_config["mutation_variance"]


# =============================================================================
# TESTING / DEBUGGING
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("TRAIT MANAGER CORE FUNCTIONS - TESTING")
    print("=" * 80)
    
    # Test inherit_traits
    print("\n1. Testing inherit_traits():")
    parent1 = {"speed": 8, "actual_traits": {"speed": 8}}
    parent2 = {"speed": 4, "actual_traits": {"speed": 4}}
    
    additive_result = inherit_traits(parent1, parent2, "speed", "additive")
    print(f"   Additive (8, 4) -> {additive_result}")
    
    dominant_result = inherit_traits(parent1, parent2, "speed", "dominant")
    print(f"   Dominant (8, 4) -> {dominant_result}")
    
    recessive_result = inherit_traits(parent1, parent2, "speed", "recessive")
    print(f"   Recessive (8, 4) -> {recessive_result}")
    
    # Test mutate
    print("\n2. Testing mutate():")
    genome = {"speed": 5, "size": 3, "strength": 7}
    mutated = mutate(genome, mutation_rate=0.5)
    print(f"   Original: {genome}")
    print(f"   Mutated: {mutated}")
    print(f"   Mutation occurred: {genome != mutated}")
    
    # Test single trait mutation
    print("\n3. Testing single trait mutation:")
    genome = {"speed": 5, "size": 3}
    mutated_speed = mutate(genome, mutation_rate=0.5, trait_name="speed")
    print(f"   Genome: {genome}")
    print(f"   Mutated speed only: {mutated_speed}")
    
    # Test calculate_fitness
    print("\n4. Testing calculate_fitness():")
    mob = {
        "actual_traits": {
            "speed": 8,
            "hunting_skill": 7,
            "strength": 6,
            "size": 4
        },
        "age": 10,
        "offspring_count": 3
    }
    fitness = calculate_fitness(mob)
    print(f"   Mob traits: {mob['actual_traits']}")
    print(f"   Age: 10, Offspring: 3")
    print(f"   Fitness score: {fitness}")
    
    # Test with survival metrics
    print("\n5. Testing calculate_fitness() with survival metrics:")
    survival_metrics = {
        "alive": True,
        "age": 10,
        "reproduced": True,
        "offspring_count": 3,
        "survival_time": 20
    }
    fitness_with_survival = calculate_fitness(mob, survival_metrics)
    print(f"   With survival metrics: {fitness_with_survival}")
    
    # Test get_trait_value
    print("\n6. Testing get_trait_value():")
    genome = {"speed": 5.5, "size": 3.5, "strength": 7.2}
    speed_value = get_trait_value(genome, "additive", "speed")
    size_value = get_trait_value(genome, "dominant", "size")
    strength_value = get_trait_value(genome, "recessive", "strength")
    print(f"   Speed (5.5): {speed_value}")
    print(f"   Size (3.5): {size_value}")
    print(f"   Strength (7.2): {strength_value}")
    
    # Test utility functions
    print("\n7. Testing utility functions:")
    for trait_name in list(TRAIT_TYPES.keys())[:3]:
        bounds = get_trait_bounds(trait_name)
        default = get_default_trait_value(trait_name)
        mutation_rate = get_mutation_rate(trait_name)
        variance = get_mutation_variance(trait_name)
        print(f"   {trait_name}: bounds={bounds}, default={default}, "
              f"mutation_rate={mutation_rate}, variance={variance}")
    
    print("\n" + "=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)
