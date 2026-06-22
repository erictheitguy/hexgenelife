"""
Property-based and unit tests for launch_helpers.py.

Feature: mob-brain-tester-launch
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Load launch_helpers from .codex/ if the optional mob brain tester skill is installed.
# ---------------------------------------------------------------------------
_skill_path = (
    pathlib.Path(__file__).parent.parent
    / ".codex"
    / "skills"
    / "mob_brain_tester"
    / "launch_helpers.py"
)
if not _skill_path.exists():
    pytest.skip("optional mob_brain_tester Codex skill is not installed", allow_module_level=True)

_spec = importlib.util.spec_from_file_location("launch_helpers", _skill_path)
launch_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(launch_helpers)

render_recommendation_report = launch_helpers.render_recommendation_report
get_directional_indicator = launch_helpers.get_directional_indicator
get_threshold_annotation = launch_helpers.get_threshold_annotation
write_brain_snapshot = launch_helpers.write_brain_snapshot
list_brain_snapshots = launch_helpers.list_brain_snapshots


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_STATUS_VALUES = ["BASELINE_MET", "BASELINE_NOT_MET", "MANUAL_REVIEW_REQUIRED"]

_recommendation_strategy = st.fixed_dictionaries({
    "target": st.text(min_size=1, max_size=30),
    "name": st.text(min_size=1, max_size=30),
    "current_value": st.text(min_size=0, max_size=50),
    "suggested_value": st.text(min_size=0, max_size=50),
    "rationale": st.text(min_size=1, max_size=100),
})

_test_result_strategy = st.fixed_dictionaries({
    "survival_rate": st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    "breed_event_count": st.integers(min_value=0, max_value=100),
    "eat_action_count": st.integers(min_value=0, max_value=1000),
    "starvation_death_count": st.integers(min_value=0, max_value=100),
    "mean_ticks_survived": st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
})

_report_strategy = st.fixed_dictionaries({
    "status": st.sampled_from(_STATUS_VALUES),
    "iteration": st.integers(min_value=1, max_value=3),
    "test_result": _test_result_strategy,
    "recommendations": st.lists(_recommendation_strategy, min_size=0, max_size=5),
    "markdown_summary": st.text(max_size=200),
})

# Safe alphabet for filenames: uppercase letters, lowercase letters, digits
_safe_label_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    min_size=1,
    max_size=20,
)

# Simple decision tree dict strategy
_decision_tree_strategy = st.dictionaries(
    keys=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=1, max_size=10),
    values=st.one_of(st.text(max_size=20), st.integers(), st.booleans()),
    max_size=5,
)


# ---------------------------------------------------------------------------
# 8.1 Property test: render_recommendation_report — render completeness (Property 1)
# Validates: Requirements 8.1, 8.2, 8.3
# ---------------------------------------------------------------------------

@given(report=_report_strategy)
@settings(max_examples=100)
def test_render_recommendation_report_completeness(report):
    """
    **Tag: Feature: mob-brain-tester-launch, Property 1: RecommendationReport render completeness**
    **Validates: Requirements 8.1, 8.2, 8.3**

    For any valid RecommendationReport, the rendered string must contain:
    - The status value
    - The iteration number (as a string)
    - All five metric names
    - For each recommendation: target, name, current_value, suggested_value, rationale
    """
    rendered = render_recommendation_report(report)

    # Status must appear
    assert report["status"] in rendered, (
        f"Status '{report['status']}' not found in rendered output"
    )

    # Iteration number must appear
    assert str(report["iteration"]) in rendered, (
        f"Iteration '{report['iteration']}' not found in rendered output"
    )

    # All five metric names must appear
    for metric_name in [
        "survival_rate",
        "breed_event_count",
        "eat_action_count",
        "starvation_death_count",
        "mean_ticks_survived",
    ]:
        assert metric_name in rendered, (
            f"Metric name '{metric_name}' not found in rendered output"
        )

    # Each recommendation's fields must appear
    for rec in report["recommendations"]:
        assert rec["target"] in rendered, (
            f"Recommendation target '{rec['target']}' not found in rendered output"
        )
        assert rec["name"] in rendered, (
            f"Recommendation name '{rec['name']}' not found in rendered output"
        )
        assert str(rec["current_value"]) in rendered, (
            f"Recommendation current_value '{rec['current_value']}' not found in rendered output"
        )
        assert str(rec["suggested_value"]) in rendered, (
            f"Recommendation suggested_value '{rec['suggested_value']}' not found in rendered output"
        )
        assert rec["rationale"] in rendered, (
            f"Recommendation rationale '{rec['rationale']}' not found in rendered output"
        )


# ---------------------------------------------------------------------------
# 8.2 Property test: get_directional_indicator — directional indicator correctness (Property 2)
# Validates: Requirements 11.3
# ---------------------------------------------------------------------------

_VALID_INDICATORS = {"↑ improved", "↓ worsened", "→ unchanged"}


@given(
    prev=st.floats(allow_nan=False, allow_infinity=False),
    curr=st.floats(allow_nan=False, allow_infinity=False),
    higher_is_better=st.booleans(),
)
@settings(max_examples=100)
def test_get_directional_indicator_returns_valid_value(prev, curr, higher_is_better):
    """
    **Tag: Feature: mob-brain-tester-launch, Property 2: Directional indicator correctness**
    **Validates: Requirements 11.3**

    The function must always return exactly one of the three valid indicator strings.
    """
    result = get_directional_indicator(prev, curr, higher_is_better)
    assert result in _VALID_INDICATORS, (
        f"get_directional_indicator({prev}, {curr}, {higher_is_better}) returned "
        f"unexpected value: {result!r}"
    )


@given(
    prev=st.floats(allow_nan=False, allow_infinity=False),
    curr=st.floats(allow_nan=False, allow_infinity=False),
    higher_is_better=st.booleans(),
)
@settings(max_examples=100)
def test_get_directional_indicator_unchanged_when_equal(prev, curr, higher_is_better):
    """
    **Tag: Feature: mob-brain-tester-launch, Property 2: Directional indicator correctness**
    **Validates: Requirements 11.3**

    When prev == curr, the result must be "→ unchanged" regardless of higher_is_better.
    """
    # Use prev as both values to guarantee equality
    result = get_directional_indicator(prev, prev, higher_is_better)
    assert result == "→ unchanged", (
        f"Expected '→ unchanged' when prev == curr == {prev}, got {result!r}"
    )


@given(
    prev=st.floats(allow_nan=False, allow_infinity=False),
    curr=st.floats(allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_get_directional_indicator_higher_is_better_improved(prev, curr):
    """
    **Tag: Feature: mob-brain-tester-launch, Property 2: Directional indicator correctness**
    **Validates: Requirements 11.3**

    When higher_is_better=True and curr > prev → "↑ improved".
    """
    assume(curr > prev)
    result = get_directional_indicator(prev, curr, True)
    assert result == "↑ improved", (
        f"Expected '↑ improved' for higher_is_better=True, prev={prev}, curr={curr}, got {result!r}"
    )


@given(
    prev=st.floats(allow_nan=False, allow_infinity=False),
    curr=st.floats(allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_get_directional_indicator_higher_is_better_worsened(prev, curr):
    """
    **Tag: Feature: mob-brain-tester-launch, Property 2: Directional indicator correctness**
    **Validates: Requirements 11.3**

    When higher_is_better=True and curr < prev → "↓ worsened".
    """
    assume(curr < prev)
    result = get_directional_indicator(prev, curr, True)
    assert result == "↓ worsened", (
        f"Expected '↓ worsened' for higher_is_better=True, prev={prev}, curr={curr}, got {result!r}"
    )


@given(
    prev=st.floats(allow_nan=False, allow_infinity=False),
    curr=st.floats(allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_get_directional_indicator_lower_is_better_improved(prev, curr):
    """
    **Tag: Feature: mob-brain-tester-launch, Property 2: Directional indicator correctness**
    **Validates: Requirements 11.3**

    When higher_is_better=False and curr < prev → "↑ improved".
    """
    assume(curr < prev)
    result = get_directional_indicator(prev, curr, False)
    assert result == "↑ improved", (
        f"Expected '↑ improved' for higher_is_better=False, prev={prev}, curr={curr}, got {result!r}"
    )


@given(
    prev=st.floats(allow_nan=False, allow_infinity=False),
    curr=st.floats(allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_get_directional_indicator_lower_is_better_worsened(prev, curr):
    """
    **Tag: Feature: mob-brain-tester-launch, Property 2: Directional indicator correctness**
    **Validates: Requirements 11.3**

    When higher_is_better=False and curr > prev → "↓ worsened".
    """
    assume(curr > prev)
    result = get_directional_indicator(prev, curr, False)
    assert result == "↓ worsened", (
        f"Expected '↓ worsened' for higher_is_better=False, prev={prev}, curr={curr}, got {result!r}"
    )


# ---------------------------------------------------------------------------
# 8.3 Property test: get_threshold_annotation — threshold-crossing detection (Property 3)
# Validates: Requirements 11.4
# ---------------------------------------------------------------------------

@given(
    prev=st.floats(allow_nan=False, allow_infinity=False),
    curr=st.floats(allow_nan=False, allow_infinity=False),
    threshold=st.floats(allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_get_threshold_annotation_correctness(prev, curr, threshold):
    """
    **Tag: Feature: mob-brain-tester-launch, Property 3: Threshold-crossing detection**
    **Validates: Requirements 11.4**

    Annotation is "✓ threshold met" iff prev < threshold AND curr >= threshold.
    In all other cases the annotation is "".
    """
    result = get_threshold_annotation(prev, curr, threshold)

    if prev < threshold and curr >= threshold:
        assert result == "✓ threshold met", (
            f"Expected '✓ threshold met' for prev={prev}, curr={curr}, threshold={threshold}, "
            f"got {result!r}"
        )
    else:
        assert result == "", (
            f"Expected '' for prev={prev}, curr={curr}, threshold={threshold}, "
            f"got {result!r}"
        )


# ---------------------------------------------------------------------------
# 8.4 Property test: write_brain_snapshot / list_brain_snapshots — round-trip (Property 4)
# Validates: Requirements 12.1, 12.2
# ---------------------------------------------------------------------------

@given(
    label=_safe_label_strategy,
    decision_tree=_decision_tree_strategy,
)
@settings(max_examples=100)
def test_write_brain_snapshot_round_trip(label, decision_tree):
    """
    **Tag: Feature: mob-brain-tester-launch, Property 4: Brain snapshot round-trip**
    **Validates: Requirements 12.1, 12.2**

    Writing a snapshot and reading it back must preserve label, timestamp,
    default_decision_tree, and brain_registry_source.
    """
    brain_registry_source = "def evaluate_hunger(): pass"

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = write_brain_snapshot(
            label=label,
            decision_tree=decision_tree,
            brain_registry_source=brain_registry_source,
            snapshots_dir=tmpdir,
        )

        # Read the file back
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        assert data["label"] == label, (
            f"label mismatch: expected {label!r}, got {data['label']!r}"
        )
        assert isinstance(data["timestamp"], str) and len(data["timestamp"]) > 0, (
            f"timestamp must be a non-empty string, got {data['timestamp']!r}"
        )
        assert data["default_decision_tree"] == decision_tree, (
            f"decision_tree mismatch: expected {decision_tree!r}, got {data['default_decision_tree']!r}"
        )
        assert isinstance(data["brain_registry_source"], str) and len(data["brain_registry_source"]) > 0, (
            f"brain_registry_source must be a non-empty string, got {data['brain_registry_source']!r}"
        )


# ---------------------------------------------------------------------------
# 8.5 Property test: list_brain_snapshots — snapshot listing completeness (Property 5)
# Validates: Requirements 12.4
# ---------------------------------------------------------------------------

@given(
    labels=st.lists(
        _safe_label_strategy,
        min_size=1,
        max_size=10,
        unique=True,
    )
)
@settings(max_examples=100)
def test_list_brain_snapshots_completeness(labels):
    """
    **Tag: Feature: mob-brain-tester-launch, Property 5: Snapshot listing completeness**
    **Validates: Requirements 12.4**

    After writing a snapshot for each label, list_brain_snapshots must return
    an entry for every label, and each entry must have a non-empty timestamp.
    """
    brain_registry_source = "def evaluate_hunger(): pass"
    decision_tree = {"root": "evaluate_state"}

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write one snapshot per label
        for label in labels:
            write_brain_snapshot(
                label=label,
                decision_tree=decision_tree,
                brain_registry_source=brain_registry_source,
                snapshots_dir=tmpdir,
            )

        result = list_brain_snapshots(tmpdir)

        # Result length must match number of labels written
        assert len(result) == len(labels), (
            f"Expected {len(labels)} snapshots, got {len(result)}"
        )

        # Every label must appear in the result
        result_labels = [entry["label"] for entry in result]
        for label in labels:
            assert label in result_labels, (
                f"Label {label!r} not found in list_brain_snapshots result"
            )

        # Every entry must have a non-empty timestamp
        for entry in result:
            assert isinstance(entry["timestamp"], str) and len(entry["timestamp"]) > 0, (
                f"Entry has empty or missing timestamp: {entry!r}"
            )


# ---------------------------------------------------------------------------
# 8.6 Example-based unit tests
# ---------------------------------------------------------------------------

def _make_report(status: str, iteration: int = 1, recommendations: list | None = None) -> dict:
    """Helper to build a minimal RecommendationReport dict."""
    return {
        "status": status,
        "iteration": iteration,
        "test_result": {
            "survival_rate": 0.8 if status == "BASELINE_MET" else 0.3,
            "breed_event_count": 2 if status == "BASELINE_MET" else 0,
            "eat_action_count": 10,
            "starvation_death_count": 0 if status == "BASELINE_MET" else 2,
            "mean_ticks_survived": 150.0,
        },
        "recommendations": recommendations or [],
        "markdown_summary": "",
    }


def test_baseline_met_next_steps_contains_evolutionary_mechanics():
    """BASELINE_MET report renders a Next Steps section containing 'evolutionary mechanics may proceed'."""
    report = _make_report("BASELINE_MET")
    rendered = render_recommendation_report(report)
    assert "evolutionary mechanics may proceed" in rendered.lower(), (
        f"Expected 'evolutionary mechanics may proceed' in BASELINE_MET Next Steps, got:\n{rendered}"
    )


def test_baseline_not_met_next_steps_contains_iterations_remaining():
    """BASELINE_NOT_MET report renders a Next Steps section containing 'iteration(s) remaining'."""
    report = _make_report("BASELINE_NOT_MET", iteration=1)
    rendered = render_recommendation_report(report)
    assert "iteration(s) remaining" in rendered, (
        f"Expected 'iteration(s) remaining' in BASELINE_NOT_MET Next Steps, got:\n{rendered}"
    )


def test_manual_review_required_references_key_files():
    """MANUAL_REVIEW_REQUIRED report renders references to the three key files."""
    report = _make_report("MANUAL_REVIEW_REQUIRED", iteration=3)
    rendered = render_recommendation_report(report)
    assert "client/mob_brain.py" in rendered, (
        "Expected 'client/mob_brain.py' in MANUAL_REVIEW_REQUIRED report"
    )
    assert "client/brain_registry.py" in rendered, (
        "Expected 'client/brain_registry.py' in MANUAL_REVIEW_REQUIRED report"
    )
    assert "server/constants.py" in rendered, (
        "Expected 'server/constants.py' in MANUAL_REVIEW_REQUIRED report"
    )


def test_get_directional_indicator_improved_higher_is_better():
    """get_directional_indicator(0.4, 0.6, True) → '↑ improved'."""
    assert get_directional_indicator(0.4, 0.6, True) == "↑ improved"


def test_get_directional_indicator_worsened_higher_is_better():
    """get_directional_indicator(0.6, 0.4, True) → '↓ worsened'."""
    assert get_directional_indicator(0.6, 0.4, True) == "↓ worsened"


def test_get_directional_indicator_improved_lower_is_better():
    """get_directional_indicator(3, 1, False) → '↑ improved' (lower is better, count decreased)."""
    assert get_directional_indicator(3, 1, False) == "↑ improved"


def test_get_directional_indicator_unchanged():
    """get_directional_indicator(5.0, 5.0, True) → '→ unchanged'."""
    assert get_directional_indicator(5.0, 5.0, True) == "→ unchanged"


def test_get_threshold_annotation_threshold_met():
    """get_threshold_annotation(0.6, 0.75, 0.7) → '✓ threshold met'."""
    assert get_threshold_annotation(0.6, 0.75, 0.7) == "✓ threshold met"


def test_get_threshold_annotation_already_above_threshold():
    """get_threshold_annotation(0.75, 0.8, 0.7) → '' (was already above threshold)."""
    assert get_threshold_annotation(0.75, 0.8, 0.7) == ""


def test_get_threshold_annotation_did_not_cross_threshold():
    """get_threshold_annotation(0.6, 0.65, 0.7) → '' (did not cross threshold)."""
    assert get_threshold_annotation(0.6, 0.65, 0.7) == ""
