# Contract: topology re-stamp migration and doctor finding

## Migration `m_4_0_0rc5_single_branch_code_lanes_restamp`

| Property | Value |
|---|---|
| `MIGRATION_ID` | `4_0_0rc5_single_branch_code_lanes_restamp` |
| `TARGET_VERSION` | `4.0.0rc5` |
| `runs_on_worktrees` | `False` |

Behaviour:

- **Selection.** Walks the `kitty-specs/*/` directories on the checked-out branch. A mission is selected when `read_topology(meta) == single_branch` and `has_code_lanes(lanes.json)`.
- **Write.** For each selected mission it writes `topology: lanes` through the canonical meta writer, and changes no other field.
- **No commit.** The migration does not commit. The upgrade auto-commit owns that.
- **Idempotent.** A second run changes nothing (NFR-003).
- **Operator CLI.** `spec-kitty migrate backfill-topology --restamp-single-branch [--dry-run]` calls the same `restamp_single_branch_with_code_lanes()`.

## Doctor

`spec-kitty doctor topology` adds per-mission `finding` rows:

| Finding | Carries |
|---|---|
| `SINGLE_BRANCH_CODE_LANES_UNMIGRATED` | the mission slug and the remedy |
| (none) | clean `single_branch` missions produce no row |
