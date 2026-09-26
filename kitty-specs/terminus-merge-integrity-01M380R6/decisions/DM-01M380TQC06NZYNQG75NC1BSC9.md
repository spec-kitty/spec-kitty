# Decision Moment `01M380TQC06NZYNQG75NC1BSC9`

- **Mission:** `terminus-merge-integrity-01M380R6`
- **Origin flow:** `specify`
- **Slot key:** `specify.migration.retroactive_scope`
- **Input key:** `retroactive_scope`
- **Status:** `resolved`
- **Created:** `2026-09-23T20:55:31.968899+00:00`
- **Resolved:** `2026-09-23T20:57:22.850953+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should the fail-closed terminus guarantees apply to in-flight interrupted merges started before this fix (existing MergeState/coord branches), or only to terminus commands started after the fix?

## Options

- Forward-only + detect-and-refuse legacy
- Retroactive incl. in-flight recovery
- Other

## Final answer

Forward-only: new fail-closed guarantees apply to terminus commands started after the fix; pre-fix in-flight MergeState/coord state is detected and refused with a recovery instruction, never auto-healed.

## Rationale

_(none)_

## Change log

- `2026-09-23T20:55:31.968899+00:00` — opened
- `2026-09-23T20:57:22.850953+00:00` — resolved (final_answer="Forward-only: new fail-closed guarantees apply to terminus commands started after the fix; pre-fix in-flight MergeState/coord state is detected and refused with a recovery instruction, never auto-healed.")
