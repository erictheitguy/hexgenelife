# # Server Implementation
# Communication protocol is websocket.
# The server operates on a tick schedule. In each tick, the server processes all active mob actions
# (e.g., movement, interactions) and updates the persistent state in the SQLite database
# by referencing the MobSchema (MobGene, MobHealth, MobBrain) and HexTileSchema (for spatial data).
#
# WebSocket handling is responsible for receiving client commands (e.g., MOVE_MOB, REQUEST_WORLD_STATE)
# and broadcasting state updates (STATE messages) back to connected clients.
#
# Core Responsibilities:
# 1. Tick Management: Orchestrating the game loop and processing actions.
# 2. Database Interaction: CRUD operations on hex_tiles and mobs tables.
# 3. Validation: Ensuring all incoming client commands conform to schema rules.
# 4. State Broadcasting: Generating and sending structured STATE messages to clients.
#
# For detailed tick logic and interaction resolution, refer to the logic within server.py.
