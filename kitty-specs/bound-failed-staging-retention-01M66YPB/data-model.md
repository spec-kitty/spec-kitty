# Failed-staging retention model

Audience: software-engineer. Updated: 2026-10-30.

This mission changes how long a refused synthesis run's evidence survives, not
what synthesis produces and not any stored schema. Authority:
`src/charter/activation/synthesizer/staging.py` (`StagingDir`), the atomicity
ADR `docs/adr/3.x/2026-04-17-2-charter-synthesizer-atomicity.md`, and
[spec.md](spec.md).

## Entities

### Failed staging directory

- **Path**: `.kittify/charter/.staging/<run_id>.failed/`
- **Created by**: `StagingDir.commit_to_failed` (renames `.staging/<run_id>/` to
  the `.failed` name; also called from `StagingDir.__exit__` on an unhandled
  exception)
- **Contents**: the staged content subtree the refused run wrote
  (`charter-packs/{directive,tactic,styleguide}/`, `charter/provenance/`) plus
  `cause.yaml`
- **`cause.yaml` fields**: `reason`, `traceback`, `timestamp` — the diagnostic
  contract; unchanged by this mission
- **Retention**: preserved as evidence, bounded by count (below)

### In-progress staging directory

- **Path**: `.kittify/charter/.staging/<run_id>/`
- **Meaning**: the live workspace of a running synthesis (this process or
  another). Never a retention candidate.

### Retention bound

- **Value**: 3 (`DEFAULT_KEEP_FAILED_RUNS` in the staging lifecycle module)
- **Meaning**: after a failure is preserved, at most 3 `.failed` directories
  remain under `.staging/`.
- **Single source**: the constant feeds the retention pass and the operator text
  (FR-008).

## Ordering

Candidates are ordered newest-first by directory modification time, with the
directory name as a descending tiebreak so equal mtimes resolve deterministically
(ULID run ids sort lexicographically by creation time, so the tiebreak agrees
with the intent).

## Invariants

1. The directory the current command just preserved is never removed, whatever
   the ordering says (`preserve` is passed explicitly).
2. Only entries whose name ends in `.failed` are candidates: an in-progress
   `<run_id>/` directory, or any other entry under `.staging/`, is never removed.
3. A tree that already holds more than the bound is reduced to the bound
   (surplus removal, not merely growth prevention).
4. Removal is through `PathGuard.rmtree`; no unguarded deletion primitive and no
   new allowed-write prefix.
5. Retention never raises: listing/removal errors are suppressed so the
   original synthesis failure is what the command reports.
6. `cause.yaml` is never rewritten, and the surviving newest failure is readable
   when the command exits.

## Drift classification

Review against [reasons-canvas.md](reasons-canvas.md): approved scope,
documented local deviation, stale canvas, or blocking scope/safeguard violation.
A retention-only edit inside `staging.py` plus its tests and the stated text is
approved scope. Touching `write_pipeline.py`'s validation logic, the
`cause.yaml` schema, `PathGuard`'s allowlist, or the #6510 collision remedy is
scope drift.
