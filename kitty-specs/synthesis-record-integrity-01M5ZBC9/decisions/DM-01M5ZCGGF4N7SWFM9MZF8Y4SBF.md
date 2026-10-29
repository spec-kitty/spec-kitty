# Decision Moment `01M5ZCGGF4N7SWFM9MZF8Y4SBF`

- **Mission:** `synthesis-record-integrity-01M5ZBC9`
- **Origin flow:** `plan`
- **Slot key:** `plan.locking.other-manifest-writers`
- **Input key:** `other_manifest_writers`
- **Status:** `resolved`
- **Created:** `2026-10-27T19:13:35.716774+00:00`
- **Resolved:** `2026-10-27T19:13:39.353570+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How far should the lock reach beyond synthesize/resynthesize (restamp_bundle_hash, activation-ledger migration, activate/deactivate)?

## Options

- Also lock restamp; file rest
- Synthesis only; file all
- Lock every writer
- Other

## Final answer

Also lock restamp_bundle_hash; file the activation-ledger migration and activate/deactivate config race as a follow-up under #6518

## Rationale

_(none)_

## Change log

- `2026-10-27T19:13:35.716774+00:00` — opened
- `2026-10-27T19:13:39.353570+00:00` — resolved (final_answer="Also lock restamp_bundle_hash; file the activation-ledger migration and activate/deactivate config race as a follow-up under #6518")
