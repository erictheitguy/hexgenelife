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
        self.brain_btn_rect = None
        self.brain_window_rect = None
        self.lineage_btn_rect = None
        self.lineage_window_rect = None
        
    def get_hex_color(self, water, grass):
        if grass > 0:
            # Interpolate from light green (low grass) to dark green (high grass)
            # grass range roughly 0–20; clamp to [0, 20]
            t = min(1.0, grass / 20.0)
            r = int(200 - t * 124)  # 200 → 76
            g = int(230 - t * 55)   # 230 → 175
            b = int(150 - t * 70)   # 150 → 80
            return (r, g, b)
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
            size = mob.get("size", 1.0)
            radius = max(2, int(size * camera.zoom * 2))

            # Life stage ring: infant=cyan, adult=no ring, elder=orange
            life_stage = mob.get("life_stage", "adult")
            if life_stage == "infant":
                pygame.draw.circle(self.screen, (0, 220, 220), (int(sx), int(sy)), radius + 3, 2)
            elif life_stage == "elder":
                pygame.draw.circle(self.screen, (255, 140, 0), (int(sx), int(sy)), radius + 3, 2)
            
            # Highlight under-glow for selected mob
            if mob["id"] == selected_mob_id:
                pygame.draw.circle(self.screen, (255, 255, 255), (int(sx), int(sy)), radius + 5, 2)
            
            # Highlight active mobs with an outer green glow
            if mob.get("is_active"):
                pygame.draw.circle(self.screen, (0, 255, 0), (int(sx), int(sy)), radius + 2, 2)

            pygame.draw.circle(self.screen, color, (int(sx), int(sy)), radius)
            pygame.draw.circle(self.screen, (0, 0, 0), (int(sx), int(sy)), radius, 1)

    def render_hud(self, tick_counter=0):
        panel_rect = pygame.Rect(10, self.screen.get_height() - 195, 250, 185)
        
        # Draw transparent background via alpha surface
        s = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
        s.fill((40, 40, 40, 180))
        self.screen.blit(s, (panel_rect.x, panel_rect.y))
        pygame.draw.rect(self.screen, (200, 200, 200), panel_rect, 2)

        # Tick counter at top
        tick_surf = self.font.render(f"Tick: {tick_counter}", True, (255, 215, 0))
        self.screen.blit(tick_surf, (20, panel_rect.top + 8))
        
        lines = [
            ("Grass (dense)", (76, 175, 80), "square"),
            ("Grass (sparse)", (200, 230, 150), "square"),
            ("Deep water", COLOR_DEEP_WATER, "square"),
            ("Shallow water", COLOR_SHALLOW_WATER, "square"),
            ("Barren", COLOR_BARREN, "square"),
            ("Predator mob", COLOR_MOB_PREDATOR, "circle"),
            ("Prey mob", COLOR_MOB_PREY, "circle"),
        ]
        
        y = panel_rect.top + 28
        for text, color, shape in lines:
            if shape == "square":
                pygame.draw.rect(self.screen, color, (20, y, 15, 15))
            else:
                pygame.draw.circle(self.screen, color, (27, y + 7), 7)
            
            surface = self.font.render(text, True, (255, 255, 255))
            self.screen.blit(surface, (45, y))
            y += 22

    def render_selection_info(self, selected_obj, obj_type):
        self.brain_btn_rect = None
        self.lineage_btn_rect = None
        if not selected_obj:
            return
            
        panel_w = 300
        panel_h = 240
        if obj_type == "mob":
            panel_h = 360
            
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
            lineage = selected_obj.get("lineage")
            lines = [
                f"ID: {selected_obj['id']}",
                f"Species: {selected_obj.get('species_name', 'Unknown')}",
                f"Type: {selected_obj['type']}",
                f"Stage: {selected_obj.get('life_stage', 'unknown')}",
                f"Pos: ({selected_obj['x']:.1f}, {selected_obj['y']:.1f})",
                f"Health: {selected_obj['health']:.1f}",
                f"Energy: {selected_obj.get('energy', 0):.1f}",
                f"Hunger: {selected_obj['hunger']:.1f}",
                f"Fat: {selected_obj['fat']:.1f}",
                f"Age: {selected_obj['age']:.1f}",
                f"Gen: {selected_obj['generation']}",
                f"Fitness: {selected_obj['fitness'] if selected_obj['fitness'] is not None else 'N/A'}",
            ]
            if lineage:
                root = lineage[0]
                lines += [
                    f"Parent A: {root.get('parent_a_id') or 'N/A'}",
                    f"Parent B: {root.get('parent_b_id') or 'N/A'}",
                    f"Species ID: {root.get('species_id') or 'N/A'}",
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
            
        if obj_type == "mob":
            btn_rect = pygame.Rect(panel_rect.x + 10, panel_rect.bottom - 35, 120, 25)
            pygame.draw.rect(self.screen, (100, 100, 255), btn_rect)
            pygame.draw.rect(self.screen, (255, 255, 255), btn_rect, 1)
            btn_surf = self.font.render("View Brain", True, (255, 255, 255))
            self.screen.blit(btn_surf, (btn_rect.x + 20, btn_rect.y + 4))
            self.brain_btn_rect = btn_rect

            lin_rect = pygame.Rect(panel_rect.x + 140, panel_rect.bottom - 35, 130, 25)
            pygame.draw.rect(self.screen, (80, 160, 80), lin_rect)
            pygame.draw.rect(self.screen, (255, 255, 255), lin_rect, 1)
            lin_surf = self.font.render("View Lineage", True, (255, 255, 255))
            self.screen.blit(lin_surf, (lin_rect.x + 10, lin_rect.y + 4))
            self.lineage_btn_rect = lin_rect

    def render_lineage_window(self, lineage, mob_id):
        entries = lineage or []
        row_h = 22
        panel_w = 500
        panel_h = min(400, max(120, len(entries) * row_h + 70))
        panel_rect = pygame.Rect(
            self.screen.get_width() // 2 - panel_w // 2,
            self.screen.get_height() // 2 - panel_h // 2,
            panel_w, panel_h
        )
        s = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        s.fill((30, 50, 30, 240))
        self.screen.blit(s, (panel_rect.x, panel_rect.y))
        pygame.draw.rect(self.screen, (100, 200, 100), panel_rect, 2)

        hdr = self.font.render(f"Lineage: {mob_id}", True, (100, 255, 100))
        self.screen.blit(hdr, (panel_rect.x + 10, panel_rect.y + 10))
        close_surf = self.font.render("[Click outside to close]", True, (150, 150, 150))
        self.screen.blit(close_surf, (panel_rect.right - 220, panel_rect.y + 10))

        y = panel_rect.y + 40
        if entries:
            for entry in entries:
                depth = entry["depth"]
                mid = entry["mob_id"]
                sp = entry.get("species_id") or "?"
                pa = entry.get("parent_a_id") or "—"
                pb = entry.get("parent_b_id") or "—"
                indent = "  " * depth
                if pa == "—" and pb == "—":
                    text = f"{indent}Gen {depth}: {mid}  [sp:{sp}]  (founder)"
                else:
                    text = f"{indent}Gen {depth}: {mid}  [sp:{sp}]  A:{pa} / B:{pb}"
                surf = self.font.render(text, True, (220, 255, 220))
                self.screen.blit(surf, (panel_rect.x + 10, y))
                y += row_h
        else:
            surf = self.font.render("No lineage data (founder mob or no breeding record).", True, (220, 255, 220))
            self.screen.blit(surf, (panel_rect.x + 10, y))

        self.lineage_window_rect = panel_rect

    def render_brain_window(self, brain_tree, functions, scroll_y=0):
        panel_w = 650
        panel_h = 500
        panel_rect = pygame.Rect(self.screen.get_width() // 2 - panel_w // 2, 
                                 self.screen.get_height() // 2 - panel_h // 2, 
                                 panel_w, panel_h)
        # Transparent background
        s = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
        s.fill((30, 30, 50, 240))
        self.screen.blit(s, (panel_rect.x, panel_rect.y))
        pygame.draw.rect(self.screen, (200, 200, 255), panel_rect, 2)
        
        # Header
        surf = self.font.render("Mob Brain Workflow & Functions", True, (200, 200, 255))
        self.screen.blit(surf, (panel_rect.x + 10, panel_rect.y + 10))
        
        # Close prompt
        close_surf = self.font.render("[Click outside to close]", True, (150, 150, 150))
        self.screen.blit(close_surf, (panel_rect.right - 220, panel_rect.y + 10))

        y = panel_rect.y + 40
        
        # Functions section
        func_hdr = self.font.render("Available Brain Functions:", True, (255, 255, 255))
        self.screen.blit(func_hdr, (panel_rect.x + 10, y))
        y += 20
        
        max_funcs = 8
        for i, func in enumerate(functions[:max_funcs]):
            desc = func['description'] if func['description'] else 'No description'
            if len(desc) > 65: desc = desc[:62] + '...'
            line = f"- {func['name']}: {desc}"
            f_surf = self.font.render(line, True, (200, 255, 200))
            self.screen.blit(f_surf, (panel_rect.x + 20, y))
            y += 18
            
        if len(functions) > max_funcs:
            f_surf = self.font.render(f"... and {len(functions)-max_funcs} more.", True, (150, 150, 150))
            self.screen.blit(f_surf, (panel_rect.x + 20, y))
            y += 18
            
        y += 10
        
        # Current workflow section
        wf_hdr = self.font.render("Current Decision Tree (Scrollable):", True, (255, 255, 255))
        self.screen.blit(wf_hdr, (panel_rect.x + 10, y))
        y += 20
        
        import json
        if brain_tree:
            tree_str = json.dumps(brain_tree, indent=2)
        else:
            tree_str = "No decision tree available."
        
        lines = tree_str.split("\n")
        
        max_lines = (panel_rect.bottom - y - 10) // 16
        
        # Bound the scroll offset
        max_scroll = max(0, len(lines) - max_lines)
        scroll_y = min(scroll_y, max_scroll)
        
        visible_lines = lines[scroll_y : scroll_y + max_lines]
        
        for line in visible_lines:
            if len(line) > 85: line = line[:82] + '...'
            t_surf = self.font.render(line, True, (240, 240, 240))
            self.screen.blit(t_surf, (panel_rect.x + 20, y))
            y += 16
            
        if scroll_y < max_scroll:
            t_surf = self.font.render("... [scroll down]", True, (150, 150, 150))
            self.screen.blit(t_surf, (panel_rect.x + 20, panel_rect.bottom - 20))
            
        self.brain_window_rect = panel_rect
