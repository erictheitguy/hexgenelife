# # Phase 1 for Server Implementation

## Plan: WebSocket Specification Design

**TL;DR** - Design a JSON-based WebSocket protocol to handle client actions (movement, etc.), server state synchronization (mob positions, world updates), and server-to-client state broadcasts, adhering to the roles defined (Client sends actions, Server manages state).

**Steps**
1.  **Define Message Structures**: Design the core JSON message schemas for all necessary interactions (Client $\to$ Server, Server $\to$ Client). This includes structures for:
    *   Client Actions (e.g., `MOVE_MOB`, `REQUEST_WORLD_STATE`).
    *   Server State Updates (e.g., `MOB_UPDATE`, `WORLD_UPDATE`).    *   **Message Definitions**: See `websocket_messages.json` for the defined schemas.2.  **Define Connection Lifecycle**: Outline the handshake process (connection establishment, authentication/initial state synchronization).
3.  **Implement Server Logic Flow**: Detail how the server will receive client actions, validate them, update the core game state (hex tiles, mob positions), and generate necessary state update messages. Outlined in `server_phase1_s3.md`
4.  **Implement Client Logic Flow**: Detail how the client will send input messages and how it will process incoming state update messages to render the game world.
5.  **Verification**:
    *   Verify that a client sending a `MOVE_MOB` command results in a corresponding `MOB_UPDATE` message being sent back to all relevant clients.
    *   Verify that the server correctly updates the hex tile data upon a state change.
    *   Verify that the JSON format is strictly adhered to for all messages.

**Relevant files**
- `MobSchema.md` — To define the structure of mob data being sent/received.
- `HexTileSchema.md` — To define the structure of hex tile data being sent/received.
- `server_implementation.md` — To guide the implementation of the server's WebSocket handling logic.

**Verification**
1.  Create mock client and server endpoints to test the basic message exchange flow.
2.  Manually trace a simple client action (e.g., move a mob) through the proposed message flow to ensure all state transitions are covered.
3.  Validate that the JSON payloads match the defined schemas.

**Decisions**
- **Protocol**: WebSocket with JSON payloads.
- **Message Types**: Clearly distinguish between command messages (Client $\to$ Server) and state messages (Server $\to$ Client).
- **State Management**: Server is the single source of truth for game state.

**Further Considerations**
1.  **Error Handling**: Close the connection and log the error.)
2.  **Mob/Tile Data Granularity**: Position updates are per-tile. Periodic world state snapshot.
