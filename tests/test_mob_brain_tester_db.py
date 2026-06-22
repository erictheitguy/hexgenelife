"""Unit tests for db_skill.py — uses temp SQLite files seeded with known data."""

import importlib.util
import os
import sqlite3
import sys
import tempfile
import pathlib

# ---------------------------------------------------------------------------
# Load db_skill from .codex/ if the optional mob brain tester skill is installed.
# ---------------------------------------------------------------------------
_skill_path = (
    pathlib.Path(__file__).parent.parent
    / ".codex"
    / "skills"
    / "mob_brain_tester"
    / "db_skill.py"
)
if not _skill_path.exists():
    import pytest
    pytest.skip("optional mob_brain_tester Codex skill is not installed", allow_module_level=True)

_spec = importlib.util.spec_from_file_location("db_skill", _skill_path)
db_skill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(db_skill)


# ---------------------------------------------------------------------------
# Helper: create a temp SQLite file, run a setup function, return the path
# ---------------------------------------------------------------------------
def make_temp_db(setup_fn):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    setup_fn(conn)
    conn.close()
    return path


def _create_tables(conn):
    """Create all tables that db_skill queries."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS mobs (
            mob_id TEXT PRIMARY KEY,
            position TEXT,
            mob_type TEXT,
            species_id TEXT,
            generation INTEGER,
            timestamp REAL,
            is_active BOOLEAN DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS mob_health (
            mob_id TEXT PRIMARY KEY,
            hunger REAL,
            fat REAL,
            health REAL,
            age REAL,
            energy REAL DEFAULT 50.0,
            life_stage TEXT DEFAULT 'adult',
            birth_tick REAL DEFAULT 0.0,
            max_age REAL DEFAULT 10000.0
        );
        CREATE TABLE IF NOT EXISTS mob_physical (
            mob_id TEXT PRIMARY KEY,
            size REAL DEFAULT 1.0,
            speed REAL DEFAULT 1.0,
            mass REAL DEFAULT 1.0,
            vision REAL DEFAULT 10.0,
            metabolism_active REAL DEFAULT 1.0,
            metabolism_resting REAL DEFAULT 0.2,
            diet_type REAL DEFAULT 0.0,
            attack_power REAL DEFAULT 1.0,
            defense REAL DEFAULT 1.0,
            camouflage REAL DEFAULT 0.5
        );
        CREATE TABLE IF NOT EXISTS mob_brain (
            mob_id TEXT PRIMARY KEY,
            cognition_attributes TEXT,
            decision_tree TEXT,
            memory TEXT
        );
        CREATE TABLE IF NOT EXISTS mob_genes (
            mob_id TEXT,
            mobType TEXT,
            fitnessScore REAL,
            death REAL,
            expired BOOLEAN,
            PRIMARY KEY (mob_id, mobType)
        );
        CREATE TABLE IF NOT EXISTS hex_tiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loc TEXT,
            centerXY TEXT,
            centerX INTEGER,
            centerY INTEGER,
            Water REAL,
            Grass REAL,
            Created TEXT,
            Updated TEXT,
            q INTEGER,
            r INTEGER
        );
        CREATE TABLE IF NOT EXISTS family_tree (
            mob_id TEXT PRIMARY KEY,
            parent_a_id TEXT,
            parent_b_id TEXT,
            species_id TEXT,
            timestamp REAL
        );
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_get_all_prey_mobs():
    """Seed 2 prey mobs and 1 predator; assert only 2 returned."""
    def setup(conn):
        _create_tables(conn)
        conn.executemany(
            "INSERT INTO mobs (mob_id, mob_type) VALUES (?, ?)",
            [("prey1", "prey"), ("prey2", "prey"), ("pred1", "predator")],
        )
        conn.commit()

    path = make_temp_db(setup)
    try:
        result = db_skill.get_all_prey_mobs(db_path=path)
        assert len(result) == 2
        assert all(r["mob_type"] == "prey" for r in result)
    finally:
        os.unlink(path)


def test_get_mob_summary():
    """Seed 1 mob across all tables; assert all expected fields present."""
    def setup(conn):
        _create_tables(conn)
        conn.execute(
            "INSERT INTO mobs (mob_id, position, mob_type, species_id, generation, timestamp, is_active) "
            "VALUES ('m1', '0,0', 'prey', 'sp1', 1, 100.0, 1)"
        )
        conn.execute(
            "INSERT INTO mob_health (mob_id, hunger, fat, health, age, energy, life_stage, birth_tick, max_age) "
            "VALUES ('m1', 10.0, 5.0, 100.0, 50.0, 80.0, 'adult', 0.0, 10000.0)"
        )
        conn.execute(
            "INSERT INTO mob_physical (mob_id, size, speed, mass, vision) "
            "VALUES ('m1', 1.5, 2.0, 3.0, 12.0)"
        )
        conn.execute(
            "INSERT INTO mob_brain (mob_id, cognition_attributes, decision_tree, memory) "
            "VALUES ('m1', '{}', '{}', '{}')"
        )
        conn.execute(
            "INSERT INTO mob_genes (mob_id, mobType, fitnessScore, death, expired) "
            "VALUES ('m1', 'prey', 0.9, NULL, 0)"
        )
        conn.commit()

    path = make_temp_db(setup)
    try:
        result = db_skill.get_mob_summary("m1", db_path=path)
        assert result, "Expected a non-empty dict"
        # Fields from mobs
        for field in ("mob_id", "position", "mob_type", "species_id", "generation", "timestamp", "is_active"):
            assert field in result, f"Missing field: {field}"
        # Fields from mob_health
        for field in ("hunger", "fat", "health", "age", "energy", "life_stage", "birth_tick", "max_age"):
            assert field in result, f"Missing field: {field}"
        # Fields from mob_physical
        for field in ("size", "speed", "mass", "vision"):
            assert field in result, f"Missing field: {field}"
        # Fields from mob_brain
        for field in ("cognition_attributes", "decision_tree", "memory"):
            assert field in result, f"Missing field: {field}"
        # Fields from mob_genes
        for field in ("mobType", "fitnessScore", "death", "expired"):
            assert field in result, f"Missing field: {field}"
    finally:
        os.unlink(path)


def test_get_grass_coverage():
    """Seed 3 tiles with Grass > 0 and 1 with Grass = 0; assert tile_count=3, totals correct."""
    def setup(conn):
        _create_tables(conn)
        conn.executemany(
            "INSERT INTO hex_tiles (Grass, Water) VALUES (?, ?)",
            [(10.0, 0.0), (20.0, 0.0), (30.0, 0.0), (0.0, 5.0)],
        )
        conn.commit()

    path = make_temp_db(setup)
    try:
        result = db_skill.get_grass_coverage(db_path=path)
        assert result["tile_count"] == 3
        assert abs(result["total_grass"] - 60.0) < 1e-6
        assert abs(result["mean_grass_per_tile"] - 20.0) < 1e-6
    finally:
        os.unlink(path)


def test_get_breed_events():
    """Seed 3 family_tree rows with timestamps 10, 20, 30; call with since_tick=15, assert 2 rows."""
    def setup(conn):
        _create_tables(conn)
        conn.executemany(
            "INSERT INTO family_tree (mob_id, parent_a_id, parent_b_id, species_id, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                ("child1", "pa1", "pb1", "sp1", 10.0),
                ("child2", "pa2", "pb2", "sp1", 20.0),
                ("child3", "pa3", "pb3", "sp1", 30.0),
            ],
        )
        conn.commit()

    path = make_temp_db(setup)
    try:
        result = db_skill.get_breed_events(since_tick=15.0, db_path=path)
        assert len(result) == 2
        timestamps = {r["timestamp"] for r in result}
        assert timestamps == {20.0, 30.0}
    finally:
        os.unlink(path)


def test_get_death_summary():
    """Seed 2 dead mobs (hunger=30 → starvation, hunger=5 → unknown); assert correct summary."""
    def setup(conn):
        _create_tables(conn)
        # Two mobs with a death recorded in mob_genes
        conn.executemany(
            "INSERT INTO mobs (mob_id, mob_type) VALUES (?, ?)",
            [("dead1", "prey"), ("dead2", "prey")],
        )
        conn.executemany(
            "INSERT INTO mob_genes (mob_id, mobType, fitnessScore, death, expired) VALUES (?, ?, ?, ?, ?)",
            [("dead1", "prey", 0.5, 100.0, 1), ("dead2", "prey", 0.3, 200.0, 1)],
        )
        conn.executemany(
            "INSERT INTO mob_health (mob_id, hunger, fat, health, age) VALUES (?, ?, ?, ?, ?)",
            [("dead1", 30.0, 0.0, 0.0, 500.0), ("dead2", 5.0, 0.0, 0.0, 500.0)],
        )
        conn.commit()

    path = make_temp_db(setup)
    try:
        result = db_skill.get_death_summary(db_path=path)
        assert result.get("starvation") == 1
        assert result.get("unknown") == 1
    finally:
        os.unlink(path)


def test_file_not_found():
    """Calling any function with a non-existent path raises FileNotFoundError."""
    bad_path = "/tmp/this_db_does_not_exist_xyz_12345.db"
    # Make sure it really doesn't exist
    if os.path.exists(bad_path):
        os.unlink(bad_path)

    import pytest
    with pytest.raises(FileNotFoundError):
        db_skill.get_all_prey_mobs(db_path=bad_path)


def test_get_grass_coverage_empty():
    """Empty hex_tiles table → tile_count=0, total_grass=0.0, mean=0.0."""
    def setup(conn):
        _create_tables(conn)
        # No rows inserted

    path = make_temp_db(setup)
    try:
        result = db_skill.get_grass_coverage(db_path=path)
        assert result["tile_count"] == 0
        assert result["total_grass"] == 0.0
        assert result["mean_grass_per_tile"] == 0.0
    finally:
        os.unlink(path)
