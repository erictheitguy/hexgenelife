Plan: Migrate from MongoDB to SQLite

Phase 1: Schema Design & Setup
Design SQLite schema mirroring MongoDB collections
Create database connection module using sqlite3
Define data models matching current MongoDB structure
1.1 Design SQLite Schema Mirroring MongoDB Collections

**Hex Tiles Collection** (hexgenlife_database.hex_tiles):

loc (BLOB or TEXT): Store GeoJSON Polygon as JSON text for 7-vertex hexagon
centerX, centerY (REAL): Fallback indices for bounding box queries
centerXY (TEXT/REAL): Array [x, y] stored as JSON text
Water, Grass (INTEGER): Resource amounts 0-100
Created (timestamp): ISO 8601 timestamp string\
updated (timestamp):
Constraint: Add PRIMARY KEY on _id (store as TEXT for MongoDB compatibility)

**Hex Centers Collection** (hexgenlife_database.hex_tiles_center):

centerX, centerY (REAL): Primary coordinates
centerXY (TEXT): Array [x, y]
hex_id (TEXT): Reference to parent hex tile
Composite Index on centerX, centerY for spatial queries

**Mob Collection** (mobgenlife_database.mob.grasseater):

mob_id (TEXT): Primary key, surrogate ID for MongoDB compatibility
mX, mY (REAL): Position coordinates
mXY (TEXT): Array [x, y]
Vital stats: hunger, energy, fat, size, eyesight (INTEGER)
mob_type (TEXT): "grass_eater" | "prey" | "predator"
mob_herd, age, generation (INTEGER)
parent_ids (TEXT): JSON array of parent mob_ids
genome, actual_traits (TEXT): JSON objects with 8 traits
fitness_score (REAL)
Created (TEXT): ISO 8601 timestamp

1.2 Create Database Connection Module Using sqlite3

update db_connection.py
Module structure:
Singleton pattern: Single sqlite3.Connection instance
Collection wrappers: Create class-based wrappers for hex_tiles, mob, hex_centers
Query helpers: Methods for bounding box queries, point-in-polygon validation
Migration functions: Export/Import adapters between PyMongo and sqlite3
Connection pooling: Use connection context managers
Error handling: Wrap sqlite3 exceptions with custom exceptions

1.3 Define Data Models Matching Current MongoDB Structure

**HexTileModel**: Python class/dataclass mirroring MongoDB hex tile document

Properties matching: loc, centerX, centerY, centerXY, Water, Grass, Created
Helper methods: is_point_inside(hex_id, x, y), get_resource_amount()
**MobModel**: Python class/dataclass mirroring MongoDB mob document

Properties matching: mob_id, mX, mY, mXY, stats, genome, actual_traits
Trait inheritance validation methods
Helper: calculate_fitness_score()

**Trait model**: Leverage existing trait_definitions.py and trait_manager.py

Map 8 traits: speed, size, strength, camouflage, hunting_skill, tracking_range, reproduction_rate, metabolism_rate
Validate trait ranges and inheritance modes
Ensure JSON serialization compatibility with SQLite TEXT fields

Phase 2: Migration Adapters
No migration of data from Monogdb sqllite. Sqllite database will be created from scratch. 

Phase 3: Application Updates
Update db_connection.py to use sqlite3
Modify queries in HexSearch.py, grass_eater.py, etc.
Handle GeoJSON geometry storage in SQLite

Phase 4: Testing & Verification
Test CRUD operations with sqlite3
Validate spatial queries work correctly
Migration data integrity checks