
import asyncio
import os
import unittest
import sqlite3
from server.server import GameServer

DB_PATH = "test_aging.db"

def _cleanup(path: str):
    if os.path.exists(path):
        try:
            os.remove(path)
        except:
            pass

class TestAging(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    async def test_default_aging_rate(self):
        """Test that age increases by 0.125 per tick and costs 0.125 energy."""
        mob_id = "mob_aging_test"
        self.server._ensure_client_mob("aging_test")
        
        cursor = self.server.db_conn.cursor()
        
        # Initial state
        cursor.execute("SELECT age, energy FROM mob_health WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        initial_age = row["age"]
        initial_energy = 100.0
        
        # Set energy to 100 and fat to 0 to avoid metabolism gains
        cursor.execute("UPDATE mob_health SET energy = 100.0, fat = 0.0 WHERE mob_id = ?", (mob_id,))
        # Set metabolism_resting to 0 to avoid energy gain from fat
        cursor.execute("UPDATE mob_physical SET metabolism_resting = 0.0 WHERE mob_id = ?", (mob_id,))
        self.server.db_conn.commit()
        
        # Process metabolism once
        await self.server.mob_interactions.process_metabolism()
        
        cursor.execute("SELECT age, energy FROM mob_health WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        new_age = row["age"]
        new_energy = row["energy"]
        
        self.assertAlmostEqual(new_age - initial_age, 0.125, places=2, msg="Age should increase by 0.125 units per tick by default.")
        self.assertAlmostEqual(initial_energy - new_energy, 0.125, places=2, msg="Aging by 0.125 units should cost 0.125 energy.")

    async def test_custom_aging_rate(self):
        """Test that custom aging rate from physical traits is used."""
        mob_id = "mob_custom_aging_test"
        self.server._ensure_client_mob("custom_aging_test")
        
        cursor = self.server.db_conn.cursor()
        
        # Set custom aging rate
        custom_rate = 0.5
        cursor.execute("UPDATE mob_physical SET aging_rate = ? WHERE mob_id = ?", (custom_rate, mob_id))
        cursor.execute("UPDATE mob_health SET energy = 100.0, fat = 0.0, age = 0.0 WHERE mob_id = ?", (mob_id,))
        cursor.execute("UPDATE mob_physical SET metabolism_resting = 0.0 WHERE mob_id = ?", (mob_id,))
        self.server.db_conn.commit()
        
        # Process metabolism
        await self.server.mob_interactions.process_metabolism()
        
        cursor.execute("SELECT age, energy FROM mob_health WHERE mob_id = ?", (mob_id,))
        row = cursor.fetchone()
        
        self.assertAlmostEqual(row["age"], custom_rate, places=2, msg=f"Age should increase by {custom_rate} units.")
        self.assertAlmostEqual(100.0 - row["energy"], custom_rate, places=2, msg=f"Aging by {custom_rate} should cost {custom_rate} energy.")

    async def test_aging_rate_inheritance(self):
        """Test that aging_rate is inherited during breeding."""
        p1_id = "mob_parent1"
        p2_id = "mob_parent2"
        self.server._ensure_client_mob("parent1")
        self.server._ensure_client_mob("parent2")
        
        cursor = self.server.db_conn.cursor()
        # Set parents to adults and give them energy
        cursor.execute("UPDATE mob_health SET life_stage = 'adult', energy = 100.0 WHERE mob_id IN (?, ?)", (p1_id, p2_id))
        
        # Set custom aging rates for parents
        p1_rate = 0.2
        p2_rate = 0.4
        cursor.execute("UPDATE mob_physical SET aging_rate = ? WHERE mob_id = ?", (p1_rate, p1_id))
        cursor.execute("UPDATE mob_physical SET aging_rate = ? WHERE mob_id = ?", (p2_rate, p2_id))
        self.server.db_conn.commit()
        
        # Breed
        payload = {"mobId": p1_id, "targetId": p2_id}
        # Mock websocket
        class MockWS:
            async def send(self, msg): pass
        
        await self.server.mob_interactions.handle_breed(payload, MockWS())
        
        # Find child
        cursor.execute("SELECT mob_id FROM mobs WHERE mob_id LIKE 'mob_child_%'")
        child_id = cursor.fetchone()["mob_id"]
        
        cursor.execute("SELECT aging_rate FROM mob_physical WHERE mob_id = ?", (child_id,))
        child_rate = cursor.fetchone()["aging_rate"]
        
        # Expected rate is (0.2 + 0.4) / 2 = 0.3 +/- 0.1 mutation
        self.assertTrue(0.1 <= child_rate <= 0.5, f"Child aging rate {child_rate} should be near average of parents (0.3) with mutation.")

if __name__ == "__main__":
    unittest.main()
