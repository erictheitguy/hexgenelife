import pygame

COLOR_GRASS = (76, 175, 80)     # #4CAF50
COLOR_DEEP_WATER = (33, 150, 243) # #2196F3
COLOR_SHALLOW_WATER = (96, 125, 139) # #607D8B
COLOR_BARREN = (121, 85, 72)     # #795548

COLOR_MOB_PREDATOR = (244, 67, 54) # #F44336
COLOR_MOB_PREY = (255, 235, 59)    # #FFEB3B
COLOR_MOB_OTHER = (255, 255, 255) # #FFFFFF

class Renderer:
    def __init__(self, screen, font):
        self.screen = screen
        self.font = font
        
    def get_hex_color(self, water, grass):
        if grass > 0:
            return COLOR_GRASS
        elif water > 50:
            return COLOR_DEEP_WATER
        elif water > 0:
            return COLOR_SHALLOW_WATER
        return COLOR_BARREN
        
    def get_mob_color(self, mob_type):
        if mob_type == "predator":
            return COLOR_MOB_PREDATOR
        elif mob_type == "prey":
            return COLOR_MOB_PREY
        return COLOR_MOB_OTHER

    def render_world(self, camera, world_state, selected_mob_id=None, selected_tile_id=None):
        self.screen.fill((30, 30, 30))
        
        # Render tiles
        for tile in world_state.get("tiles", []):
            color = self.get_hex_color(tile["water"], tile["grass"])
            poly_screen = [camera.world_to_screen(px, py) for px, py in tile["polygon"]]
            pygame.draw.polygon(self.screen, color, poly_screen)
            
            # Highlight OR standard outline
            if tile["id"] == selected_tile_id:
                pygame.draw.polygon(self.screen, (255, 255, 255), poly_screen, 3) # Thick white highlight
            else:
                pygame.draw.polygon(self.screen, (0, 0, 0), poly_screen, 1)
            
        # Render mobs
        for mob in world_state.get("mobs", []):
            color = self.get_mob_color(mob["type"])
            sx, sy = camera.world_to_screen(mob["x"], mob["y"])
            radius = max(2, int(4 * camera.zoom))
            
            # Highlight under-glow for selected mob
            if mob["id"] == selected_mob_id:
                pygame.draw.circle(self.screen, (255, 255, 255), (int(sx), int(sy)), radius + 3, 2)

            pygame.draw.circle(self.screen, color, (int(sx), int(sy)), radius)
            pygame.draw.circle(self.screen, (0, 0, 0), (int(sx), int(sy)), radius, 1)

    def render_hud(self):
        panel_rect = pygame.Rect(10, self.screen.get_height() - 170, 250, 160)
        
        # Draw transparent background via alpha surface
        s = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
        s.fill((40, 40, 40, 180))
        self.screen.blit(s, (panel_rect.x, panel_rect.y))
        pygame.draw.rect(self.screen, (200, 200, 200), panel_rect, 2)
        
        lines = [
            ("Grass present", COLOR_GRASS, "square"),
            ("Deep water", COLOR_DEEP_WATER, "square"),
            ("Shallow water", COLOR_SHALLOW_WATER, "square"),
            ("Barren", COLOR_BARREN, "square"),
            ("Predator mob", COLOR_MOB_PREDATOR, "circle"),
            ("Prey mob", COLOR_MOB_PREY, "circle"),
        ]
        
        y = panel_rect.top + 10
        for text, color, shape in lines:
            if shape == "square":
                pygame.draw.rect(self.screen, color, (20, y, 15, 15))
            else:
                pygame.draw.circle(self.screen, color, (27, y + 7), 7)
            
            surface = self.font.render(text, True, (255, 255, 255))
            self.screen.blit(surface, (45, y))
            y += 24

    def render_selection_info(self, selected_obj, obj_type):
        if not selected_obj:
            return
            
        panel_w = 300
        panel_h = 220
        panel_rect = pygame.Rect(self.screen.get_width() - panel_w - 10, 10, panel_w, panel_h)
        
        # Transparent background
        s = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
        s.fill((40, 40, 40, 220))
        self.screen.blit(s, (panel_rect.x, panel_rect.y))
        pygame.draw.rect(self.screen, (255, 255, 255), panel_rect, 1)
        
        header = f"Selection: {obj_type.upper()}"
        surf = self.font.render(header, True, (255, 215, 0)) # Gold
        self.screen.blit(surf, (panel_rect.x + 10, panel_rect.y + 10))
        
        lines = []
        if obj_type == "mob":
            lines = [
                f"ID: {selected_obj['id']}",
                f"Type: {selected_obj['type']}",
                f"Pos: ({selected_obj['x']}, {selected_obj['y']})",
                f"Health: {selected_obj['health']:.1f}",
                f"Hunger: {selected_obj['hunger']:.1f}",
                f"Fat: {selected_obj['fat']:.1f}",
                f"Age: {selected_obj['age']:.1f}",
                f"Gen: {selected_obj['generation']}",
                f"Fitness: {selected_obj['fitness'] if selected_obj['fitness'] is not None else 'N/A'}"
            ]
        elif obj_type == "tile":
            lines = [
                f"Tile ID: {selected_obj['id']}",
                f"Resources:",
                f"  Water: {selected_obj['water']:.1f}",
                f"  Grass: {selected_obj['grass']:.1f}",
                f"Center: ({selected_obj['centerX']:.1f}, {selected_obj['centerY']:.1f})",
                f"Updated: {selected_obj['updated']}"
            ]
            
        y = panel_rect.y + 40
        for line in lines:
            surf = self.font.render(line, True, (240, 240, 240))
            self.screen.blit(surf, (panel_rect.x + 10, y))
            y += 18
