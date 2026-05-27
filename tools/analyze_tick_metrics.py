#!/usr/bin/env python3
"""Summarize ACTION_LIMIT_EXCEEDED telemetry from a HexGenLife server log.

Reads [TICK-METRICS] JSON lines emitted by server.py and prints aggregated
rejection/deferral counts so we can see which limit is firing under load.

Usage:
    python tools/analyze_tick_metrics.py [logs/server.log] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

METRICS_PREFIX = "[TICK-METRICS] "
LINE_RE = re.compile(r"\[TICK-METRICS\] (\{.*\})\s*$")


def parse_log(path: Path):
    ticks = []
    with path.open() as f:
        for line in f:
            m = LINE_RE.search(line)
            if not m:
                continue
            try:
                ticks.append(json.loads(m.group(1)))
            except json.JSONDecodeError:
                continue
    return ticks


def summarize(ticks: list[dict]) -> dict:
    accepted = Counter()
    rej_ws_cap = Counter()
    def_budget = Counter()
    def_mob_cap = Counter()
    drop_queue_full = Counter()
    rej_by_client = Counter()
    rej_by_mob = Counter()
    ticks_with_rej = 0
    worst_tick = None
    worst_tick_rej = 0
    degraded_ticks = 0
    deeply_degraded_ticks = 0

    for t in ticks:
        accepted.update(t.get("accepted") or {})
        rej_ws_cap.update(t.get("rej_ws_cap") or {})
        def_budget.update(t.get("def_budget") or {})
        def_mob_cap.update(t.get("def_mob_cap") or {})
        drop_queue_full.update(t.get("drop_queue_full") or {})
        for client_id, n in (t.get("top_rej_clients") or []):
            rej_by_client[client_id] += n
        for mob_id, n in (t.get("top_rej_mobs") or []):
            rej_by_mob[mob_id] += n
        tier = t.get("load_tier", 1 if t.get("degraded") else 0)
        if tier >= 1:
            degraded_ticks += 1
        if tier >= 2:
            deeply_degraded_ticks += 1
        tick_rej_total = sum((t.get("rej_ws_cap") or {}).values())
        if tick_rej_total > 0:
            ticks_with_rej += 1
        if tick_rej_total > worst_tick_rej:
            worst_tick_rej = tick_rej_total
            worst_tick = t.get("tick")

    return {
        "tick_count": len(ticks),
        "ticks_with_rejections": ticks_with_rej,
        "degraded_ticks": degraded_ticks,
        "deeply_degraded_ticks": deeply_degraded_ticks,
        "worst_tick": worst_tick,
        "worst_tick_rejections": worst_tick_rej,
        "total_accepted": dict(accepted),
        "total_rej_ws_cap": dict(rej_ws_cap),
        "total_def_budget": dict(def_budget),
        "total_def_mob_cap": dict(def_mob_cap),
        "total_drop_queue_full": dict(drop_queue_full),
        "top_rej_clients": rej_by_client.most_common(10),
        "top_rej_mobs": rej_by_mob.most_common(10),
    }


def format_counter(d: dict) -> str:
    if not d:
        return "  (none)"
    return "\n".join(f"  {k:<24} {v}" for k, v in sorted(d.items(), key=lambda x: -x[1]))


def print_summary(s: dict) -> None:
    print(f"Ticks analyzed:           {s['tick_count']}")
    print(f"Ticks with rejections:    {s['ticks_with_rejections']}")
    print(f"Ticks in degraded mode:   {s['degraded_ticks']}")
    print(f"Ticks in deeply-degraded: {s['deeply_degraded_ticks']}")
    print(f"Worst tick:               #{s['worst_tick']} ({s['worst_tick_rejections']} rejections)")
    print()
    print("Accepted actions (total, by type):")
    print(format_counter(s["total_accepted"]))
    print()
    print("Rejected by per-mob cap (age-evicted -> ACTION_LIMIT_EXCEEDED), by type:")
    print(format_counter(s["total_rej_ws_cap"]))
    print()
    print("Deferred by per-mob cap (waiting for cap window), by type:")
    print(format_counter(s["total_def_mob_cap"]))
    print()
    print("Deferred by global per-tick budget, by type:")
    print(format_counter(s["total_def_budget"]))
    print()
    print("Dropped by queue-full (SERVER_BUSY), by type:")
    print(format_counter(s["total_drop_queue_full"]))
    print()
    print("Top 10 clients by per-ws-cap rejection count:")
    if s["top_rej_clients"]:
        for cid, n in s["top_rej_clients"]:
            print(f"  {cid:<24} {n}")
    else:
        print("  (none)")
    print()
    print("Top 10 mobs by per-ws-cap rejection count:")
    if s["top_rej_mobs"]:
        for mid, n in s["top_rej_mobs"]:
            print(f"  {mid:<24} {n}")
    else:
        print("  (none)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", nargs="?", default="logs/server.log",
                        help="Path to server log (default: logs/server.log)")
    parser.add_argument("--json", action="store_true",
                        help="Emit the summary as JSON instead of formatted text")
    args = parser.parse_args()

    path = Path(args.log)
    if not path.exists():
        print(f"Log file not found: {path}", file=sys.stderr)
        return 1

    ticks = parse_log(path)
    if not ticks:
        print(f"No [TICK-METRICS] lines found in {path}", file=sys.stderr)
        return 1

    summary = summarize(ticks)
    if args.json:
        json.dump(summary, sys.stdout, indent=2)
        print()
    else:
        print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
