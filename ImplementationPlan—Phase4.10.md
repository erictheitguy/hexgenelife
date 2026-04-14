# Implementation Plan — Phase 4.10: Species & Taxonomy

This phase introduces biological classification to the HexGenLife world. Mobs will no longer just be "prey" or "predator", but members of distinct species with unique names and tracked lineages.

## User Review Required

> [!IMPORTANT]
> **Species Definition**: Species are defined by a vector of physical traits. A "new" species is declared when an offspring's traits deviate significantly (Z-score > 3.0) from its parent species' mean.
> **Unique Founders**: Initial mobs (generation 1) will be assigned unique "Founder" species names from the start.
> **Naming**: Names will be strictly procedurally generated from Latin roots. No user manual renaming will be supported.

## Proposed Changes

### [Component] Server — Database Schema

#### [MODIFY] [server.py](file:///C:/Users/eric/hexgenlife/server/server.py)
Update `_initialize_db` to include new tables and columns.

- [NEW] `species` table:
  - `species_id` (TEXT PRIMARY KEY)
  - `name` (TEXT)
  - `mean_traits` (TEXT JSON) — stores the average stats for this species.
  - `member_count` (INTEGER)
- [NEW] `family_tree` table:
  - `mob_id` (TEXT PRIMARY KEY)
  - `parent_a_id` (TEXT)
  - `parent_b_id` (TEXT)
  - `species_id` (TEXT)
  - `timestamp` (REAL)
- [MODIFY] `mobs` table: Add `species_id` column.

### [Component] Server — Taxonomy Logic

#### [MODIFY] [server.py](file:///C:/Users/eric/hexgenlife/server/server.py)
Implement the core taxonomy system.

- **`_generate_latin_name(is_founder=False)`**: A helper to create names like "Velocisaurus" or "Herbivorus". If `is_founder=True`, it generates a more ornate, unique name.
- **`_get_species_prototype(species_id)`**: Fetches the mean trait vector for a species.
- **`_classify_mob(mob_id, parent_species_id=None)`**:
  - Calculates the Z-score of the mob's traits against the parent species.
  - Using `SPECIES_THRESHOLD = 3.0`.
  - If deviation > threshold, create a new species entry.
  - Update `mobs.species_id` and the species mean traits (running average).
- **Update `_ensure_client_mob`**: Assign a unique "Founder" species to generation-1 mobs using `_generate_latin_name(is_founder=True)`.
- **Update `_handle_breed`**: 
  - Record the parents in `family_tree`.
  - Trigger `_classify_mob(child_id, parent_species_id)` for the offspring.

### [Component] Server — Message Payloads

#### [MODIFY] [server.py](file:///C:/Users/eric/hexgenlife/server/server.py)
- Include `species_name` and `species_id` in `MOB_UPDATE` and `WORLD_UPDATE` payloads.

### [Component] Viewer — UI Updates

#### [MODIFY] [viewer/db_reader.py](file:///C:/Users/eric/hexgenlife/viewer/db_reader.py)
- Update queries to join with `species` table to fetch names.

## Open Questions

- None. User feedback integrated.

## Verification Plan

### Automated Tests
- `tests/test_taxonomy.py`:
  - `test_latin_naming`: Verify names are generated and unique-ish.
  - `test_species_classification`: Force high mutation and verify a new species is created.
  - `test_family_tree_recording`: Verify parent/child relationship is saved in DB.

### Manual Verification
- Run the viewer and check if the HUD (once implemented/updated) shows species names.
- Inspect the SQLite database after a few generations of breeding to see the `species` and `family_tree` entries.
