import os
import tempfile
import sqlite3
import json
import unittest
from unittest.mock import MagicMock
import pygame

# Initialize pygame display for rendering tests (needed early)
pygame.init()
_screen = pygame.display.set_mode((100, 100))

from viewer.db_reader import DBReader
from viewer.camera import Camera
from viewer.renderer import Renderer, COLOR_GRASS, COLOR_DEEP_WATER, COLOR_SHALLOW_WATER, COLOR_BARREN, COLOR_MOB_PREDATOR, COLOR_MOB_PREY, COLOR_MOB_OTHER

class TestCamera(unittest.TestCase):
    def test_camera_init_and_reset(self):
        cam = Camera(800, 600)
        self.assertEqual(cam.zoom, 1.0)
        self.assertEqual(cam.offset_x, 400)
        self.assertEqual(cam.offset_y, 300)
        
        cam.pan(50, 50)
        self.assertEqual(cam.offset_x, 450)
        self.assertEqual(cam.offset_y, 350)
        
        cam.reset()
        self.assertEqual(cam.offset_x, 400)
        self.assertEqual(cam.offset_y, 300)
        self.assertEqual(cam.zoom, 1.0)
        
    def test_camera_world_to_screen(self):
        cam = Camera(800, 600)
        # origin should map to center of screen initially
        sx, sy = cam.world_to_screen(0, 0)
        self.assertEqual(sx, 400)
        self.assertEqual(sy, 300)
        
        sx, sy = cam.world_to_screen(10, -10)
        self.assertEqual(sx, 410)
        self.assertEqual(sy, 290)

    def test_camera_apply_zoom(self):
        cam = Camera(800, 600)
        cam.apply_zoom(1.0, 400, 300) # zoom by +1.0 around center
        self.assertAlmostEqual(cam.zoom, 2.0)
        
        cam.apply_zoom(-1.5, 400, 300) # zoom by -1.5 around center (will cap at min_zoom)
        self.assertAlmostEqual(cam.zoom, 0.5)

class TestRenderer(unittest.TestCase):
    def setUp(self):
        # We need a valid font to initialize Renderer
        font = pygame.font.SysFont("monospace", 14)
        self.renderer = Renderer(_screen, font)

    def test_get_hex_color(self):
        # Condition 1: Grass > 0
        self.assertEqual(self.renderer.get_hex_color(water=100, grass=1), COLOR_GRASS)
        # Condition 2: Grass == 0 and Water > 50
        self.assertEqual(self.renderer.get_hex_color(water=51, grass=0), COLOR_DEEP_WATER)
        # Condition 3: Grass == 0 and 0 < Water <= 50
        self.assertEqual(self.renderer.get_hex_color(water=50, grass=0), COLOR_SHALLOW_WATER)
        self.assertEqual(self.renderer.get_hex_color(water=1, grass=0), COLOR_SHALLOW_WATER)
        # Condition 4: Grass == 0 and Water == 0
        self.assertEqual(self.renderer.get_hex_color(water=0, grass=0), COLOR_BARREN)

    def test_get_mob_color(self):
        self.assertEqual(self.renderer.get_mob_color("predator"), COLOR_MOB_PREDATOR)
        self.assertEqual(self.renderer.get_mob_color("prey"), COLOR_MOB_PREY)
        self.assertEqual(self.renderer.get_mob_color("unknown_type"), COLOR_MOB_OTHER)


class TestDBReader(unittest.TestCase):
    def setUp(self):
        # Create a temporary sqlite DB
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix=".db")
        self._init_mock_db()
        self.db_reader = DBReader(self.temp_path)

    def tearDown(self):
        self.db_reader.close()
        os.close(self.temp_fd)
        # Attempt to delete file
        try:
            os.remove(self.temp_path)
        except OSError:
            pass
            
    def _init_mock_db(self):
        conn = sqlite3.connect(self.temp_path)
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE hex_tiles (
            id TEXT PRIMARY KEY,
            centerX REAL, centerY REAL,
            q INTEGER, r INTEGER, s INTEGER,
            Water REAL, Grass REAL,
            hexcp1 TEXT, hexcp2 TEXT, hexcp3 TEXT,
            hexcp4 TEXT, hexcp5 TEXT, hexcp6 TEXT
        )''')
        
        cursor.execute('''CREATE TABLE mobs (
            mob_id TEXT PRIMARY KEY,
            position TEXT,
            mob_type TEXT
        )''')
        
        cursor.execute('''CREATE TABLE mob_health (
            mob_id TEXT PRIMARY KEY,
            health INTEGER
        )''')
        
        # Insert test tile
        p = json.dumps([0.0, 0.0])
        cursor.execute('''
            INSERT INTO hex_tiles (id, Water, Grass, hexcp1, hexcp2, hexcp3, hexcp4, hexcp5, hexcp6)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ("hex1", 10.0, 5.0, p, p, p, p, p, p))
        
        # Insert test mob
        cursor.execute('''
            INSERT INTO mobs (mob_id, position, mob_type)
            VALUES (?, ?, ?)
        ''', ("mob1", json.dumps({"x": 10, "y": 20}), "predator"))
        
        cursor.execute('''
            INSERT INTO mob_health (mob_id, health)
            VALUES (?, ?)
        ''', ("mob1", 100))
        
        conn.commit()
        conn.close()

    def test_get_world_state(self):
        state = self.db_reader.get_world_state()
        
        self.assertIn("tiles", state)
        self.assertIn("mobs", state)
        
        # Verify tile
        self.assertEqual(len(state["tiles"]), 1)
        tile = state["tiles"][0]
        self.assertEqual(tile["id"], "hex1")
        self.assertEqual(tile["water"], 10.0)
        self.assertEqual(tile["grass"], 5.0)
        self.assertEqual(len(tile["polygon"]), 6)
        
        # Verify mob
        self.assertEqual(len(state["mobs"]), 1)
        mob = state["mobs"][0]
        self.assertEqual(mob["id"], "mob1")
        self.assertEqual(mob["x"], 10)
        self.assertEqual(mob["y"], 20)
        self.assertEqual(mob["type"], "predator")
        self.assertEqual(mob["health"], 100)

class TestDBReaderLineage(unittest.TestCase):
    """Tests for get_mob_lineage multi-generation BFS traversal.

    Fixture (3-gen chain):
      mob_child  → parent_a=mob_pa,  parent_b=mob_pb   (Gen 0)
      mob_pa     → parent_a=mob_gpa, parent_b=None      (Gen 1)
      mob_pb     — no family_tree entry (founder)
      mob_gpa    — no family_tree entry (founder)
    """

    def setUp(self):
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix=".db")
        conn = sqlite3.connect(self.temp_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE family_tree "
            "(mob_id TEXT, parent_a_id TEXT, parent_b_id TEXT, species_id TEXT)"
        )
        cursor.executemany(
            "INSERT INTO family_tree VALUES (?, ?, ?, ?)",
            [
                ("mob_child", "mob_pa", "mob_pb", "sp_child"),
                ("mob_pa",    "mob_gpa", None,     "sp_a"),
                # mob_pb and mob_gpa are founders — no rows
            ],
        )
        conn.commit()
        conn.close()
        self.db_reader = DBReader(self.temp_path)

    def tearDown(self):
        self.db_reader.close()
        os.close(self.temp_fd)
        try:
            os.remove(self.temp_path)
        except OSError:
            pass

    def test_founder_returns_none(self):
        """Mob with no family_tree entry returns None."""
        self.assertIsNone(self.db_reader.get_mob_lineage("mob_pb"))
        self.assertIsNone(self.db_reader.get_mob_lineage("mob_gpa"))
        self.assertIsNone(self.db_reader.get_mob_lineage("nonexistent"))

    def test_chain_root_is_queried_mob(self):
        """First entry in chain is always the queried mob at depth 0."""
        chain = self.db_reader.get_mob_lineage("mob_child")
        self.assertIsNotNone(chain)
        self.assertEqual(chain[0]["mob_id"], "mob_child")
        self.assertEqual(chain[0]["depth"], 0)
        self.assertEqual(chain[0]["species_id"], "sp_child")

    def test_chain_includes_all_ancestors(self):
        """Chain contains depth-0, depth-1 parents, and depth-2 grandparent."""
        chain = self.db_reader.get_mob_lineage("mob_child")
        mob_ids = [e["mob_id"] for e in chain]
        self.assertIn("mob_child", mob_ids)
        self.assertIn("mob_pa",    mob_ids)
        self.assertIn("mob_pb",    mob_ids)   # referenced parent, no row → included as founder
        self.assertIn("mob_gpa",   mob_ids)

    def test_chain_depths_are_correct(self):
        """Depth values reflect generation distance from queried mob."""
        chain = self.db_reader.get_mob_lineage("mob_child")
        by_id = {e["mob_id"]: e for e in chain}
        self.assertEqual(by_id["mob_child"]["depth"], 0)
        self.assertEqual(by_id["mob_pa"]["depth"],    1)
        self.assertEqual(by_id["mob_pb"]["depth"],    1)
        self.assertEqual(by_id["mob_gpa"]["depth"],   2)

    def test_max_depth_limits_traversal(self):
        """max_depth=1 stops before grandparents."""
        chain = self.db_reader.get_mob_lineage("mob_child", max_depth=1)
        mob_ids = [e["mob_id"] for e in chain]
        self.assertIn("mob_child", mob_ids)
        self.assertIn("mob_pa",    mob_ids)
        self.assertIn("mob_pb",    mob_ids)
        self.assertNotIn("mob_gpa", mob_ids)

    def test_cycle_guard_prevents_infinite_loop(self):
        """Inserting a circular parent reference does not cause an infinite loop."""
        conn = sqlite3.connect(self.temp_path)
        cursor = conn.cursor()
        # mob_gpa points back to mob_child — artificial cycle
        cursor.execute(
            "INSERT INTO family_tree VALUES (?, ?, ?, ?)",
            ("mob_gpa", "mob_child", None, "sp_cycle"),
        )
        conn.commit()
        conn.close()
        chain = self.db_reader.get_mob_lineage("mob_child")
        # Each mob_id should appear only once (visited set)
        seen_ids = [e["mob_id"] for e in chain]
        self.assertEqual(len(seen_ids), len(set(seen_ids)))


if __name__ == '__main__':
    unittest.main()
