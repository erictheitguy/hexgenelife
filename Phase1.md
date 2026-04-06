# Phase 1: Trait System Foundation (Dependency: None)

## Overview
This phase implements the foundation for the trait system, establishing the schema, manager, and basic mechanics. The work is divided into 5 manageable chunks.

## Phase 1 Breakdown

### Chunk 1: Trait Definitions & Schema (30-60 min)
**New File:** `theory/trait_definitions.py`

- Define trait constants and types
- Add trait types: `speed`, `size`, `strength`, `camouflage`, `hunting_skill`, `tracking_range`, `reproduction_rate`, `metabolism_rate`
- Implement inheritance modes: `additive`, `dominant`, `recessive`
- Define mutation mechanics with variance ranges

### Chunk 2: Trait Manager Core Functions (60-90 min)
**File:** `theory/trait_manager.py` (new file)

- `inherit_traits(parent1, parent2)` - Combine parent genes
- `mutate(genome, mutation_rate)` - Apply mutations (random, no deterministic seed)
- `calculate_fitness(mob, survival_metrics)` - Compute fitness score
- `get_trait_value(genome, mode)` - Resolve trait values by inheritance mode

### Chunk 3: Trait Inheritance Logic (60-90 min)
**File:** `theory/trait_manager.py` (extends Chunk 2)

- Implement complex inheritance patterns
- Handle trait dominance and recessiveness
- Add generation tracking for inheritance depth

### Chunk 4: Extended Mob Schema (30-60 min)
**File:** `theory/createmob.py` (modified)

- Add `mob_type`: `"prey" | "predator" | "grass_eater"`
- Add `generation`: integer tracking
- Add `parent_ids`: array of parent mob IDs
- Add `genome`: object with base trait values
- Add `actual_traits`: object with modified trait values (post-mutation)
- Add `fitness_score`: survival/reproduction metric

### Chunk 5: Fitness Calculation (45-60 min)
**Files:** `theory/trait_manager.py` and `theory/createmob.py` (extended)

- Implement fitness scoring algorithm
- Integrate with survival metrics
- Update mob schema with fitness tracking

## File Summary

| File | Action | Description |
|------|--------|-------------|
| `theory/trait_definitions.py` | NEW | Trait types, constants, inheritance modes |
| `theory/trait_manager.py` | NEW | Core trait management functions |
| `theory/createmob.py` | MODIFIED | Extended mob schema with traits |

## Verification Steps

1. [ ] `trait_definitions.py` defines all 8 trait types with proper constants
2. [ ] `trait_definitions.py` implements 3 inheritance modes (additive, dominant, recessive)
3. [ ] `trait_manager.py` has `inherit_traits()` function combining parent genes
4. [ ] `trait_manager.py` has `mutate()` function with random mutation (no seed)
5. [ ] `trait_manager.py` has `calculate_fitness()` function
6. [ ] `trait_manager.py` has `get_trait_value()` function
7. [ ] `createmob.py` includes extended schema with mob_type, generation, parent_ids
8. [ ] `createmob.py` includes genome and actual_traits objects
9. [ ] `createmob.py` includes fitness_score tracking

## Decisions

- **Trait Interactions:** Explicitly deferred to Phase 2. This phase handles individual trait mechanics only; trait-to-trait interactions (e.g., camouflage affecting hunting success) will be implemented in Phase 2.
- **Mutation Tracking:** Random mutations with no deterministic seed. Each mutation is probabilistic and unpredictable, enabling natural genetic variation.

## Further Considerations

### Trait Interaction Rules
**Status:** Deferred to Phase 2
Traits may interact in complex ways (e.g., high hunting_skill + high strength = predator dominance). These interactions will be implemented in Phase 2 as part of the extended trait system.

### Mutation Tracking
**Status:** Random (no deterministic seed)
Mutations will be applied randomly during trait generation. No seed-based reproducibility is implemented in this version, allowing for natural genetic variation.

---
*Note: This document was updated to reflect the modular 5-chunk breakdown and clarified that trait interactions go to Phase 2. Mutation is random with no deterministic seed.*