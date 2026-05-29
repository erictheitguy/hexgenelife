---
description: Run a supervised HexGenLife simulation. Starts the server, spawns prey, monitors survival/breeding, adds predators once prey breed, then writes a run report to Obsidian at Projects/HexGenLife/Runs/run-<N>.md. Usage: /sim-running [--prey N] [--predators N] [--max-minutes N] [--breed-threshold N]
---

Run a supervised HexGenLife simulation using the sim-runner skill.

## Steps

1. Parse any arguments from `$ARGUMENTS` (optional: `--prey`, `--predators`, `--max-minutes`, `--breed-threshold`).
2. Run the sim runner script:

```bash
.venv/bin/python .codex/skills/sim-runner/sim_runner_skill.py $ARGUMENTS
```

The script prints live status lines every ~10 seconds during the run. Wait for it to finish — it will print `[sim_runner] Done. Run #N report saved.` when complete.

3. After it finishes, read the run report from Obsidian:

```bash
obsidian read path="Projects/HexGenLife/Runs/run-<N>.md"
```

(Replace `<N>` with the run number printed by the script.)

4. Summarise the run for the user:
   - Phase timeline (key events)
   - Final prey/predator population
   - Breeding and feeding activity (`eat_grass_events`, `breed_events`)
   - Any issues detected and recommendations
   - Notable log errors if any

## Default parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--prey` | 5 | Starting prey count |
| `--predators` | 2 | Predators added after prey breed |
| `--max-minutes` | 30 | Hard time cap |
| `--breed-threshold` | 1 | Bred prey needed before predators are introduced |

## Notes

- The script wipes the DB and logs before starting (`mode="new"`).
- Report is written to Obsidian at `Projects/HexGenLife/Runs/run-<N>.md` (auto-incremented).
- Depends on `.codex/skills/hexgenlife-server/server_skill.py` and `.codex/skills/hexgenlife-client/client_skill.py`.
- Canonical runner: `.codex/skills/sim-runner/sim_runner_skill.py` (1004+ lines). Do NOT use the stale copy at `~/.codex/skills/sim-running/sim_runner_skill.py`.
