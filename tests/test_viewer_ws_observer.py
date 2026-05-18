"""
Tests for viewer/ws_observer.py — apply_event() and ViewerWSObserver queue mechanics.
"""
import unittest
from viewer.ws_observer import apply_event, ViewerWSObserver


def _make_world():
    return {
        "mobs": [
            {"id": "mob_1", "x": 0.0, "y": 0.0, "health": 80.0},
            {"id": "mob_2", "x": 5.0, "y": 5.0, "health": 100.0},
        ],
        "tiles": [
            {"id": "tile_3", "grass": 20.0, "water": 10.0},
        ],
    }


class TestApplyEvent(unittest.TestCase):

    def test_mob_moved_updates_position(self):
        ws = _make_world()
        apply_event(ws, "MOB_MOVED", {"mobId": "mob_1", "position": {"x": 3.0, "y": 7.0}})
        mob = next(m for m in ws["mobs"] if m["id"] == "mob_1")
        self.assertAlmostEqual(mob["x"], 3.0)
        self.assertAlmostEqual(mob["y"], 7.0)

    def test_mob_moved_ignores_unknown_mob(self):
        ws = _make_world()
        apply_event(ws, "MOB_MOVED", {"mobId": "ghost", "position": {"x": 1.0, "y": 1.0}})
        self.assertEqual(len(ws["mobs"]), 2)  # no change, no crash

    def test_mob_attacked_decrements_health(self):
        ws = _make_world()
        apply_event(ws, "MOB_ATTACKED", {"attackerId": "mob_2", "targetId": "mob_1", "damage": 20.0})
        mob = next(m for m in ws["mobs"] if m["id"] == "mob_1")
        self.assertAlmostEqual(mob["health"], 60.0)

    def test_mob_attacked_health_floors_at_zero(self):
        ws = _make_world()
        apply_event(ws, "MOB_ATTACKED", {"attackerId": "mob_2", "targetId": "mob_1", "damage": 200.0})
        mob = next(m for m in ws["mobs"] if m["id"] == "mob_1")
        self.assertEqual(mob["health"], 0.0)

    def test_mob_eaten_removes_target(self):
        ws = _make_world()
        apply_event(ws, "MOB_EATEN", {"eaterId": "mob_2", "targetId": "mob_1"})
        ids = [m["id"] for m in ws["mobs"]]
        self.assertNotIn("mob_1", ids)
        self.assertIn("mob_2", ids)

    def test_mob_eaten_ignores_unknown_target(self):
        ws = _make_world()
        apply_event(ws, "MOB_EATEN", {"eaterId": "mob_2", "targetId": "ghost"})
        self.assertEqual(len(ws["mobs"]), 2)

    def test_grass_eaten_patches_tile(self):
        ws = _make_world()
        apply_event(ws, "GRASS_EATEN", {"mobId": "mob_1", "tileId": "tile_3", "grassRemaining": 5.0})
        tile = next(t for t in ws["tiles"] if t["id"] == "tile_3")
        self.assertAlmostEqual(tile["grass"], 5.0)

    def test_grass_eaten_ignores_unknown_tile(self):
        ws = _make_world()
        apply_event(ws, "GRASS_EATEN", {"mobId": "mob_1", "tileId": "tile_99", "grassRemaining": 0.0})
        tile = ws["tiles"][0]
        self.assertAlmostEqual(tile["grass"], 20.0)  # unchanged

    def test_mob_bred_is_no_op(self):
        """MOB_BRED has no incremental patch — child appears on next DB reconciliation."""
        ws = _make_world()
        apply_event(ws, "MOB_BRED", {"parentAId": "mob_1", "parentBId": "mob_2", "childId": "child_1"})
        self.assertEqual(len(ws["mobs"]), 2)  # child not inserted yet

    def test_unknown_event_type_does_not_raise(self):
        ws = _make_world()
        apply_event(ws, "UNKNOWN_FUTURE_EVENT", {"foo": "bar"})

    def test_sequence_move_then_eat(self):
        """Chain of events: mob moves then gets eaten — position updates then disappears."""
        ws = _make_world()
        apply_event(ws, "MOB_MOVED", {"mobId": "mob_1", "position": {"x": 9.0, "y": 9.0}})
        apply_event(ws, "MOB_EATEN", {"eaterId": "mob_2", "targetId": "mob_1"})
        ids = [m["id"] for m in ws["mobs"]]
        self.assertNotIn("mob_1", ids)


class TestViewerWSObserverQueue(unittest.TestCase):

    def test_drain_returns_handled_events(self):
        """_handle() enqueues observed event types; drain() returns and clears them."""
        observer = ViewerWSObserver("ws://unused:9999")
        observer._handle({"type": "MOB_MOVED", "payload": {"mobId": "mob_1"}})
        observer._handle({"type": "GRASS_EATEN", "payload": {"tileId": "t1", "grassRemaining": 3.0}})
        events = observer.drain()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0][0], "MOB_MOVED")
        self.assertEqual(events[1][0], "GRASS_EATEN")

    def test_drain_clears_queue(self):
        """Second drain() call returns empty list."""
        observer = ViewerWSObserver("ws://unused:9999")
        observer._handle({"type": "MOB_MOVED", "payload": {}})
        observer.drain()
        self.assertEqual(observer.drain(), [])

    def test_unobserved_event_types_not_queued(self):
        """TICK_COMPLETE and other non-broadcast types are silently ignored."""
        observer = ViewerWSObserver("ws://unused:9999")
        observer._handle({"type": "TICK_COMPLETE", "payload": {}})
        observer._handle({"type": "WORLD_UPDATE", "payload": {}})
        observer._handle({"type": "MOB_UPDATE", "payload": {}})
        self.assertEqual(observer.drain(), [])


if __name__ == "__main__":
    unittest.main()
