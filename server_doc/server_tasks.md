# Server Tasks

## Phase 1
See `server_phase1.md` for design details.

- [x] Server initializes SQLite DB (creates tables if needed)
- [x] Server ensures at least 1 hex tile exists on startup
- [x] WebSocket server accepts client connections
- [x] Tick-based game loop with `TICK_COMPLETE` broadcast
- [x] `MOVE_MOB` command — validate, update DB, broadcast `MOB_UPDATE`
- [x] `REQUEST_WORLD_STATE` command — return current world snapshot
- [x] Integer-only coordinate enforcement on `MOVE_MOB`
- [x] Action-limit enforcement per tick per client
- [x] Standardized `ERROR` response format

## Phase 2
See `server_phase2.md` for design details.

- [ ] Implement boundary detection after each `MOVE_MOB` (point-in-polygon against all existing tiles)
- [ ] Implement adjacent hex centre calculation using flat-top axial grid offsets
- [ ] Fetch existing neighbours (up to 6) from the DB for a candidate new tile position
- [ ] Compute `Water` and `Grass` as the mean of existing-neighbour values only
- [ ] Fall back to `DEFAULT_WATER = 5.0` / `DEFAULT_GRASS = 3.0` when no neighbours exist
- [ ] Insert full new hex tile record into DB (all corner points, loc, timestamps)
- [ ] Define `HEX_CREATION_BROADCAST_RANGE = 100` constant in server config
- [ ] Broadcast `HEX_CREATED` only to clients whose mobs are within range 100 units
- [ ] Unit test: boundary detection triggers tile creation
- [ ] Unit test: neighbour-averaging formula
- [ ] Unit test: zero-neighbour default values
- [ ] Unit test: range filter on `HEX_CREATED` broadcast
- [ ] Integration test: mob moves far out → DB has new tile row with correct Water/Grass
