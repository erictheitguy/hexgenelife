# # Requirements

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

### 5. Error Handling
- A standardized error response format must be defined for all server-side errors, including specific error codes for common issues (e.g., invalid input, connection error).
