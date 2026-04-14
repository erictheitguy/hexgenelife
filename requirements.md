# Requirements

Database sqllite3
Server is written in python
Client is written in python
Viewer is written in python using pygame.
Protocol: WebSocket for communication

User mermaid style for workflow and design outline.

Try to maintain test driven develeopment.

## Phase 1 Specific Requirements Additions

### 1. Game Loop and Tick Synchronization

- The server must implement a strict tick-based loop.
- Each connected client must be allocated a specific, limited number of actions per tick.
- The server must broadcast a 'tick_complete' signal to all clients once all active mobs have executed their actions for that tick.

### 2. Mob Interaction Logic

- Define the precise rules for breeding, attacking, and consumption. This must include:
  - Conditions under which an interaction is valid.
  - The resulting state change for the involved mobs (e.g., health reduction, consumption).
  - Any associated probabilities for random events.

### 3. Database Schema Specification

- The SQLite3 database schema must be fully defined, including tables for:
  - Hex Tile data (position, type, size).
  - Mob data (ID, position, health, status).
  - Interaction/History data.
- All schema definitions must be documented in detail.

### 4. Client Input Validation

- The server must validate all incoming client actions against current game state and client action limits. Invalid actions must result in a specific error response.
- The server must strictly enforce that all movement coordinates are integers. Non-integer coordinates in a `MOVE_MOB` command must be rejected.

### 5. Error Handling

- A standardized error response format must be defined for all server-side errors, including specific error codes for common issues (e.g., invalid input, connection error).

### 6. Server start

- The server is able to start and able to accept incoming web socket connections. It connects to the sqllite database, ensures that the database is populated with at least 1 hexagon.

### 7. Client Start

- The client is able to start and connect to a running server. It creates a mob if one does not exist and then performs randmom movemtent updates.

## Phase 2 Specific Requirements Additions

### 1. Viewer Render

- A viewer that connects to the SQLite database in read-only mode and renders the hex tiles and existing mobs.
- The viewer **must not** write to the database.
- Should update from the database at a fixed wall-clock interval of **500 ms** (not per frame).
- Allow the user to pan the world view (left-click drag) and zoom in/out (scroll wheel).
- The `R` key resets the camera to the origin and default zoom.
- **Future phase note**: The poll interval should be exposed as a user-adjustable setting in the viewer UI.

#### Hex Tile Colour Rules

| Condition | Colour |
|-----------|--------|
| `Grass > 0` | Green |
| `Grass == 0` and `Water > 50` | Blue |
| `Grass == 0` and `0 < Water ≤ 50` | Muted teal |
| `Grass == 0` and `Water == 0` | Brown |

#### Mob Colour Rules

| `mob_type` | Colour |
|------------|--------|
| `predator` | Red |
| `prey` | Yellow |

- A colour legend HUD is displayed in the bottom-left corner of the window at all times.

### 2. Dynamic World Expansion (Server)

- When a mob moves to coordinates that do not fall within any existing hex tile, the server must automatically create a new adjacent hex tile covering that location.
- The new tile's `Water` and `Grass` values must be set to the **arithmetic mean of the same attribute across all existing neighbouring tiles** (up to 6 neighbours in a flat-top hex grid).
- **Missing neighbours are excluded from the average** — they do not contribute a zero or any other value.
- If no neighbours exist (edge case), defaults are used: `Water = 5.0`, `Grass = 3.0`.
- After creation, the server broadcasts a `HEX_CREATED` message.
- `HEX_CREATED` is sent **only** to clients whose mobs are within `HEX_CREATION_BROADCAST_RANGE = 100` units of the new tile's centre.

### 3. Client Auto-Reconnect

- The client must automatically attempt to reconnect if the WebSocket connection drops unexpectedly.
- Reconnect uses **exponential back-off**: starting at 1 s, doubling each attempt, capped at 30 s.
- On successful reconnect the client sends `REQUEST_WORLD_STATE` to re-sync before resuming the movement loop.

### 4. HEX_CREATED Client Message Handling

- The client must handle the `HEX_CREATED` server broadcast.
- On receipt, the new tile must be added to the client's local `worldTiles` state.

## Phase 3 Specific Requirements Additions

### 1. Viewer Interactions

- Update viewer to allow the user to click on a tile and get the relevant data about that tile.

- Update viewer to allow the user to click on a mob and get relevant data about that mob.

- Create a launcher application. It will launch the server, client or viewer. It should have the ability to stop any of the items it launches. For the server it should only allow launching of one server at a time. For the client it should allow for a selection of mob ids to be passed to it for that particular client to handle. It should allow for multiple clients to run but mob ids should not be allowed to be passed to multiple clients at once.

## Phase 4 Specific Requirements Additions

 - Start the implementation of the basic mob functions. 
 - 


## Phase 5 Specific Requirements Additions

- Split up server.py logically into smaller class files so that all similar functions are grouped together. Such as mob interactions into one file and message validation into another.
- Add the ability for the server to spawn sub processes that interact with the game world. The two sub processes that spawn will be one that creates rain and another that grows grass. 
- Rain will spawn at the far edge of the world and move across it to the other side. The direction it moves will be set randomly at the start and it will continue in that direction until it reaches the end of the game world. The size of the rain cloud will be random from 10 to 500 units across. It will move at a rate of 5 units per server tic. For each hexagon tile it crosses it will update the water value of that tile by a certain amount per server tic. The amount of water updated will be set by a random number for that rain cloud. A rain cloud will spawn once ever 500 server tics.
- The sub process for grass will update the grass value of all the hexagon tiles for the game world. It will update all hex tiles at least once every 100 server tics. It will update the grass value if the hexagon tile has a value of water in it. For each unit of water the hexagon till has it will increase the value of the grass value by two. It will then decrease the value of water by one for that hexagon. If the hexagon has a water value of zero then it will decrease the grass value by 1. If a tile has a water value of zero no grass can grow. 

## Phase 6 Specific Requirements Additions

- Split up the client logically into smaller class files. Group similar functions into the same file. 