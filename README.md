hexgenelife
===========
Overview
Extend your existing hex-based life simulation with a complete ecological system featuring prey, predators, genetic traits, mutation, and natural selection. The system will build upon your existing grass_eater.py architecture while adding new evolutionary mechanics.

TL;DR
Add genetic trait systems to existing mob entities, implement prey-predator hunting/fleeing mechanics, and create reproduction with inheritance/mutation. The plan reuses ~70% of existing code (grid, database, movement) and extends it with new trait systems.

Steps



Phase 2: New Entity Types (Depends on Phase 1)
Implement Prey Behavior - Extend theory/grass_eater.py

Add flee() method - Detect predators, flee in opposite direction
Add speed trait - Influenced by speed genome value
Add camouflage trait - Reduces predator detection probability
Add reproduction_rate trait - Higher values = more offspring
Modify motivate() to check for predator threats
Implement Predator Behavior - Extend theory/grass_eater.py

Add hunt() method - Detect prey, chase closest target
Add hunting_skill trait - Increases capture success rate
Add tracking_range trait - Extended detection radius
Add consumption_rate trait - How much prey biomass consumed
Modify motivate() to prioritize hunting over grazing

Phase 3: Prey-Predator Dynamics (Depends on Phase 2)
Add Predator Detection - Extend theory/HexSearch.py

find_preys(predator) - Find prey within tracking range
find_predators(prey) - Find predators within eyesight range
calculate_threat_level(prey, predator_list) - Compute danger score
Implement Hunting Mechanics - Add to theory/grass_eater.py

predator_capture(predator, prey) - Capture logic based on hunting_skill
prey_escape(prey, predator_distance) - Escape chance based on camouflage
consume_prey(predator, prey) - Energy/fat transfer with consumption_rate
Implement Fleeing Mechanics - Add to theory/grass_eater.py

prey_flee(prey, predator_angle) - Calculate optimal escape direction
Increase prey speed when threatened
Add panic mechanic - Higher threat = faster movement
Phase 4: Reproduction & Evolution (Depends on Phase 1, 2, 3)
Add Reproduction Logic - Extend theory/matrix_v1.py

can_reproduce(mob) - Check energy, fat, health thresholds
create_offspring(parent) - Generate new mob with inherited traits
reproduce_prey(prey) - Prey reproduction based on reproduction_rate
reproduce_predator(predator) - Predator reproduction based on consumption success
Implement Mutation System - Add to theory/trait_manager.py

Per-trait mutation rates (e.g., speed ±5%, camouflage ±10%)
Rare beneficial mutations (1% chance of large positive mutation)
Track mutation history for debugging
Add Evolution Loop - Extend theory/matrix_v1.py

After each generation, calculate fitness scores
Track average population traits over time
Implement "survival of the fittest" - weaker individuals die faster
Phase 5: Visualization & Debugging (Depends on Phase 4)
Add Trait Visualization - Extend theory/drawhex.py

Color-code mobs by mob_type (prey = green, predator = red)
Add size indicators for size trait
Add aura/glow for high camouflage or hunting_skill
Display trait values on hover (if GUI supports tooltips)
Add Statistics Dashboard - New file: theory/stats_tracker.py

Track population counts by type
Track average trait values over time
Track species diversity metrics
Export evolution data for analysis
Relevant Files
File	Full Path	Purpose	Lines
createmob.py	createmob.py	Add trait initialization, new mob types	92
grass_eater.py	grass_eater.py	Add hunting/fleeing logic, reproduction	233
HexSearch.py	HexSearch.py	Add predator-prey detection queries	57
matrix_v1.py	matrix_v1.py	Add reproduction loop, evolution tracking	43
drawhex.py	drawhex.py	Add trait visualization	102
theory/trait_manager.py	NEW	Trait inheritance, mutation, fitness calculation	-
theory/stats_tracker.py	NEW	Evolution statistics and tracking	-
Verification
Unit Tests for Trait System

Test inherit_traits() with various inheritance modes
Test mutate() generates mutations within expected ranges
Test calculate_fitness() returns valid scores
Integration Tests

Verify prey can be detected by predators within tracking_range
Verify prey flee successfully when predator approaches
Verify offspring inherit traits from parents with mutation applied
Simulation Tests

Run 1000 steps and verify population dynamics stabilize
Verify predator-prey cycles emerge (Lotka-Volterra dynamics)
Verify traits evolve over multiple generations
Visual Verification

Confirm prey and predators are color-coded correctly
Verify movement vectors show fleeing/chasing behavior
Check statistics dashboard updates in real-time
Decisions
Inheritance Mode: Use additive inheritance (average of parents + mutation) for quantitative traits
Mutation Rate: Default 5% per trait per generation, configurable per trait type
Fitness Calculation: Weight survival (energy > 30) and reproduction (offspring count) equally
Reproduction Trigger: When fat > 80 AND energy > 70 AND age > 10
Initial Population: 50 prey, 5 predators, 1000 grass tiles
Further Considerations
Trait Interactions

Question: Should traits interact (e.g., high speed + low camouflage = higher predation risk)?
Recommendation: Yes, add simple interaction rules (e.g., effective_camouflage = camouflage - speed * 0.1)
Environment Evolution

Question: Should the environment change (grass growth rates, water distribution)?
Recommendation: Start static, add environmental evolution in Phase 2
Population Caps

Question: Should there be carrying capacity limits?
Recommendation: Yes, implement logistic growth with max population thresholds
Summary
This plan adds a complete evolutionary ecosystem to your existing simulation:

12 steps across 5 phases
~300 lines of new code minimum
7 files to modify/create
60% code reuse from existing systems