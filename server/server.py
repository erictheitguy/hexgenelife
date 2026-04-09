import json
import sqlite3
import websockets
# Assume websocket_messages.json is available for schema validation
# Assume a mechanism for WebSocket connection handling exists

class GameServer:
    def __init__(self, db_path="game_state.db"):
        self.db_path = db_path
        self.db_conn = None
        self._initialize_db()
        # Placeholder for message parsing/validation logic
        print("GameServer initialized. Database connection established.")

    def _initialize_db(self):
        """Initializes the SQLite database and necessary tables."""
        self.db_conn = sqlite3.connect(self.db_path)
        cursor = self.db_conn.cursor()
        # Placeholder for creating tables based on requirements (hex tiles, mobs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hex_tiles (
                tile_id TEXT PRIMARY KEY,
                resource TEXT,
                timestamp REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mobs (
                mob_id TEXT PRIMARY KEY,
                position TEXT,
                health INTEGER,
                brain REAL,
                genes REAL,
                timestamp REAL
            )
        """)
        self.db_conn.commit()
        print(f"Database initialized at {self.db_path}")

    def _validate_message(self, message: dict, command_type: str) -> bool:
        """1. Message Reception & Parsing: Validates message structure against schema."""
        # TODO: Replace this with actual JSON schema validation logic (e.g., using jsonschema library)
        # For now, we perform a very basic structural check.
        required_fields = {
            "MOVE_MOB": ["mob_id", "new_pos"],
            "REQUEST_WORLD_STATE": ["client_id", "scope"]
        }
        
        if command_type in required_fields:
            for field in required_fields[command_type]:
                if field not in message.get("data", {}):
                    print(f"Validation Error: Missing required field '{field}' for command type '{command_type}'.")
                    return False
        
        # TODO: Add complex schema validation here based on websocket_messages.json content

        return True

    def receive_message(self, raw_message: str):
        """1. Message Reception & Parsing"""
        try:
            message = json.loads(raw_message)
            command_type = message.get("type")
            data = message.get("data")

            if not self._validate_message(message, command_type):
                return # Stop processing if validation fails

            if command_type == "MOVE_MOB":
                self._handle_move_mob(data)
            elif command_type == "REQUEST_WORLD_STATE":
                self._handle_request_world_state(data)
            else:
                print(f"Unknown command type received: {command_type}")
        except json.JSONDecodeError:
            print("Error: Malformed JSON received.")
        except Exception as e:
            print(f"Error during message processing: {e}")

    def _handle_move_mob(self, data: dict):
        """2. Action Validation & 3. Core Game State Updates for MOVE_MOB"""
        try:
            mob_id = data.get("mob_id")
            new_pos = data.get("new_pos")

            if not mob_id or not new_pos:
                print("Error: MOVE_MOB data missing mob_id or new_pos.")
                return
            # --- 2. Action Validation (Placeholder) ---
            # TODO: Implement validation against websocket_messages.json schema
            # TODO: Validate mob existence, coordinates, and movement rules
            if not self._mob_exists(mob_id):
                print(f"Error: Mob {mob_id} does not exist.")
                return
            # Add coordinate/rule validation here...

            # --- 3. Core Game State Updates ---
            if not self.db_conn:
                print("Error: Database connection is not established.")
                return
            cursor = self.db_conn.cursor()
            timestamp = self._get_current_timestamp()
            # Atomically update mob position and timestamp
            cursor.execute("""
                UPDATE mobs
                SET position = ?, timestamp = ?
                WHERE mob_id = ?
            """, (new_pos, timestamp, mob_id))
            self.db_conn.commit()
            print(f"Successfully updated mob {mob_id} position to {new_pos}.")
        except ConnectionError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Database or validation error during MOVE_MOB: {e}")
            # Error Handling: Handle database failures
            if self.db_conn:
                self.db_conn.rollback()

    def _handle_request_world_state(self, data: dict):
        """2. Action Validation & 3. Core Game State Updates for REQUEST_WORLD_STATE"""
        try:
            client_id = data.get("client_id")
            scope = data.get("scope")

            if not client_id or not scope:
                print("Error: REQUEST_WORLD_STATE data missing client_id or scope.")
                return

            # --- 2. Action Validation (Placeholder) ---
            # TODO: Validate client ID and scope
            if not self._is_valid_client(client_id, scope):
                print(f"Error: Invalid client request from {client_id} for scope {scope}.")
                return

            # --- 3. Core Game State Updates ---
            if not self.db_conn:
                print("Error: Database connection is not established.")
                return
            cursor = self.db_conn.cursor()
            
            # Fetch current world state (example: fetching all mobs and tiles)
            cursor.execute("SELECT * FROM mobs")
            mobs_data = cursor.fetchall()
            
            cursor.execute("SELECT * FROM hex_tiles")
            tiles_data = cursor.fetchall()
            
            world_state = {
                "mobs": [dict(row) for row in mobs_data],
                "tiles": [dict(row) for row in tiles_data]
            }
            
            print(f"Successfully retrieved world state for client {client_id}.")
            # TODO: Construct WORLD_UPDATE message and send to client
            # self.generate_broadcast("WORLD_UPDATE", world_state)

        except Exception as e:
            print(f"Database or validation error during REQUEST_WORLD_STATE: {e}")
            # Error Handling: Handle database failures
            if self.db_conn:
                self.db_conn.rollback()

    def _mob_exists(self, mob_id: str) -> bool:
        """Helper to check if a mob exists in the database."""
        if not self.db_conn:
                print("Error: Database connection is not established.")
                return False
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT 1 FROM mobs WHERE mob_id = ?", (mob_id,))
        return cursor.fetchone() is not None

    def _is_valid_client(self, client_id: str, scope: str) -> bool:
        """Helper to validate client credentials/scope."""
        # TODO: Implement actual validation logic here
        return True # Placeholder: Assume valid for now

    def _get_current_timestamp(self) -> float:
        """Helper to get the current timestamp."""
        import time
        return time.time()

    def generate_broadcast(self, message_type: str, payload: dict):
        """4. State Broadcast Generation"""
        # TODO: Construct MOB_UPDATE or WORLD_UPDATE messages
        broadcast_message = {
            "type": message_type,
            "data": payload
        }
        print(f"Generated {message_type} broadcast: {json.dumps(broadcast_message)}")
        # TODO: 5. Message Broadcasting (Send to clients)
        pass

    def close(self):
        if self.db_conn:
            self.db_conn.close()
            print("Database connection closed.")

# --- Main execution block (WebSocket server setup) ---
async def main():
    server = GameServer()
    # Start the WebSocket server
    async with websockets.serve(server.receive_message, "localhost", 8765):
        print("WebSocket server started on ws://localhost:8765")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer shutting down.")
        # In a real app, you might call server.close() here if it manages resources
