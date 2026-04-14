# Mob Schema

Mob schema is broken into multiple tables and joined by ID. The tables reflect the schema initialized in `server.py`.

**Table mobs**
mob_id : Text PRIMARY KEY
position : Text (JSON object with integer "x" and "y" coordinates)
mob_type : Text (e.g. "prey", "predator")
generation : Integer
timestamp : Real

**Table mob_genes**
mob_id : Text
mobType : Text
fitnessScore : Real
death : Real (Timestamp of death, NULL if not dead)
expired : Boolean (Flag if gene has expired)
PRIMARY KEY (mob_id, mobType)

**Table mob_health** *(extended Phase 4.1)*
mob_id : Text PRIMARY KEY
hunger : Real
fat : Real
health : Real
age : Real
energy : Real (DEFAULT 50.0 — current energy available for actions)
life_stage : Text (DEFAULT 'adult' — one of: baby, juvenile, adult, senior)
birth_tick : Real (DEFAULT 0.0 — timestamp of mob creation)
max_age : Real (DEFAULT 10000.0 — age at which mob dies naturally)

**Table mob_brain** *(extended Phase 4.1)*
mob_id : Text PRIMARY KEY
cognition_attributes : Text (JSON — legacy field)
decision_tree : Text (JSON — the flow-chart decision tree structure)
memory : Text (JSON — persistent memory blob read/written by brain functions)

**Table mob_physical** *(Phase 4.1)*
mob_id : Text PRIMARY KEY
size : Real (DEFAULT 1.0 — physical size of the mob)
speed : Real (DEFAULT 1.0 — movement speed)
mass : Real (DEFAULT 1.0 — body mass, affects energy cost and combat)
vision : Real (DEFAULT 10.0 — how far the mob can see)
metabolism_active : Real (DEFAULT 1.0 — fat→energy conversion rate when active)
metabolism_resting : Real (DEFAULT 0.2 — fat→energy conversion rate when idle)
diet_type : Real (DEFAULT 0.0 — spectrum: 0.0=herbivore, 0.5=omnivore, 1.0=carnivore)
attack_power : Real (DEFAULT 1.0 — base damage dealt in combat)
defense : Real (DEFAULT 1.0 — damage reduction in combat)
camouflage : Real (DEFAULT 0.5 — how hidden the mob is from LOOK; 0.0=visible, 1.0=hidden)

**Table brain_functions** *(Phase 4.1)*
function_id : Text PRIMARY KEY
function_name : Text NOT NULL (human-readable name)
function_code : Text NOT NULL (Python function reference key)
description : Text (what this function does)
input_schema : Text (JSON — expected input format)
output_schema : Text (JSON — output format description)
version : Integer (DEFAULT 1 — for tracking updates)
created : Text (ISO 8601 timestamp)
updated : Text (ISO 8601 timestamp)

---

## Type-Specific Defaults

### Prey (diet_type = 0.0)
| Attribute | Default |
|-----------|---------|
| speed | 1.3 |
| defense | 1.2 |
| camouflage | 0.7 |
| diet_type | 0.0 |

### Predator (diet_type = 1.0)
| Attribute | Default |
|-----------|---------|
| speed | 1.5 |
| attack_power | 3.0 |
| defense | 1.5 |
| vision | 15.0 |
| metabolism_active | 1.5 |
| camouflage | 0.6 |
| diet_type | 1.0 |
