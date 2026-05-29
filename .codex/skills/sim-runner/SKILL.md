---
name: sim-runner
description: Runs a full supervised HexGenLife simulation cycle. Starts the server, spawns prey, monitors the DB and logs for survival and breeding, adds predators once prey breed, then kills everything after 30 minutes and writes a run report to Obsidian at Projects/HexGenLife/Runs/run-<N>.md. Use when the user asks to run a sim, test the simulation, or do a supervised run.
---

# HexGenLife Sim Runner — `sim_runner_skill.py`

## Module Location

**Canonical:** `.codex/skills/sim-runner/sim_runner_skill.py`
**Do NOT use:** `~/.codex/skills/sim-running/sim_runner_skill.py` (stale 651-line copy — see SKILL.md there)

## Description

Orchestrates a full supervised simulation:

1. Start server (`new` mode — wipes DB and logs)
2. Spawn prey clients
3. Poll DB every 10 s — monitor prey survival and breeding
4. Once prey start breeding, add predator clients
5. Continue monitoring until 30 min elapsed (or all prey die)
6. Kill server and all clients
7. Analyse results and write a run report to Obsidian

## Environment

- **Workspace root:** `/home/eric/Projects/hexgenlife/hexgenelife`
- **Python:** `.venv/bin/python`
- **Depends on:** `.codex/skills/hexgenlife-server/server_skill.py`, `.codex/skills/hexgenlife-client/client_skill.py`, `obsidian` CLI

## Usage (Python API)

```python
import importlib.util, sys
sys.path.insert(0, "/home/eric/Projects/hexgenlife/hexgenelife")
spec = importlib.util.spec_from_file_location(
    "sim_runner_skill",
    ".codex/skills/sim-runner/sim_runner_skill.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Default run: 5 prey, 2 predators, 30 min max
mod.run_sim()

# Custom run
mod.run_sim(prey=8, predators=3, max_seconds=600, prey_breed_threshold=2)
```

## CLI Usage

```bash
# Default run
.venv/bin/python .codex/skills/sim-runner/sim_runner_skill.py

# Custom
.venv/bin/python .codex/skills/sim-runner/sim_runner_skill.py \
  --prey 8 --predators 3 --max-minutes 15 --breed-threshold 2
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `prey` | 5 | Number of prey mobs to start with |
| `predators` | 2 | Number of predators added after prey breed |
| `max_seconds` | 1800 | Hard cap on run duration |
| `prey_breed_threshold` | 1 | Bred prey count needed before predators are added |

## Monitoring (per 10 s poll)

- Prey/predator alive / total / bred / generation
- Life-stage breakdown: baby / juvenile / adult (breeding-capable) / senior (non-breeding)
- Avg/min/max health, hunger, energy, fat per type
- Breed, attack, EAT_GRASS, EAT_MOB event counts (cumulative + per-interval delta visible in console)
- Grass: total supply, avg per tile, depleted-tile count
- Prey dispersal: centroid drift, spread avg/max, % still near start
- Server load: queue depth, deferred actions, degraded mode
- **Stall detection:** warns when tick hasn't advanced for 3+ consecutive polls (30+ s)

## Report

Written to Obsidian at `Projects/HexGenLife/Runs/run-<N>.md` (auto-incremented).

Contains:
- **Verdict** (PASS / WARN / FAIL) in frontmatter and header
- Phase timeline (key events with tick numbers)
- Metrics snapshot table (one row per tick change)
- Final state summary including hunt success rate, generation, adult vs senior counts
- **Genetics section:** trait min/avg/max and drift-since-start for each heritable trait
- **Death cause tally:** starvation / predation / old-age / unknown counts parsed from server log
- **Grass supply** at end of run (total, avg/tile, depleted tiles)
- Issues detected and **data-driven recommendations** (branch on observed grass, death cause, hunt rate)
- Predator death context (nearest prey, vision, etc.) if any predators died
- Last 80 lines of server and client logs
