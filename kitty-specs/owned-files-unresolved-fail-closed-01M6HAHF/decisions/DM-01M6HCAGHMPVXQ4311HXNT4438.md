# Decision Moment `01M6HCAGHMPVXQ4311HXNT4438`

- **Mission:** `owned-files-unresolved-fail-closed-01M6HAHF`
- **Origin flow:** `plan`
- **Slot key:** `plan.contract.version-bump`
- **Input key:** `contract_version_bump`
- **Status:** `resolved`
- **Created:** `2026-11-03T18:56:38.964076+00:00`
- **Resolved:** `2026-11-03T18:56:40.189342+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Does adding OWNERSHIP_UNRESOLVED bump the orchestrator-api CONTRACT_VERSION?

## Options

_(none)_

## Final answer

Yes: 1.22.0 -> 1.23.0 with a changelog comment in envelope.py, following the 1.21.0 precedent that bumped when evidence codes were added (post-tasks squad finding). WP01 owns the envelope bump; docs/api/orchestrator-api.md (version line and changelog entry) is updated at closeout.

## Rationale

_(none)_

## Change log

- `2026-11-03T18:56:38.964076+00:00` - opened
- `2026-11-03T18:56:40.189342+00:00` - resolved (final_answer="Yes: 1.22.0 -> 1.23.0 with a changelog comment in envelope.py, following the 1.21.0 precedent that bumped when evidence codes were added (post-tasks squad finding). WP01 owns the envelope bump; docs/api/orchestrator-api.md (version line and changelog entry) is updated at closeout.")
