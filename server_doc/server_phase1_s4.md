**Implement Client Logic Flow**: Detail how the client will send input messages and how it will process incoming state update messages to render the game world.


Plan: Implement Client Logic Flow for Server Phase 1 Step 4
TL;DR - The goal is to implement the client-side logic flow that mirrors the server's message exchange for Phase 1 Step 4. This involves setting up WebSocket communication, handling outgoing user commands (MOVE_MOB, REQUEST_WORLD_STATE), and processing incoming state updates (MOB_UPDATE, WORLD_UPDATE) to correctly update the local application state and signal the renderer.

Steps

Phase 1: WebSocket Setup and Message Schemas
Set up the WebSocket client connection within the client application structure.
Verify the client-side message structures align with websocket_messages.json.
Implement basic connection/disconnection handlers.
Phase 2: Outgoing Message Implementation (Client 
→
→ Server)
Implement a function to capture user input (e.g., movement commands).
Implement logic to compose and serialize the MOVE_MOB message (including mobId and target coordinates).
Implement logic to compose and serialize the REQUEST_WORLD_STATE message (including clientId).
Implement the WebSocket sending mechanism for these composed messages.
Phase 3: Incoming Message Handling and State Update (Server 
→
→ Client)
Implement a message handler for MOB_UPDATE. This handler must parse the data and update the local state variables corresponding to mob health, brain state, and genes.
Implement a message handler for WORLD_UPDATE. This handler must parse the data and update the local state variables for hex tile resources and positions.
Implement a function to signal the rendering component/state manager upon any state change.
Phase 4: End-to-End Verification
Write unit/integration tests to simulate a full cycle: User Input 
→
→ Send 
→
→ Receive 
→
→ State Update 
→
→ Render Signal.
Manually test the flow by simulating a move command and observing the state change in the application view.
Relevant files

client directory: Will be the primary location for implementing the connection, message handlers, and state logic.
websocket_messages.json: Used as the definitive source for message structures.
viewer/viewer_doc/README.md / viewer/viewer_tasks.md: Reference for how the state updates should ultimately affect the viewer.
Verification

Unit Test: Verify that the message serialization functions correctly generate valid JSON payloads matching websocket_messages.json for MOVE_MOB and REQUEST_WORLD_STATE.
Integration Test: Simulate a server broadcast of a MOB_UPDATE message and assert that the local state variables (e.g., mob health) are correctly updated.
End-to-End Test: Execute a simulated user action (e.g., move a mob) and confirm the corresponding MOB_UPDATE or WORLD_UPDATE is received and reflected in the application view.
Decisions

Assumption: The client will utilize a standard WebSocket client library (to be determined in Phase 1 setup).
Scope: This plan focuses solely on the client-side implementation of the flow, not the server-side logic (which is assumed to be partially done).
Further Considerations

Error Handling: Define specific error handling for connection failures, malformed messages, and unexpected server responses. O Implement simple logging and reconnection logic.
State Management Pattern: Decide on the exact pattern for state management (e.g., Redux, simple observable pattern) to ensure clean separation between state updates and rendering calls. Option A: Use a simple observable pattern.