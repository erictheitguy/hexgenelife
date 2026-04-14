import unittest
import asyncio
import os
import json
import sqlite3
import time
import random
from server.server import GameServer

DB_PATH = "test_taxonomy.db"

def _cleanup(path):
    if os.path.exists(path):
        os.remove(path)

class TestTaxonomy(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    async def test_founder_naming(self):
        """Generation 1 mobs should be named 'Primus ...'."""
        self.server._ensure_client_mob("founder_test")
        cursor = self.server.db_conn.cursor()
        cursor.execute("""
            SELECT s.name 
            FROM species s
            JOIN mobs m ON m.species_id = s.species_id
            WHERE m.mob_id = 'mob_founder_test'
        """)
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertTrue(row["name"].startswith("Primus"))

    async def test_breeding_lineage_recorded(self):
        """Breeding should record parentage in family_tree."""
        self.server._ensure_client_mob("p1")
        self.server._ensure_client_mob("p2")
        
        # Manually ensure they are adults and close together
        cursor = self.server.db_conn.cursor()
        cursor.execute("UPDATE mob_health SET energy = 100, life_stage = 'adult' WHERE mob_id IN ('mob_p1', 'mob_p2')")
        self.server.db_conn.commit()
        
        # Create mock websocket
        class MockWS:
            async def send(self, data): pass
        ws = MockWS()
        
        # Patch self.broadcast to avoid network issues
        from unittest.mock import AsyncMock
        self.server.broadcast = AsyncMock()
        
        # BREED
        await self.server._handle_breed({"mobId": "mob_p1", "targetId": "mob_p2"}, ws)
        
        # Check family_tree
        cursor.execute("SELECT * FROM family_tree")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["parent_a_id"], "mob_p1")
        self.assertEqual(row["parent_b_id"], "mob_p2")

    async def test_species_split_on_high_mutation(self):
        """If traits deviate > 3.0 Z-score, a new species should be formed."""
        self.server._ensure_client_mob("parent_orig")
        cursor = self.server.db_conn.cursor()
        cursor.execute("SELECT species_id FROM mobs WHERE mob_id = 'mob_parent_orig'")
        orig_species_id = cursor.fetchone()["species_id"]
        
        # Manually inject a child with extreme traits
        child_id = "mob_mutant"
        cursor.execute("INSERT INTO mobs (mob_id, mob_type, species_id) VALUES (?, ?, ?)", 
                       (child_id, "prey", orig_species_id))
        
        # Extreme vision (default is 10, mean is 10. Let's make it 20. Diff = 10. Z = 10/0.1 = 100!)
        cursor.execute("""
            INSERT INTO mob_physical (mob_id, vision, camouflage, size, mass, speed, diet_type, attack_power, defense, metabolism_active, metabolism_resting)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (child_id, 20.0, 0.5, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.2))
        self.server.db_conn.commit()
        
        # Classify
        new_species_id = self.server._classify_mob(child_id, orig_species_id)
        
        self.assertNotEqual(orig_species_id, new_species_id)
        self.assertIsNotNone(new_species_id)
        
        # Verify name doesn't have Primus (it's a split, not a founder)
        cursor.execute("SELECT name FROM species WHERE species_id = ?", (new_species_id,))
        self.assertFalse(cursor.fetchone()["name"].startswith("Primus"))

if __name__ == "__main__":
    unittest.main()
