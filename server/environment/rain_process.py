import sqlite3
import time
import logging
import random
import math
from multiprocessing import Process, Queue

logger = logging.getLogger("Server.Rain")

class RainCloud:
    def __init__(self, x, y, vx, vy, size, water_amount, target_max_x, target_max_y, target_min_x, target_min_y):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.size = size
        self.water_amount = water_amount
        self.radius = size / 2.0
        
        # Determine when to despawn
        self.despawn_x_max = target_max_x + size
        self.despawn_x_min = target_min_x - size
        self.despawn_y_max = target_max_y + size
        self.despawn_y_min = target_min_y - size

    def move(self):
        self.x += self.vx
        self.y += self.vy

    def is_out_of_bounds(self) -> bool:
        if self.vx > 0 and self.x > self.despawn_x_max: return True
        if self.vx < 0 and self.x < self.despawn_x_min: return True
        if self.vy > 0 and self.y > self.despawn_y_max: return True
        if self.vy < 0 and self.y < self.despawn_y_min: return True
        return False


class RainProcess(Process):
    def __init__(self, db_path: str, tick_queue: Queue):
        super().__init__()
        self.db_path = db_path
        self.tick_queue = tick_queue
        self.tick_count = 0
        self.active_clouds = []

    def run(self):
        logger.info("Rain sub-process started.")
        while True:
            try:
                msg = self.tick_queue.get()
                if msg == "STOP":
                    break
            except Exception:
                continue

            self.tick_count += 1
            
            # Spawn a cloud every 500 ticks
            if self.tick_count >= 500:
                self.tick_count = 0
                self.spawn_cloud()

            # Process active clouds
            if self.active_clouds:
                self.process_clouds()

    def spawn_cloud(self):
        # Query world bounds
        min_x, max_x, min_y, max_y = 0.0, 0.0, 0.0, 0.0
        retries = 3
        while retries > 0:
            try:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT MIN(centerX), MAX(centerX), MIN(centerY), MAX(centerY) FROM hex_tiles")
                    row = cursor.fetchone()
                    if row and row[0] is not None:
                        min_x, max_x, min_y, max_y = row
                break
            except Exception as e:
                retries -= 1
                time.sleep(0.1)

        size = random.uniform(10.0, 500.0)
        water_amount = random.uniform(1.0, 20.0)
        speed = 5.0
        
        # Edges: 0=Left, 1=Right, 2=Top, 3=Bottom
        edge = random.randint(0, 3)
        if edge == 0:
            x = min_x - size
            y = random.uniform(min_y, max_y)
            vx = speed
            vy = 0.0
        elif edge == 1:
            x = max_x + size
            y = random.uniform(min_y, max_y)
            vx = -speed
            vy = 0.0
        elif edge == 2:
            x = random.uniform(min_x, max_x)
            y = min_y - size
            vx = 0.0
            vy = speed
        else:
            x = random.uniform(min_x, max_x)
            y = max_y + size
            vx = 0.0
            vy = -speed

        cloud = RainCloud(x, y, vx, vy, size, water_amount, max_x, max_y, min_x, min_y)
        self.active_clouds.append(cloud)
        logger.info(f"Spawned rain cloud at ({x:.1f}, {y:.1f}), size={size:.1f}, moving ({vx},{vy})")

    def process_clouds(self):
        # Move clouds
        for cloud in self.active_clouds[:]:
            cloud.move()
            if cloud.is_out_of_bounds():
                self.active_clouds.remove(cloud)

        if not self.active_clouds:
            return

        # Update DB for all tiles under clouds
        retries = 5
        while retries > 0:
            try:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    cursor = conn.cursor()
                    
                    for cloud in self.active_clouds:
                        # Find tiles within bounding box of cloud to limit mathematical computation in sqlite
                        min_cx = cloud.x - cloud.radius
                        max_cx = cloud.x + cloud.radius
                        min_cy = cloud.y - cloud.radius
                        max_cy = cloud.y + cloud.radius

                        # Euclidean distance squared
                        r2 = cloud.radius ** 2
                        
                        # Apply water to hexes under the cloud sphere
                        cursor.execute("""
                            UPDATE hex_tiles
                            SET Water = Water + ?
                            WHERE centerX >= ? AND centerX <= ?
                              AND centerY >= ? AND centerY <= ?
                              AND ((centerX - ?) * (centerX - ?) + (centerY - ?) * (centerY - ?)) <= ?
                        """, (
                            cloud.water_amount,
                            min_cx, max_cx, min_cy, max_cy,
                            cloud.x, cloud.x, cloud.y, cloud.y, r2
                        ))

                    conn.commit()
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower():
                    retries -= 1
                    time.sleep(0.1)
                else:
                    logger.error(f"SQLite Error in Rain Process: {e}")
                    break
            except Exception as e:
                logger.error(f"Unexpected error in Rain Process: {e}")
                break
        
        if retries == 0:
            logger.warning("Rain Process failed to update tiles due to database lock.")
