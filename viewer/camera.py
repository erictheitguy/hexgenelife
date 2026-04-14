class Camera:
    def __init__(self, screen_w, screen_h):
        self.screen_width = screen_w
        self.screen_height = screen_h
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0

    def world_to_screen(self, world_x, world_y):
        cx = self.screen_width / 2.0
        cy = self.screen_height / 2.0
        screen_x = (world_x - self.offset_x) * self.zoom + cx
        screen_y = (world_y - self.offset_y) * self.zoom + cy
        return screen_x, screen_y

    def screen_to_world(self, screen_x, screen_y):
        cx = self.screen_width / 2.0
        cy = self.screen_height / 2.0
        world_x = (screen_x - cx) / self.zoom + self.offset_x
        world_y = (screen_y - cy) / self.zoom + self.offset_y
        return world_x, world_y

    def pan(self, dx, dy):
        self.offset_x -= dx / self.zoom
        self.offset_y -= dy / self.zoom

    def apply_zoom(self, amount, focus_x=None, focus_y=None):
        if focus_x is not None and focus_y is not None:
            world_x_before, world_y_before = self.screen_to_world(focus_x, focus_y)
            self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom + amount))
            world_x_after, world_y_after = self.screen_to_world(focus_x, focus_y)
            self.offset_x += (world_x_before - world_x_after)
            self.offset_y += (world_y_before - world_y_after)
        else:
            self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom + amount))

    def reset(self):
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.zoom = 1.0
