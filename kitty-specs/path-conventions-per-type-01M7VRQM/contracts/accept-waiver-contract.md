# Contract: path-convention waivers

## Per run (CLI)

`spec-kitty accept --waive-path-conventions --waive-reason "<why>"` and `spec-kitty agent mission accept` (forwarded)

- `--waive-path-conventions` without a non-blank `--waive-reason` → a usage error (exit 2), nothing written.
- `--waive-reason` without `--waive-path-conventions` → a usage error (exit 2).
- Effect: path-convention misses are reported as a warning; all other checks keep their strictness.
- Recorded: the acceptance history entry gains `"path_conventions_waived": {"reason": "<why>"}`.
- Not available on `orchestrator-api` (it stays strict).

## Per Mission (meta.json)

```json
{ "path_conventions": "waived", "path_conventions_rationale": "Content repository; no src/ layout." }
```

- Exact value `"waived"` and a non-blank string rationale. Anything else waives nothing, and the blocking text carries a warning naming the problem.
- Honoured on every accept path, orchestrator-api included (operator ruling Q4), like `contracts: none`.
- Effect: as for the per-run flag. The rationale is surfaced in the accept warning: `path conventions waived by meta.json (path_conventions: waived): <rationale>`.
