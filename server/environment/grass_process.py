import sqlite3
import time
import logging
from multiprocessing import Process, Queue

logger = logging.getLogger("Server.Grass")

class GrassProcess(Process):
    def __init__(self, db_path: str, tick_queue: Queue):
        super().__init__()
        self.db_path = db_path
        self.tick_queue = tick_queue
        self.tick_count = 0

    def run(self):
        logger.info("Grass sub-process started.")
        while True:
            # Wait for the next tick signal from the server
            try:
                msg = self.tick_queue.get()
                if msg == "STOP":
                    break
            except Exception:
                continue

            self.tick_count += 1
            if self.tick_count >= 100:
                self.tick_count = 0
                self.update_grass()

    def update_grass(self):
        # Retry mechanism for SQLite DB locking
        retries = 5
        while retries > 0:
            try:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE hex_tiles
                        SET 
                            Grass = CASE 
                                WHEN Water > 0 THEN Grass + MIN(Water, 1.0)
                                ELSE MAX(0.0, Grass - 1.0)
                            END,
                            Water = MAX(0.0, Water - 1.0)
                    """)
                    conn.commit()
                break  # Success
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower():
                    retries -= 1
                    time.sleep(0.1)
                else:
                    logger.error(f"SQLite Error in Grass Process: {e}")
                    break
            except Exception as e:
                logger.error(f"Unexpected error in Grass Process: {e}")
                break
        
        if retries == 0:
            logger.warning("Grass Process failed to update tiles due to database lock.")
