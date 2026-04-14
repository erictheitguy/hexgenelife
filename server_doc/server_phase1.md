# Phase 1 for Server Implementation

## Plan: WebSocket Specification Design

**TL;DR** - Design a JSON-based WebSocket protocol to handle client actions (movement, etc.), server state synchronization (mob positions, world updates), and server-to-client state broadcasts, adhering to the roles defined (Client sends actions, Server manages state).

### Steps

1. **Define Message Structures (Step 1)**: Design the core JSON message schemas for all necessary interactions (Client $\to$ Server, Server $\to$ Client). 
    * Client Actions (e.g., `MOVE_MOB`, `REQUEST_WORLD_STATE`).
    * Server State Updates (e.g., `MOB_UPDATE`, `WORLD_UPDATE`).
    * Error Handling (`ERROR`).
    * **Message Definitions**: See `websocket_messages.json` for the defined schemas. 
    * A standard JSON error response has been defined as `ERROR` with fields `errorCode` and `errorMessage` inside `payload`.

2. **Define Connection Lifecycle (Step 2)**: 
    * When a client connects, the server accepts the WebSocket connection.
    * The server should verify if the client has an assigned mob. If a mob does not exist for the client, one should be created.
    * Initial state synchronization should occur (e.g., client requests world state).

3. **Implement Server Logic Flow (Step 3)**: Detail how the server will receive client actions, validate them, update the core game state (hex tiles, mob positions), and generate necessary state update messages. Outlined in `server_phase1_s3.md`

4. **Implement Client Logic Flow (Step 4)**: Detail how the client will send input messages and how it will process incoming state update messages to render the game world. Outlined in `server_phase1_s4.md`

5. **Server Start & End-to-End Verification (Step 5)**:
    * **Server Start**: The server must initialize the SQLite3 database, creating tables (`mobs`, `mob_genes`, `mob_health`, `mob_brain`) and ensure that at least 1 hexagon is populated in the database.
    * **Tick Synchronization**: The server must implement a strict tick-based loop. Each connected client has a limited number of actions per tick. A `tick_complete` signal is broadcast when all actions are executed.
    * **Verification**: Simulate client actions (e.g., `MOVE_MOB`) and verify corresponding `MOB_UPDATE` responses. Validate database updates, and ensure correct JSON payload formats.

### Relevant files

* `MobSchema.md` — To define the structure of mob data.
* `HexTileSchema.md` — To define the structure of hex tile data.
* `websocket_messages.json` — For precise message schemas over WebSocket.
* `server_implementation.md` — To guide the implementation of the server's WebSocket handling logic.

### Decisions

* **Protocol**: WebSocket with JSON payloads.
* **Message Types**: Clearly distinguish between command messages (Client $\to$ Server) and state messages (Server $\to$ Client).
* **State Management**: Server is the single source of truth for game state.

### Further Considerations

1. **Error Handling**: Use the explicit `ERROR` JSON payload to communicate issues. Log the error server-side and potentially close connection for severe validation faults.
2. **Mob/Tile Data Granularity**: Position updates are per-tile. Periodic world state snapshots.
