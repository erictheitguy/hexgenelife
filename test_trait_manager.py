import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import all functions directly
from theory.trait_manager import (
    inherit_traits,
    mutate,
    calculate_fitness,
    get_trait_value,
    get_trait_bounds,
    get_default_trait_value,
    get_mutation_rate,
    get_mutation_variance
)
from theory.trait_definitions import (
    TRAIT_TYPES
)

print('=' * 80)
print('TRAIT MANAGER CORE FUNCTIONS - TESTING')
print('=' * 80)

# Test inherit_traits
print('\n1. Testing inherit_traits():')
parent1 = {'speed': 8, 'actual_traits': {'speed': 8}}
parent2 = {'speed': 4, 'actual_traits': {'speed': 4}}

additive_result = inherit_traits(parent1, parent2, 'speed', 'additive')
print(f'   Additive (8, 4) -> {additive_result}')

dominant_result = inherit_traits(parent1, parent2, 'speed', 'dominant')
print(f'   Dominant (8, 4) -> {dominant_result}')

recessive_result = inherit_traits(parent1, parent2, 'speed', 'recessive')
print(f'   Recessive (8, 4) -> {recessive_result}')

# Test mutate
print('\n2. Testing mutate():')
genome = {'speed': 5, 'size': 3, 'strength': 7}
mutated = mutate(genome, mutation_rate=0.5)
print(f'   Original: {genome}')
print(f'   Mutated: {mutated}')
print(f'   Mutation occurred: {genome != mutated}')

# Test single trait mutation
print('\n3. Testing single trait mutation:')
genome = {'speed': 5, 'size': 3}
mutated_speed = mutate(genome, mutation_rate=0.5, trait_name='speed')
print(f'   Genome: {genome}')
print(f'   Mutated speed only: {mutated_speed}')

# Test calculate_fitness
print('\n4. Testing calculate_fitness():')
mob = {
    'actual_traits': {
        'speed': 8,
        'hunting_skill': 7,
        'strength': 6,
        'size': 4
    },
    'age': 10,
    'offspring_count': 3
}
fitness = calculate_fitness(mob)
print(f'   Mob traits: {mob["actual_traits"]}')
print(f'   Age: 10, Offspring: 3')
print(f'   Fitness score: {fitness}')

# Test with survival metrics
print('\n5. Testing calculate_fitness() with survival metrics:')
survival_metrics = {
    'alive': True,
    'age': 10,
    'reproduced': True,
    'offspring_count': 3,
    'survival_time': 20
}
fitness_with_survival = calculate_fitness(mob, survival_metrics)
print(f'   With survival metrics: {fitness_with_survival}')

# Test get_trait_value
print('\n6. Testing get_trait_value():')
genome = {'speed': 5.5, 'size': 3.5, 'strength': 7.2}
speed_value = get_trait_value(genome, 'additive', 'speed')
size_value = get_trait_value(genome, 'dominant', 'size')
strength_value = get_trait_value(genome, 'recessive', 'strength')
print(f'   Speed (5.5): {speed_value}')
print(f'   Size (3.5): {size_value}')
print(f'   Strength (7.2): {strength_value}')

# Test utility functions
print('\n7. Testing utility functions:')
for trait_name in list(TRAIT_TYPES.keys())[:3]:
    bounds = get_trait_bounds(trait_name)
    default = get_default_trait_value(trait_name)
    mutation_rate = get_mutation_rate(trait_name)
    variance = get_mutation_variance(trait_name)
    print(f'   {trait_name}: bounds={bounds}, default={default}, '
          f'mutation_rate={mutation_rate}, variance={variance}')

print('\n' + '=' * 80)
print('TESTING COMPLETE')
print('=' * 80)
