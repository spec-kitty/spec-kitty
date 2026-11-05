# Data Model: retired merge-driver row

The mission changes strings in one tracked file and clone-local git config; there is no database
or serialized schema. The "model" is the set of `.gitattributes` rows and driver configs an
upgrade guarantees.

## Entity: merge-driver row

| Field | Meaning |
|---|---|
| `pattern` | The `kitty-specs/**` path glob the row maps (a `DriverSpec.pattern`). |
| `config_key` | The git merge-driver key the row names (`merge=<config_key>`). |
| `state` | `canonical` (declared by `_MERGE_DRIVERS` and seeded) or `retired` (declared by nothing, seeded by nothing, removed wherever found). |

Rows after an upgrade:

| pattern | config_key | state |
|---|---|---|
| `kitty-specs/**/acceptance-matrix.json` | `spec-kitty-acceptance-matrix` | canonical (filled-side merge) |
| `kitty-specs/**/issue-matrix.json` | `spec-kitty-issue-matrix` | canonical (row-aware merge) |
| `kitty-specs/**/issue-matrix.md` | `spec-kitty-issue-matrix` | **retired** |

## Entity: driver config (clone-local)

`git config --local merge.<config_key>.{name,driver}`. `clone_local_effect = True` means the
config half never travels with a clone, so every seeding migration is re-selected per clone and
must be idempotent.

| config_key | name | driver |
|---|---|---|
| `spec-kitty-acceptance-matrix` | Spec Kitty acceptance matrix filled-side merge | `spec-kitty merge-driver-acceptance-matrix %O %A %B` |
| `spec-kitty-issue-matrix` | Spec Kitty issue matrix row-aware merge | `spec-kitty merge-driver-issue-matrix %O %A %B` |

## Entity: migration state

| migration id | state |
|---|---|
| `3.2.6_gate_artifact_merge_drivers` | Recorded no-op (`SupersededMigration`); `superseded_by` names the successor. Never applies. |
| `3.2.6_issue_matrix_driver_repoint` | Unchanged; adds the `.json` row and its driver config. |
| `4.0.0rc8_retire_issue_matrix_md_row` | Successor: seeds the two canonical rows/configs and removes the retired row. `clone_local_effect = True`. |
