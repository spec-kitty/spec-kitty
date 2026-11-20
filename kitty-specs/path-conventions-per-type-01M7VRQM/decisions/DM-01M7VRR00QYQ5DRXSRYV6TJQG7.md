# Decision Moment `01M7VRR00QYQ5DRXSRYV6TJQG7`

- **Mission:** `path-conventions-per-type-01M7VRQM`
- **Origin flow:** `specify`
- **Slot key:** `specify.escape.mechanism`
- **Input key:** `escape_mechanism`
- **Status:** `resolved`
- **Created:** `2026-11-20T06:01:49.847947+00:00`
- **Resolved:** `2026-11-20T06:31:00.956245+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Narrow escape for path conventions (distinct from accept --lenient): per-run flag, per-Mission meta.json waiver, or both?

## Options

- A: accept --waive-path-conventions --waive-reason (per run, recorded in acceptance history)
- B: meta.json path_conventions waived + rationale (per Mission, like contracts: none)
- C: both
- Other

## Final answer

C: both - per-run accept --waive-path-conventions --waive-reason recorded on the acceptance history entry, and a durable per-Mission meta.json waiver (path_conventions: waived + required rationale, mirroring contracts: none). Both waive path conventions only; metadata and orchestrator-api stay strict.

## Rationale

_(none)_

## Change log

- `2026-11-20T06:01:49.847947+00:00` - opened
- `2026-11-20T06:31:00.956245+00:00` - resolved (final_answer="C: both - per-run accept --waive-path-conventions --waive-reason recorded on the acceptance history entry, and a durable per-Mission meta.json waiver (path_conventions: waived + required rationale, mirroring contracts: none). Both waive path conventions only; metadata and orchestrator-api stay strict.")
