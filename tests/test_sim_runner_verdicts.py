"""
Run-level regression tests for the sim-runner verdict logic.

These exercise `_build_report` from the sim-runner skill against synthetic
snapshot streams and assert the three-axis verdict (mechanical / ecological /
observability) plus the overall verdict, which is the worst of the three.

The report builder pulls reliability/perf/death/error figures from the live
server/client logs on disk; we monkeypatch those four helpers (plus the log
tail / load-pressure readers) so every test is deterministic regardless of
what logs happen to exist.

Fixtures based on real runs:
  * runs 33 & 34 — were marked PASS by the old logic; must now reclassify to FAIL.
  * run 35 — mutual extinction via predator overshoot; must be FAIL.

See: Projects/HexGenLife/Plans/2026-06-15-adversarial-review-fix-plan.md (Phase 2 #5)
"""
import importlib.util
import os
import re

import pytest

# ---------------------------------------------------------------------------
# Load the sim-runner module (prefer the .claude copy, fall back to .codex).
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CANDIDATES = [
    os.path.join(_ROOT, ".claude", "skills", "sim-runner", "sim_runner_skill.py"),
    os.path.join(_ROOT, ".codex", "skills", "sim-runner", "sim_runner_skill.py"),
]
_SKILL_PATH = next((p for p in _CANDIDATES if os.path.exists(p)), None)

pytestmark = pytest.mark.skipif(
    _SKILL_PATH is None, reason="sim_runner_skill.py not found in .claude or .codex"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("sim_runner_skill_under_test", _SKILL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod(monkeypatch):
    """sim-runner module with all log-reading helpers neutralised to clean defaults."""
    m = _load_module()
    monkeypatch.setattr(m, "_client_reliability_stats",
                        lambda: {"connection_failed": 0, "look_timeouts": 0, "forced_reconnect": 0})
    monkeypatch.setattr(m, "_performance_metrics", lambda: {})
    monkeypatch.setattr(m, "_death_cause_tally",
                        lambda: {"starvation": 0, "predation": 0, "old_age": 0, "unknown": 0})
    monkeypatch.setattr(m, "_error_code_tally",
                        lambda: {"MOB_NOT_FOUND": 0, "TARGET_NOT_FOUND": 0, "BREED_FAILED": 0, "other": 0})
    monkeypatch.setattr(m, "_load_pressure_summary", lambda: "(test)")
    monkeypatch.setattr(m, "_tail_log", lambda *a, **k: "(test)")
    return m


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _snap(**kw):
    """A snapshot dict with sane zero defaults; override only what a test cares about."""
    base = {
        "tick": 0,
        "prey_alive": 0, "prey_total": 0, "prey_bred": 0,
        "pred_alive": 0, "pred_total": 0, "pred_bred": 0,
        "prey_health_avg": 0.0,
        "attack_events": 0, "eat_mob_events": 0, "eat_grass_events": 0,
        "breed_events": 0, "degraded_mode": 0,
    }
    base.update(kw)
    return base


def _verdicts(mod, snapshots, log_errors=None):
    """Build a report and parse the four verdict values out of its frontmatter."""
    report = mod._build_report(
        run_num=1,
        timestamp="2026-06-15 00:00:00",
        duration_s=1800.0,
        snapshots=snapshots,
        phases=["test"],
        log_errors=log_errors or [],
    )
    out = {}
    for line in report.splitlines():
        m = re.match(r"(verdict(?:_\w+)?):\s*(PASS|WARN|FAIL)\s*$", line)
        if m:
            out[m.group(1)] = m.group(2)
        if line.strip() == "---" and out:
            break  # end of frontmatter
    return out


def _set_clean_logs(m, monkeypatch, **overrides):
    """Override individual log-derived figures while keeping the rest clean."""
    rel = {"connection_failed": 0, "look_timeouts": 0, "forced_reconnect": 0}
    err = {"MOB_NOT_FOUND": 0, "TARGET_NOT_FOUND": 0, "BREED_FAILED": 0, "other": 0}
    rel.update({k: v for k, v in overrides.items() if k in rel})
    err.update({k: v for k, v in overrides.items() if k in err})
    monkeypatch.setattr(m, "_client_reliability_stats", lambda: rel)
    monkeypatch.setattr(m, "_error_code_tally", lambda: err)


# ---------------------------------------------------------------------------
# Structural sanity
# ---------------------------------------------------------------------------
def test_frontmatter_exposes_three_axes(mod):
    v = _verdicts(mod, [
        _snap(tick=10, prey_alive=8, prey_total=8, prey_health_avg=90),
        _snap(tick=900, prey_alive=10, prey_total=12, prey_bred=4, prey_health_avg=80),
    ])
    assert {"verdict", "verdict_mechanical", "verdict_ecological", "verdict_observability"} <= v.keys()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_clean_bounded_survival_and_breeding_passes(mod):
    snaps = [
        _snap(tick=10,   prey_alive=8,  prey_total=8,  prey_bred=0, prey_health_avg=95,
              pred_total=0, pred_alive=0, pred_bred=0),
        _snap(tick=500,  prey_alive=12, prey_total=14, prey_bred=6, prey_health_avg=82,
              pred_total=3, pred_alive=3, pred_bred=1),
        _snap(tick=1000, prey_alive=13, prey_total=18, prey_bred=8, prey_health_avg=80,
              pred_total=3, pred_alive=3, pred_bred=1),
        _snap(tick=1500, prey_alive=14, prey_total=20, prey_bred=9, prey_health_avg=78,
              pred_total=3, pred_alive=3, pred_bred=2, attack_events=40, eat_mob_events=10),
    ]
    v = _verdicts(mod, snaps)
    assert v["verdict"] == "PASS"
    assert v["verdict_mechanical"] == "PASS"
    assert v["verdict_ecological"] == "PASS"
    assert v["verdict_observability"] == "PASS"


# ---------------------------------------------------------------------------
# Ecological failures
# ---------------------------------------------------------------------------
def test_runaway_predator_growth_is_not_pass(mod):
    # Predators start at 5, peak at 30 (>= 4x start) -> ecological FAIL.
    snaps = [
        _snap(tick=20,  prey_alive=50, prey_total=50, prey_bred=5,  prey_health_avg=90,
              pred_total=5,  pred_alive=5,  pred_bred=0),
        _snap(tick=400, prey_alive=40, prey_total=60, prey_bred=30, prey_health_avg=60,
              pred_total=18, pred_alive=18, pred_bred=8),
        _snap(tick=800, prey_alive=25, prey_total=70, prey_bred=35, prey_health_avg=40,
              pred_total=30, pred_alive=30, pred_bred=12),
    ]
    v = _verdicts(mod, snaps)
    assert v["verdict"] != "PASS"
    assert v["verdict_ecological"] == "FAIL"


def test_prey_critical_late_health_warns(mod):
    # No predators; prey survive and bred but limp along at HP 12 -> ecological WARN.
    snaps = [
        _snap(tick=10,   prey_alive=10, prey_total=10, prey_bred=0, prey_health_avg=90),
        _snap(tick=600,  prey_alive=9,  prey_total=14, prey_bred=4, prey_health_avg=30),
        _snap(tick=1000, prey_alive=9,  prey_total=16, prey_bred=6, prey_health_avg=14),
        _snap(tick=1500, prey_alive=9,  prey_total=18, prey_bred=7, prey_health_avg=12),
    ]
    v = _verdicts(mod, snaps)
    assert v["verdict_ecological"] in {"WARN", "FAIL"}
    assert v["verdict"] != "PASS"


def test_prey_near_zero_late_health_fails(mod):
    snaps = [
        _snap(tick=10,   prey_alive=10, prey_total=10, prey_bred=0, prey_health_avg=90),
        _snap(tick=900,  prey_alive=6,  prey_total=14, prey_bred=4, prey_health_avg=7),
        _snap(tick=1200, prey_alive=5,  prey_total=14, prey_bred=4, prey_health_avg=5),
        _snap(tick=1500, prey_alive=4,  prey_total=14, prey_bred=4, prey_health_avg=3),
    ]
    v = _verdicts(mod, snaps)
    assert v["verdict_ecological"] == "FAIL"


def test_top_heavy_ratio_is_not_pass(mod):
    # Predators outnumber prey but no runaway growth and health OK -> ecological WARN.
    snaps = [
        _snap(tick=20,   prey_alive=20, prey_total=20, prey_bred=2, prey_health_avg=90,
              pred_total=12, pred_alive=12, pred_bred=0),
        _snap(tick=800,  prey_alive=12, prey_total=30, prey_bred=10, prey_health_avg=70,
              pred_total=14, pred_alive=14, pred_bred=4),
        _snap(tick=1400, prey_alive=10, prey_total=34, prey_bred=12, prey_health_avg=65,
              pred_total=13, pred_alive=12, pred_bred=5),
    ]
    v = _verdicts(mod, snaps)
    assert v["verdict_ecological"] in {"WARN", "FAIL"}
    assert v["verdict"] != "PASS"


# ---------------------------------------------------------------------------
# Observability / reliability failures (ecology stays healthy)
# ---------------------------------------------------------------------------
def test_high_breed_failed_volume_is_not_pass(mod, monkeypatch):
    _set_clean_logs(mod, monkeypatch, BREED_FAILED=200)  # >= ERR_CODE_FAIL
    snaps = [
        _snap(tick=10,   prey_alive=8,  prey_total=8,  prey_bred=0, prey_health_avg=95,
              pred_total=3, pred_alive=3, pred_bred=0),
        _snap(tick=1500, prey_alive=14, prey_total=20, prey_bred=9, prey_health_avg=80,
              pred_total=3, pred_alive=3, pred_bred=2),
    ]
    v = _verdicts(mod, snaps)
    assert v["verdict_observability"] == "FAIL"
    assert v["verdict_ecological"] == "PASS"   # ecology untouched
    assert v["verdict"] == "FAIL"              # overall = worst axis


def test_repeated_look_timeouts_warn(mod, monkeypatch):
    _set_clean_logs(mod, monkeypatch, look_timeouts=5)  # WARN band (>=3, <20)
    snaps = [
        _snap(tick=10,   prey_alive=8,  prey_total=8,  prey_bred=0, prey_health_avg=95,
              pred_total=3, pred_alive=3, pred_bred=0),
        _snap(tick=1500, prey_alive=14, prey_total=20, prey_bred=9, prey_health_avg=80,
              pred_total=3, pred_alive=3, pred_bred=2),
    ]
    v = _verdicts(mod, snaps)
    assert v["verdict_observability"] == "WARN"
    assert v["verdict"] != "PASS"


# ---------------------------------------------------------------------------
# Mechanical failures
# ---------------------------------------------------------------------------
def test_server_stall_low_tick_count_fails_mechanically(mod):
    snaps = [
        _snap(tick=5, prey_alive=8, prey_total=8, prey_bred=2, prey_health_avg=95,
              pred_total=3, pred_alive=3, pred_bred=1),
    ]
    v = _verdicts(mod, snaps)
    assert v["verdict_mechanical"] == "FAIL"
    assert v["verdict"] == "FAIL"


def test_traceback_in_logs_fails_mechanically(mod):
    snaps = [
        _snap(tick=10,   prey_alive=8,  prey_total=8,  prey_bred=0, prey_health_avg=95,
              pred_total=3, pred_alive=3, pred_bred=0),
        _snap(tick=1500, prey_alive=14, prey_total=20, prey_bred=9, prey_health_avg=80,
              pred_total=3, pred_alive=3, pred_bred=2),
    ]
    v = _verdicts(mod, snaps, log_errors=["2026-06-15 ERROR Traceback (most recent call last):"])
    assert v["verdict_mechanical"] == "FAIL"


# ---------------------------------------------------------------------------
# Real-run fixtures
# ---------------------------------------------------------------------------
def test_run34_shape_reclassifies_to_fail(mod):
    """Run 34 was PASS under the old logic; the hardened logic must FAIL it.

    Real numbers: ended 16 prey / 75 predators alive (4.7x ratio), avg prey HP 8.94.
    """
    snaps = [
        _snap(tick=12,   prey_alive=55, prey_total=55,  prey_bred=0,   prey_health_avg=100,
              pred_total=5,   pred_alive=5,  pred_bred=0),
        _snap(tick=300,  prey_alive=60, prey_total=120, prey_bred=50,  prey_health_avg=55,
              pred_total=40,  pred_alive=40, pred_bred=20),
        _snap(tick=700,  prey_alive=45, prey_total=150, prey_bred=90,  prey_health_avg=30,
              pred_total=60,  pred_alive=60, pred_bred=120),
        _snap(tick=1100, prey_alive=28, prey_total=165, prey_bred=110, prey_health_avg=15,
              pred_total=72,  pred_alive=72, pred_bred=160),
        _snap(tick=1521, prey_alive=16, prey_total=172, prey_bred=123, prey_health_avg=8.94,
              pred_total=183, pred_alive=75, pred_bred=178,
              attack_events=2390, eat_mob_events=1955),
    ]
    v = _verdicts(mod, snaps)
    assert v["verdict"] == "FAIL"
    assert v["verdict_ecological"] == "FAIL"  # ratio >= 2.0 and late HP < 8


# ---------------------------------------------------------------------------
# ADD-1: error tally must count unattributed server errors, not just attributed
# ---------------------------------------------------------------------------
def test_error_tally_counts_unattributed_server_errors(tmp_path, monkeypatch):
    """`Server error [CODE]` lines are logged even when the client cannot attribute
    the error to a Mob — the tally must count them so the COR-3 attribution gap
    cannot hide a COR-2 error storm from the verdict."""
    m = _load_module()
    log = tmp_path / "client.log"
    log.write_text(
        "2026-06-15 - ClientManager - WARNING - Server error [MOB_NOT_FOUND]: Mob x not found.\n"
        "2026-06-15 - ClientManager - WARNING - Server error [MOB_NOT_FOUND]: Mob y not found.\n"
        "2026-06-15 - ClientManager - WARNING - Server error [BREED_FAILED]: no partner.\n"
        "2026-06-15 - ClientManager - WARNING - Could not attribute error TARGET_NOT_FOUND to any mob.\n"
    )
    monkeypatch.setattr(m, "CLIENT_LOG", str(log))
    t = m._error_code_tally()
    assert t["MOB_NOT_FOUND"] == 2
    assert t["BREED_FAILED"] == 1


def test_error_tally_falls_back_to_action_lines(tmp_path, monkeypatch):
    """Logs that predate the `Server error [CODE]` line still count via the
    attributed `Action error recorded:` fallback (no double counting)."""
    m = _load_module()
    log = tmp_path / "client.log"
    log.write_text(
        "Mob_x - WARNING - Action error recorded: TARGET_NOT_FOUND (action=ATTACK_MOB)\n"
    )
    monkeypatch.setattr(m, "CLIENT_LOG", str(log))
    t = m._error_code_tally()
    assert t["TARGET_NOT_FOUND"] == 1


def test_unattributed_error_storm_drives_observability_fail(tmp_path, monkeypatch):
    """End-to-end: a log of only unattributed `Server error [MOB_NOT_FOUND]`
    lines must push the observability verdict to FAIL while ecology stays PASS."""
    m = _load_module()
    log = tmp_path / "client.log"
    log.write_text(
        "".join(
            "2026-06-15 - ClientManager - WARNING - Server error [MOB_NOT_FOUND]: gone.\n"
            for _ in range(200)  # >= ERR_CODE_FAIL
        )
    )
    monkeypatch.setattr(m, "CLIENT_LOG", str(log))
    # Keep the other log-derived helpers clean; use the REAL _error_code_tally.
    monkeypatch.setattr(m, "_client_reliability_stats",
                        lambda: {"connection_failed": 0, "look_timeouts": 0, "forced_reconnect": 0})
    monkeypatch.setattr(m, "_performance_metrics", lambda: {})
    monkeypatch.setattr(m, "_death_cause_tally",
                        lambda: {"starvation": 0, "predation": 0, "old_age": 0, "unknown": 0})
    monkeypatch.setattr(m, "_load_pressure_summary", lambda: "(test)")
    monkeypatch.setattr(m, "_tail_log", lambda *a, **k: "(test)")
    snaps = [
        _snap(tick=10,   prey_alive=8,  prey_total=8,  prey_bred=0, prey_health_avg=95,
              pred_total=3, pred_alive=3, pred_bred=0),
        _snap(tick=1500, prey_alive=14, prey_total=20, prey_bred=9, prey_health_avg=80,
              pred_total=3, pred_alive=3, pred_bred=2),
    ]
    v = _verdicts(m, snaps)
    assert v["verdict_observability"] == "FAIL"
    assert v["verdict_ecological"] == "PASS"


# ---------------------------------------------------------------------------
# ADD-2: guard against .claude / .codex sim-runner divergence
# ---------------------------------------------------------------------------
def test_codex_claude_sim_runner_parity():
    """The verdict tests load the .claude copy first; if a .codex copy also
    exists the two must be byte-identical, or the suite could validate the
    wrong runner."""
    claude_p = os.path.join(_ROOT, ".claude", "skills", "sim-runner", "sim_runner_skill.py")
    codex_p = os.path.join(_ROOT, ".codex", "skills", "sim-runner", "sim_runner_skill.py")
    if not (os.path.exists(claude_p) and os.path.exists(codex_p)):
        pytest.skip("only one sim-runner copy present")
    with open(claude_p, "rb") as a, open(codex_p, "rb") as b:
        assert a.read() == b.read(), (
            ".claude and .codex sim_runner_skill.py have diverged — re-sync them "
            "(the verdict tests load the .claude copy first)."
        )


def test_run35_shape_mutual_extinction_fails(mod):
    """Run 35: predator overshoot -> mutual extinction. Prey reach zero.

    Mechanically the run was clean (no stalls/crashes), so only the ecological
    axis should fail — the verdict must still distinguish the two.
    """
    snaps = [
        _snap(tick=10,   prey_alive=111, prey_total=111, prey_bred=11,  prey_health_avg=100,
              pred_total=0,   pred_alive=0,   pred_bred=0,   eat_grass_events=252),
        _snap(tick=192,  prey_alive=213, prey_total=230, prey_bred=130, prey_health_avg=83.7,
              pred_total=29,  pred_alive=29,  pred_bred=218),
        _snap(tick=804,  prey_alive=60,  prey_total=206, prey_bred=107, prey_health_avg=29.1,
              pred_total=205, pred_alive=128, pred_bred=621),
        _snap(tick=1528, prey_alive=8,   prey_total=168, prey_bred=69,  prey_health_avg=4.8,
              pred_total=320, pred_alive=28,  pred_bred=797),
        _snap(tick=2408, prey_alive=3,   prey_total=167, prey_bred=68,  prey_health_avg=1.8,
              pred_total=327, pred_alive=0,   pred_bred=810),
        _snap(tick=3947, prey_alive=0,   prey_total=167, prey_bred=68,  prey_health_avg=0.0,
              pred_total=327, pred_alive=0,   pred_bred=810),
    ]
    v = _verdicts(mod, snaps)
    assert v["verdict"] == "FAIL"
    assert v["verdict_ecological"] == "FAIL"   # prey went extinct
    assert v["verdict_mechanical"] == "PASS"   # tick loop was clean
