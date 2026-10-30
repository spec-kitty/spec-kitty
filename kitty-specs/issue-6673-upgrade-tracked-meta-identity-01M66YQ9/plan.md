# Implementation Plan: Upgrade never re-mints a Mission identity that git already holds

**Branch**: `issue-6673-upgrade-tracked-meta-identity` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/issue-6673-upgrade-tracked-meta-identity-01M66YQ9/spec.md`

## Summary

`spec-kitty upgrade` reads a Mission's `meta.json` from the working tree only. When that file is
tracked by git but absent on disk, the `2.0.6` consistency sweep writes a baseline `meta.json`
rebuilt from the directory name (no `mission_id`), and the `3.2.0a4` lifecycle normalization then
calls `backfill_mission`, which mints a **fresh random ULID** into it. The Mission silently gains a
second identity.

The fix adds one read-only owner, `mission_metadata.read_tracked_meta(feature_dir)`, that answers
"what does git hold for this Mission's `meta.json`" from the content `git checkout -- <path>` would
restore (`HEAD`'s blob, with the index as the "tracked but not committed" signal). The seams that can
write a `meta.json` for such a Mission consult it:

- `upgrade/feature_meta.py::build_baseline_feature_meta` seeds `existing_meta` from the tracked copy
  instead of from an empty dict when the working-tree copy is absent, and gives a present copy its
  tracked `mission_id` back when the copy has lost it, so the sweep rebuilds the tracked metadata
  rather than a nameless baseline.
- `upgrade/migrations/m_2_0_6_residue_safe_consistency_sweep.py` reports the restore (or the refusal)
  per Mission and skips a Mission whose tracked copy cannot be read.
- `migration/normalize_mission_lifecycle.py::normalize_repo` refuses a Mission whose tracked
  `meta.json` exists but cannot be read (no write, actionable notice) and reports when a tracked copy
  was missing and is being rebuilt.
- `upgrade/migrations/m_zz_runtime_state_backfill.py` skips a Mission whose tracked `meta.json` is
  absent from the working tree, so the cutover's phase flip cannot create a one-key stub `meta.json`
  that git never had (proven on `main`: `_flip_phase` writes `{"status_phase": "1"}` for a missing
  file).
- `migration/backfill_identity.py::backfill_mission` returns a "skip + restore command" result instead
  of minting when the `meta.json` it is asked to repair is tracked but absent on disk (defence in
  depth for every other entry point, `migrate backfill-identity` included).

The shipped `2.0.6` migration module stays byte-frozen; the fix is in live shared helpers plus the
residue-safe successor's apply loop (which already owns the per-folder walk and its notices).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Typer CLI, `kernel.git` (`blob_at`, `is_tracked`, `run_git`), `kernel.meta_decode`
**Storage**: `kitty-specs/<slug>/meta.json` (JSON, canonical writer `mission_metadata.write_meta`)
**Testing**: pytest; the reproduction is an integration test that runs the real `upgrade --yes` CLI
in-process over a scratch git repository (`tests/integration/migration/`), plus focused unit tests
**Target Platform**: developer workstations / CI (Linux, macOS)
**Project Type**: single Python package (`src/specify_cli`)
**Performance Goals**: at most one extra git read per Mission whose `meta.json` is absent from disk; none otherwise
**Constraints**: shipped migration bytes frozen where they are shipped (C-001 — `2.0.6_consistency_sweep` is
frozen; the residue-safe successor and `m_zz_runtime_state_backfill` are live code); `meta.json` single-writer
preserved (C-002); `kernel.git` stays the only reader of git paths (C-003); affected paths are probed before any
write (C-005).
**Scale/Scope**: ~5 source modules, 1 new public reader, 1 new notice module, 3 test files, changelog + docs

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict |
|------|---------|
| Single canonical authority (DIRECTIVE_044) | PASS — one new reader in `mission_metadata` (the `meta.json` owner) with a docstring saying it is the only answer to "what does git hold for this file"; the seams call it instead of re-deriving. |
| Architectural alignment (DIRECTIVE_001) | PASS — no new module boundary; the reader sits with the other `meta.json` reads, git access goes through `kernel.git`. |
| ATDD-first / red-first (DIRECTIVE_034) | PASS — the reproduction test fails on `main` before the fix and is the acceptance test for FR-001/FR-002. |
| Terms and terminology | PASS — "Mission", "identity (`mission_id`)", "residue" used in their canonical senses; the tracked copy is named "tracked `meta.json`". |
| Smallest viable diff (tactic) vs Boy Scout (DIRECTIVE_025) | PASS — the diff touches only the seams that can mint; no unrelated cleanup, no frozen migration edited. |
| Frozen migration discipline | PASS — `m_2_0_6_consistency_sweep.py` is untouched (it is in `SUPERSEDED_MIGRATIONS` anyway); the successor, `normalize_mission_lifecycle` and `m_zz_runtime_state_backfill` are live code and may change. |
| Standing Order #4 (test remediation, not "looks fixed") | PASS — live evidence on a scratch repo, comparing the id against `git show HEAD:...`. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/issue-6673-upgrade-tracked-meta-identity-01M66YQ9/
├── plan.md              # This file
├── spec.md              # Mission specification
├── tasks.md             # Phase 2 output
├── tasks/               # Work-package prompts
└── traces/              # approach / design-decisions / tooling-friction
```

### Source Code (repository root)

```
src/
├── specify_cli/
│   ├── mission_metadata.py                     # + read_tracked_meta / TrackedMeta (new owner)
│   ├── upgrade/
│   │   ├── feature_meta.py                     # build_baseline_feature_meta seeds from the tracked copy
│   │   ├── tracked_meta_notice.py              # + the one operator notice/refusal text (new)
│   │   └── migrations/
│   │       ├── m_2_0_6_residue_safe_consistency_sweep.py   # per-Mission notice / refusal in apply()
│   │       └── m_zz_runtime_state_backfill.py              # skip a Mission with a tracked, absent meta.json
│   ├── migration/
│   │   ├── normalize_mission_lifecycle.py      # actionable notice instead of "mission skipped"
│   │   └── backfill_identity.py                # backfill_mission refuses to mint over a tracked copy
└── kernel/
    └── meta_decode.py                          # reused, unchanged

tests/
├── integration/migration/test_upgrade_tracked_meta_identity_6673.py   # red-first, real `upgrade --yes`
├── specify_cli/upgrade/test_read_tracked_meta_6673.py                 # unit: HEAD / index / unborn / absent
└── specify_cli/upgrade/test_runtime_state_cutover_skips_absent_meta_6673.py  # unit: the flip never stubs
```

**Structure Decision**: single project, existing package layout; no new package or module boundary.

## Design

### The reader (`mission_metadata.read_tracked_meta`)

```python
@dataclass(frozen=True)
class TrackedMeta:
    meta: dict[str, Any] | None   # parsed content git holds, or None
    unavailable: bool             # git knows the path but its content cannot be read/parsed
    index_only: bool              # the only copy is in the index (staged, never committed)
```

- `unavailable=False, meta=None`: git holds nothing for this path (pre-identity Mission, no repo) →
  the existing repair applies (FR-004).
- `meta` set: git holds the metadata → callers use it, never mint (FR-001/FR-002).
- `unavailable=True`: git knows the path (index or `HEAD`) but the content cannot be produced or is
  not a JSON object → callers refuse and name the restore command (FR-003). `index_only` only
  changes the wording: the copy is in the index, not in a commit.

Path resolution stays inside `kernel.git`: `run_git(feature_dir, "rev-parse", "--show-prefix")`
gives the checkout-relative prefix (`b"kitty-specs/x/\n"` — **strip the newline**, or the blob lookup
silently misses), then `blob_at(feature_dir, "HEAD", prefix + "meta.json")`. `HEAD` is verified first
(`rev-parse --verify --quiet HEAD`) so an unborn HEAD is "no committed identity", not an error. When
`HEAD` has no blob, `is_tracked(feature_dir, "meta.json")` decides "refuse (index only)" versus
"nothing tracked". `GitCommandError` while reading a tracked path is `unavailable=True` — never a
silent absence — and a timeout is re-raised (`exc.timed_out`), matching
`probe_tracked_mission_paths`.

### The seams

| Seam | Change | Requirement |
|------|--------|-------------|
| `build_baseline_feature_meta` | When the working-tree copy is absent, seed `existing_meta` from `read_tracked_meta(...).meta`; when it is present but has no `mission_id` and the tracked copy has one, take that id back. A `None` seed keeps today's behaviour. A present-but-corrupt file keeps today's behaviour (warned by the sweep), so the tracked copy never silently replaces a file the operator can see. | FR-001, FR-002 |
| `ResidueSafeConsistencySweepMigration.apply` | Per Mission whose `meta.json` is absent on disk: `unavailable` → notice naming `git checkout -- <path>`, skip the folder; `meta` present → notice that the tracked copy is being rebuilt from git, then the normal repair. Notices are computed for every affected Mission **before** the first repair write (C-005). | FR-003, FR-005, C-005 |
| `normalize_repo` | The `meta.json missing; mission skipped` branch becomes the actionable notice for a tracked path, unchanged for an untracked one. | FR-003, FR-005 |
| `RuntimeStateBackfillMigration.apply` | Partition the walk: a Mission whose tracked `meta.json` is absent from the working tree (readable or not — in the readable case the sweep already restored it) is skipped with the same notice, so `_cutover_corpus` never reaches `_flip_phase` and never writes the one-key stub. | FR-008, FR-003 |
| `backfill_mission` | `meta.json` absent on disk + tracked → `action="skip"` with the restore command in `reason`; never `_generate_ulid()`. Has its own test because no `upgrade` path reaches it with a missing file (`normalize_repo` returns before the call) — `migrate backfill-identity` does. | FR-006 |

Write ordering is preserved: notices are computed before the repair runs, and no seam writes anything
for a refused Mission, so the auto-commit (if enabled) cannot commit a fabricated identity.

### Evidence shape

`upgrade --yes` **auto-commits**, so `HEAD` after the run already holds the post-upgrade file. The
acceptance test therefore records the pre-run commit SHA and compares the surviving `mission_id`
against `git show <pre-run-sha>:kitty-specs/<slug>/meta.json`; a comparison against post-run `HEAD`
would compare a minted id with itself and pass vacuously.

## Complexity Tracking

No charter violations; no justification table needed.

## Implementation Concern Map

### IC-01 — The owned read of the tracked `meta.json`

- **Purpose**: one function decides what git holds for a Mission's `meta.json`, so the sweep, the
  normalization and the backfill cannot drift into three answers.
- **Relevant requirements**: FR-001, FR-002, FR-007, NFR-001, NFR-002, C-003
- **Affected surfaces**: `src/specify_cli/mission_metadata.py`, `src/specify_cli/upgrade/feature_meta.py`
- **Sequencing/depends-on**: none (first)
- **Risks**: an unborn `HEAD` must read as "nothing tracked", not as an error; the `--show-prefix`
  newline; a nested checkout must read the project-relative path; a corrupt committed blob must refuse
  rather than fall back; a git timeout must surface, not degrade.

### IC-02 — The upgrade seams stop fabricating identity

- **Purpose**: wire the reader into every seam that can write a `meta.json` for such a Mission (the
  sweep, the normalization, the runtime-state cutover) and the backfill they share, so a
  tracked-but-absent `meta.json` is either rebuilt from git or refused with the restore command, and
  the pre-identity repair is untouched.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, FR-008, NFR-002, NFR-003, C-001, C-002, C-005
- **Affected surfaces**: `upgrade/migrations/m_2_0_6_residue_safe_consistency_sweep.py`,
  `upgrade/migrations/m_zz_runtime_state_backfill.py`, `migration/normalize_mission_lifecycle.py`,
  `migration/backfill_identity.py`, `upgrade/tracked_meta_notice.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: the frozen `_feature_requires_repair`/`_repair_feature` helpers already return True for a
  missing `meta.json`, so detect needs no change; the refusal must skip the whole folder so no later
  step in `_repair_feature` writes state for a Mission we could not identify; the cutover's phase flip
  writes a one-key stub for a missing file, so it must be reached with a guard, not after the fact;
  the residue behaviour (#6627/#6669) must not change.

### IC-03 — Evidence and communication

- **Purpose**: pin both branches (restore and refuse) plus the pre-identity control, and tell the
  operator what changed.
- **Relevant requirements**: SC-001…SC-005, FR-005
- **Affected surfaces**: `tests/integration/migration/test_upgrade_tracked_meta_identity_6673.py`,
  `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`,
  `tests/specify_cli/upgrade/test_runtime_state_cutover_skips_absent_meta_6673.py`,
  `docs/changelog/CHANGELOG.md`, `docs/guides/how-to/installation/upgrade-project.md`,
  `docs/api/upgrade-lifecycle.md`
- **Sequencing/depends-on**: IC-02
- **Risks**: the integration test must compare against the pre-run commit SHA (auto-commit), and must
  fail on `main` for the right reason; the refusal assertions need a same-fixture positive control;
  the corrupt fixture must carry state a later step would rewrite, or the `continue` is untested.
