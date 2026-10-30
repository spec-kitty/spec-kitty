# Mission Specification: Cascade activation resolves stems in one pass (#6777)

**Mission Branch**: `issue-6777-cascade-stem-resolution-pass`
**Created**: 2026-10-30
**Status**: Draft
**Input**: User description: "Issue spec-kitty/spec-kitty#6777 — `tests/charter/activation/test_stored_spelling_6527.py::test_writer_stores_stems_only[cascade]` exceeds the 240 s per-test timeout in charter shard 6/7 and is red on `main`. Measure where the time actually goes before changing anything; fix the cause, not the marker; if the honest fix is to move the case to a slower tier, pin the tier decision in a test."

## Problem statement (measured, not assumed)

`charter activate <directive> <id> --cascade all` walks the merged DRG and then calls
`ActiveCharterManager.activate()` **once per cascade target**. The `[cascade]` case of
`test_writer_stores_stems_only` drives exactly that operator command, so its cost is the
product cost of one `--cascade all` run.

Measured in this clone on `origin/main` at `512567eee7` (v4.0.0rc8, host `llama-ramen`,
20 concurrent agent workloads, three runs):

| Run | `[cascade]` call | Whole file (`10 passed`) |
|---|---|---|
| pytest, `--timeout=0` | 70.90 s | 111.83 s total |
| scripted writer (`_project` + `_cascade`) | 80.30 s | — |

Instrumented decomposition of that 80.30 s:

* **114** `ActiveCharterManager.activate()` calls — one per cascade target across six
  kinds (directive, paradigm, procedure, styleguide, tactic, toolguide); median
  0.53 s, slowest 7.26 s; **58.0 s** of the 80.3 s is inside those calls.
* **126** whole-catalog scans (`list_available_detailed`) across those calls, and
  **9735** artifact-file parses inside them (`_declared_id`, one ruamel load per
  artifact file per scan). That is ~77 files parsed per scan.
* **121** DRG-URN → config-stem lookups (`drg_urn_to_config_id` /
  `resolve_config_id`) that re-walked and re-parsed the artifact tree **once per
  lookup**: 5309 artifact-file parses for 121 lookups.

cProfile of the same run (303 s under the profiler) attributes 165 s cumulative to
`list_available_detailed` and 87 s to `resolve_config_id`.

The second figure is an **accidental redundancy with an existing fix that was applied
too late**: `ResolutionPass` (charter.activation.kind_vocabulary) exists precisely to
memoise layer scans and artifact id reads across one read-only pass, and #5526 applied
it to the cascade *render* loops. `activate.py` creates that pass **after** the
activation loop (`activate.py:525`), so the 114 activations each resolve their own URN
with a fresh pass. The identical omission is why the case was 96–134 s on CI and tripped
the 240 s backstop on a slower runner.

Two candidate readings were tested and the first is the evidence-backed one:

* *A genuinely slow full-corpus sweep that should be tiered* — rejected as the primary
  cause: the sweep is real (114 targets is the DRG's designed closure) but the
  dominant cost is repeated, memoise-able work, not the closure itself.
* *An accidental O(targets × catalog) redundancy* — confirmed by measurement: sharing
  one `ResolutionPass` across the 114 lookups takes the writer from 80.3 s to **49.8 s**
  with no behaviour change. Memoising the per-target catalog scan as well (an upper
  bound, not proposed here) takes it to **13.4 s**.

The interim state on `main` is #6776's crutch: a 600 s per-test timeout marker on the
`[cascade]` case only (`_CASCADE_TIMEOUT_S`), with a comment asking whoever fixes #6777
at the root to remove it.

## Scope

In scope:

* Remove the accidental per-target URN → stem re-resolution in the cascade activation
  path, so one read-only `ResolutionPass` covers every cascade target and runs before
  the first write.
* Retire `_CASCADE_TIMEOUT_S` and the per-case `pytest.mark.timeout(600)` marker, so
  the suite-wide 240 s backstop from `pytest.ini` (#3143) applies to the case again.
* Mark the case with the repository's documented slow tier (`@pytest.mark.slow`,
  "test expected to take >30 seconds" in `pytest.ini`), which the module shards do
  **not** deselect (`module-tests.yml` selects `not performance and not stress`), and
  pin both decisions with deterministic tests.
* Changelog and a docs note where the operator-visible command cost is described.

Out of scope (recorded in `## Deferred`, filed as a follow-up issue):

* A batch activation seam that computes the availability catalog once per kind instead
  of once per target (the remaining ~36 s of the original writer cost). It is a
  behaviour-relevant change to `ActiveCharterManager`'s public per-artifact contract
  and needs a maintainer decision; this mission does not touch it.
* Shrinking the `[cascade]` fixture: the case's value is that *every* cascade target's
  stored spelling is checked, so coverage is kept and the cost is fixed instead.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An operator's `--cascade all` stops re-parsing the doctrine catalog per target (Priority: P1)

An operator runs `spec-kitty charter activate directive <id> --cascade all`. Today the
command resolves every cascaded artifact's config stem by re-walking and re-parsing the
whole doctrine catalog once per artifact. The operator wants the same activation lists,
in the same order, with the same messages — and without the repeated catalog walk.

**Why this priority**: it is the measured root cause of the red shard and of an
~80 s operator command. Fixing it is the whole issue.

**Independent Test**: drive the cascade writer through its pre-existing entry point
(`charter_app` via `CliRunner`, exactly as the `[cascade]` case does) and, with the
shared-pass defect re-introduced, observe the lookups no longer share one pass; with the
fix, observe one pass and one parse per artifact file. Positive control on the same
fixture: the cascade still activates the same targets and stores the same stems.

**Acceptance Scenarios**:

1. **Given** the stored-spelling fixture project, **When** `_activate_cascade_targets`
   runs, **Then** every target's config stem is resolved through the **same**
   `ResolutionPass` instance, and every such resolution completes before the first
   `ActiveCharterManager.activate()` call for that run.
2. **Given** the same fixture project and the same command, **When** the cascade runs,
   **Then** the number of `ResolutionPass` instances created for the target lookups is
   one, not one per target — asserted without a wall clock.
3. **Given** the same fixture project, **When** the `[cascade]` case runs, **Then** the
   stored `activated_*` lists are exactly the stems the pre-fix code stored (the
   positive control that the speedup changed no behaviour).

### User Story 2 - The case runs under the suite-wide timeout backstop again (Priority: P1)

A maintainer reads `pytest.ini` and expects one timeout authority: the 240 s runaway
backstop. The `[cascade]` case currently overrides it with a 600 s marker that #6776
added as an interim crutch.

**Why this priority**: leaving the override makes the fix unverifiable — the case would
pass even if the redundancy came back.

**Independent Test**: collect the module and assert the `[cascade]` case carries no
per-test `timeout` mark; assert it carries `slow`. Then run the case with the default
`pytest.ini` timeout and observe it passes with headroom.

**Acceptance Scenarios**:

1. **Given** the module's parametrisation, **When** it is collected, **Then** no case of
   `test_writer_stores_stems_only` carries a `timeout` mark, and the `[cascade]` case
   carries `slow`.
2. **Given** the measured cost of the fixed case, **When** it runs under the default
   240 s `pytest.ini` timeout on this host, **Then** it passes.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One resolution pass for every cascade target | As an operator running `--cascade all`, I want every cascaded artifact's stem resolved in one read-only pass so that the command does not re-parse the doctrine catalog per target. | High | Open | [build] | no |
| FR-002 | Resolve before the first write | As a maintainer, I want the cascade's stem lookups to complete before the first activation write so that `ResolutionPass`'s "never span a write to the files it reads" contract holds by construction. | High | Open | [build] | no |
| FR-003 | Identical stored result | As an operator, I want the cascade's activation lists, order and messages unchanged by the fix so that the speedup is behaviour-preserving. | High | Open | [ratchet] | no — positive control on the same fixture (the `[cascade]` case's own assertions) |
| FR-004 | No per-test timeout override | As a maintainer, I want the `[cascade]` case to run under the single `pytest.ini` 240 s authority again, with `_CASCADE_TIMEOUT_S` and its marker removed. | High | Open | [build] | no |
| FR-005 | Tier decision pinned | As a maintainer, I want the case's slow tier recorded with the repository's `slow` marker and its absence of a timeout override pinned by a test so that neither decision can silently regress. | Medium | Open | [build] | no — the guard fails if either the marker disappears or an override returns |
| FR-006 | Deterministic regression guard for FR-001/FR-002 | As a maintainer, I want a unit test that fails when the per-target fresh pass comes back, so the redundancy cannot return unnoticed. | High | Open | [build] | no |
| FR-007 | Changelog + docs | As an operator, I want the change recorded in `docs/changelog/CHANGELOG.md` under `[Unreleased]` with `(#6777)` so that the operator-visible cost change is discoverable. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Measured improvement with margin | On this host, the fixed `[cascade]` case measures at most 60 s wall clock (median of at least two runs), down from the 70.9–80.3 s baselines, so that a 2.2× slower runner stays well under the 240 s backstop. | Performance | High | Open |
| NFR-002 | Artifact parses bounded | For a cascade of N targets, the stem lookups create exactly one `ResolutionPass`, so artifact-file parses for URN resolution are independent of N rather than proportional to N. | Performance | High | Open |
| NFR-003 | No timing assertion added | The regression guard must not assert wall-clock seconds (repo policy: absolute seconds are not accepted evidence); it asserts pass counts and marker state. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No gate weakened | No test is skipped, xfailed, deselected or moved out of the CI shard set; the change removes an override rather than adding one. | Process | High | Open |
| C-002 | Layer boundary | The fix stays in the CLI cascade wiring (`specify_cli/cli/commands/charter/activate.py`) and does not add a `specify_cli` import to the charter layer (C-001 layering). | Technical | High | Open |
| C-003 | Single canonical authority | `ActiveCharterManager`'s public per-artifact contract and the `ResolutionPass` seam are reused, not duplicated or re-implemented. | Technical | High | Open |

### Key Entities

* **Cascade target**: one artifact the DRG walk reaches from the activation source; the
  activation loop handles 114 of them for `directive:DIRECTIVE_001 --cascade all`.
* **`ResolutionPass`**: the existing per-pass memo of layer scans and artifact id reads
  (`charter.activation.kind_vocabulary`); one instance must serve the whole lookup batch.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The `[cascade]` case passes under the default 240 s `pytest.ini` timeout with no per-test override, on this host under concurrent agent load. — [build] · no-op passable: no
- **SC-002**: The fixed `[cascade]` writer measures ≤60 s on this host (median of ≥2 runs) against a 70.9–80.3 s baseline. — [ratchet] · no-op passable: no
- **SC-003**: A cascade of 114 targets creates exactly one `ResolutionPass` for its stem lookups, all of them before the first activation write. — [build] · no-op passable: no
- **SC-004**: Every other test in `tests/charter/activation/test_stored_spelling_6527.py` still passes unchanged, and the `[cascade]` case's stored lists are unchanged. — [ratchet] · no-op passable: no
