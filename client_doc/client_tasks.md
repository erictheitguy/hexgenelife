# Client Phase 1 Tasks

## Status: In Progress

### Connection & Setup
- [x] Add `client/__init__.py` so `client` is a Python package
- [x] Connect to WebSocket server at `ws://localhost:8765`
- [x] Handle connection failure gracefully (log + return False)

### Mob Management
- [x] On connect, send `REQUEST_WORLD_STATE` to trigger server-side mob creation
- [x] Client derives own `mob_id` as `mob_{client_id}`

### Autonomous Movement Loop
- [x] Wait for `TICK_COMPLETE` before sending next action (`tick_event`)
- [x] Send exactly 1 `MOVE_MOB` per tick with random integer coordinates
- [x] Ensure `targetLocation.x` and `targetLocation.y` are integers (cast with `int()`)

### Message Handling (Server → Client)
- [x] `TICK_COMPLETE` — set `tick_event` so autonomous loop unblocks
- [x] `MOB_UPDATE` — update `ClientState.mobs[mobId]`
- [x] `WORLD_UPDATE` — update `ClientState.mobs` and `ClientState.worldTiles`
- [x] `ERROR` — log `errorCode` + `errorMessage` as a warning

### State Management
- [x] `ClientState` observable pattern with `subscribe` / `setState`
- [x] `get_state()` returns a copy of current state

### Tests (`tests/test_websocket_client.py`)
- [x] `TestClientState` — 7 synchronous unit tests
- [x] `TestHexGenLifeClientAsync` — 8 async tests using `IsolatedAsyncioTestCase`
- [x] All 34 project tests passing (`python -m pytest tests/ -v`)

### Error Handling
- [x] `ACTION_LIMIT_EXCEEDED` errors logged from server
- [x] `MALFORMED_JSON` / `VALIDATION_FAILED` errors logged
- [ ] Auto-reconnect on connection drop (deferred to Phase 2)

## Phase 2 Tasks
See `client_phase2.md` for design details.

### Auto-Reconnect
- [ ] Detect unexpected connection close (not client-initiated)
- [ ] Implement exponential back-off: start 1 s, cap 30 s, factor ×2
- [ ] On successful reconnect, send `REQUEST_WORLD_STATE` to re-sync
- [ ] Resume autonomous movement loop after reconnect
- [ ] Unit test: `test_auto_reconnect_backoff`

### HEX_CREATED Message Handler
- [ ] Add `HEX_CREATED` branch in `handle_message()`
- [ ] Parse `hexId` + `tileData` from payload
- [ ] Insert new tile into `ClientState.worldTiles[hexId]`
- [ ] Log info message with new tile centre coordinates
- [ ] Unit test: `test_hex_created_handler` — assert worldTiles updated correctly