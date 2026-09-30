---
title: Contract pinning workflow (`spec-kitty-events`)
description: 'The contract-pinning workflow for spec-kitty-events: how tests/contract pin a resolved package version, why it exists, and the ADR and mission authority behind it.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
---
# Contract pinning workflow (`spec-kitty-events`)

> **Status**: stable (2026-04-26)
>
> **Authority**:
> - [`docs/adr/3.x/2026-04-26-1-contract-pinning-resolved-version.md`](../../adr/3.x/2026-04-26-1-contract-pinning-resolved-version.md)
>   (DIRECTIVE_003)
> - Mission `stability-and-hygiene-hardening-2026-04-01KQ4ARB`,
>   FR-022 / FR-023.
> - Contract surface:
>   [`kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/contracts/events-envelope.md`](../../../kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/contracts/events-envelope.md)

## Why this exists

Contract tests under `tests/contract/` are the hard mission-review
gate (FR-023). They pin the upstream `spec-kitty-events` envelope at
the *resolved* version (`uv.lock`), not at a literal hard-coded one.
Bumping `spec-kitty-events` without regenerating the snapshot is, by
design, a hard contract failure with a clear diagnostic.

## The two-step bump workflow

When you need to bump `spec-kitty-events`:

1. **Update the dependency.**

   Either edit the compatibility range in `pyproject.toml`:

   ```toml
   [project]
   dependencies = [
       # ...
       "spec-kitty-events>=X.Y.0,<X+1",  # today: >=10.4.0,<11
       # ...
   ]
   ```

   …or just let `uv` pick a newer compatible version:

   ```bash
   uv lock --upgrade-package spec-kitty-events
   uv sync
   ```

2. **Regenerate the envelope snapshot.**

   ```bash
   python scripts/snapshot_events_envelope.py --force
   ```

   The script:

   - Resolves the version from `uv.lock` (falling back to
     `importlib.metadata`).
   - Captures `spec_kitty_events.Event.model_json_schema()`.
   - Writes
     `tests/contract/snapshots/spec-kitty-events-<resolved-version>.json`.
   - Prints the resolved version it pinned, so you can sanity-check
     against `uv.lock`.

3. **Verify the contract gate is green.**

   ```bash
   pytest tests/contract/ -q
   ```

   This is the same one-liner the mission-review skill runs.

4. **Commit both files together.**

   ```bash
   spec-kitty safe-commit --message "chore: bump spec-kitty-events to <version>" \
     pyproject.toml \
     uv.lock \
     tests/contract/snapshots/spec-kitty-events-*.json
   ```

If you skip step 2, the contract test
`tests/contract/test_events_envelope_matches_resolved_version.py` will
fail with a structured message pointing at this doc and the snapshot
script. That is intentional.

## What the snapshot script does and does not do

The script (`scripts/snapshot_events_envelope.py`) is intentionally
small. It:

- **Does** resolve the version from `uv.lock` first, then
  `importlib.metadata`.
- **Does** capture the full `Event` JSON schema, plus a sorted list of
  field names and required-field names for ergonomic diffs.
- **Does** print the resolved version it used.
- **Does not** overwrite an existing snapshot unless `--force` is
  passed.
- **Does not** install `spec-kitty-events`. Run `uv sync` first.

Useful flags:

| Flag | Purpose |
|------|---------|
| `--output-dir DIR` | Write the snapshot to a different directory (used by tests). |
| `--repo-root DIR` | Override repo root (used to point at a different `uv.lock`). |
| `--force` | Overwrite an existing snapshot for the current version. |
| `--print-version` | Print only the resolved version and exit (useful in CI scripts). |

## What happens when you forget step 2

`pytest tests/contract/` will fail with one of:

- `Missing envelope snapshot for spec-kitty-events <version>` — you
  resolved a new version but did not regenerate the snapshot. Run the
  script with `--force` and re-run the contract suite.
- `Envelope field drift detected` / `required-field drift` — the live
  envelope schema does not match the snapshot. Either the upstream
  package made a real shape change (in which case investigate), or the
  snapshot file is from a different version (regenerate).
- `spec_kitty_events.__version__ = '...' but uv.lock pins '...'` —
  installed version disagrees with `uv.lock`. Run `uv sync`.

Each diagnostic includes a pointer back to this doc.

## Snapshot lifetime

Snapshot files are version-controlled and intentionally accumulate
one-per-bump. They are small (a few KB) and serve as historical
anchors for upstream-shape regression reviews. Do not delete old
snapshots when bumping; just add the new one.

## Related

- Mission spec: [`kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/spec.md`](../../../kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/spec.md)
- Mission review gate (FR-023): `tests/integration/test_mission_review_contract_gate.py`
- Public-import freeze (FR-024): `tests/architectural/test_events_tracker_public_imports.py`
- Companion ADR (boundary cutover): [`docs/adr/3.x/2026-04-25-1-shared-package-boundary.md`](../../adr/3.x/2026-04-25-1-shared-package-boundary.md)
