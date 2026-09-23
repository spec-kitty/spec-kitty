# Mission Specification: Arch/Perf Test-Guard Non-Vacuity Hardening

**Mission Branch**: `issue-4036-test-guard-non-vacuity-hardening`
**Created**: 2026-09-23
**Status**: Draft
**Epic**: #4883 — Reclaim deferred squad-review MINOR/tidy-up findings
**In-scope issues**: #4036, #4105, #4210, #4388, #4408, #4536

## Intent Summary

**Primary actor**: a maintainer relying on the repository's architectural/performance test-guards to catch a regression in a PR.

**Trigger / problem**: six deferred squad findings each identify a guard/test that is **vacuous or non-discriminating** — it stays GREEN even when the exact thing it exists to catch is broken (a marker guard that never walks the real tree, a whole-file regex that over/under-matches, an unanchored hardcoded pattern, a path check with no `..` guard, a budget scan with no floor). A vacuous gate is worse than no gate: it advertises protection it does not provide.

**Desired outcome**: each guard is tightened so it **fails on the planted broken input it is meant to catch** (proven RED-first), while still passing on the real tree — closing the non-vacuity defect class by construction (DIRECTIVE_043 / `architectural-gate-non-vacuity`).

**Load-bearing invariant**: *a guard must be demonstrated to FAIL on a representative broken input before it is trusted; a guard that cannot be made to fail is vacuous and must be re-based on the real artifact it protects.*

**Assumptions**: (a) **test-infra only** — the fixes live in `tests/` (+ `pytest.ini` / `.github/workflows/ci-nightly.yml` for #4210); NO `src/` production runtime is changed. (b) The six own disjoint files (verified), so they are independently implementable. (c) "Red-first" for a guard means: plant the broken input, show the guard currently passes (vacuous), then tighten so it fails on that input.

## User Scenarios & Testing *(mandatory)*

Each story shares the shape: **Given** a planted broken input the guard should reject, **When** the guard runs on the current code, **Then** it currently PASSES (vacuous) — and after the fix, **Then** it FAILS on that input while still passing on the real tree.

### US1 — repo-root status-guard discriminates (#4036) (Priority: P3)
The self-test's assertion `assert not (REPO_ROOT / name).exists()` (`test_repo_root_status_guard.py:163-164`) is an *absolute* claim, not scoped to this test's window — under `-n auto` a concurrent worker's root-level `status.*` makes it flaky and it does not express the guard's real concern ("*this* test didn't leak"). The module's "Boundary (documented, deliberate)" block (`repo_root_status_guard.py:52-56`) also omits the concurrent-worker / between-tests straddle. Make the assertion window-scoped and document the xdist-straddle caveat. **Test (RED-first must be REAL, not comment-only — the scout flagged this as the easiest to fake):** demonstrate that a write which straddles the per-test window (setup snapshot → teardown compare) is now caught/correctly-attributed, not merely that a caveat comment was added. **Note:** this guard already has a genuine end-to-end firing proof (`:142-164`), so the fix is a narrow discrimination/scoping tightening, not a rebuild.

### US2 — dead-src-path gate is frontmatter-scoped (#4105) (Priority: P3)
**Scope correction (post-spec scout):** the vacuity is entirely inside `tests/architectural/test_no_dead_src_path_literals.py` — NOT `_dead_path_scan.py` (a different helper imported by four sibling `test_no_dead_*` guards; do not touch it). The offender is `is_retired_doc(text)` consuming `_DOC_STATUS_RE` (MULTILINE, `:225 finditer(text)`) over the WHOLE file, so a `doc_status: superseded` line in a page's *body/prose* (not frontmatter) makes the file skipped and a dead `src/…` literal in it pass vacuously. Also: `ARCHIVE_PATH_PREFIXES` carries an unreachable `kitty-specs/` branch (`collect_dead_paths` only walks `docs/**`), and the `:98-101` comment over-claims "frontmatter". Scope `is_retired_doc` to the leading `---…---` frontmatter block only, delete the `kitty-specs/` prefix, correct the comment. **Test**: a `docs/*.md` whose BODY (not frontmatter) contains `doc_status: superseded` + a dead `src/nonexistent.py` is caught after the fix (currently skipped/vacuous); a genuinely-deprecated page (frontmatter `doc_status`) still skips.

### US3 — performance-marker guard walks the real tree (#4210) (Priority: P3)
`test_performance_marker_guard.py`'s `find_functional_assertions_under_performance_marker` runs only on planted TEXT constants (never AST-walks `tests/performance/`), and `pytest.ini`'s marker description is stale (`:58` "not selected by any live CI job" — the nightly `-m performance` job DOES run it). Add an **additive** real-tree walk (new `_iter_performance_marked_test_sources()` + a test that AST-parses each real `tests/**/test_*.py` and calls the **unchanged pure `(source: str) -> list[str]`** function per file, with an explicit exemption list — do NOT change that function's signature: `test_timing_coverage_invariant.py:51/525` imports and calls it), and correct the stale marker desc. Bound the walk (`rglob("test_*.py")`, `try/except SyntaxError`, exemption list; reconsider the `fast` marker if it exceeds sub-second).
**Scope correction (post-spec scout):** the "e2e double-run" sub-item is a GHOST — already removed by #4865 (2026-09-22): `ci-nightly.yml` runs `-m e2e` exactly once (`:194`) and `SPEC_KITTY_RUN_PERFORMANCE` is scoped to the performance job (`:106`). Re-scope that sub-item to a REAL invariant: **assert `SPEC_KITTY_RUN_PERFORMANCE` is set on the performance job ONLY and is not leaked into any other nightly job** (the guard the #4865 split relies on). Any `ci-nightly.yml` edit must keep the existing sibling workflow assertions green (`test_performance_marker_guard.py` workflow tests, `test_marker_job_completeness.py`). **Test**: a real `@pytest.mark.performance` test carrying a functional assertion is caught (currently vacuous); the marker desc matches the live nightly job; a planted `SPEC_KITTY_RUN_PERFORMANCE` on a non-performance job is caught.

### US4 — module-shard-registry pattern is anchored (#4388) (Priority: P3)
`test_module_shard_registry.py`'s `_PYTHON_FILE_PATTERNS` is hardcoded with only a prose comment; nothing asserts `pytest.ini` carries no `python_files` override that would silently diverge the basis. Add that assertion so the hardcoded pattern is anchored to reality. **Test**: a planted `python_files` override in `pytest.ini` is caught.

### US5 — gate-coverage composite-action path rejects traversal (#4408) (Priority: P3)
`_gate_coverage.py`'s `_composite_action_path` never normalizes/rejects `..` segments, so a `uses:` path with `..` is mis-attributed. Reject/normalize `..`. **Test**: a composite-action `uses:` containing `..` is rejected (or normalized), not over-attributed.

### US6 — CLI startup-budget scan has a non-vacuity floor (#4536) (Priority: P3)
`test_cli_startup_budget_4409.py` `rglob("*.py")` with no minimum-scanned-file assertion (an empty/mis-rooted scan passes vacuously), an AST scan that matches no dynamic import (`importlib.import_module`/`__import__`), and a docstring claiming it walks "the CLI's import graph" though it walks all of `src/`. Add a min-scanned-file floor, cover the dynamic-import blind spot, correct the docstring. **Test**: a mis-rooted/empty scan fails the floor; a planted dynamic import is scanned.

### Edge Cases
- A guard whose "broken input" cannot be planted without touching `src/` → keep the fix in the test/`_support` layer; do not bleed into production code (esp. #4536).
- A fix must not make the guard flaky or slow (these run in CI); prefer a bounded, deterministic real-tree walk with an explicit exemption list over an unbounded scan.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | repo-root status-guard window-scoped + xdist caveat | As a maintainer, I want the status-guard to catch a straddling write (window-scoped assert) with the xdist-straddle boundary documented. (Source: #4036) | Low | Open |
| FR-002 | dead-src-path gate frontmatter-scoped, dead branch removed | As a maintainer, I want `is_retired_doc` in `test_no_dead_src_path_literals.py` scoped to frontmatter (not whole-file), with the unreachable `kitty-specs/` prefix and over-claiming comment removed. **`_dead_path_scan.py` is out of scope** (different helper, 4 sibling importers). (Source: #4105) | Low | Open |
| FR-003 | performance-marker guard walks the real tree (additive); desc + env-scope invariant | As a maintainer, I want an ADDITIVE real-tree AST walk (preserving the pure `find_functional_assertions_under_performance_marker(source)` contract that `test_timing_coverage_invariant.py` imports), the stale `pytest.ini` marker desc corrected, and a real invariant that `SPEC_KITTY_RUN_PERFORMANCE` stays scoped to the performance job (the e2e-double-run was already removed by #4865). (Source: #4210) | Low | Open |
| FR-004 | module-shard `_PYTHON_FILE_PATTERNS` anchored to pytest.ini | As a maintainer, I want an assertion that `pytest.ini` carries no `python_files` override, so the hardcoded shard basis cannot silently diverge. (Source: #4388) | Low | Open |
| FR-005 | gate-coverage composite-action path rejects `..` | As a maintainer, I want `_composite_action_path` to normalize/reject `..` segments so a `uses:` path is not mis-attributed. (Source: #4408) | Low | Open |
| FR-006 | CLI startup-budget non-vacuity floor + dynamic-import coverage | As a maintainer, I want the startup-budget scan to assert a minimum scanned-file count, cover dynamic imports (`importlib.import_module`/`__import__`), and correct its docstring. (Source: #4536) | Low | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Proven non-vacuity | Each of the six guards is demonstrated to FAIL on a planted broken input (a committed RED-first demonstration) that it currently passes; 6/6 guards go from vacuous→discriminating. | Reliability | High | Open |
| NFR-002 | No regression on the real tree | 100% of the six guards still pass on the real repository tree after tightening (no new false positives; the pre-existing suites stay green). | Compatibility | High | Open |
| NFR-003 | Test-infra only | 0 `src/` production runtime files changed; the diff is confined to `tests/`, `pytest.ini`, and `.github/workflows/ci-nightly.yml`. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Non-vacuity by construction | Follow DIRECTIVE_043 / `architectural-gate-non-vacuity`: a self-mutation demonstration proves each tightened guard fails on the broken input. | Technical | High | Open |
| C-002 | ATDD demonstrate-vacuous-first | Each finding lands an issue-pinned RED-first demonstration (guard passes on planted broken input) BEFORE the fix; transitional demos become the guard's own permanent non-vacuity test. | Process | High | Open |
| C-003 | Do not bleed into src/ | Fixes stay in the test/`_support` layer; #4536's dynamic-import coverage must not modify production startup code. | Technical | High | Open |
| C-004 | Scope boundary | Only these six #4883 children; the already-fixed close-only set and the claimed/needs-revision/medium siblings (#4419, #4504, #4273, #4466) are out of scope. | Scope | High | Open |

### Key Entities

- **Vacuous guard**: a test/gate that passes even on the broken input it exists to catch.
- **Non-vacuity demonstration**: a committed check that the tightened guard fails on a planted broken input (self-mutation / red-first).
- **Real-tree basis**: the guard is based on the actual repository artifact (test tree, `pytest.ini`, workflow), not a planted-only text fixture.

## Success Criteria *(mandatory)*

- **SC-001**: 6/6 guards are demonstrated vacuous-then-discriminating — each fails on a planted broken input it previously passed (RED→GREEN of the demonstration).
- **SC-002**: 6/6 guards still pass on the real tree; no new false positives; the touched test modules' suites are green.
- **SC-003**: The diff touches zero `src/` production files (test-infra only) — provable by `git diff --stat`.
- **SC-004**: Each of #4036/#4105/#4210/#4388/#4408/#4536 has an issue-pinned non-vacuity demonstration committed, so a future re-vacuation fails CI.
