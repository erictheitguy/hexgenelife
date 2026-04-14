# Viewer Tasks

## Phase 2
See `viewer_phase2.md` for design details.

### Project Structure
- [ ] Create `viewer/db_reader.py` — read-only SQLite queries for tiles and mobs
- [ ] Create `viewer/camera.py` — camera state and world-to-screen transform
- [ ] Create `viewer/renderer.py` — hex tile polygon draw, mob dot draw, HUD legend
- [ ] Rewrite `viewer/viewer_main.py` as Pygame entry point with main loop

### Database Reader (`db_reader.py`)
- [ ] Open database in read-only URI mode
- [ ] `fetch_tiles()` — return all rows from `hex_tiles` table
- [ ] `fetch_mobs()` — return alive mobs (`mob_health.health > 0`) joined with `mobs`

### Camera (`camera.py`)
- [ ] Store `offset_x`, `offset_y` (world-space pan) and `zoom` (default 1.0)
- [ ] `world_to_screen(world_x, world_y)` transform function
- [ ] `handle_pan(dx, dy)` — adjust offset on left-click drag
- [ ] `handle_zoom(delta, mouse_pos)` — scroll wheel, range 0.1×–10×
- [ ] `reset()` — return camera to origin and zoom 1.0

### Renderer (`renderer.py`)
- [ ] `draw_tile(surface, tile, camera)` — filled polygon with terrain colour rule
  - [ ] Green (`#4CAF50`) when `Grass > 0`
  - [ ] Blue (`#2196F3`) when `Grass == 0` and `Water > 50`
  - [ ] Teal (`#607D8B`) when `Grass == 0` and `0 < Water <= 50`
  - [ ] Brown (`#795548`) when `Grass == 0` and `Water == 0`
- [ ] `draw_mob(surface, mob, camera)` — filled circle
  - [ ] Red (`#F44336`) for `predator`
  - [ ] Yellow (`#FFEB3B`) for `prey`
- [ ] `draw_legend(surface)` — fixed HUD panel bottom-left

### Main Loop (`viewer_main.py`)
- [ ] Pygame init, create window (1280×720), set title "HexGenLife Viewer"
- [ ] 60 FPS render loop
- [ ] Wall-clock DB poll every 500 ms (not every frame)
- [ ] Handle `QUIT` event
- [ ] Handle left-click drag for pan
- [ ] Handle scroll wheel for zoom
- [ ] Handle `R` key for camera reset

### Tests
- [ ] `test_colour_selection` — Water/Grass → correct colour constant
- [ ] `test_camera_world_to_screen` — known input → correct screen coordinates
- [ ] `test_camera_zoom_clamp` — zoom never exceeds [0.1, 10.0]