import sqlite3
import json
import os
import sys
import subprocess
import time

# Ensure we can import from server/client
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server.mob_manager import MobManager
from server.mob_interactions import MobInteractions

def manual_breed(parent_a_id, parent_b_id):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server", "game_state.db")
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    mob_manager = MobManager(conn)
    
    # MobInteractions needs a 'server' object for broadcasts if we use handle_breed,
    # but we extracted breed_mobs which doesn't broadcast.
    class DummyServer:
        async def broadcast(self, msg_type, payload):
            pass
            
    dummy_server = DummyServer()
    interactions = MobInteractions(dummy_server, conn, mob_manager)
    
    if not mob_manager.mob_exists(parent_a_id):
        print(f"Error: Parent A {parent_a_id} does not exist.")
        conn.close()
        return
    if not mob_manager.mob_exists(parent_b_id):
        print(f"Error: Parent B {parent_b_id} does not exist.")
        conn.close()
        return
        
    print(f"Breeding {parent_a_id} and {parent_b_id}...")
    try:
        # breed_mobs is a synchronous method now
        child_id = interactions.breed_mobs(parent_a_id, parent_b_id)
        print(f"Successfully created offspring: {child_id}")
    except Exception as e:
        print(f"Error during breeding: {e}")
        conn.close()
        return
    
    conn.close()
    
    # Start the client for the new mob
    print(f"Starting client for {child_id}...")
    # Use the client ID 'manual_client'
    client_id = f"manual_{child_id[:12]}"
    
    # Try to find a suitable python executable (prefer .venv)
    python_exe = sys.executable
    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python")
    if os.path.exists(venv_python):
        python_exe = venv_python
    
    # Run the client in a new process
    try:
        subprocess.Popen([python_exe, "-m", "client.websocket_client", client_id, "--mobs", child_id])
        print(f"Client process launched using {python_exe}. It will connect to the server and manage {child_id}.")
    except Exception as e:
        print(f"Error starting client: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python manual_breed.py <parent_a_id> <parent_b_id>")
    else:
        manual_breed(sys.argv[1], sys.argv[2])
