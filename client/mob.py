"""
Phase 4.5 — Mob class.

Wraps a mob_id with its brain, state cache, and action cycle.
Each tick the mob follows this cycle:
    1. LOOK → observe surroundings
    2. Feed LOOK_RESULT into brain
    3. Brain traverses decision tree → emits an action
    4. Send action to server
"""
import os
import logging
import json
from client.mob_brain import MobBrain

# Setup base logs directory
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)


class Mob:
    """Represents a single mob managed by this client."""

    def __init__(self, mob_id: str, mob_type: str = "prey",
                 decision_tree: dict | None = None,
                 memory: dict | None = None):
        self.mob_id = mob_id
        self.mob_type = mob_type
        
        # Setup Logger — inherits level from root (set by websocket_client)
        self.logger = logging.getLogger(f"Mob_{mob_id}")
        # Avoid duplicate handlers if Mob is re-initialized (though unlikely per process)
        if not self.logger.handlers:
            fh = logging.FileHandler(os.path.join(LOGS_DIR, f"{mob_id}.log"))
            fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(fh)
            
        self.logger.debug(f"Mob {mob_id} initialized (type={mob_type})")

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
        self.brain = MobBrain(decision_tree, memory or {}, logger=self.logger)

        # Track what phase of the tick cycle we're in
        self._awaiting_look = False
        self._tick_action_done = False
        self._is_dead_logged = False

    @property
    def is_dead(self) -> bool:
        """Returns True if the mob's health is 0 or less."""
        return self.state.get("health", 100.0) <= 0


    def update_state(self, data: dict):
        """Merge incoming server data into local state cache."""
        if "position" in data:
            self.state["position"] = data["position"]
        if "health" in data:
            h = data["health"]
            old_health = self.state.get("health", 100.0)
            for key in ("hunger", "fat", "energy", "health", "life_stage"):
                if key in h:
                    self.state[key] = h[key]
            
            # Starvation/Death logging
            if self.state["health"] <= 0 and not self._is_dead_logged:
                self.logger.error(f"DEAD! Mob {self.mob_id} has died.")
                self._is_dead_logged = True
            elif self.state["health"] < old_health and self.state["hunger"] > 20:
                self.logger.warning(f"STARVING! Health dropped from {old_health:.1f} to {self.state['health']:.1f} (Hunger: {self.state['hunger']:.1f})")

        if "mob_type" in data:
            self.state["mob_type"] = data["mob_type"]
            self.mob_type = data["mob_type"]
        if "physical" in data:
            p = data["physical"]
            if "vision" in p:
                self.state["vision"] = p["vision"]
        if "brain" in data:
            b = data["brain"]
            if "decision_tree" in b:
                self.set_decision_tree(b["decision_tree"])
            if "memory" in b:
                self.brain.set_memory(b["memory"])

    def store_look_result(self, look_payload: dict):
        """Store LOOK_RESULT data into brain memory for decision-making."""
        self.brain.memory["last_look"] = look_payload
        # Update state from mob_self
        mob_self = look_payload.get("mob_self", {})
        for key in ("hunger", "fat", "energy", "health", "herd", "life_stage"):
            if key in mob_self:
                self.state[key] = mob_self[key]
        self.logger.debug(f"Stored look result for mob {self.mob_id}: {look_payload}")
        self._awaiting_look = False

    def get_tick_action(self) -> dict | None:
        """Run brain and return the action to send, or None.

        On first call each tick (when no LOOK data exists), emits LOOK.
        On second call (after LOOK_RESULT arrives), the brain thinks and
        produces an action (MOVE_MOB, EAT_GRASS, ATTACK_MOB, etc).
        """
        if self._tick_action_done:
            return None

        # If we haven't done a LOOK yet this tick, do it first
        if not self._awaiting_look and "last_look" not in self.brain.memory:
            self._awaiting_look = True
            return {"action": "LOOK", "payload": {"mobId": self.mob_id}}

        # If we're still waiting for the LOOK result, don't act yet
        if self._awaiting_look:
            return None

        # LOOK result is in memory — run the brain
        action = self.brain.think(self.state)
        self._tick_action_done = True

        if action:
            action.setdefault("payload", {})
            action["payload"]["mobId"] = self.mob_id
            return action

        return None

    def reset_tick(self):
        """Called at the start of each new tick."""
        self._tick_action_done = False
        self._awaiting_look = False
        # Clear last_look so LOOK is re-issued each tick
        self.brain.memory.pop("last_look", None)

    def get_memory(self) -> dict:
        """Return brain memory for persistence."""
        return self.brain.get_memory()

    def set_decision_tree(self, tree: dict):
        """Update the brain's decision tree structure."""
        self.brain.tree = tree
        self.brain.root_id = tree.get("root", "evaluate_state")
        self.brain.nodes = tree.get("nodes", {})
