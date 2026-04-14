"""
Phase 4.5 — Mob Brain Decision Tree Engine.

Loads a decision tree (JSON) and traverses it each tick:
    1. Start at root node
    2. Call the function registered for that node
    3. If result has 'action' key → return command to send to server
    4. If result has 'matrix' + 'next' → follow to next node
    5. Max depth guard prevents infinite loops
"""
import json
import logging
from client.brain_registry import get_function

logging.basicConfig(level=logging.INFO)

MAX_TREE_DEPTH = 20  # prevent infinite loops


class MobBrain:
    """Decision tree engine for a single mob."""

    def __init__(self, decision_tree: dict, memory: dict | None = None):
        """
        Args:
            decision_tree: JSON-derived dict with 'root' and 'nodes' keys.
            memory: persistent memory dict, loaded from mob_brain.memory.
        """
        self.tree = decision_tree
        self.memory = memory or {}
        self.root_id = decision_tree.get("root", "evaluate_state")
        self.nodes = decision_tree.get("nodes", {})

    def think(self, mob_state: dict) -> dict | None:
        """Traverse the decision tree and return an action command or None.

        Args:
            mob_state: dict with current mob info (hunger, fat, energy,
                       health, position, mob_type, vision, etc.)

        Returns:
            dict like {"action": "MOVE_MOB", "payload": {...}} or None
        """
        current_node_id = self.root_id
        matrix = []
        depth = 0

        while current_node_id and depth < MAX_TREE_DEPTH:
            depth += 1
            node = self.nodes.get(current_node_id)
            if not node:
                logging.warning(f"Brain: unknown node '{current_node_id}'")
                break

            func_id = node.get("function", current_node_id)
            func = get_function(func_id)
            if not func:
                logging.warning(f"Brain: no registered function '{func_id}'")
                break

            outputs = node.get("outputs", [])
            result = func(matrix, self.memory, outputs, mob_state)

            if result is None:
                break

            # If the function returned an action, we're done
            if "action" in result:
                return result

            # Otherwise follow the tree
            matrix = result.get("matrix", matrix)
            current_node_id = result.get("next")

        return None  # tree exhausted without producing an action

    def get_memory(self) -> dict:
        """Return memory for persistence."""
        return self.memory

    def set_memory(self, memory: dict):
        """Replace memory (e.g. after loading from DB)."""
        self.memory = memory


# Default decision trees for prey and predator
PREY_DECISION_TREE = {
    "root": "action_look_first",
    "nodes": {
        "action_look_first": {
            "function": "action_look",
            "outputs": []
        },
        "evaluate_state": {
            "function": "evaluate_state",
            "outputs": ["evaluate_hunger", "evaluate_danger_check"]
        },
        "evaluate_hunger": {
            "function": "evaluate_hunger",
            "outputs": ["action_eat", "evaluate_danger_check"]
        },
        "evaluate_danger_check": {
            "function": "evaluate_danger",
            "outputs": ["evaluate_flee", "evaluate_movement"]
        },
        "evaluate_flee": {
            "function": "evaluate_flee",
            "outputs": []
        },
        "evaluate_movement": {
            "function": "evaluate_movement",
            "outputs": []
        },
        "action_eat": {
            "function": "action_eat",
            "outputs": []
        },
    }
}

PREDATOR_DECISION_TREE = {
    "root": "action_look_first",
    "nodes": {
        "action_look_first": {
            "function": "action_look",
            "outputs": []
        },
        "evaluate_state": {
            "function": "evaluate_state",
            "outputs": ["evaluate_hunger_pred", "evaluate_hunt"]
        },
        "evaluate_hunger_pred": {
            "function": "evaluate_hunger",
            "outputs": ["evaluate_hunt", "evaluate_hunt"]
        },
        "evaluate_hunt": {
            "function": "evaluate_attack_target",
            "outputs": ["action_attack", "evaluate_movement"]
        },
        "evaluate_movement": {
            "function": "evaluate_movement",
            "outputs": []
        },
        "action_attack": {
            "function": "action_attack",
            "outputs": []
        },
    }
}
