# =============================================================================
# TRAIT DEFINITIONS - Phase 1, Chunk 1
# =============================================================================
# Trait metadata definitions for the ecological simulation trait system.
# This file contains all trait configurations, inheritance modes, and helper functions.
# =============================================================================

import random

# =============================================================================
# TRAIT TYPES DEFINITION
# =============================================================================
# Each trait has:
#   - description: Human-readable explanation
#   - min/max: Valid trait value range
#   - default: Starting value for new mobs
#   - inherit_mode: How traits are inherited (additive, dominant, recessive)
#   - mutation_rate: Probability of mutation per generation (0.0 to 1.0)
#   - mutation_variance: Maximum deviation from parent value during mutation
# =============================================================================

TRAIT_TYPES = {
    "speed": {
        "description": "Movement speed",
        "min": 1,
        "max": 10,
        "default": 5,
        "inherit_mode": "additive",
        "mutation_rate": 0.05,
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
        "mutation_rate": 0.08,  # Higher mutation rate for camouflage
        "mutation_variance": 0.15  # Larger variance for camouflage
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

# =============================================================================
# INHERITANCE MODE DEFINITIONS
# =============================================================================
# Three inheritance modes for combining parent traits:
# - additive: Average of both parents (most common for quantitative traits)
# - dominant: One parent's traits dominate (simplified: weighted toward parent 1)
# - recessive: Traits only expressed if both parents carry them (simplified: weighted toward parent 2)
# =============================================================================

INHERITANCE_MODES = {
    "additive": {
        "description": "Both parents contribute equally to offspring traits",
        "formula": "(parent1_value + parent2_value) / 2",
        "use_case": "Quantitative traits like speed, size, strength"
    },
    "dominant": {
        "description": "One parent's traits dominate the inheritance",
        "formula": "parent1_value + (parent2_value - parent1_value) * 0.3",
        "use_case": "Traits with clear dominance patterns"
    },
    "recessive": {
        "description": "Traits only expressed if both parents carry them",
        "formula": "parent2_value + (parent1_value - parent2_value) * 0.3",
        "use_case": "Traits that require homozygous expression"
    }
}

INHERITANCE_MODES_DESC = {
    "additive": "Both parents contribute equally",
    "dominant": "Dominant traits from first parent",
    "recessive": "Recessive traits from second parent"
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_trait_config(trait_name):
    """
    Get configuration for a specific trait.
    
    Args:
        trait_name: Name of the trait (e.g., "speed", "size")
        
    Returns:
        Dictionary with trait configuration, or None if trait not found
        
    Example:
        >>> get_trait_config("speed")
        {'description': 'Movement speed', 'min': 1, 'max': 10, ...}
    """
    if trait_name not in TRAIT_TYPES:
        raise ValueError(f"Unknown trait: {trait_name}. Available traits: {list(TRAIT_TYPES.keys())}")
    return TRAIT_TYPES[trait_name]


def get_inheritance_mode(mode_name):
    """
    Get configuration for a specific inheritance mode.
    
    Args:
        mode_name: Name of the inheritance mode (e.g., "additive", "dominant")
        
    Returns:
        Dictionary with mode description and formula
        
    Example:
        >>> get_inheritance_mode("additive")
        {'description': 'Both parents contribute equally...', 'formula': '(p1+p2)/2', ...}
    """
    if mode_name not in INHERITANCE_MODES:
        raise ValueError(f"Unknown inheritance mode: {mode_name}. Available modes: {list(INHERITANCE_MODES.keys())}")
    return INHERITANCE_MODES[mode_name]


def validate_trait_value(trait_name, value):
    """
    Validate that a trait value is within acceptable bounds.
    
    Args:
        trait_name: Name of the trait
        value: Value to validate
        
    Returns:
        Boolean indicating if value is valid
        
    Raises:
        ValueError: If value is out of bounds
        
    Example:
        >>> validate_trait_value("speed", 5)  # True
        True
        >>> validate_trait_value("speed", 0)  # Raises ValueError
        ValueError: Trait 'speed' value 0 is out of bounds (1-10)
    """
    config = get_trait_config(trait_name)
    if value < config["min"] or value > config["max"]:
        raise ValueError(f"Trait '{trait_name}' value {value} is out of bounds ({config['min']}-{config['max']})")
    return True


def get_all_trait_names():
    """
    Get a list of all available trait names.
    
    Returns:
        List of trait name strings
        
    Example:
        >>> get_all_trait_names()
        ['speed', 'size', 'strength', 'camouflage', 'hunting_skill', 'tracking_range', 'reproduction_rate', 'metabolism_rate']
    """
    return list(TRAIT_TYPES.keys())


def print_trait_definitions():
    """
    Print all trait definitions to console for debugging/documentation.
    
    Example Output:
        Trait Definitions:
        speed: Movement speed (1-10, default: 5, mode: additive, mutation: 5% ±10%)
        size: Physical size (1-10, default: 5, mode: additive, mutation: 5% ±10%)
        ...
    """
    print("Trait Definitions:")
    print("-" * 80)
    for trait_name, config in TRAIT_TYPES.items():
        print(f"{trait_name}: {config['description']} "
              f"({config['min']}-{config['max']}, default: {config['default']}, "
              f"mode: {config['inherit_mode']}, mutation: {config['mutation_rate']*100:.0f}% ±{config['mutation_variance']*100:.0f}%)")
    print("-" * 80)
    print(f"Inheritance modes: {list(INHERITANCE_MODES.keys())}")


# =============================================================================
# TESTING / DEBUGGING
# =============================================================================
if __name__ == "__main__":
    print_trait_definitions()
    
    # Test get_trait_config
    print("\nTesting get_trait_config('speed'):")
    print(get_trait_config("speed"))
    
    # Test validate_trait_value
    print("\nTesting validate_trait_value('speed', 5):")
    print(validate_trait_value("speed", 5))
    
    # Test invalid value
    print("\nTesting validate_trait_value('speed', 0):")
    try:
        validate_trait_value("speed", 0)
    except ValueError as e:
        print(f"Error caught: {e}")
    
    # Test get_inheritance_mode
    print("\nTesting get_inheritance_mode('additive'):")
    print(get_inheritance_mode("additive"))