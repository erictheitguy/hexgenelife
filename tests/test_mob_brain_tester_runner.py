"""Unit tests for test_runner_skill.py."""

import importlib.util
import pathlib
import sys

import pytest

# ---------------------------------------------------------------------------
# Load test_runner_skill from .kiro/ (not a Python package)
# ---------------------------------------------------------------------------
_skill_path = (
    pathlib.Path(__file__).parent.parent
    / ".kiro"
    / "skills"
    / "mob_brain_tester"
    / "test_runner_skill.py"
)
_spec = importlib.util.spec_from_file_location("test_runner_skill", _skill_path)
test_runner_skill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(test_runner_skill)

run_grass_mob_test = test_runner_skill.run_grass_mob_test
_TestResult = test_runner_skill.TestResult

# ---------------------------------------------------------------------------
# Required keys in a TestResult
# ---------------------------------------------------------------------------
REQUIRED_KEYS = {
    "survival_rate",
    "breed_event_count",
    "starvation_death_count",
    "mean_ticks_survived",
    "eat_action_count",
    "per_tick_snapshots",
    "mob_ids",
}


# ---------------------------------------------------------------------------
# Tests: ValueError on invalid inputs
# ---------------------------------------------------------------------------

def test_raises_value_error_num_mobs_zero():
    with pytest.raises(ValueError, match="num_mobs"):
        run_grass_mob_test(num_mobs=0, num_ticks=10)


def test_raises_value_error_num_mobs_negative():
    with pytest.raises(ValueError, match="num_mobs"):
        run_grass_mob_test(num_mobs=-1, num_ticks=10)


def test_raises_value_error_num_ticks_zero():
    with pytest.raises(ValueError, match="num_ticks"):
        run_grass_mob_test(num_mobs=1, num_ticks=0)


def test_raises_value_error_num_ticks_negative():
    with pytest.raises(ValueError, match="num_ticks"):
        run_grass_mob_test(num_mobs=1, num_ticks=-5)


# ---------------------------------------------------------------------------
# Tests: valid run returns correct structure
# ---------------------------------------------------------------------------

def test_1mob_10ticks_returns_all_required_keys():
    """A 1-mob, 10-tick run must return a TestResult with all required keys."""
    result = run_grass_mob_test(num_mobs=1, num_ticks=10)
    for key in REQUIRED_KEYS:
        assert key in result, f"Missing key in TestResult: {key}"


def test_survival_rate_between_0_and_1():
    """survival_rate must be in [0.0, 1.0]."""
    result = run_grass_mob_test(num_mobs=1, num_ticks=10)
    assert 0.0 <= result["survival_rate"] <= 1.0, (
        f"survival_rate out of range: {result['survival_rate']}"
    )


def test_per_tick_snapshots_has_entries():
    """per_tick_snapshots must contain at least some entries."""
    result = run_grass_mob_test(num_mobs=1, num_ticks=10)
    assert len(result["per_tick_snapshots"]) > 0, "per_tick_snapshots should not be empty"


def test_mob_ids_length_matches_num_mobs():
    """mob_ids must contain exactly num_mobs entries."""
    result = run_grass_mob_test(num_mobs=2, num_ticks=5)
    assert len(result["mob_ids"]) == 2


def test_eat_action_count_is_non_negative():
    """eat_action_count must be >= 0."""
    result = run_grass_mob_test(num_mobs=1, num_ticks=10)
    assert result["eat_action_count"] >= 0


def test_breed_event_count_is_non_negative():
    """breed_event_count must be >= 0."""
    result = run_grass_mob_test(num_mobs=2, num_ticks=10)
    assert result["breed_event_count"] >= 0


def test_starvation_death_count_is_non_negative():
    """starvation_death_count must be >= 0."""
    result = run_grass_mob_test(num_mobs=1, num_ticks=10)
    assert result["starvation_death_count"] >= 0


def test_mean_ticks_survived_is_non_negative():
    """mean_ticks_survived must be >= 0."""
    result = run_grass_mob_test(num_mobs=1, num_ticks=10)
    assert result["mean_ticks_survived"] >= 0.0


def test_per_tick_snapshot_fields():
    """Each snapshot must have the expected fields."""
    result = run_grass_mob_test(num_mobs=1, num_ticks=5)
    expected_fields = {"tick", "mob_id", "hunger", "fat", "energy", "health", "life_stage"}
    for snap in result["per_tick_snapshots"]:
        for field in expected_fields:
            assert field in snap, f"Snapshot missing field: {field}"


def test_uses_memory_db_by_default():
    """Two separate runs with default :memory: should not interfere with each other."""
    r1 = run_grass_mob_test(num_mobs=1, num_ticks=5)
    r2 = run_grass_mob_test(num_mobs=1, num_ticks=5)
    # Both should succeed and return valid results
    assert "survival_rate" in r1
    assert "survival_rate" in r2
