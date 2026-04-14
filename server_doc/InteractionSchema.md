# Interaction/History Schema

This document defines the structure for the table/data model that will track interactions between mobs, including breeding events, attacks, and consumption events.

## Table: InteractionHistory

| Field Name | Data Type | Description | Constraints |
| :--- | :--- | :--- | :--- |
| `interaction_id` | UUID | Unique identifier for the interaction. | Primary Key |
| `mob_a_id` | UUID | ID of the first mob involved in the interaction. | Foreign Key to MobGene |
| `mob_b_id` | UUID | ID of the second mob involved in the interaction (can be NULL for single-mob events). | Foreign Key to MobGene |
| `interaction_type` | String (Enum) | Type of interaction (e.g., 'BREEDING', 'ATTACK', 'CONSUMPTION'). | Not Null |
| `timestamp` | DateTime | The time the interaction occurred. | Not Null |
| `details` | JSONB | Detailed information about the interaction (e.g., attack damage, consumption amount, breeding success stats). | Nullable |
| `outcome` | String | Result of the interaction (e.g., 'SUCCESS', 'FAILURE', 'PARTIAL'). | Not Null |