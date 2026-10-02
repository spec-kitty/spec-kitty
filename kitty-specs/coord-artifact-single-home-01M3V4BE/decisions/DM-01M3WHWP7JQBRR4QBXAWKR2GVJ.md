# Decision Moment `01M3WHWP7JQBRR4QBXAWKR2GVJ`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.ledger-topology-less-verdict`
- **Input key:** `ledger_topology_less_verdict`
- **Status:** `resolved`
- **Created:** `2026-10-01T20:18:30.770077+00:00`
- **Resolved:** `2026-10-01T20:18:32.263668+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

After DECISION_LEDGER moves to PRIMARY, how do the six topology-less callers classify uncommitted decisions/* on lanes and single_branch Missions? (Round-4 ruling asked for both byte-identical base verdicts and no compatibility set — contradictory.)

## Options

_(none)_

## Final answer

Real work everywhere: an uncommitted decisions/* ledger file is real work, never residue, under every topology (coord, lanes_with_coord, lanes, single_branch) at every caller. Accepted C-008 exception; no compatibility set; no coherence.py logic change. Matches topology-aware callers' base verdict for lanes; topology-less callers now block on such dirt instead of discarding it (the safe direction). WP22 records it in the ADR.

## Rationale

_(none)_

## Change log

- `2026-10-01T20:18:30.770077+00:00` — opened
- `2026-10-01T20:18:32.263668+00:00` — resolved (final_answer="Real work everywhere: an uncommitted decisions/* ledger file is real work, never residue, under every topology (coord, lanes_with_coord, lanes, single_branch) at every caller. Accepted C-008 exception; no compatibility set; no coherence.py logic change. Matches topology-aware callers' base verdict for lanes; topology-less callers now block on such dirt instead of discarding it (the safe direction). WP22 records it in the ADR.")
