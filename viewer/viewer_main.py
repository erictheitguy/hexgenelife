import os
import argparse
import pygame

from viewer.db_reader import DBReader
from viewer.camera import Camera
from viewer.renderer import Renderer

def main():
    parser = argparse.ArgumentParser(description="HexGenLife Pygame Viewer")
    default_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server", "game_state.db")
    parser.add_argument("--db", default=default_db, help="Path to game_state.db")
    args = parser.parse_args()

    pygame.init()
    
    # Window setup
    WIDTH, HEIGHT = 1280, 720
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("HexGenLife Phase 2 Viewer")
    
    font = pygame.font.SysFont("monospace", 14)
    
    db_reader = DBReader(args.db)
    camera = Camera(WIDTH, HEIGHT)
    renderer = Renderer(screen, font)
    
    clock = pygame.time.Clock()
    
    world_state = {"tiles": [], "mobs": []}
    
    # Selection state
    selected_mob_id = None
    selected_tile_id = None

    def point_in_polygon(x, y, polygon):
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if min(p1y, p2y) < y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside
    
    POLL_INTERVAL_MS = 500
    last_poll_time = 0
    
    running = True
    is_dragging = False
    
    while running:
        current_time = pygame.time.get_ticks()
        
        # 1. DB Polling
        if current_time - last_poll_time >= POLL_INTERVAL_MS:
            try:
                world_state = db_reader.get_world_state()
            except Exception as e:
                print(f"Error reading DB: {e}")
            last_poll_time = current_time
            
        # 2. Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            elif event.type == pygame.VIDEORESIZE:
                camera.screen_width = event.w
                camera.screen_height = event.h
                
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    is_dragging = True
                    # Selection check
                    mx, my = event.pos
                    wx, wy = camera.screen_to_world(mx, my)
                    
                    found_selection = False
                    # Check for mobs first (higher priority)
                    for mob in world_state.get("mobs", []):
                        dist = ((mob["x"] - wx)**2 + (mob["y"] - wy)**2)**0.5
                        # Radius is approx 4 in world units, allow 6 for hit area
                        if dist < 6:
                            selected_mob_id = mob["id"]
                            selected_tile_id = None
                            found_selection = True
                            break
                    
                    if not found_selection:
                        # Check for tiles
                        for tile in world_state.get("tiles", []):
                            if point_in_polygon(wx, wy, tile["polygon"]):
                                selected_tile_id = tile["id"]
                                selected_mob_id = None
                                found_selection = True
                                break
                    
                    if not found_selection:
                        selected_mob_id = None
                        selected_tile_id = None

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    is_dragging = False
                    
            elif event.type == pygame.MOUSEMOTION:
                if is_dragging:
                    camera.pan(event.rel[0], event.rel[1])
                    
            elif event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if event.y > 0:
                    camera.apply_zoom(camera.zoom * 0.1, mx, my)
                elif event.y < 0:
                    camera.apply_zoom(-camera.zoom * 0.1, mx, my)
                    
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    camera.reset()
                    
        # 3. Render
        renderer.render_world(camera, world_state, selected_mob_id, selected_tile_id)
        renderer.render_hud()
        
        # 4. Selection Info HUD
        selected_obj = None
        obj_type = None
        if selected_mob_id:
            for mob in world_state.get("mobs", []):
                if mob["id"] == selected_mob_id:
                    selected_obj = mob
                    obj_type = "mob"
                    break
        elif selected_tile_id:
            for tile in world_state.get("tiles", []):
                if tile["id"] == selected_tile_id:
                    selected_obj = tile
                    obj_type = "tile"
                    break
        
        if selected_obj:
            renderer.render_selection_info(selected_obj, obj_type)
        
        pygame.display.flip()
        clock.tick(60)

    db_reader.close()
    pygame.quit()

if __name__ == "__main__":
    main()