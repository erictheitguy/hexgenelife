"""
Unit tests for log_skill.py

Uses importlib to load the skill module from its non-package location.
"""

import importlib.util
import os
import sys
import tempfile
import shutil

import pytest

# ---------------------------------------------------------------------------
# Load log_skill via importlib
# ---------------------------------------------------------------------------
_SKILL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    ".kiro",
    "skills",
    "mob_brain_tester",
    "log_skill.py",
)

_spec = importlib.util.spec_from_file_location("log_skill", _SKILL_PATH)
log_skill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(log_skill)

get_recent_log_lines = log_skill.get_recent_log_lines
count_log_events = log_skill.count_log_events
get_action_distribution = log_skill.get_action_distribution
get_brain_errors = log_skill.get_brain_errors


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_logs():
    """Create a temporary directory for log files; clean up after each test."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _write_log(logs_dir: str, mob_id: str, content: str) -> str:
    """Write content to {logs_dir}/{mob_id}.log and return the path."""
    path = os.path.join(logs_dir, f"{mob_id}.log")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ---------------------------------------------------------------------------
# get_recent_log_lines
# ---------------------------------------------------------------------------

class TestGetRecentLogLines:
    def test_returns_last_n_lines(self, tmp_logs):
        content = "line1\nline2\nline3\nline4\nline5\n"
        _write_log(tmp_logs, "mob1", content)
        result = get_recent_log_lines("mob1", 3, tmp_logs)
        assert result == ["line3", "line4", "line5"]

    def test_returns_all_lines_when_n_exceeds_file(self, tmp_logs):
        content = "alpha\nbeta\n"
        _write_log(tmp_logs, "mob1", content)
        result = get_recent_log_lines("mob1", 100, tmp_logs)
        assert result == ["alpha", "beta"]

    def test_returns_empty_list_for_missing_file(self, tmp_logs):
        result = get_recent_log_lines("nonexistent_mob", 10, tmp_logs)
        assert result == []

    def test_strips_trailing_newlines(self, tmp_logs):
        _write_log(tmp_logs, "mob2", "hello\nworld\n")
        result = get_recent_log_lines("mob2", 2, tmp_logs)
        assert result == ["hello", "world"]

    def test_mob_test_client_special_id(self, tmp_logs):
        content = "event1\nevent2\nevent3\n"
        _write_log(tmp_logs, "mob_test_client", content)
        result = get_recent_log_lines("mob_test_client", 2, tmp_logs)
        assert result == ["event2", "event3"]

    def test_n_zero_returns_empty(self, tmp_logs):
        _write_log(tmp_logs, "mob1", "line1\nline2\n")
        result = get_recent_log_lines("mob1", 0, tmp_logs)
        assert result == []


# ---------------------------------------------------------------------------
# count_log_events
# ---------------------------------------------------------------------------

class TestCountLogEvents:
    def test_counts_matching_lines(self, tmp_logs):
        content = (
            "2024-01-01 - INFO - mob connected\n"
            "2024-01-01 - INFO - mob moved\n"
            "2024-01-01 - INFO - mob connected\n"
            "2024-01-01 - DEBUG - tick processed\n"
        )
        _write_log(tmp_logs, "mob1", content)
        assert count_log_events("mob1", "mob connected", tmp_logs) == 2

    def test_returns_zero_for_no_matches(self, tmp_logs):
        _write_log(tmp_logs, "mob1", "nothing relevant here\n")
        assert count_log_events("mob1", "CRITICAL", tmp_logs) == 0

    def test_returns_zero_for_missing_file(self, tmp_logs):
        assert count_log_events("ghost_mob", "anything", tmp_logs) == 0

    def test_counts_all_occurrences(self, tmp_logs):
        content = "eat\neat\neat\neat\n"
        _write_log(tmp_logs, "mob1", content)
        assert count_log_events("mob1", "eat", tmp_logs) == 4

    def test_event_type_substring_match(self, tmp_logs):
        content = "Action produced: move_north\nAction produced: move_south\n"
        _write_log(tmp_logs, "mob1", content)
        assert count_log_events("mob1", "Action produced:", tmp_logs) == 2


# ---------------------------------------------------------------------------
# get_action_distribution
# ---------------------------------------------------------------------------

class TestGetActionDistribution:
    def test_basic_distribution(self, tmp_logs):
        content = (
            "2024-01-01 - INFO - Action produced: move_north\n"
            "2024-01-01 - INFO - Action produced: eat\n"
            "2024-01-01 - INFO - Action produced: move_north\n"
            "2024-01-01 - INFO - Action produced: idle\n"
            "2024-01-01 - INFO - Action produced: eat\n"
            "2024-01-01 - INFO - Action produced: eat\n"
        )
        _write_log(tmp_logs, "mob1", content)
        dist = get_action_distribution("mob1", tmp_logs)
        assert dist == {"move_north": 2, "eat": 3, "idle": 1}

    def test_returns_empty_dict_for_missing_file(self, tmp_logs):
        assert get_action_distribution("no_mob", tmp_logs) == {}

    def test_returns_empty_dict_when_no_action_lines(self, tmp_logs):
        _write_log(tmp_logs, "mob1", "INFO - connected\nDEBUG - tick\n")
        assert get_action_distribution("mob1", tmp_logs) == {}

    def test_single_action_type(self, tmp_logs):
        content = "Action produced: breed\nAction produced: breed\n"
        _write_log(tmp_logs, "mob1", content)
        dist = get_action_distribution("mob1", tmp_logs)
        assert dist == {"breed": 2}

    def test_ignores_non_action_lines(self, tmp_logs):
        content = (
            "INFO - mob started\n"
            "Action produced: move_south\n"
            "ERROR - something failed\n"
            "Action produced: move_south\n"
        )
        _write_log(tmp_logs, "mob1", content)
        dist = get_action_distribution("mob1", tmp_logs)
        assert dist == {"move_south": 2}


# ---------------------------------------------------------------------------
# get_brain_errors
# ---------------------------------------------------------------------------

class TestGetBrainErrors:
    def test_returns_error_lines(self, tmp_logs):
        content = (
            "2024-01-01 - INFO - all good\n"
            "2024-01-01 - ERROR - brain exploded\n"
            "2024-01-01 - DEBUG - tick\n"
            "2024-01-01 - WARNING - low energy\n"
        )
        _write_log(tmp_logs, "mob1", content)
        result = get_brain_errors("mob1", tmp_logs)
        assert len(result) == 2
        assert any("ERROR" in line for line in result)
        assert any("WARNING" in line for line in result)

    def test_returns_empty_list_for_missing_file(self, tmp_logs):
        assert get_brain_errors("ghost", tmp_logs) == []

    def test_returns_empty_list_when_no_errors(self, tmp_logs):
        content = "INFO - connected\nDEBUG - tick\nINFO - moved\n"
        _write_log(tmp_logs, "mob1", content)
        assert get_brain_errors("mob1", tmp_logs) == []

    def test_strips_trailing_newlines(self, tmp_logs):
        content = "2024-01-01 - ERROR - bad thing\n"
        _write_log(tmp_logs, "mob1", content)
        result = get_brain_errors("mob1", tmp_logs)
        assert result == ["2024-01-01 - ERROR - bad thing"]

    def test_multiple_errors_and_warnings(self, tmp_logs):
        content = (
            "ts - ERROR - err1\n"
            "ts - WARNING - warn1\n"
            "ts - ERROR - err2\n"
            "ts - INFO - ok\n"
            "ts - WARNING - warn2\n"
        )
        _write_log(tmp_logs, "mob1", content)
        result = get_brain_errors("mob1", tmp_logs)
        assert len(result) == 4
        assert all(" - ERROR - " in r or " - WARNING - " in r for r in result)
