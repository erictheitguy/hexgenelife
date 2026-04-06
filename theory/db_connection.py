"""
Shared database connection module for hexgenlife project.
This ensures single MongoDB connection and proper connection pooling.
"""
import pymongo

# Global database client and collections
client = pymongo.MongoClient('candygram', 27017)
db = client.map
hex_tiles_collection = db.hex_tiles
hex_tiles_center = db.hex_tiles_center
db_mob = client.mob
grass_eater_collection = db_mob.grasseater

# Create indexes if they don't exist (for spatial queries)
try:
    hex_tiles_collection.create_index("centerX", unique=False)
    hex_tiles_collection.create_index("centerY", unique=False)
    hex_tiles_collection.create_index("centerXY", unique=False)
except pymongo.errors.PyMongoError:
    pass  # Index may already exist

# Helper to get collections (singleton pattern)
def get_hex_tiles():
    """Return hex_tiles collection"""
    return hex_tiles_collection

def get_hex_tiles_center():
    """Return hex_tiles_center collection"""
    return hex_tiles_center

def get_grass_eater_collection():
    """Return grass_eater collection"""
    return grass_eater_collection

def close_connections():
    """Close all database connections"""
    client.close()
