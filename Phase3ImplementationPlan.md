# Phase 3 Implementation Plan - Viewer Enhancements & Launcher

This plan covers the implementation of Phase 3 requirements: Viewer interactions (clicking tiles/mobs) and a centralized Launcher application.

## User Review Required

> [!IMPORTANT]
> **Launcher UI Technology**: I am proposing to use `tkinter` for the launcher application as it is built-in, lightweight, and well-suited for a utility application that manages subprocesses.
> **Selection Display**: In the viewer, the clicking interactions will show a new "Details" panel in the top-right corner.
> **Process Management**: The launcher will track subprocesses by PID and handle cleanup. It will also enforce the "single server" and "unique mob ID" rules.

## Proposed Changes

---

### Viewer Enhancements

#### [MODIFY] [db_reader.py](file:///c:/Users/eric/hexgenlife/viewer/db_reader.py)
- Update `get_world_state` to fetch additional fields:
    - Mobs: `hunger`, `fat`, `age`, `mobType`, `fitnessScore`, `generation`.
    - Tiles: `Updated`, `centerX`, `centerY`.

#### [MODIFY] [renderer.py](file:///c:/Users/eric/hexgenlife/viewer/renderer.py)
- Add selection highlighting logic.
- Implement selection HUD (top-right side).
- Add a helper method for point-in-polygon detection for tiles.

#### [MODIFY] [viewer_main.py](file:///c:/Users/eric/hexgenlife/viewer/viewer_main.py)
- Add state variables: `selected_mob_id` and `selected_tile_id`.
- Update event loop to handle `MOUSEBUTTONDOWN` for selection.
- Clear selection when clicking empty space.
- Display detailed info in the HUD when an object is selected.

---

### Launcher Application

#### [NEW] [hex_launcher.py](file:///c:/Users/eric/hexgenlife/hex_launcher.py)
- Create a Tkinter-based GUI.
- **Server Control**: Start/Stop `server/server.py`. Detect if server is already running.
- **Client Control**:
    - **Existing Mobs**: Query `game_state.db` for existing Mob IDs and launch clients.
    - **Create New Mob**: 
        - UI for entering Mob ID, type, and health/gene attributes (hunger, fat, age, health, fitness score, generation).
        - "Randomize" button to generate default/random values for attributes.
        - "Save & Launch" button to insert the mob into the database and start a client process for it.
    - Track active clients to prevent ID overlap and manage multiple processes.
- **Viewer Control**: Button to launch `viewer/viewer_main.py`.
- **Process Tracking**: Maintain a list of active `subprocess.Popen` objects and ensure they are terminated on exit.

---

### Documentation & Tasks

#### [MODIFY] [Tasks.md](file:///c:/Users/eric/hexgenlife/Tasks.md)
- Add Phase 3 tasks to the overall checklist.

#### [NEW] [viewer_doc/viewer_phase3.md](file:///c:/Users/eric/hexgenlife/viewer_doc/viewer_phase3.md)
- Document the new viewer features and selection logic.

## Open Questions

- All questions resolved. User requested mob creation in the launcher with editable/random values.

## Verification Plan

### Automated Tests
- No new automated tests planned yet, but I will verify `point_in_polygon` logic via manual interaction.

### Manual Verification
1. **Viewer Selection**:
    - Launch server and client.
    - Open viewer.
    - Click on a moving mob -> Verify info panel shows ID, health, age, etc.
    - Click on a hex tile -> Verify info panel shows resources and coordinates.
    - Click empty space -> Selection clears.
2. **Launcher**:
    - Start launcher.
    - Start server -> Check status.
    - Try to start another server -> Verify it's blocked.
    - Select a mob ID and launch a client -> Verify the client starts and handles that mob.
    - Stop the server from the launcher -> Verify the process ends.
    - Close the launcher -> Verify all child processes (clients, viewer) are closed.
