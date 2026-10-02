# Decision Moment `01M3XE5CJBGC8C0X564QMAAG03`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.undeclared-coord-branch`
- **Input key:** `undeclared_coord_branch`
- **Status:** `resolved`
- **Created:** `2026-10-02T04:32:35.915306+00:00`
- **Resolved:** `2026-10-02T04:32:37.381364+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

A coordination-routed Mission (coord / lanes_with_coord) whose meta.json declares no coordination_branch (even after the repository-root fallback): what does the write-location accessor do? (The O8 owned lanes_with_coord shape mints its branch under the deterministic name without recording it.)

## Options

_(none)_

## Final answer

Derive the canonical coordination branch name via lanes.branch_naming (the single naming authority; meta.json is a record, not the authority). If that branch exists locally, use it (materialize/seed as usual); if it does not exist, REFUSE with a typed error and recovery hint. Never degrade to PRIMARY for a coordination-routed topology. Topology-less legacy meta stays PRIMARY. Supersedes the 'refuse' half of the WP09 B1 ruling (a blanket refusal would break the supported O8 owned flow).

## Rationale

_(none)_

## Change log

- `2026-10-02T04:32:35.915306+00:00` — opened
- `2026-10-02T04:32:37.381364+00:00` — resolved (final_answer="Derive the canonical coordination branch name via lanes.branch_naming (the single naming authority; meta.json is a record, not the authority). If that branch exists locally, use it (materialize/seed as usual); if it does not exist, REFUSE with a typed error and recovery hint. Never degrade to PRIMARY for a coordination-routed topology. Topology-less legacy meta stays PRIMARY. Supersedes the 'refuse' half of the WP09 B1 ruling (a blanket refusal would break the supported O8 owned flow).")
