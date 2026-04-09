# # Server Phase 1 Step 3

Plan: Implement Server Logic Flow for WebSocket
TL;DR - Implement the server logic flow to handle client WebSocket messages by first parsing and validating commands, then atomically updating the core game state (hex tiles and mob positions) in the database, and finally generating and broadcasting appropriate state update messages to clients.

Steps

Message Reception & Parsing: Listen for incoming WebSocket messages, parse JSON payloads, and validate message structure against schemas defined in websocket_messages.json.
Action Validation: Validate incoming commands:
For MOVE_MOB: Check mobId existence, coordinate validity, mob status, and movement rules.
For REQUEST_WORLD_STATE: Validate clientId and determine the required scope of the world state snapshot.
Core Game State Updates:
Hex Tile Updates: Retrieve the target hex tile, update resource values (Water, Grass), and update the Updated timestamp, persisting changes to the database.
Mob Position Updates: Update the mob's location reference, adjust MobHealth (Hunger, Age, Health), update MobBrain, and update MobGene tables, persisting all changes to the database.
State Broadcast Generation:
For MOB_UPDATE messages: Gather the latest data from MobGene, MobHealth, and MobBrain to construct the required payload format.
For WORLD_UPDATE messages: Gather the updated hex tile data (coordinates, resources) to construct the required payload format.
Message Broadcasting:
Broadcast MOB_UPDATE to all relevant clients.
Broadcast WORLD_UPDATE to all relevant clients.
Send a confirmation response to the originating client regarding command execution success/failure.
Error Handling: Implement robust error paths: send error responses for invalid actions, log and close connections for database failures, and close connections for malformed JSON payloads.
Relevant files

server_phase1.md — Guide for the overall WebSocket protocol and flow.
websocket_messages.json — Defines the required JSON message schemas for command and state messages.
MobSchema.md — Defines the structure for mob data used in updates.
HexTileSchema.md — Defines the structure for hex tile data used in updates.
Verification

Unit Test Message Flow: Create mock client/server endpoints to test the basic message exchange flow (Client
→
→ Server
→
→ State Update
→
→ Server
→
→ Client).
Trace Execution: Manually trace a simple client action (e.g., move a mob) through the proposed message flow to ensure all state transitions and database calls are covered.
Schema Validation: Validate that all generated JSON payloads strictly adhere to the formats specified in websocket_messages.json.
Database Integrity Check: Verify that after a state change, the corresponding records in the SQLite3 database are correctly updated with the new timestamps and values.
Decisions

Server as single source of truth: All state modifications must be validated and executed server-side only.
Granularity: Position and resource updates must be handled on a per-hex-tile basis.
Protocol: Maintain strict distinction between command messages (Client
→
→ Server) and state messages (Server
→
→ Client).
Synchronization: All state changes must include Updated timestamps for client synchronization.
Further Considerations

Error Handling Detail: Define specific error codes and logging levels for database update failures vs. validation failures. (Option A: Log all errors to a centralized service. Option B: Close connection immediately upon DB failure.)
Mob/Tile Data Granularity: Determine the optimal frequency for periodic world state snapshots versus real-time per-tile updates. (Option A: Real-time for high-activity areas. Option B: Periodic snapshot every N seconds.)
