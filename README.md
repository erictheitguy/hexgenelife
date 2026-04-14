# HexGenLife

===========
An expansion on Conways game of life.

Learning experience in genetic adaption models in a simplifed computer simulation.
Requirements -> requirements.md

## Game World -

The game world will consist of hexagon tiles. The hexagon size is 5 units from the center to the side or top. So the distance between the two sides of the hexagon as an example from top to bottom is 10 units. Each hex tile has grass and water values. Grass consume water to grow and mobs eat the grass.

## Mobs -

Mobs are simulated entites that interact in the game world. At the start there are two primary mob types. A predator and prey. Prey eat grass and predators puruse the prey. At a certain point mobs will breed with their respective type and produce offspring.

Parts:
A server that clients connect to. The server connects to a sqllite3 database that contains the data. The server and clients will operate on a tick schedule. In that each client gets a limited amount of actions it can perform per tick. The server will keep track of all active mobs and once all active mobs have performed their actions for that tick, it will inform connected clients that they can began submitting the next set of actions. The server will also handle informing the client if two mobs interacted and the outcome of that interactions. Interactions could be breding or attacking in order to reduce the health of a mob so that it may be consumed for food.
See folder server_doc for more infomation.  

A viewer that allows a user to see the simulated world. It connects directly to the sqllite database. It only performs read only actions. The controls allow you to pan /zoom around the world. Click on mobs and view the information about them.
See folder viewer_doc for more infomation.

A client which represents the mobs. It will connect to the server. It will be able to process a certain number of mobs. It will take in a list of ids which represent the ids of the mobs it should process.
See folder client_doc for more infomation.

Schema for the game world of hex tiles is HexTileSchema.md
Schema for the mobs is MobSchema.md

## Setup and Installation

Before running the project, you need to set up a Python virtual environment and install the required dependencies.

### 1. Create a Virtual Environment (Optional but Recommended)
In the project root directory, run:
```powershell
python -m venv .venv
```

### 2. Activate the Virtual Environment
- **Windows (PowerShell):**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- **Windows (CMD):**
  ```cmd
  .\.venv\Scripts\activate.bat
  ```
- **Linux/macOS:**
  ```bash
  source .venv/bin/activate
  ```

### 3. Install Dependencies
Once the virtual environment is activated, install the required packages:
```bash
pip install -r requirements.txt
```
*Note: If you are using Python 3.14+, you may need to install `pygame-ce` instead of `pygame`: `pip install pygame-ce`.*

## Running the Project

To run the different components of HexGenLife, ensure you are in the project root directory.

### 1. Launch the Server
The server manages the game state, handles WebSocket connections, and synchronizes ticks.
```bash
python server/server.py
```
*Note: This will manage the `game_state.db` located within the `server/` folder by default.*

### 2. Launch the Client(s)
Clients represent mobs and connect to the server. You can specify one or more client IDs to run multiple mob controllers.
```bash
# Start a single client with default ID (client_1)
python client/websocket_client.py

# Start multiple clients with specific IDs
python client/websocket_client.py client_1 client_2 client_3
```

### 3. Launch the Viewer
The viewer provides a real-time visualization of the hex grid and mobs. It connects directly to the database in read-only mode.
```bash
python -m viewer.viewer_main
```

### Running Tests
To verify the system and ensure all components are functioning correctly, run the test suite:
```bash
pytest
```
