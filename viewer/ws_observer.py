"""
ViewerWSObserver — background thread that connects to the game WebSocket server
and enqueues incremental broadcast events for the viewer's main loop to apply.

The viewer's main loop calls drain() each frame to get pending events, then
applies them to world_state via apply_event().  The 500ms DB poll continues to
run as a full reconciliation pass so the viewer stays consistent even if events
are missed during a reconnect.
"""
import asyncio
import json
import logging
import threading

import websockets

logger = logging.getLogger("ViewerWSObserver")

RECONNECT_DELAY_S = 2.0
# Event types we care about; others are silently dropped.
OBSERVED_TYPES = frozenset({"MOB_MOVED", "MOB_ATTACKED", "MOB_EATEN", "GRASS_EATEN", "MOB_BRED"})


class ViewerWSObserver:
    """Runs an asyncio event loop in a daemon thread.

    Thread-safe API:
        start()  — begin background connection loop
        stop()   — signal the loop to exit (non-blocking)
        drain()  — return and clear all pending (msg_type, payload) tuples
    """

    def __init__(self, uri: str):
        self.uri = uri
        self._queue: list[tuple[str, dict]] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ViewerWSObserver")

    def start(self):
        self._thread.start()
        logger.info(f"ViewerWSObserver started, connecting to {self.uri}")

    def stop(self):
        self._stop_event.set()

    def drain(self) -> list[tuple[str, dict]]:
        """Return all pending events and clear the internal queue (thread-safe)."""
        with self._lock:
            events, self._queue = self._queue, []
        return events

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self):
        asyncio.run(self._listen())

    async def _listen(self):
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(self.uri) as ws:
                    logger.info("ViewerWSObserver connected.")
                    async for raw in ws:
                        if self._stop_event.is_set():
                            break
                        try:
                            self._handle(json.loads(raw))
                        except Exception:
                            pass
            except Exception as exc:
                if not self._stop_event.is_set():
                    logger.debug(f"ViewerWSObserver connection lost ({exc}). Retrying in {RECONNECT_DELAY_S}s.")
                    await asyncio.sleep(RECONNECT_DELAY_S)

    def _handle(self, msg: dict):
        msg_type = msg.get("type")
        if msg_type not in OBSERVED_TYPES:
            return
        with self._lock:
            self._queue.append((msg_type, msg.get("payload", {})))


def apply_event(world_state: dict, msg_type: str, payload: dict) -> None:
    """Apply a single broadcast event as an incremental patch to world_state.

    world_state has the shape produced by DBReader.get_world_state():
        {"mobs": [{id, x, y, health, ...}, ...], "tiles": [{id, grass, ...}, ...]}
    """
    if msg_type == "MOB_MOVED":
        mob_id = payload.get("mobId")
        position = payload.get("position", {})
        if mob_id:
            for mob in world_state.get("mobs", []):
                if mob.get("id") == mob_id:
                    mob["x"] = position.get("x", mob["x"])
                    mob["y"] = position.get("y", mob["y"])
                    break

    elif msg_type == "MOB_ATTACKED":
        target_id = payload.get("targetId")
        damage = payload.get("damage", 0.0)
        if target_id:
            for mob in world_state.get("mobs", []):
                if mob.get("id") == target_id:
                    mob["health"] = max(0.0, mob.get("health", 100.0) - damage)
                    break

    elif msg_type == "MOB_EATEN":
        target_id = payload.get("targetId")
        if target_id:
            world_state["mobs"] = [
                m for m in world_state.get("mobs", []) if m.get("id") != target_id
            ]

    elif msg_type == "GRASS_EATEN":
        tile_id = str(payload.get("tileId", ""))
        remaining = payload.get("grassRemaining")
        if tile_id and remaining is not None:
            for tile in world_state.get("tiles", []):
                if str(tile.get("id")) == tile_id:
                    tile["grass"] = remaining
                    break

    elif msg_type == "MOB_BRED":
        # New mob — will appear fully on next DB reconciliation pass.
        # Nothing to patch incrementally.
        pass
