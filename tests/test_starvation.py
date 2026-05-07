
import asyncio
import json
import os
import unittest
from server.server import GameServer

DB_PATH = "test_starvation.db"

def _cleanup(path: str):
    if os.path.exists(path):
        try:
            os.remove(path)
        except:
            pass

class TestStarvation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _cleanup(DB_PATH)
        self.server = GameServer(db_path=DB_PATH)

    def tearDown(self):
        self.server.close()
        _cleanup(DB_PATH)

    async def test_starvation_damage_scaling(self):
        """Test that health decreases at different hunger levels (new thresholds: first tier > 30)."""
        mob_id = "mob_starve_test"
        self.server._ensure_client_mob("starve_test")
        
        cursor = self.server.db_conn.cursor()
        
        # Helper to set hunger and get health change after one metabolism tick
        async def check_damage(hunger_val):
            # fat=0 so hunger increments normally and no healing occurs
            cursor.execute("UPDATE mob_health SET hunger = ?, health = 100.0, fat = 0.0 WHERE mob_id = ?", (hunger_val, mob_id))
            self.server.db_conn.commit()
            
            await self.server.mob_interactions.process_metabolism()
            
            cursor.execute("SELECT health FROM mob_health WHERE mob_id = ?", (mob_id,))
            return 100.0 - cursor.fetchone()["health"]

        # 1. Hunger <= 30 -> No starvation damage (first tier now > 30)
        damage_29 = await check_damage(29.0)
        self.assertEqual(damage_29, 0.0, "Hunger 29.0 should deal 0 starvation damage")

        # 2. Hunger >= 30 -> 2 damage
        damage_30 = await check_damage(30.0)
        self.assertAlmostEqual(damage_30, 2.0, places=1)

        # 3. Hunger > 40 -> 3 damage
        damage_41 = await check_damage(41.0)
        self.assertAlmostEqual(damage_41, 3.0, places=1)

    async def test_starvation_death(self):
        """Test that a mob eventually dies from starvation."""
        mob_id = "mob_die_test"
        self.server._ensure_client_mob("die_test")
        
        cursor = self.server.db_conn.cursor()
        # Set low health, high hunger, and NO fat so it doesn't heal
        cursor.execute("UPDATE mob_health SET health = 2.0, hunger = 45.0, fat = 0.0 WHERE mob_id = ?", (mob_id,))
        self.server.db_conn.commit()
        
        # One tick should deal 3.0 damage, which kills the mob (health 2.0 - 3.0 < 0)
        await self.server.mob_interactions.process_metabolism()
        
        cursor.execute("SELECT death FROM mob_genes WHERE mob_id = ?", (mob_id,))
        death_val = cursor.fetchone()["death"]
        self.assertIsNotNone(death_val, "Mob should be dead after starvation damage exceeds remaining health")

if __name__ == "__main__":
    unittest.main()
