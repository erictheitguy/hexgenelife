# Overall Tasks

Server Tasks found in server\server_tasks.md
Client Tasks found in client\client_tasks.md
Viewer Tasks found in viewer\viewer_tasks.md

## Phase 1

**Status: Not Started**
Create script that intilizes the gameworld with at least 1 hex and 1 mob.
Create server that accepts client connections.
Create client that performs random movements of the mob it is assigned to control.
See server_doc\server_phase1.md
See client_doc\client_phase1.md

## Phase 2

**Status: Not Started**

Three parallel workstreams. See component docs for full checklists.

### Server — Dynamic World Expansion
See `server_doc/server_phase2.md` and `server_doc/server_tasks.md`.

- [ ] Boundary detection: determine if mob position is outside all existing hex tiles
- [ ] Adjacent hex centre calculation (flat-top axial grid, hex radius = 5)
- [ ] Neighbour-averaging for `Water` and `Grass` (existing neighbours only)
- [ ] Default seeding (`Water=5.0`, `Grass=3.0`) when no neighbours exist
- [ ] Insert new hex tile row into database (all corner fields, loc, timestamps)
- [ ] Range-limited `HEX_CREATED` broadcast (constant = 100 units)

### Viewer — Pygame World Renderer
See `viewer_doc/viewer_phase2.md` and `viewer_doc/viewer_tasks.md`.

- [ ] `viewer/db_reader.py` — read-only SQLite tile and mob queries
- [ ] `viewer/camera.py` — pan / zoom camera transform
- [ ] `viewer/renderer.py` — hex tile polygon rendering + mob dots + HUD legend
- [ ] `viewer/viewer_main.py` — Pygame entry point, 60 FPS loop, 500 ms DB poll

### Client — Resilience
See `client_doc/client_phase2.md` and `client_doc/client_tasks.md`.

- [ ] Auto-reconnect with exponential back-off (1 s → 30 s cap)
- [ ] `HEX_CREATED` message handler → update `ClientState.worldTiles`

## Phase 2.5: Schema Update and Consistency

Status: Not Started

- [x] Review and update `MobSchema.md` to reflect the current mob structure and data fields.
- [x] Review and update server-related schemas in `server_doc/` (e.g., in `server_phase1_s1.md` through `server_phase1_s5.md`) to ensure they align with the implementation in `server/`.
- [x] Validate consistency between `MobSchema.md` and all relevant server schemas.
- [x] Update any necessary documentation in `server_doc/` and `server_tasks.md` to reflect schema changes.

## Phase 3

**Status: Complete**

- [x] **Viewer Interactions**: Click to select mobs/tiles and view details in HUD.
- [x] **Launcher Application**: Tkinter GUI to manage server, clients, and viewer processes.
- [x] **Mob Creation**: Support for creating mobs with randomized/editable values via the launcher.
- See `viewer_doc/viewer_phase3.md` for details.
