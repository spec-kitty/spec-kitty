# Work Packages: Cascade activation resolves stems in one pass (#6777)

**Inputs**: Design documents from `kitty-specs/cascade-stem-resolution-pass-01M67JG7/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md (measurements)

**Tests**: This mission is ATDD/red-first (charter, DIRECTIVE_034). The red test is written
against unmodified `main` first, through the pre-existing entry point.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). The
three plan ICs become three WPs on one branch (`topology: coord`, planning artifacts merge
back to `main`).

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** = safe to parallelize (different files). Completion is recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/specify_cli/`, `src/charter/`, `tests/`, `docs/`.

---

## Work Package WP01: One read-only stem-resolution batch (Priority: P1) — the fix

**Goal**: Make the cascade resolve every target's config stem through one shared
`ResolutionPass`, before the first activation write, so the lookup cost stops scaling with
the target count (114 targets → 1 pass instead of 121).
**Independent Test**: the new deterministic guard fails on unmodified `main` (a fresh
`ResolutionPass` per target, resolution interleaved with writes) and passes after the fix;
the scripted writer drops from 80.3 s to ≈50 s on this host.
**Prompt**: `/tasks/WP01-one-resolution-pass.md`
**Requirement Refs**: FR-001, FR-002, FR-006

### Included Subtasks

T001 RED-first: add `tests/charter/activation/test_cascade_stem_resolution_6777.py` asserting (a) every cascade target's `config_id` lookup receives the *same* `ResolutionPass` instance, (b) every lookup happens before the first `activate()` call, through `_activate_cascade_targets` with a recording fake manager — assert it fails on `main`
T002 Extract the target-ref resolution into one batch in `src/specify_cli/cli/commands/charter/activate.py::_activate_cascade_targets` — create one `ResolutionPass`, resolve all refs, then activate
T003 Keep the render path's pass (activate.py:525) and the `_bucket_entries` callers unchanged; do not add a `specify_cli` import to the charter layer
T004 Re-measure the scripted writer twice and record both numbers in `traces/approach.md`

### Dependencies

- None (substrate for WP03's changelog evidence).

### Risks & Mitigations

- A pass must never span a write to the files it reads: resolve the whole batch *before* the first `activate()` (T002), and pin that ordering (T001b) so a later refactor cannot reintroduce the interleave.

---

## Work Package WP02: Retire the timeout override, pin the slow tier (Priority: P1)

**Goal**: Delete `_CASCADE_TIMEOUT_S = 600` and the per-case `pytest.mark.timeout(600)`
marker #6776 added as an interim crutch, put the case on the repository's documented `slow`
tier, and pin both decisions with a collected-mark test.
**Independent Test**: the collected-mark guard fails if a `timeout` mark returns or the
`slow` mark disappears; the case passes under the default 240 s `pytest.ini` timeout.
**Prompt**: `/tasks/WP02-retire-timeout-override.md`
**Requirement Refs**: FR-004, FR-005; C-001

### Included Subtasks

T005 Delete `_CASCADE_TIMEOUT_S` and the parametrised `pytest.mark.timeout` marker; mark the `cascade` param `@pytest.mark.slow` (pytest.ini: "test expected to take >30 seconds")
T006 Add the collected-mark guard to the module: no case of `test_writer_stores_stems_only` carries a `timeout` mark and the `cascade` case carries `slow`
T007 Confirm the module shard selector does not deselect `slow` (`module-tests.yml`: `-m "not performance and not stress"`) and cite it in the guard's docstring

### Dependencies

- WP01 (the marker removal is only honest once the cost is down).

### Risks & Mitigations

- Marking `slow` must not remove the case from CI: verified against the shard selector (T007); no deselect, skip or xfail is added (C-001).

---

## Work Package WP03: Behaviour parity, changelog and docs (Priority: P2)

**Goal**: Prove the fix changed no stored behaviour, record the operator-visible cost change
in the changelog, and note it where the command's cost is described.
**Independent Test**: the whole `test_stored_spelling_6527.py` file passes, including the
`[cascade]` case's stored-list assertions (the same-fixture positive control), and
`docs/changelog/CHANGELOG.md` carries the `[Unreleased]` entry with `(#6777)`.
**Prompt**: `/tasks/WP03-parity-changelog-docs.md`
**Requirement Refs**: FR-003, FR-007; NFR-001, NFR-002, NFR-003; C-002, C-003

### Included Subtasks

T008 Run the full `tests/charter/activation/test_stored_spelling_6527.py` module under the default timeout and record the `--durations` output
T009 Run the wider charter activation neighbours (`tests/charter/activation/`) to prove no cross-test drift
T010 Changelog `[Unreleased]` entry: bold impact-first lead with `(#6777)`, before/after, under 1,200 characters
T011 Update the docs surface that describes the cascade command's cost/behaviour if it states one; regenerate only what the diff touches and check freshness

### Dependencies

- WP01, WP02.

### Risks & Mitigations

- Changelog conflicts with other agents' `[Unreleased]` entries: keep both sides on rebase.
- A full docs-reference rebuild races other agents on the shared CLI asset cache: regenerate only the touched surface and verify with `check_docs_freshness --ci`.
