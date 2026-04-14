# Server Schema Update Tasks

This document outlines the granular steps required to review, update, and validate the schemas related to the server components and the mob schema.

## Goals

- Ensure `MobSchema.md` is accurate.
- Ensure all server-specific schema definitions (e.g., in `server_doc/`) are consistent with the actual implementation in `server/`.

## Tasks

- [x] **Review `MobSchema.md`**:
  - Read the current `MobSchema.md` to understand the expected structure.
  - Compare it against the actual mob data structure used in `server/` and `client/`.
  - Create a list of required schema updates for `MobSchema.md`.
- [x] **Review Server Schemas**:
  - Examine all schema files within `server_doc/` (e.g., `server_phase1_s1.md` to `server_phase1_s5.md`).
  - For each server schema, compare its definition against the corresponding logic in `server/`.
  - Identify discrepancies and propose necessary schema modifications.
- [x] **Implement Schema Updates**:
  - Apply necessary changes to `MobSchema.md`.
  - Apply necessary changes to all identified server schema files in `server_doc/`.
- [x] **Validation**:
  - Run integration tests (e.g., `tests/test_server.py`) to ensure that the updated schemas do not break existing server logic.
  - Manually verify data flow between the updated schemas and the server code.
- [x] **Documentation Update**:
  - Update `server_tasks.md` to reflect the completed schema update phase.
  - Update relevant READMEs in `server_doc/` if schema changes impact external documentation.wd
