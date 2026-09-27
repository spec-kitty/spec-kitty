# Mission Specification: Merge-seam placement, test-isolation sweep & model-slot verdict

**Mission Branch**: `issue-5119-merge-seam-test-isolation`
**Created**: 2026-09-26
**Status**: Draft (post-spec squad folded — rigour + boundary lenses)
**Input**: Mission from issues #5119, #5118, #5117 (#5116 triaged and parked — blocked on #2633). Scope confirmed by the operator after a pre-spec grounding squad (alignment + scope lenses) on `main` at `da6d0af97e`.

## Context

Three open tech-debt issues were confirmed still real on current `main` and free of file collisions with the in-flight ratchet mission `ratchet-baseline-census-gate-remediation-01M3EW3Z` (epic #5104):

- **#5119** — the merge domain carries two copies of the same raw git blob-read helper, and the merge domain's in-process driver replay reaches *up* into the CLI command layer to call merge-driver logic that lives in a CLI command module.
- **#5118** — test code mutates process-global state (working directory, import path, loaded-module table, environment, argv) by hand instead of through scoped, auto-restoring patching, so state can leak across tests. The external static-analysis rule that used to report this class is no longer active on the live project, so nothing watches it.
- **#5117** — the agent-profile schema's `model` slot looks inert to the inert-slot detector (a name-collision hides it), but it is a real, consumer-authored slot wired end-to-end into the dispatch routing advisory. Its status needs one explicit, owned verdict.

Parked (not in scope): **#5116** (bridge-parity oracle retire/relax) — blocked on open #2633 and owned by the ratchet mission's WP11.

Scope decision **DM `01M3F61VWEFDY2036QP3S4K04R`** (operator): the #5118 sweep covers **everything the local detector finds** (pre-sweep census 474 sites / 155 files on `da6d0af97e`), not only the 41 sites the legacy SonarCloud project still lists — an ~11× widening, deliberately chosen.

## Domain Language

| Canonical term | Meaning | Avoid |
|---|---|---|
| **merge domain** | The `specify_cli.merge` package — merge execution, reconciliation, projection and git probes. | "merge layer", "merge CLI" |
| **CLI command layer** | The `specify_cli.cli.commands` package — Typer command entrypoints. Distinct from the shared presentation object `specify_cli.cli.console`. | "CLI domain", bare "CLI" when the console is meant |
| **merge-driver body** | The file-level implementation of one registered merge driver (read the ancestor/ours/theirs files, reconcile, serialize, write the result) that raises a typed error on an unresolvable conflict and never exits the process. One per registered driver kind. | "driver" alone (ambiguous with the git-registered subprocess entry) |
| **merge-driver entrypoint** | The CLI command git invokes as a registered merge driver via subprocess; it calls the merge-driver body, echoes any typed error, and sets the exit status. | — |
| **in-process driver replay** | The merge integrity gate's re-execution of a registered merge driver inside the running process, to attribute squashed content to approved lanes (#5038 / PR #5055). | "driver replay" without the gate context |
| **manual global-state mutation** | A write in test code to process-global state (cwd; `sys.path`; `sys.modules`; `os.environ`; `sys.argv`) that is not made through a scoped, auto-restoring facility. A hand-written `try/finally` restore **is** a manual mutation (it is not auto-restoring and leaks on mid-block failure paths the author did not foresee). | "leak" (that's the consequence, not the site) |
| **scoped patching facility** | The accepted replacements: `monkeypatch.chdir/setenv/delenv/setitem/delitem/setattr/syspath_prepend`; `pytest.MonkeyPatch.context()` for module/session-scoped fixtures; `contextlib.chdir` for block-scoped cwd changes (where `monkeypatch.chdir` would restore too late); `unittest.mock.patch.dict(os.environ, …)` / `mock.patch.object`. | — |
| **census gate** | A non-vacuous, shrink-only architectural test that freezes the justified remaining offender set and fails on any new offender. | "ratchet" when meaning the gate itself |

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Merge-domain code never depends on the CLI command layer (Priority: P1)

A maintainer changing merge-driver logic works entirely inside the merge domain. Both callers of a merge driver — git's subprocess invocation and the merge integrity gate's in-process driver replay — execute the **same** merge-driver body in the merge domain, so they cannot disagree. The CLI command module is only a thin entrypoint. There is exactly one raw git blob reader in the merge domain.

**Why this priority**: The upward dependency is an architectural boundary leak in the merge-integrity path that just shipped (#5055); every further change there will deepen it. The duplicated helper can silently diverge.

**Independent Test**: The layer-rules ledger for the merge domain fails on today's `main` naming the in-process driver resolver's import of the merge-driver command module, and passes after the relocation; golden outputs captured before relocation are reproduced byte-for-byte after it.

**Acceptance Scenarios**:

1. **Given** today's `main`, **When** the merge-domain → CLI-command-layer import rule runs, **Then** it fails naming exactly one offender: the function-local import of the merge-driver command module in the in-process driver resolver.
2. **Given** the relocation is done, **When** the rule runs, **Then** it passes; and a self-mutation check that plants a CLI-command-layer import (module-level, function-local, relative, or `importlib` string form) in a merge-domain module makes it fail.
3. **Given** each registered merge-driver kind (all six in the driver registry: event-log, meta, traces, issue-matrix, acceptance-matrix, review-cycle) and its pre-relocation golden fixture set, **When** git invokes the driver via subprocess after relocation, **Then** the written output and the exit status are byte-identical to the goldens.
4. **Given** the merge integrity gate's in-process driver replay, **When** it replays any of the six registered drivers, **Then** it calls the same merge-driver body the subprocess entrypoint calls, resolves all six (no regression to an unresolvable-driver error), and produces the same attribution verdict as before.
5. **Given** the merge domain, **When** anyone looks for the raw git blob reader, **Then** exactly one definition exists (in the git-probes module) and the bookkeeping projection reuses it; its semantics (any non-zero git exit → "no content") are unchanged.

---

### User Story 2 — Tests cannot leak process-global state (Priority: P1)

A contributor running the test suite (serially or in parallel workers) gets the same results regardless of test order, because test code does not mutate cwd, import path, loaded-module table, environment or argv except through scoped patching facilities. A contributor who adds a new manual mutation gets an immediate, actionable failure naming the file, the enclosing function, the mutation kind and the scoped replacement.

**Why this priority**: Order-dependent leaks are the root of intermittent reds; the watching rule was lost, so the class is currently unguarded and growing.

**Independent Test**: The census gate scans every Python file under `tests/`, reports zero unjustified offenders, and fails when a manual mutation (including an aliased form) is planted in a test file.

**Acceptance Scenarios**:

1. **Given** the full sweep has landed, **When** the census gate runs, **Then** every remaining detected site matches an allowlist row that names its justification class and exact site count.
2. **Given** a contributor adds `os.chdir(...)` — or `from os import chdir; chdir(...)`, `import os as _o; _o.environ[...] = ...`, `setattr(sys, "argv", ...)`, `sys.path[:0] = ...` — inside a test function, **When** the census gate runs, **Then** it fails naming file, enclosing function, kind and the suggested scoped replacement.
3. **Given** an allowlisted site is fixed so a row's actual count drops below its recorded count (or to zero), **When** the census gate runs, **Then** it fails with "shrink the allowlist" and the exact row to update (shrink-only; a new gate is born exact, so staleness is an error, not a warning).
4. **Given** a Python file under `tests/` that fails to parse, **When** the census gate runs, **Then** it fails (never silently skips), unless the file lives under an explicitly listed fixture-data directory.
5. **Given** any converted test file, **When** its tests run before and after conversion (serial, and under `-n auto --dist loadfile`), **Then** the pass/skip/xfail outcome per test id is identical.

---

### User Story 3 — The agent-profile `model` slot has one owned, verified verdict (Priority: P2)

A consumer who authors `model:` in their own agent-profile YAML file gets it validated by the schema, loaded by the profile repository, and surfaced as the profile's routing preference in the dispatch advisory. The schema's canonical source says the slot is consumer-authored (built-in profiles deliberately do not set it), so no one mistakes it for an inert slot and deletes it.

**Why this priority**: Low blast radius, but without an owned verdict the slot is at risk of being "cleaned up" as dead schema — and a provisional record today even says "delete-the-declaration".

**Independent Test**: A test writes a consumer profile YAML with `model:` to disk, loads it through the profile repository, runs the dispatch routing advisory, and asserts the profile-preference candidate carries that model id; removing the schema alias makes it fail.

**Acceptance Scenarios**:

1. **Given** a consumer profile YAML on disk declaring `model: <id>`, **When** it is loaded through the profile repository and the dispatch routing advisory runs, **Then** the advisory carries a profile-preference candidate with that model id.
2. **Given** the `model` alias is removed from the profile model (mutation), **When** that test runs, **Then** it fails.
3. **Given** the schema's canonical source, **When** a reader looks at the `model` slot, **Then** its description states it is consumer-authored, not set by built-in profiles, and names the routing advisory as its consumer; the shipped schema artifact agrees.

---

### Edge Cases

- **Session-/module-scoped fixtures and import-time mutations** use `pytest.MonkeyPatch.context()` or move to test configuration. **Relocating** a mutation (collapsing 40 `sys.path.insert` calls into one conftest line or a shared helper) is **not** a fix: the relocated site is still counted. A `tests/` helper that performs a manual mutation on a caller's behalf is itself an offender. Changing `pytest.ini` `pythonpath` is cross-cutting and requires a full `tests/architectural/` run.
- **Genuine process-state needs** (e.g. process-wide HOME isolation in `pytest_configure`; a non-test runner script executed as a subprocess entry; an environment default that must be set before a module is imported) are allowlisted per site with a justification class — never silently skipped.
- **Files owned by the in-flight ratchet mission** (`tests/architectural/test_docs_cli_reference_parity.py`, `tests/architectural/test_single_mission_surface_resolver.py`, `tests/status/test_parity.py`) are not edited; their sites are allowlisted under the `deferred-01M3EW3Z` class.
- **Sub-classes already owned by existing gates are not re-detected**: `patch.dict(sys.modules, …)` belongs to `tests/architectural/test_no_sys_modules_patch_dict.py`; `SPEC_KITTY_HOME` writes to `os.environ` belong to the `_home_pin_scan` gate (which forbids a second copy of its scanner). The new detector excludes exactly those sub-classes so no site carries two verdicts.
- **`sys.modules` removal** via `monkeypatch.delitem(sys.modules, name, raising=False)` does not restore a parent package attribute (`pkg.sub`); conversions that depend on re-import must also patch the parent attribute.
- **Block-scoped cwd changes**: where a test relies on cwd being restored mid-test, `contextlib.chdir` is the replacement (not `monkeypatch.chdir`, which restores only at teardown).
- **Tests that assert on cwd/env side effects of the product** (the product itself calls `os.chdir`) are not offenders — the detector targets mutation *in test code*; product code is out of scope.
- **Path pins on the relocated merge-driver code** are re-pinned in the same change: `tests/architectural/test_inline_meta_read_gate.py` (shared with ratchet WP13 — whichever lands second re-pins; must also assert the pinned qualname exists so it cannot go vacuous), the merge/cli test modules importing the moved pure-logic symbols (including a `monkeypatch` target on the old module), and stale docstring/comment references (`upgrade/migrations/m_3_2_7_review_cycle_merge_driver.py`, `lanes/merge.py`, test docstrings). **Not re-pinned:** `tests/release/coverage_breadth_baseline.json` is a dated provenance snapshot (its `produced_at_commit` would be falsified); `tests/cli/test_lazy_command_module_imports.py` and the shell-level imports keep working because the CLI module name and command function names are unchanged. The review-cycle driver's stdout notice is emitted only by the CLI entrypoint, not by the in-process replay (benign; recorded).
- **Merge-domain uses of the shared console** (`specify_cli.cli.console`, seven modules) are not a CLI-command-layer dependency; they are recorded as a named, shrink-only ledger entry, not relocated in this mission.
- **Sibling domains with the same upward leak** (`status/doctor.py` → `cli.commands.review`; `tasks/` → `cli.commands`) are out of scope (merge-only) and recorded as follow-up in the PR.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Single raw blob reader | As a maintainer, I want the merge domain to have exactly one raw git blob-read helper (in the git-probes module) that the bookkeeping projection reuses, with unchanged semantics, so that the two copies cannot diverge. (#5119) | High | Open |
| FR-002 | Merge-driver bodies live in the merge domain | As a maintainer, I want the file-level body of **all six** registered merge drivers (event-log, meta, traces, issue-matrix, acceptance-matrix, review-cycle) — including their reconciliation helpers, serialization and typed conflict errors — to live in one merge-domain module (not named to collide with the existing WP-set reconciliation gate module), with the event-log body delegating to the status domain as today, so that merge logic and its output format have one owner. (#5119) | High | Open |
| FR-003 | Thin CLI entrypoint | As a maintainer, I want each merge-driver CLI command to only call its merge-domain body, echo a typed error, and set the exit status, so that the CLI command layer holds no reconciliation or serialization logic. (#5119) | High | Open |
| FR-004 | Replay and subprocess share one body | As a maintainer, I want the in-process driver replay to resolve and call the same merge-domain body the entrypoint calls (for all six registered kinds), so that no merge-domain module imports the CLI command layer and the two paths are equivalent by construction. (#5119) | High | Open |
| FR-005 | Merge → CLI-command-layer rule | As a maintainer, I want the existing architectural layer-rules ledger extended so it fails whenever a `specify_cli.merge` module imports `specify_cli.cli.commands` (module-level, function-local, relative or `importlib` string form), with `specify_cli.cli.console` recorded as a named shrink-only ledger entry, landed red-first before the relocation, so that the boundary cannot regress without a second bespoke guard. (#5119) | High | Open |
| FR-006 | Full test-isolation sweep | As a contributor, I want every manual global-state mutation in test code found by the local detector converted to a scoped patching facility (or, only where genuinely required, allowlisted per FR-008), so that tests cannot leak state. (#5118, DM `01M3F61VWEFDY2036QP3S4K04R`) | High | Open |
| FR-007 | Local census gate | As a contributor, I want a local AST census gate over **every** `*.py` under `tests/` (parse failure fails the gate; only explicitly listed fixture-data directories are excluded) that resolves import aliases, covers call, assignment, subscript-write, `del` and `setattr` forms on the five global-state targets, excludes exactly the sub-classes owned by existing gates, and fails on any unallowlisted site. (#5118) | High | Open |
| FR-008 | Justified, exact allowlist | As a reviewer, I want each allowlist row keyed on (file, enclosing qualname, mutation kind) using the repo's shared content-anchored key primitive (no line numbers), carrying an exact site count and a named justification class with a reason, with the gate failing when an actual count exceeds or falls below the recorded count, so that the allowlist can neither excuse new sites nor rot. (#5118) | High | Open |
| FR-009 | Actionable failure message | As a contributor, I want the census gate failure to name file, enclosing function, mutation kind and the scoped-patching replacement, so that I can fix it without reading the gate. (#5118) | Medium | Open |
| FR-010 | `model` slot keep-verdict, one owner | As a consumer, I want the `model` slot's description in the schema's canonical source (the Pydantic schema model) to state that it is a consumer-authored routing-preference slot not set by built-in profiles, with the shipped schema artifact kept in agreement, so that the slot is not removed as inert. (#5117) | Medium | Open |
| FR-011 | `model` end-to-end proof | As a consumer, I want the existing agent-profile `model` test module extended with a test that writes a profile YAML to disk, loads it through the profile repository, and asserts the dispatch routing advisory surfaces the profile-preference candidate, proven non-vacuous by a mutation that removes the alias, so that the untested link of the chain is pinned. (#5117) | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Behavior preservation (merge) | Golden outputs (written file bytes + exit status) are captured for all six registered driver kinds from the existing fixtures **at the pre-relocation commit** and reproduced byte-for-byte after relocation; 100% of existing merge-driver, reconciliation and driver-replay tests pass with unchanged assertions. | Reliability | High | Open |
| NFR-002 | Behavior preservation (tests) | For every converted test file, junit-xml captured before and after conversion shows identical per-test-id outcomes (pass/skip/xfail); 0 tests deleted or newly skipped; converted files also pass under `-n auto --dist loadfile`. | Reliability | High | Open |
| NFR-003 | Census reaches floor | After the sweep: 0 unjustified sites; total allowlisted **sites** ≤ 20% of the pre-sweep census (≤ 95 of 474), each in one of the justification classes fixed at plan time from a classified baseline, with a per-class cap. | Maintainability | High | Open |
| NFR-004 | Gate non-vacuity | The census gate and the layer rule each have a self-mutation test that plants an offender (including an aliased form for the census) and proves the gate fails; the census gate asserts it scanned every `*.py` under `tests/` outside the listed fixture-data exclusions and that this count is ≥ 3000 (3353 today). | Maintainability | High | Open |
| NFR-005 | Gate cost | The census gate completes in under 10 s on a developer machine over the full `tests/` tree. | Performance | Medium | Open |
| NFR-006 | Code quality | New and changed code passes `ruff check`, `ruff format --check` and `mypy` with zero new suppressions; every function stays at cyclomatic complexity ≤ 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Subprocess contract unchanged | The merge-driver subprocess invocation contract (CLI command names, arguments, exit codes, written output) and the driver-registry shape must not change. (#5119 non-goal) | Technical | High | Open |
| C-002 | No ratchet-mission collisions | Do not edit files owned by in-flight mission `01M3EW3Z` (the inert-slot detector files incl. `_inert_slots_baseline.yaml`, `test_bridge_parity.py`, the three census-flagged test files above, `_baselines.yaml`, `test_ratchet_baselines.py`, `test_ratchet_positional_anchor_ban.py`, `_ratchet_keys.py`, `_destructive_op_census.py`, `test_destructive_op_routing.py`); defer census sites in them via allowlist rows of class `deferred-01M3EW3Z`. **Sole operator-approved exception** (scoping decision 2026-09-26): the relocation re-pins the single merge-driver path pin in `test_inline_meta_read_gate.py` (shared with ratchet WP13 — whichever lands second rebases). | Technical | High | Open |
| C-003 | #5117 drift check deferred | Restoring a code-only drift check for inert schema slots is out of scope until mission `01M3EW3Z` merges (its WP05 deletes that detector and its contradicting `model: delete-the-declaration, provisional` baseline row). Until then the schema description (FR-010) plus the FR-011 test are the verdict's single record; #5117 stays open for the remainder. | Business | High | Open |
| C-004 | #5116 out of scope | The bridge-parity oracle is not touched (blocked on #2633). | Business | High | Open |
| C-005 | Test code only for the sweep | The #5118 sweep changes test code/config only; product source is not modified to accommodate tests. | Technical | High | Open |
| C-006 | Red-first / mutation proof | The layer rule and the census gate are committed red-first through their entry point before the change that turns them green (ADR 2026-07-17-1). Where the behavior already works (the `model` chain), non-vacuity is shown by a mutation proof instead. | Technical | High | Open |
| C-007 | Reuse existing gate conventions | New gating extends existing authorities (the layer-rules import collector/ledger, the shared content-anchored key primitive in `specify_cli.contracts.anchoring`, the existing `_home_pin_scan` parser for the SPEC_KITTY_HOME sub-class) rather than adding bespoke parallel guards or line-keyed census rows. Registration of the new caps in the central baselines registry (`_baselines.yaml` / `test_ratchet_baselines.py`) is **deferred** until mission `01M3EW3Z` merges (C-002 wins); until then each gate self-enforces its exact counts and per-class caps. | Technical | High | Open |
| C-008 | Merge-only boundary fix | Only the merge domain's CLI-command-layer dependency is fixed; the same leak in `status` and `tasks` is recorded as follow-up, not fixed here. | Business | Medium | Open |
| C-009 | Terminology canon | Use "Mission", never "feature", in new code, docs and messages. | Business | Medium | Open |

### Key Entities

- **Merge-driver body** — one per registered driver kind; inputs are the ancestor/ours/theirs file paths, effect is the written reconciled file, failure is a typed conflict error.
- **Census site** — (file, enclosing qualname, normalized token line, mutation kind) detected in test code.
- **Allowlist row** — (file, enclosing qualname, mutation kind, exact count, justification class, reason) exempting census sites.
- **Justification class** — named reason category fixed at plan time (e.g. process-wide test bootstrap, subprocess-entry script, pre-import environment default, `deferred-01M3EW3Z`), each with a site cap.
- **Agent profile `model` slot** — optional consumer-authored model id that becomes the profile's routing preference.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero merge-domain modules depend on the CLI command layer (rule green; self-mutation proves it bites across all four import forms).
- **SC-002**: Exactly one raw git blob-read helper exists in the merge domain (down from two).
- **SC-003**: Manual global-state mutations in test code drop from 474 to ≤ 95 allowlisted sites (≥ 80% reduction), with 0 unjustified sites.
- **SC-004**: 0 tests deleted or newly skipped by the sweep; per-test outcomes of converted files unchanged.
- **SC-005**: A newly planted manual mutation (direct or aliased) fails the gate on the first run with a message naming the fix.
- **SC-006**: All six merge drivers produce byte-identical output to pre-relocation goldens, via both subprocess and in-process replay.
- **SC-007**: The agent-profile `model` slot has one owned keep-verdict (canonical schema description + a disk-to-advisory test that fails under mutation).

## Assumptions

- The merge-driver bodies relocate under `specify_cli/merge/` (not `lanes/`); the exact module name is a plan-time decision constrained by FR-002.
- The local detector's target set (cwd, `sys.path`, `sys.modules`, `os.environ`, `sys.argv`) is the operational definition of the #5118 class; the legacy SonarCloud S8997 list (41 open sites) is a subset.
- The pre-sweep census (474) was produced by a coarse scan; the plan re-runs it with the FR-007 detector and freezes the classified baseline — SC-003's percentage applies to that re-run count if it differs.
- Pre-existing known-P0 reds on `main` are classified per the baseline-red policy and are not this mission's to fix.

## Dependencies

- Follow-up: the #5117 drift-check remainder and the #5116 oracle verdict unblock when mission `01M3EW3Z` merges (and, for #5116, when #2633 lands).
- Follow-up: the `status` / `tasks` → CLI-command-layer leaks (C-008).
- Parent context: epic #5104 (ratchet/census friction), epic #5001 (merge integrity; #5119's provenance is PR #5055).
