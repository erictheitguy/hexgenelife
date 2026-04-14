# Phase 3 Documentation - Viewer Interactions and Launcher

Phase 3 introduces user interactions in the viewer and a centralized launcher for managing the HexGenLife ecosystem.

## Viewer Interaction

The viewer now supports object selection and detailed inspection.

### Selection Logic
- **Left-Click** on any mob or hex tile to select it.
- Clicking a mob takes priority over a tile if they overlap.
- Selecting an object will highlight it:
    - **Mobs**: A white "under-glow" circle appears.
    - **Tiles**: A thick white outline appears around the hex.

### Information Panel (HUD)
When an object is selected, a details panel appears in the **top-right corner** of the screen.
- **Mob Details**: ID, Type, Coordinates, Health, Hunger, Fat, Age, Generation, and Fitness Score.
- **Tile Details**: Tile ID, Resources (Water/Grass), Center Coordinates, and last Updated timestamp.

## Launcher Application

The `hex_launcher.py` script provides a GUI (built with Tkinter) to manage all project components.

### Functions
1. **Server Control**: Start and stop the Python server. Displays real-time status.
2. **Viewer Control**: Launch multiple viewer instances.
3. **Client Management**:
    - **Existing Mobs**: Lists all mobs currently in the database. Permits launching a dedicated client for any selected mob.
    - **Stop All Clients**: Quickly terminates all running client processes.
4. **Mob Creation**:
    - A dedicated form to create new mobs with custom or randomized attributes.
    - **Save & Launch**: Automatically inserts the new mob into the database and starts a client for it.

### Safety Features
- **Single Server**: Prevents multiple server instances from running simultaneously.
- **Process Cleanup**: Closing the launcher automatically terminates all child processes (server, clients, viewers) to ensure a clean exit.
