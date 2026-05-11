"""
Tests for mob-breeding-behavior spec.

Covers:
  5.1  Registration smoke tests
  5.2  Tree structure smoke tests
  5.3  Example: action_breed with empty memory returns MOVE_MOB (fallback)
  5.4  Example: find_partner with no LOOK data routes to second output
  5.5  End-to-end: MobBrain produces BREED_MOB
  5.6  PBT Property 1: find_partner selects closest valid partner
  5.7  PBT Property 2: find_partner routes to second output when no valid partner
  5.8  PBT Property 3: find_partner matrix pass-through
  5.9  PBT Property 4: action_breed emits BREED_MOB and clears target when in range
  5.10 PBT Property 5: action_breed emits MOVE_MOB when out of range
  5.11 PBT Property 6: evaluate_breed_energy routes high-energy adults to find_partner
  5.12 PBT Property 7: evaluate_breed_energy routes ineligible mobs to danger check

Run from the project root:
    python -m pytest tests/test_mob_breeding.py -v --tb=short
"""
import unittest

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from client.brain_registry import get_function, list_functions, ATTACK_RANGE
from client.mob_brain import PREY_DECISION_TREE, MobBrain

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _mob_state(
    mob_type="prey",
    life_stage="adult",
    energy=80.0,
    vision=10.0,
    position=None,
):
    return {
        "mob_type": mob_type,
        "life_stage": life_stage,
        "energy": energy,
        "vision": vision,
        "position": position or {"x": 0.0, "y": 0.0},
        "hunger": 0,
        "fat": 50,
        "health": 100,
    }


def _mob_entry(mob_id="mob_a", mob_type="prey", distance=2.0, alive=True):
    return {
        "mobId": mob_id,
        "mob_type": mob_type,
        "distance": distance,
        "alive": alive,
        "position": {"x": distance, "y": 0.0},
        "size": 1.0,
    }


# ---------------------------------------------------------------------------
# 5.1 — Registration smoke tests
# ---------------------------------------------------------------------------
class TestRegistrationSmoke(unittest.TestCase):
    """5.1 — New functions must be present in the registry."""

    def test_find_partner_registered(self):
        self.assertIn("find_partner", list_functions())

    def test_action_breed_registered(self):
        self.assertIn("action_breed", list_functions())

    def test_evaluate_breed_energy_registered(self):
        self.assertIn("evaluate_breed_energy", list_functions())


# ---------------------------------------------------------------------------
# 5.2 — Tree structure smoke tests
# ---------------------------------------------------------------------------
class TestTreeStructureSmoke(unittest.TestCase):
    """5.2 — PREY_DECISION_TREE must contain correct nodes."""

    def _node(self, name):
        return PREY_DECISION_TREE["nodes"][name]

    # New nodes
    def test_evaluate_breed_energy_node_exists(self):
        self.assertIn("evaluate_breed_energy", PREY_DECISION_TREE["nodes"])

    def test_evaluate_breed_energy_outputs(self):
        self.assertEqual(
            self._node("evaluate_breed_energy")["outputs"],
            ["find_partner", "evaluate_danger_check"],
        )

    def test_find_partner_node_exists(self):
        self.assertIn("find_partner", PREY_DECISION_TREE["nodes"])

    def test_find_partner_outputs(self):
        self.assertEqual(
            self._node("find_partner")["outputs"],
            ["action_breed", "evaluate_movement"],
        )

    def test_action_breed_node_exists(self):
        self.assertIn("action_breed", PREY_DECISION_TREE["nodes"])

    def test_action_breed_outputs_empty(self):
        self.assertEqual(self._node("action_breed")["outputs"], [])

    # Existing nodes unchanged
    def test_evaluate_danger_check_unchanged(self):
        node = self._node("evaluate_danger_check")
        self.assertEqual(node["function"], "evaluate_danger")
        self.assertEqual(node["outputs"], ["evaluate_flee", "evaluate_movement"])

    def test_evaluate_flee_unchanged(self):
        node = self._node("evaluate_flee")
        self.assertEqual(node["function"], "evaluate_flee")
        self.assertEqual(node["outputs"], [])

    def test_evaluate_movement_unchanged(self):
        node = self._node("evaluate_movement")
        self.assertEqual(node["function"], "evaluate_movement")
        self.assertEqual(node["outputs"], [])

    def test_action_eat_unchanged(self):
        node = self._node("action_eat")
        self.assertEqual(node["function"], "action_eat")
        self.assertEqual(node["outputs"], [])


# ---------------------------------------------------------------------------
# 5.3 — action_breed with empty memory returns MOVE_MOB (fallback)
# ---------------------------------------------------------------------------
class TestActionBreedFallback(unittest.TestCase):
    """5.3 — action_breed falls back to evaluate_movement when no breed_target."""

    def test_empty_memory_returns_move_mob(self):
        func = get_function("action_breed")
        memory = {}
        mob_state = _mob_state()
        result = func([], memory, ["evaluate_movement"], mob_state)
        self.assertEqual(result["action"], "MOVE_MOB")


# ---------------------------------------------------------------------------
# 5.4 — find_partner with no LOOK data routes to second output
# ---------------------------------------------------------------------------
class TestFindPartnerNoLookData(unittest.TestCase):
    """5.4 — find_partner routes to outputs[1] when memory has no LOOK data."""

    def test_empty_memory_routes_to_second_output(self):
        func = get_function("find_partner")
        memory = {}
        mob_state = _mob_state()
        result = func([], memory, ["out0", "out1"], mob_state)
        self.assertEqual(result["next"], "out1")
        self.assertNotIn("breed_target", memory)


# ---------------------------------------------------------------------------
# 5.5 — End-to-end: MobBrain produces BREED_MOB
# ---------------------------------------------------------------------------
class TestEndToEndBreedMob(unittest.TestCase):
    """5.5 — Full tree traversal produces BREED_MOB when conditions are met."""

    def test_brain_produces_breed_mob(self):
        brain = MobBrain(PREY_DECISION_TREE)

        # Inject LOOK result with a nearby same-type adult mob within ATTACK_RANGE
        partner = _mob_entry(mob_id="mob_partner", mob_type="prey", distance=2.0)
        brain.memory["last_look"] = {
            "tiles": [],
            "mobs": [partner],
        }

        mob_state = _mob_state(
            mob_type="prey",
            life_stage="adult",
            energy=80.0,
            vision=10.0,
        )

        result = brain.think(mob_state)

        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "BREED_MOB")
        self.assertEqual(result["payload"]["targetId"], "mob_partner")


# ---------------------------------------------------------------------------
# 5.6 — PBT Property 1: find_partner selects closest valid partner
# ---------------------------------------------------------------------------

@st.composite
def valid_mob_list(draw):
    """Generate ≥ 1 mobs: same type, alive, varying distances within vision."""
    n = draw(st.integers(min_value=1, max_value=10))
    mob_ids = draw(
        st.lists(
            st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    distances = draw(
        st.lists(
            st.floats(min_value=0.1, max_value=9.9, allow_nan=False, allow_infinity=False),
            min_size=n,
            max_size=n,
        )
    )
    mobs = [
        {
            "mobId": mob_ids[i],
            "mob_type": "prey",
            "distance": distances[i],
            "alive": True,
            "position": {"x": distances[i], "y": 0.0},
            "size": 1.0,
        }
        for i in range(n)
    ]
    return mobs


class TestPBTFindPartnerClosest(unittest.TestCase):
    """5.6 — PBT Property 1: find_partner selects closest valid partner.

    Validates: Requirements 1.2
    """

    @given(mobs=valid_mob_list())
    @settings(max_examples=100)
    def test_selects_closest_partner(self, mobs):
        func = get_function("find_partner")
        memory = {"last_look": {"mobs": mobs}}
        mob_state = _mob_state(mob_type="prey", life_stage="adult", vision=10.0)
        outputs = ["out0", "out1"]

        result = func([], memory, outputs, mob_state)

        expected_closest = min(mobs, key=lambda m: m["distance"])
        self.assertEqual(result["next"], "out0")
        self.assertIn("breed_target", memory)
        self.assertEqual(memory["breed_target"]["mobId"], expected_closest["mobId"])


# ---------------------------------------------------------------------------
# 5.7 — PBT Property 2: find_partner routes to second output when no valid partner
# ---------------------------------------------------------------------------

@st.composite
def no_valid_partner_scenario(draw):
    """Generate scenarios with no valid partners or non-adult caller."""
    scenario_type = draw(st.integers(min_value=0, max_value=3))

    if scenario_type == 0:
        # Empty mob list
        mobs = []
        life_stage = "adult"
    elif scenario_type == 1:
        # Wrong mob type
        n = draw(st.integers(min_value=1, max_value=5))
        mobs = [
            {
                "mobId": f"mob_{i}",
                "mob_type": "predator",  # wrong type
                "distance": draw(st.floats(min_value=0.1, max_value=9.9, allow_nan=False, allow_infinity=False)),
                "alive": True,
                "position": {"x": 1.0, "y": 0.0},
                "size": 1.0,
            }
            for i in range(n)
        ]
        life_stage = "adult"
    elif scenario_type == 2:
        # All dead
        n = draw(st.integers(min_value=1, max_value=5))
        mobs = [
            {
                "mobId": f"mob_{i}",
                "mob_type": "prey",
                "distance": draw(st.floats(min_value=0.1, max_value=9.9, allow_nan=False, allow_infinity=False)),
                "alive": False,  # dead
                "position": {"x": 1.0, "y": 0.0},
                "size": 1.0,
            }
            for i in range(n)
        ]
        life_stage = "adult"
    else:
        # Non-adult caller
        mobs = [
            {
                "mobId": "mob_valid",
                "mob_type": "prey",
                "distance": 2.0,
                "alive": True,
                "position": {"x": 2.0, "y": 0.0},
                "size": 1.0,
            }
        ]
        life_stage = draw(st.sampled_from(["infant", "juvenile", "elder", ""]))

    return mobs, life_stage


class TestPBTFindPartnerNoValidPartner(unittest.TestCase):
    """5.7 — PBT Property 2: find_partner routes to second output when no valid partner.

    Validates: Requirements 1.3, 1.5
    """

    @given(scenario=no_valid_partner_scenario())
    @settings(max_examples=100)
    def test_routes_to_second_output_no_valid_partner(self, scenario):
        mobs, life_stage = scenario
        func = get_function("find_partner")
        memory = {"last_look": {"mobs": mobs}}
        mob_state = _mob_state(mob_type="prey", life_stage=life_stage, vision=10.0)
        outputs = ["out0", "out1"]

        result = func([], memory, outputs, mob_state)

        self.assertEqual(result["next"], "out1")
        self.assertNotIn("breed_target", memory)


# ---------------------------------------------------------------------------
# 5.8 — PBT Property 3: find_partner matrix pass-through
# ---------------------------------------------------------------------------

class TestPBTFindPartnerMatrixPassthrough(unittest.TestCase):
    """5.8 — PBT Property 3: find_partner passes matrix through unchanged.

    Validates: Requirements 1.4
    """

    @given(matrix=st.lists(st.floats(allow_nan=False, allow_infinity=False), max_size=20))
    @settings(max_examples=100)
    def test_matrix_passthrough_no_partner(self, matrix):
        func = get_function("find_partner")
        memory = {}
        mob_state = _mob_state()
        result = func(matrix, memory, ["out0", "out1"], mob_state)
        self.assertEqual(result["matrix"], matrix)

    @given(matrix=st.lists(st.floats(allow_nan=False, allow_infinity=False), max_size=20))
    @settings(max_examples=100)
    def test_matrix_passthrough_with_partner(self, matrix):
        func = get_function("find_partner")
        memory = {"last_look": {"mobs": [_mob_entry()]}}
        mob_state = _mob_state()
        result = func(matrix, memory, ["out0", "out1"], mob_state)
        self.assertEqual(result["matrix"], matrix)


# ---------------------------------------------------------------------------
# 5.9 — PBT Property 4: action_breed emits BREED_MOB and clears target when in range
# ---------------------------------------------------------------------------

@st.composite
def breed_target_in_range(draw):
    """Generate a breed_target with distance in [0.0, ATTACK_RANGE]."""
    distance = draw(st.floats(min_value=0.0, max_value=ATTACK_RANGE, allow_nan=False, allow_infinity=False))
    mob_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")))
    return {
        "mobId": mob_id,
        "mob_type": "prey",
        "distance": distance,
        "alive": True,
        "position": {"x": distance, "y": 0.0},
        "size": 1.0,
    }


class TestPBTActionBreedInRange(unittest.TestCase):
    """5.9 — PBT Property 4: action_breed emits BREED_MOB and clears target when in range.

    Validates: Requirements 2.2, 2.5
    """

    @given(target=breed_target_in_range())
    @settings(max_examples=100)
    def test_breed_mob_emitted_and_target_cleared(self, target):
        func = get_function("action_breed")
        memory = {"breed_target": target}
        mob_state = _mob_state()

        result = func([], memory, [], mob_state)

        self.assertEqual(result["action"], "BREED_MOB")
        self.assertEqual(result["payload"]["targetId"], target["mobId"])
        self.assertNotIn("breed_target", memory)


# ---------------------------------------------------------------------------
# 5.10 — PBT Property 5: action_breed emits MOVE_MOB when out of range
# ---------------------------------------------------------------------------

@st.composite
def breed_target_out_of_range(draw):
    """Generate a breed_target with distance > ATTACK_RANGE."""
    distance = draw(st.floats(min_value=ATTACK_RANGE + 0.001, max_value=100.0, allow_nan=False, allow_infinity=False))
    mob_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")))
    position = {"x": distance, "y": 0.0}
    return {
        "mobId": mob_id,
        "mob_type": "prey",
        "distance": distance,
        "alive": True,
        "position": position,
        "size": 1.0,
    }


class TestPBTActionBreedOutOfRange(unittest.TestCase):
    """5.10 — PBT Property 5: action_breed emits MOVE_MOB toward partner when out of range.

    Validates: Requirements 2.3
    """

    @given(target=breed_target_out_of_range())
    @settings(max_examples=100)
    def test_move_mob_emitted_toward_partner(self, target):
        func = get_function("action_breed")
        memory = {"breed_target": target}
        mob_state = _mob_state()

        result = func([], memory, [], mob_state)

        self.assertEqual(result["action"], "MOVE_MOB")
        self.assertEqual(result["payload"]["targetLocation"], target["position"])


# ---------------------------------------------------------------------------
# 5.11 — PBT Property 6: evaluate_breed_energy routes high-energy adults to find_partner
# ---------------------------------------------------------------------------

class TestPBTEvaluateBreedEnergyHighEnergy(unittest.TestCase):
    """5.11 — PBT Property 6: evaluate_breed_energy routes eligible adults to find_partner.

    Validates: Requirements 3.2
    """

    @given(
        energy=st.floats(min_value=45.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        matrix=st.lists(st.floats(allow_nan=False, allow_infinity=False), max_size=10),
    )
    @settings(max_examples=100)
    def test_routes_to_first_output_high_energy_adult(self, energy, matrix):
        func = get_function("evaluate_breed_energy")
        memory = {}
        mob_state = _mob_state(life_stage="adult", energy=energy)
        mob_state["health"] = 100.0
        outputs = ["find_partner", "evaluate_danger_check"]

        result = func(matrix, memory, outputs, mob_state)

        self.assertEqual(result["next"], outputs[0])
        self.assertEqual(result["matrix"], matrix)


# ---------------------------------------------------------------------------
# 5.12 — PBT Property 7: evaluate_breed_energy routes ineligible mobs to danger check
# ---------------------------------------------------------------------------

@st.composite
def ineligible_mob_state(draw):
    """Generate mob_state where energy < 45 OR life_stage != 'adult' OR health < 80."""
    ineligible_type = draw(st.integers(min_value=0, max_value=2))
    
    if ineligible_type == 0:
        # No energy and no fat
        energy = draw(st.floats(min_value=-10.0, max_value=44.9, allow_nan=False, allow_infinity=False))
        fat = draw(st.floats(min_value=-10.0, max_value=0.0, allow_nan=False, allow_infinity=False))
        life_stage = "adult"
        health = 100.0
    elif ineligible_type == 1:
        # Non-adult
        energy = draw(st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False))
        fat = 10.0
        life_stage = draw(st.sampled_from(["infant", "juvenile", "elder", ""]))
        health = 100.0
    else:
        # Hurt
        energy = 50.0
        fat = 50.0
        life_stage = "adult"
        health = draw(st.floats(min_value=0.0, max_value=79.9, allow_nan=False, allow_infinity=False))
        
    return energy, fat, life_stage, health


class TestPBTEvaluateBreedEnergyIneligible(unittest.TestCase):
    """5.12 — PBT Property 7: evaluate_breed_energy routes ineligible mobs to danger check.

    Validates: Requirements 3.3
    """

    @given(
        state=ineligible_mob_state(),
        matrix=st.lists(st.floats(allow_nan=False, allow_infinity=False), max_size=10),
    )
    @settings(max_examples=100)
    def test_routes_to_second_output_ineligible(self, state, matrix):
        energy, fat, life_stage, health = state
        func = get_function("evaluate_breed_energy")
        memory = {}
        mob_state = _mob_state(life_stage=life_stage, energy=energy)
        mob_state["fat"] = fat
        mob_state["health"] = health
        outputs = ["find_partner", "evaluate_danger_check"]

        result = func(matrix, memory, outputs, mob_state)

        self.assertEqual(result["next"], outputs[1])
        self.assertEqual(result["matrix"], matrix)


if __name__ == "__main__":
    unittest.main()
