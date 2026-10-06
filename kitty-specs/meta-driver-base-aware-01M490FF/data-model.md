# Data model: merge sides and the per-key rule

## Entities

- **Mission record (`meta.json`)** — a flat JSON object; relevant fields: lifecycle markers (`discarded_at`, `flattened`, `topology`, `coordination_branch`), target-minted provenance (`accepted_at`, `accepted_by`, `accepted_from_commit`, `acceptance_mode`, `accept_commit`, `vcs`, `vcs_locked_at`, `mission_number`, `status`, `baseline_merge_commit`, `merged_at`, `merged_by`, `merged_into`, `merged_strategy`, `merged_push`, `merged_commit`), append-only `acceptance_history`, planning keys (everything else).
- **Merge sides** — `base` (git `%O`), `ours` (git `%A`: the local branch in a pull; the upstream in a rebase; the target checkout in a consolidation squash), `theirs` (git `%B`).
- **Merge unit** — either a single key or a coupled key group; a unit's value is the tuple of its members' values, where an absent member is the `MISSING` sentinel.

## Invariants

1. Output serialisation is the canonical writer's (`indent=2`, `ensure_ascii=False`, `sort_keys=True`, trailing newline).
2. The output contains a key exactly when the winning side contains it; `null` is a value, `MISSING` is absence.
3. `acceptance_history` in the output is the deduplicated, time-ordered union of both sides (never the ancestor's).
4. An unassigned `mission_number` never replaces an assigned one.
5. With an empty ancestor (absent file, whitespace-only file, or `{}`), the output equals today's two-way result byte-for-byte.
6. With the squash opt-out set (environment variable `SPEC_KITTY_META_MERGE_TWO_WAY=1`, exported as the constant `META_DRIVER_TWO_WAY_ENV` in `drivers.py`; set only by the consolidation squash subprocesses), the output equals today's two-way result regardless of the ancestor.

## Per-unit rule (ordinary merge with a non-empty ancestor)

| ours vs base | theirs vs base | result |
|---|---|---|
| ours == theirs | — | that value (present/absent as on both sides) |
| unchanged | changed/deleted | theirs' value (or absence) |
| changed/deleted | unchanged | ours' value (or absence) |
| changed | changed, different | precedence winner: `ours` when the unit is target-authoritative (any member in `_TARGET_AUTHORITATIVE_META_FIELDS`; the `merged_*` and acceptance-stamp groups), else `theirs` |
| deleted | changed | genuine conflict → precedence winner (absence if the winner deleted it) |

After the rule: apply invariant 4 to `mission_number`; apply invariant 3 to `acceptance_history`.

## State transitions touched

- `mission close --discard` → flatten triple deleted/set + `discarded_at` added on one side; a later ordinary merge must keep that state (FR-001).
- `mission reopen` → `merged_*` deleted; a merge against a side that re-recorded `merged_*` is a group conflict resolved by precedence, never a half block (FR-010).
