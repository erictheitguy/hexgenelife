"""
Phase 4.5 — Mob class.

Wraps a mob_id with its brain, state cache, and action cycle.
Each tick the mob follows this cycle:
    1. LOOK → observe surroundings
    2. Feed LOOK_RESULT into brain
    3. Brain traverses decision tree → emits an action
    4. Send action to server
"""
import json
import logging
from client.mob_brain import MobBrain

logging.basicConfig(level=logging.INFO)


class Mob:
    """Represents a single mob managed by this client."""

    def __init__(self, mob_id: str, mob_type: str = "prey",
                 decision_tree: dict | None = None,
                 memory: dict | None = None):
        self.mob_id = mob_id
        self.mob_type = mob_type
        self.state: dict = {
            "mob_id": mob_id,
            "mob_type": mob_type,
            "position": {"x": 0, "y": 0},
            "hunger": 0.0,
            "fat": 10.0,
            "energy": 50.0,
            "health": 100.0,
            "life_stage": "adult",
            "vision": 10.0,
        }
        # Brain
        if decision_tree is None:
            from client.mob_brain import PREY_DECISION_TREE, PREDATOR_DECISION_TREE
            decision_tree = (PREDATOR_DECISION_TREE if mob_type == "predator"
                             else PREY_DECISION_TREE)
        self.brain = MobBrain(decision_tree, memory or {})

        # Track what phase of the tick cycle we're in
        self._awaiting_look = False
        self._tick_action_done = False

    def update_state(self, data: dict):
        """Merge incoming server data into local state cache."""
        if "position" in data:
            self.state["position"] = data["position"]
        if "health" in data:
            h = data["health"]
            for key in ("hunger", "fat", "energy", "health", "life_stage"):
                if key in h:
                    self.state[key] = h[key]
        if "physical" in data:
            p = data["physical"]
            if "vision" in p:
                self.state["vision"] = p["vision"]
            self.state["mob_type"] = self.mob_type

    def store_look_result(self, look_payload: dict):
        """Store LOOK_RESULT data into brain memory for decision-making."""
        self.brain.memory["last_look"] = look_payload
        self._awaiting_look = False

    def get_tick_action(self) -> dict | None:
        """Run brain and return the action to send, or None.

        On first call each tick, the mob issues a LOOK command.
        On second call (after LOOK_RESULT arrives), the brain thinks and
        produces an action (MOVE_MOB, EAT_GRASS, ATTACK_MOB, etc).
        """
        if self._tick_action_done:
            return None

        # Phase 1: Issue LOOK first
        if self._awaiting_look is False and "last_look" not in self.brain.memory:
            self._awaiting_look = True
            return {"action": "LOOK", "payload": {"mobId": self.mob_id}}

        # Phase 2: Think and produce action
        action = self.brain.think(self.state)
        self._tick_action_done = True

        if action:
            # Ensure mobId is in payload
            action.setdefault("payload", {})
            action["payload"]["mobId"] = self.mob_id
            return action

        return None

    def reset_tick(self):
        """Called at the start of each new tick."""
        self._tick_action_done = False
        self._awaiting_look = False

    def get_memory(self) -> dict:
        """Return brain memory for persistence."""
        return self.brain.get_memory()
