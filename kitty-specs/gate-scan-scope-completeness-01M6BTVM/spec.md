# Mission Specification: Architectural gate scan scopes — mechanical completeness check

**Status**: Draft
**Issues**: Closes #7000
**Mission branch**: `kitty/mission-gate-scan-scope-completeness-01M6BTVM`

## Problem

#6996 (follow-up to #6994) declares, per architectural gate, the repository paths the gate
READS beyond its code scope, in `.github/ci-module-registry.yml`
(`special_tiers.architectural.scan_scopes`, 98 rows). `scripts/ci/gate_selection.py` derives the
router group and the per-gate selection from it, and `tests/architectural/test_battery_scan_scope_routing.py`
proves the *routing* property: a change inside a declared glob selects the gate.

Nothing checks that a **declaration is complete**. When a gate starts reading a new path
(`_REPO_ROOT / "<root>"`, a new `rglob`, a new config file), its row silently goes stale and
routing misses the gate again — the original #6994 defect class (#6988 added
`scripts/release/changelog_fragments.py` with a raw `date.today()`; the clock bans scan
`scripts/**`, but no routing group selected the battery, so `main` went red).

## Grounding (confirmed on current `main`, 287a226cfe)

- There is no scan of gate source for repo-root reads: `grep -rn "REPO_ROOT" tests/architectural/`
  finds 137 files that read the repository through a `Path(__file__).resolve().parents[2]` root,
  and no test compares those reads with the 98 declarations.
- A planted read passes today: adding `_REPO_ROOT / "planted-undeclared"` to any gate file changes
  no test outcome (the only related gate, `test_battery_scan_scope_routing.py`, only reads the
  registry's declarations).
- Applying the proposed extraction to the live tree (prototype over 374 files,
  `src/**` + `tests/architectural/**` + the router's `ci_config` globs treated as code scope)
  finds **34 undeclared reads across 19 gates** — real gaps (for example
  `test_pyproject_shape.py` reads `uv.lock`, `test_scenario_contract.py` reads `.github/CODEOWNERS`
  and `contracts/tools/**`, `test_lifted_root_gitignore_contract.py` reads `.gitignore`, and
  `test_single_mission_surface_resolver.py` walks `kitty-specs/**`), plus two reads that are
  synthetic (`test_help_startup_third_party_imports.py` probes `.nonexistent-home`) or untracked
  (`test_real_home_isolation_guard.py` creates `.pytest_cache/home-isolation-probes`).
- The existing single source of truth for "what makes a diff run the whole battery" is the router:
  the `architectural-heavy` job's groups other than `arch_scan_scope` (`architectural`, `ci_config`,
  `unmatched src`, …). `tests/architectural/test_battery_scan_scope_routing.py` pins the
  `arch_scan_scope` transcription; nothing pins a hardcoded copy of the code scope.

## User Stories

### User Story 1 — An undeclared read reds instead of silently escaping routing (Priority: P1)

As a maintainer, when a gate starts reading a new repository path, CI tells me to declare it (or
the gate's scope row is already wrong and the check says so), instead of the gate silently not
running on the diff that can break it.

**Independent test**: plant `_REPO_ROOT / "planted-undelcared-dir"` in a gate; the new gate reds
naming the gate file, the line and the path. Declare the glob (or move the read into code scope);
it goes green. No other file changes.

### User Story 2 — The current declarations become complete (Priority: P1)

As a maintainer, every declaration in the registry today matches what the gate actually reads, so
the new check lands green rather than as a permanently-exempted alarm.

**Independent test**: run the new gate on the live tree: zero failures. Every one of the 34
undeclared reads found by grounding is either declared in the gate's registry row or covered by a
narrow, justified exemption.

### User Story 3 — The check cannot be weakened silently (Priority: P2)

As a reviewer, the check's own controls prove it is not vacuous and not self-satisfying: a dropped
declaration reds it, a stale exemption reds it, an uncovered dynamic read reds it, and the code
scope is derived from the router instead of hardcoded.

**Independent test**: each control mutates one input (registry row, exemption table, a synthetic
gate) and asserts the failure message names the mutated thing.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status |
| --- | --- | --- | --- | --- |
| FR-001 | Static repo-root read extraction | US1 — extract, from every gate file under `tests/architectural/` and the `tests.architectural` helper modules it imports transitively, the repository paths it roots at `Path(__file__).resolve().parents[2]` (including names derived from that root, `_REPO_ROOT / "a"`, `_REPO_ROOT / "a" / name`, f-string components, and glob/rglob/iterdir/walk/`/` chains). | High | Open |
| FR-002 | Coverage decision | US1 — a read is covered when a declared scan-scope glob of the owning gate, or the battery code scope, covers its path; a partially dynamic read requires its literal parent directory to be covered; a read rooted at the repository root requires `**`. | High | Open |
| FR-003 | Code scope is derived, not copied | US3 — code scope = `src/**`, `tests/architectural/**` plus the router's code groups for the `architectural-heavy` job (every group but `arch_scan_scope`), read from `.github/workflows/ci-router.yml` through `scripts/ci/gate_selection.py`; no second hardcoded list. | High | Open |
| FR-004 | The gate | US1 — `tests/architectural/test_gate_scan_scope_completeness.py` fails, naming gate file, line, path prefix and the owning gate, for every uncovered read. | High | Open |
| FR-005 | Narrow exemptions | US2 — an in-repo exemption table (gate → path prefix → reason) admits a read that is not a repository read (synthetic probe path) or is untracked (never in a diff). Each entry carries a non-empty reason, may not be a bare `**`, and a stale entry (its read is gone or now declared) reds. | High | Open |
| FR-006 | Declarations fixed | US2 — every currently undeclared read is declared in its gate's registry row (a new row for gates without one) or exempted under FR-005; the `arch_scan_scope` router transcription and the per-file timing budget are regenerated/pinned so the existing routing property test stays green. | High | Open |
| FR-007 | Controls | US3 — planted undeclared read, dropped declaration, stale exemption, uncovered dynamic read and a non-vacuity floor (the scan sees ≥ 300 reads over ≥ 90 gates) each red the check with a message naming the mutation. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
| --- | --- | --- | --- | --- | --- |
| NFR-001 | Fast and static | The check is AST-only and static: no repository file is executed, and the whole scan stays in the fast tier's budget (target < 5 s locally, budget entry added). | Performance | High | Open |
| NFR-002 | No new routing hole | Adding declarations may only widen the `arch_scan_scope` union consistently with the registry (pinned by the existing router-transcription test); no glob may match nothing tracked (the dead-glob gate stays green). | Reliability | High | Open |
| NFR-003 | Fail loud, not silent | If the registry, router or a gate file cannot be parsed, the check errors with the file and the reason; it never degrades to "no reads found" and passes. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
| --- | --- | --- | --- | --- | --- |
| C-001 | One source per fact | Reads come from source (AST); declarations from the registry; code scope from the router. The exemption table is the only new authority and is pinned by FR-005/FR-007. | Technical | High | Open |
| C-002 | Scope discipline | No change to `scripts/ci/gate_selection.py` semantics or to the routing property; no gate is weakened, skipped or xfailed; no dependency added. | Technical | High | Open |
| C-003 | Red-first | The gate is written before the declarations are fixed and its red is recorded (the 34 pairs), then the declarations land. | Process | High | Open |

### Key Entities

- **`tests/architectural/test_gate_scan_scope_completeness.py`** — the new gate.
- **`tests/architectural/_gate_read_scope.py`** — the AST scanner (read extraction, coverage,
  exemption validation), importable so its controls can unit-test it.
- **`.github/ci-module-registry.yml`** — `special_tiers.architectural.scan_scopes` rows (the
  declarations) and `battery_file_durations.architectural` (the budget).
- **`.github/workflows/ci-router.yml`** — `arch_scan_scope` (transcribed) and the code groups
  `architectural-heavy` already selects (derived as code scope).
- **`scripts/ci/gate_selection.py`** — `load_router`, `battery_scan_scopes`,
  `always_on_battery_files`, `scope_trigger_globs`, `battery_code_helpers`, `cached` helpers.

## Success Criteria

- **SC-001**: Planting an undeclared repo-root read in a gate reds the new check, naming the gate
  file, line and path; removing it (or declaring it) is green. (FR-001, FR-002, FR-004, FR-007)
- **SC-002**: The live tree is green: all 98 declarations plus the 19 gates whose rows were added
  or extended match what the gates read; every exemption is named with a reason and currently
  needed. (FR-005, FR-006)
- **SC-003**: The existing routing property, router transcription, dead-glob and battery budget
  gates stay green after the registry change. (NFR-002)
- **SC-004**: No gate is weakened: the new check adds coverage, removes nothing, and the scan is
  AST-only. (C-002, NFR-001)

## Out of Scope

- Changing routing semantics, the router group derivation, or `select_battery_gates`.
- Rewriting the declarations of gates that already pass (no opportunistic churn).
- Any scan of `src/`, `scripts/` or the Java tree for the same property.
- Runtime enforcement: the check is static analysis, not an execution tracer.

## Assumptions

- `Path(__file__).resolve().parents[2]` remains the repository-root idiom in the battery; a gate
  that roots itself differently (`parents[1]`, a checkout helper) is out of the scan's reach and
  is documented as such in the gate's docstring.
- Declaring a genuinely read path (even a small config file) is acceptable routing cost; the
  affected globs are few and the union is already mostly covered.
