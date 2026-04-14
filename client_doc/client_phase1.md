# Client Phase 1: Logic Flow

**TL;DR** - The goal is to implement the client-side logic flow that handles the client's role in the simulation. This involves setting up WebSocket communication, handling autonomous client actions (such as random movements of assigned mobs, `MOVE_MOB`, `REQUEST_WORLD_STATE`), and processing incoming state updates (`MOB_UPDATE`, `WORLD_UPDATE`) to correctly update the local state.

## Steps

### 1. WebSocket Setup and Message Schemas
* Set up the WebSocket client connection to the server within the client application structure.
* Verify the client-side message structures align with `websocket_messages.json`.
* Implement basic connection and disconnection event handlers.

### 2. Outgoing Message Implementation (Client $\to$ Server)
* Implement logic to connect to the server and ensure a mob exists for the client to control.
* Implement a continuous loop/routine that performs random movements or automated actions for the assigned mob based on available tick actions.
* Implement logic to compose and serialize the `MOVE_MOB` message (including `mobId` and target coordinates).
* Implement logic to compose and serialize the `REQUEST_WORLD_STATE` message (including `clientId`).
* Implement the WebSocket sending mechanism for these composed messages.

### 3. Incoming Message Handling and State Update (Server $\to$ Client)
* Implement a message handler for `MOB_UPDATE`. This handler must parse the data and update the local state variables corresponding to mob health, brain state, and genes.
* Implement a message handler for `WORLD_UPDATE`. This handler must parse the data and update the local state variables for hex tile resources and positions.

### 4. End-to-End Verification
* Write unit/integration tests to simulate a full cycle: Action Logic $\to$ Send $\to$ Receive $\to$ State Update.
* Execute the client and verify it successfully connects, assigns/creates a mob, and begins sending random movement commands that mirror back as `MOB_UPDATE` messages from the server.

## Relevant files

* `client` directory: The primary location for implementing the connection, message handlers, and state logic.
* `websocket_messages.json`: Used as the definitive source for message structures.

## Verification

1. **Unit Test**: Verify that the message serialization functions correctly generate valid JSON payloads matching `websocket_messages.json` for `MOVE_MOB` and `REQUEST_WORLD_STATE`.
2. **Integration Test**: Simulate a server broadcast of a `MOB_UPDATE` message and assert that the local state variables are correctly updated.
3. **End-to-End Test**: Execute the client against a running server and confirm it connects and performs autonomous actions as specified in the Phase 1 requirements.

## Decisions

* **Assumption**: The client will utilize a standard WebSocket client library (e.g., `websockets` in python).
* **Role**: In Phase 1, the client acts primarily as an automated agent driving mob behavior (random movements), rather than a human-controlled interface. (The Viewer handles rendering, which is Phase 2).

## Further Considerations

* **Error Handling**: Define specific error handling for connection failures, malformed messages, and unexpected server responses. Implement simple logging and auto-reconnection logic.
* **Tick Synchronization**: Ensure the client responds to or respects the tick synchronization from the server, keeping actions within the allocated limits per tick.
