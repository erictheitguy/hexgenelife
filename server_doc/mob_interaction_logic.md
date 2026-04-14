# Mob Interaction Logic

This document details the specific rules and calculations for mob interactions as required for Phase 1. This logic should be implemented within `server.py` and referenced by `server_implementation.md`.

## 1. Breeding Logic

**Trigger Condition:** A mob attempts to breed once it reaches a specified age threshold.
**Process:**
1.  The mob scans the current world state for other mobs of the same type.
2.  It evaluates potential mates based on the mate's `fitness` attribute (highest fitness wins).
3.  **Success Condition:** Breeding is successful if the fitness of the potential mate meets a minimum threshold.
4.  **Result:** If successful, a new mob instance is created, and an entry is logged in the `InteractionHistory` table with `interaction_type='BREEDING'` and the result as 'SUCCESS'.

## 2. Attack Logic

**Trigger Condition:** A mob initiates an attack on another mob.
**Process:**
1.  The attack calculation uses the attacking mob's stats (`speed`, `mass`, `energy`, `vision`) against the target mob's stats.
2.  **Success Condition:** An attack is considered successful if the calculated attack value (derived from the mob stats) exceeds the target mob's defense/resistance.
3.  **Result:** If successful, the target mob's health is reduced according to the calculated damage, and an entry is logged in the `InteractionHistory` table with `interaction_type='ATTACK'` and the result as 'SUCCESS'. If unsuccessful, no health change occurs, and an entry is logged with `outcome='FAILURE'`.

## 3. Consumption Logic

**Trigger Condition:** A mob attempts to consume another mob or resource.
**Process:**
1.  The consumption amount is determined by the consumer mob's metabolism, speed, mass, and current movement state.
2.  **Result:** The target mob's health or hunger/fat stats are adjusted based on the calculated consumption amount. An entry is logged in the `InteractionHistory` table with `interaction_type='CONSUMPTION'` and the result as 'SUCCESS' or 'PARTIAL'.

## 4. Error Response Format

**Format:** All errors returned to the client via the WebSocket must be in a standardized JSON format.

**Structure:**
```json
{
  "status": "ERROR",
  "code": "ERROR_CODE_STRING", // e.g., "INVALID_COMMAND", "DB_ERROR"
  "message": "Human-readable error description.",
  "details": {
    "field": "Optional field that caused the error",
    "reason": "Specific reason for the failure"
  }
}
```