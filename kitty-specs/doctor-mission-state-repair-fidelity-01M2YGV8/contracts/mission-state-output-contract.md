# Contract — `doctor mission-state` output fidelity

<!-- round-trip: skip: illustrative CLI-output samples, not mission frontmatter -->

## `--fix` terminal output

For any run, in addition to the existing summary line, the terminal MUST name each non-successful mission and its reason.

```
Mission-state repair complete (updated=101, unchanged=2, errors=21).
Errored missions:
  - audit-interpretation-moment0-01KSBGBS: Invalid canonical meta.json: <reason>
  - <slug>: <reason>
  ...
Manifest: .kittify/migrations/mission-state/<run_id>.json   (sidecar)
```

After this mission's normalization change, a legacy `change_mode` no longer appears as an errored mission — it is counted as `updated` with a recorded `normalized_change_mode` action, e.g.:

```
Mission-state repair complete (updated=122, unchanged=2, errors=0).
Normalized missions:
  - <slug>: normalized_change_mode:regular
```

## `--fix --json`

`report.to_json()` MUST include a per-mission record for every mission (already does); this contract pins that errored/normalized missions carry `mission_slug`, `status`, `meta_actions`, and `validation_errors` (the healing actions applied, e.g. `normalized_change_mode:regular`, are on `meta_actions`).

## `--teamspace-dry-run` terminal output

MUST name each affected mission + reason, not only a count:

```
TeamSpace dry-run: 20 validation issues.
  - <slug> (<artifact_path>:<line>): <error_code> — <message>
  ...
```

## `--teamspace-dry-run --json`

MUST emit a structured `errors[]` list (mission_slug, artifact_path, line_number, error, message) — shape-equivalent to the repair report's error records (parity).

## Invariants

- **OUT-1 (single-invocation triage)**: 100% of failing/affected missions and their reasons are obtainable from one command invocation's terminal or `--json` output, with no git-ignored file read (NFR-003).
- **OUT-2 (no behavior loss)**: the summary counts and manifest sidecar remain; this contract only *adds* per-mission detail.
- **OUT-3 (dry-run parity)**: dry-run and fix expose per-mission error records of equivalent shape.
