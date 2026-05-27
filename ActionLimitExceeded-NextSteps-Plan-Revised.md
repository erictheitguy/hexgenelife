# Action Limit Exceeded Mitigation Plan (Revised)

Date: 2026-05-27
Owner: Simulation/Server-Client Runtime
Scope: Reduce `ACTION_LIMIT_EXCEEDED` storms under heavy load (`50 prey / 5 predators / 30 min`) without regressing tick throughput.

Supersedes: `ActionLimitExceeded-NextSteps-Plan.md` (2026-05-26).

## Why this revision

The prior plan conflated two independent limits in `server/server.py`:

1. **Per-websocket per-tick cap** — `MAX_ACTIONS_PER_TICK = 3` (server.py:41), enforced at server.py:238–244. This is the **only** code path that emits `ACTION_LIMIT_EXCEEDED`. Hard reject, no deferral.
2. **Global per-sim-tick budgets** — `MAX_ACTIONS_PER_SIM_TICK = 600` / `MAX_LOOKS_PER_SIM_TICK = 240` (server.py:43–44), enforced at server.py:314–319. Overflow already defers into `next_pending` (server.py:310, 315, 318, 347). No error is emitted.

Implications for the prior plan:

- Phase 2.4 ("backpressure instead of hard-fail") is already implemented for the global budget. The remaining gap is the per-websocket cap, which the original plan did not name.
- Phase 1.2 ("max 1 outbound action per mob per tick") is already enforced by `autonomous_loop()` structure (client:174–245). A client with N mobs still emits ~2N messages per server tick (LOOK + action), which trips the per-websocket cap of 3 the moment N ≥ 2.
- Phase 2.3 (server-side same-tick `LOOK` dedupe) is low yield. The client uses `look_stride + mob_hash` (client:177–179), so per-mob `LOOK` duplication in a single tick is rare; most `LOOK` traffic is legitimate fan-out across mobs.

This revision reorders work so the highest-leverage fix is item #1, drops low-yield items, and reframes deferred items as building on what already exists.

## Goals (unchanged)

1. Reduce `ACTION_LIMIT_EXCEEDED` frequency by at least 80% in heavy-load runs.
2. Reduce `LOOK` timeouts and forced reconnects to near/below prior baseline.
3. Maintain or improve tick throughput.
4. Preserve behavior quality (no major drop in attack/eat-mob events).

## Phase 1: Fix the structural mismatch (highest leverage)

### 1. Rework the per-websocket action cap

The current `MAX_ACTIONS_PER_TICK = 3` is a per-websocket-per-tick hard reject. It was sized for a single mob per client, but child spawns mean a websocket can legitimately drive multiple mobs, each needing roughly LOOK + 1 action per tick. With N ≥ 2 mobs the cap is exceeded by construction.

Pick one of the following — listed in order of preference:

- **1a. Per-mob accounting.** Replace `self._client_action_counts[websocket]` with a `(websocket, mob_id)` keyed counter and cap **per mob** (e.g., 2/tick). Move the cap check after `mobId` is extracted from the payload. This makes the cap track the actual unit of work.
- **1b. Dynamic per-websocket cap.** Keep the per-websocket model but scale: `cap = BASE + PER_MOB * active_mobs_for_ws`. Active mob count is already known via `_ws_to_mob` and `MobManager`. Cheaper to land than 1a; less precise under uneven mob ownership.
- **1c. Remove the per-websocket cap entirely.** Rely on the global per-sim-tick budget + `inbound_queue` (size 5000) + queue-full `SERVER_BUSY` backpressure as the sole defenses. Smallest diff; gives up per-client fairness.

Recommendation: ship **1b** first (one-line change, low risk), measure, then move to **1a** if per-client fairness regresses.

Deliverables:
- Cap implementation + tests for the multi-mob client case.
- One regression test that reproduces the current storm: 1 client, 3 mobs, normal cadence, expect zero `ACTION_LIMIT_EXCEEDED`.

### 2. Replace the hard reject with a deferral path

Even after item 1, transient bursts will occasionally exceed the cap. Today those messages are rejected immediately (server.py:240–244), and the client reacts with a 6-tick throttle (client:301–303), amplifying the problem.

Change the cap-exceeded path to enqueue into `_pending_actions` with a small max-age (e.g., 2 ticks) instead of rejecting, mirroring how the global budget already defers. Only emit `ACTION_LIMIT_EXCEEDED` when an action is evicted by age — making the error rare and meaningful again.

Deliverables:
- Defer-with-age implementation reusing `next_pending`.
- Tests that a burst of N+1 actions for one mob produces N processed + 1 deferred (no error), and that stale deferrals are evicted with the error code.

### 3. Split telemetry by limit source

Before any phase-2 work, make it possible to tell *which* limit fired. Today, server.py:400 logs aggregate `action_counts` per tick but does not separate rejections.

Add per-tick counters and log lines:
- accepted actions by type
- rejected actions, broken out by: per-websocket cap, global per-tick budget eviction, queue-full
- deferrals by type (already partially visible via `_deferred_actions`)
- per-client and per-mob top-5 rejection sources

Log a single structured line per tick containing all of the above so an analyzer script can parse the run.

Deliverables:
- Counter additions on the existing rejection paths.
- A short script under `tests/` or a dev-tools dir that summarizes a server log.

## Phase 2: Reduce wasteful work

### 4. Client-side dedupe of redundant `LOOK`

Cheaper than server dedupe and addresses the real risk: when `_stale_perception[mob_id]` is True (client:179), the loop forces a `LOOK` even if one was sent very recently. Add a per-mob "look in flight" guard so we never issue a second `LOOK` for the same mob before its `LOOK_RESULT` or timeout resolves.

Deliverables:
- Guard inside `autonomous_loop()` near client:181–207.
- Unit test that a stale-perception flag plus an in-flight LOOK does **not** double-send.

### 5. Drop low-value items from the prior plan

The following items from the prior plan are removed:

- ~~Server same-tick `LOOK` dedupe (prior 2.3)~~ — low yield given client cadence.
- ~~"Hard cap 1 action per mob per tick" on the client (prior 1.2)~~ — already enforced by loop structure.
- ~~Generic "backpressure deferral queue" framing (prior 2.4)~~ — replaced by the more targeted item 2 above.

## Phase 3: Burst shaping (lowest priority — only if needed after Phase 1+2)

### 6. Jitter on `LOOK` cadence

Current cadence uses `look_stride + mob_hash` (client:177–179), a deterministic offset. After any reconnect storm, clients re-synchronize. Add a small bounded jitter (±1 tick) per mob per cycle to break re-synchronization. Keep jitter seeded by `mob_id` so tests remain deterministic.

Deliverables:
- Jitter in the cadence calculation.
- Test confirming the jitter distribution and no burst re-synchronization across 50 simulated clients.

### 7. Make degraded-mode budgets configurable

Today `DEGRADED_ACTION_BUDGET_SCALE = 0.75` and `DEGRADED_LOOK_BUDGET_SCALE = 0.6` are constants (server.py:47–48). Expose as env vars or a small config block so heavy-run tuning doesn't require code edits. Optionally add a heavier-load tier (e.g., `>= 8 slow ticks → scale 0.5`).

Deliverables:
- Config plumbing, no behavior change at defaults.

## Execution order

1. Item 3 (telemetry split) — land first so items 1 and 2 are measurable.
2. Item 1b (dynamic per-websocket cap) — single highest-leverage fix.
3. Item 2 (defer instead of reject) — closes the residual storm path.
4. Item 4 (client in-flight LOOK guard).
5. Re-run benchmark matrix. **Stop here if success criteria are met.**
6. Items 6–7 only if Phase 1+2 leave residual issues.

## Benchmark matrix (unchanged)

1. Light: `10 prey / 2 predators / 15 min`
2. Heavy: `50 prey / 5 predators / 30 min`

## Success criteria (unchanged)

- `ACTION_LIMIT_EXCEEDED` reduced ≥ 80% in heavy run.
- `LOOK` timeouts and forced reconnects substantially below the current heavy baseline.
- No regression in ticks completed over the same wall time.
- `ATTACK` / `EAT_MOB` rates do not materially decline.

## Risks and mitigations

- **Risk:** Per-mob or scaled cap lets one greedy client dominate the global budget.
  - **Mitigation:** Global `MAX_ACTIONS_PER_SIM_TICK` already bounds total work; add a per-client fairness metric to the per-tick telemetry line.
- **Risk:** Deferring instead of rejecting hides genuine misbehavior (e.g., a runaway client).
  - **Mitigation:** Age-based eviction still emits `ACTION_LIMIT_EXCEEDED`; rejection becomes rare-but-meaningful instead of common-and-noisy.
- **Risk:** Telemetry overhead on every action.
  - **Mitigation:** Counters are O(1) increments; emit the structured line once per tick, not per action.

## Open questions for review

- Prefer item **1a** (per-mob accounting) or **1b** (dynamic per-websocket) as the first landing? Lets do the 1a method. 
- Deferral max-age of 2 ticks reasonable, or should it scale with load tier? - scale it with load tier starting with 2
- Should `SERVER_BUSY` (queue full) and `ACTION_LIMIT_EXCEEDED` collapse into a single client-side throttle path, or stay distinct? - lets try and stay distinct
