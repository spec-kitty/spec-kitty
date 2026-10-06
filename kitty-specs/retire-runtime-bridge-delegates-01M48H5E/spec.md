# Mission Specification: Retire the runtime_bridge compat-delegate layer

**Mission Branch**: `issue-2561-retire-runtime-bridge-delegates`
**Created**: 2026-10-06
**Status**: Draft
**Input**: Operator dispatch brief for #2561 (with sub-issue #2633), plus the grounding Op `01M48EGX6W10155GCSDWJCZAT1` on reference branch `spike/runtime-bridge-grounding-2560-2562` (`GROUNDING.md`, prototype commit `20547b2d`).

## Intent Summary

The earlier decomposition of the runtime bridge (#2531, PR #2558) moved logic into six seam
modules but left a thin forwarding function in `runtime_bridge.py` for every moved symbol, so
old test patches kept working. The seams in turn look those forwarders up again through
deferred `runtime_bridge` imports, only so the patches take effect. Nothing in production
needs this layer. It hides which module owns each symbol, and it lets a test patch the wrong
place without noticing.

- **Primary actor:** a Spec Kitty maintainer changing the runtime (`spec-kitty next`) code.
- **Trigger:** the maintainer needs to change or test a seam-owned function.
- **Desired outcome:** each function has one home; tests patch that home; the bridge keeps only
  what it really owns plus the two public entry points other CLI modules call.
- **Invariant:** runtime behaviour does not change. Every test that passed before still passes
  (or is replaced by an equivalent test against the owning seam), and no patch silently stops
  intercepting the call it was written for.

## Domain Language

| Term | Meaning | Avoid |
|------|---------|-------|
| Runtime bridge | `src/runtime/next/runtime_bridge.py`, the orchestration entry for `spec-kitty next` | "the bridge god module" |
| Seam | One of the six modules split out of the bridge: `runtime_bridge_identity`, `_retrospective`, `_io`, `_composition`, `_engine`, `_cores` | "submodule", "helper module" |
| Compat delegate | A function or class in the runtime bridge whose body only forwards to a seam (docstring "Thin compat delegate") | "shim" (overloaded) |
| Adapter delegate | A compat delegate that also changes arguments on the way through | "pure forward" |
| Back-edge | A deferred `from runtime.next import runtime_bridge as _rb` lookup inside a seam that reads a name back off the bridge | |
| Public re-export | A bridge name bound to the very same function object as the seam's, kept for callers outside `src/runtime/next/` | "alias" |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A seam function has exactly one home (Priority: P1)

A maintainer opens `runtime_bridge.py` to find where `_build_run_ref` lives. Today there is a
forwarder that hands off to `runtime_bridge_io`, which may itself look the bridge up again.
After this mission the name is gone from the bridge and the maintainer reads it in the seam.

**Why this priority**: this is the debt the issue tracks; every other story depends on it.

**Independent Test**: list the bridge's top-level definitions and confirm none of the 36
delegated names remain as a forwarding definition; the runtime test surface stays green.

**Acceptance Scenarios**:

1. **Given** the bridge on `main` with 37 "Thin compat delegate" docstrings, **When** the mission lands, **Then** the 36 pure-forward and adapter delegates are gone and only `_check_cli_guards` (real logic) remains, with an accurate docstring.
2. **Given** a seam that needs a function another seam owns, **When** it calls it, **Then** it calls the owning seam (or itself) directly, never by reading the name back off the bridge.

---

### User Story 2 - A test patch intercepts the call it targets (Priority: P1)

A maintainer writes `monkeypatch.setattr(runtime_bridge_io, "_build_run_ref", fake)`. The patch
must take effect for the code path under test. A patch on a deleted bridge name must fail loudly.

**Why this priority**: the main hazard of the change is a patch that silently stops working.

**Independent Test**: every test file that referenced a deleted name patches the owning seam
and still passes; each test that patches the kept public re-exports is checked to exercise a
path that really goes through the patched binding.

**Acceptance Scenarios**:

1. **Given** a test that patched `runtime_bridge.<deleted name>`, **When** the mission lands, **Then** it patches `<owning seam>.<name>` and still asserts the same behaviour.
2. **Given** a test that patches the kept `runtime_bridge.get_or_start_run` while exercising the bridge's own internal decide/query path, **When** the internal call now resolves to the seam, **Then** the test is repointed to the binding the path actually uses, so it still intercepts.
3. **Given** a test whose only purpose was to pin the compat mechanism (a forwarder or a live lookup through the bridge), **When** the mechanism is removed, **Then** that test is deleted or rewritten as a test of the owning seam's patch point.

---

### User Story 3 - CLI entry points keep working (Priority: P1)

`spec-kitty next`, `implement`, the workflow executor, the mission loader and the orchestrator
API call `runtime_bridge.get_or_start_run` and `runtime_bridge.build_operational_context_for_claim`.
They keep working unchanged.

**Why this priority**: these are production callers outside the mission boundary.

**Independent Test**: `runtime_bridge.get_or_start_run is runtime_bridge_io.get_or_start_run`
and the same for `build_operational_context_for_claim`; the CLI tests that use them pass.

**Acceptance Scenarios**:

1. **Given** a CLI module importing those two names from the bridge, **When** the mission lands, **Then** the import still works and returns the seam's own function object.

---

### User Story 4 - Adapter behaviour is preserved (Priority: P2)

Three delegates did more than forward: `_load_feature_runs(repo_root)` resolved the runs file
path first, `_parse_requirement_refs_from_tasks_md` supplied a `grammar=` argument, and
`_build_run_ref` threaded a `run_ref_cls`. Their call sites keep the same behaviour once the
adapter is gone.

**Why this priority**: the grounding prototype caused a real regression on exactly this.

**Independent Test**: characterisation tests written before deletion pin each adapter's
observable result and stay green after its call sites are rewritten.

**Acceptance Scenarios**:

1. **Given** a repo root with a runs file, **When** the bridge loads mission runs, **Then** it reads the file at the resolved runs path, as before.
2. **Given** a `tasks.md` with requirement references, **When** the bridge parses them, **Then** the same references come back, parsed with the same grammar.
3. **Given** a run reference is built, **When** the bridge builds it, **Then** it has the same type and fields as before.

### Edge Cases

- A seam back-edge points at a name the bridge **still owns** (for example `_should_advance_wp_step`, `_is_wp_iteration_step`, `_map_runtime_decision`, or the guard facts io reads). It stays: it is not a delegate.
- An import cycle (io and composition import each other) forces a call to stay deferred. A deferred import of the **owning seam** is allowed; a deferred lookup on the bridge is not.
- A test file outside `tests/runtime`/`tests/next` (integration, retrospective, orchestrator API) patches a deleted name. It is repointed too.
- A name is both deleted and read by a docstring outside `src/runtime/next/` (`mission_loader/command.py` mentions `runtime_bridge._build_discovery_context`). That docstring is out of scope and recorded as deferred.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Delete the 36 compat delegates | As a maintainer, I want the 36 forwarding definitions (identity 3, retrospective 9, io 13, composition 8, engine 1, cores 2) removed from the runtime bridge so that each name has one home. | High | Open | [build] | no — a static check lists the bridge's top-level definitions and fails while any of the 36 is still defined there |
| FR-002 | Keep `_check_cli_guards` with an accurate docstring | As a maintainer, I want the one mislabelled real function kept and its docstring describing what it does so that the label no longer lies. | Medium | Open | [build] | no — the "Thin compat delegate" text count on the bridge must reach 0 while `_check_cli_guards` stays defined |
| FR-003 | Remove back-edges to delegated names | As a maintainer, I want every seam lookup of a delegated name through the runtime bridge replaced by an intra-module call or a call on the owning seam so that seams no longer depend on the bridge for names it does not own. | High | Open | [build] | no — a static scan of the seams for `_rb.<name>` where `<name>` is one of the 36 must report zero |
| FR-004 | Keep back-edges to bridge-owned names | As a maintainer, I want back-edges to names the bridge genuinely still owns left as they are so that this mission does not move logic (#2560's job). | Medium | Open | [ratchet] | yes — paired with FR-003 on the same scan: names not in the 36 are allowed and listed |
| FR-005 | Keep the two public entry points as re-exports | As a CLI module, I want `runtime_bridge.get_or_start_run` and `runtime_bridge.build_operational_context_for_claim` to stay importable as the seam's same function objects so that callers outside `src/runtime/next/` keep working. | High | Open | [ratchet] | no — an identity assertion (`is`) against `runtime_bridge_io` fails if either becomes a wrapper or disappears |
| FR-006 | Repoint every test patch to the owning seam | As a maintainer, I want every test that patched, imported or read a deleted bridge name to target the owning seam so that the suite passes without the delegates. | High | Open | [build] | no — any leftover patch of a deleted name raises AttributeError and the surface run fails |
| FR-007 | Review façade patches by call path | As a maintainer, I want each test that patches a kept re-export while exercising the bridge's internal path repointed to the binding that path uses so that no patch silently stops intercepting. | High | Open | [build] | no — each reviewed test asserts its fake was called (or the behaviour only the fake produces) |
| FR-008 | Characterise the adapter delegates red-first | As a maintainer, I want `_load_feature_runs`, `_parse_requirement_refs_from_tasks_md` and `_build_run_ref` pinned by characterisation tests at their bridge call sites before deletion so that the adapter behaviour is preserved. | High | Open | [build] | no — the tests drive the bridge's production entry and fail if the runs path, grammar or run-ref class is dropped |
| FR-009 | Retire compat-mechanism tests | As a maintainer, I want tests that only pinned the forwarding or live-lookup mechanism deleted or rewritten as owner patch-point tests so that the suite stops protecting the debt. | Medium | Open | [build] | no — a grep for the deleted names in tests returns no bridge-qualified hit |
| FR-010 | Describe ownership in seam docstrings | As a maintainer, I want seam module and function docstrings that described the compat mechanism rewritten to say what the seam owns so that the docs match the code. | Low | Open | [build] | no — a grep for "compat delegate" / "live lookup through runtime_bridge" in `src/runtime/next/` returns no hits |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No behaviour change | The runtime_bridge test surface (every test file referencing `runtime_bridge`, plus `tests/runtime`, `tests/next`, `tests/specify_cli/next`) passes with 0 failures; the baseline on `main` 7297d8c0 is 2738 passed / 4 skipped, and any drop in the pass count is fully explained by deleted mechanism-only tests. | Reliability | High | Open |
| NFR-002 | No new type errors | `mypy` over `src/runtime/next/` reports no more than the 21 errors present on `main`, and none in lines this mission changes. | Maintainability | High | Open |
| NFR-003 | Complexity ceiling | No function touched by the mission exceeds cyclomatic complexity 15 (ruff C901). | Maintainability | Medium | Open |
| NFR-004 | Lint and format clean | `ruff check` and `ruff format --check --force-exclude` report 0 issues on changed files. | Maintainability | High | Open |
| NFR-005 | Architectural gates green | `test_no_dead_symbols`, `test_layer_rules`, `test_bridge_cores_import_boundary` and `test_runtime_emitter_seam` pass. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Stay inside the runtime package | Source changes stay inside `src/runtime/next/`; test changes are limited to tests that reference the deleted names. No mission-create, consolidation or lanes code is touched. | Technical | High | Open |
| C-002 | Do not do #2560 or #2562 | No logic moves out of the bridge (the query/answer seam is #2560); the composition-advance dedup is #2562. | Technical | High | Open |
| C-003 | Prototype is reference only | Commit `20547b2d` is research input and a call-site map; it is not cherry-picked as-is. | Technical | High | Open |
| C-004 | Tracker relationships untouched | The `#2561 blockedBy #2560` link is reported, not edited. | Business | Medium | Open |
| C-005 | PR workflow | Topic branch from `main`, draft PR, the operator merges. | Business | High | Open |

### Key Entities

- **Compat delegate**: a bridge definition that forwards to a seam; 36 in scope.
- **Back-edge**: a seam's deferred lookup of a name on the bridge; those to delegated names are removed.
- **Public re-export**: `get_or_start_run`, `build_operational_context_for_claim`; kept, identical objects.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The runtime bridge shrinks by at least 500 lines and contains 0 "Thin compat delegate" docstrings. — [build] · no-op passable: no
- **SC-002**: 0 seam lookups through the bridge reach a name the bridge does not own. — [build] · no-op passable: no
- **SC-003**: The runtime_bridge test surface has 0 failures, and every deleted test is named with its reason in the PR. — [ratchet] · no-op passable: yes — paired with SC-001 on the same tree
- **SC-004**: The two public re-exports resolve to the seam's same objects, and all of their CLI callers' tests pass. — [ratchet] · no-op passable: yes — paired with SC-001

## Assumptions

- The guard test `tests/runtime/test_bridge_compat_surface.py` was already deleted (#3285); nothing else pins the delegates except `test_no_dead_symbols`'s façade list.
- The production callers listed in #2633 reach only the two kept re-exports (plus names the bridge still owns, such as `query_current_state`), so #2633's "repoint live callers" is satisfied without leaving `src/runtime/next/`.
- `tests/runtime/test_reassess_under_lock.py` fails on a dirty worktree for environmental reasons; it is run on a clean tree.

## Out of Scope / Deferred

- The stale `runtime_bridge._build_discovery_context` docstring mention in `src/specify_cli/mission_loader/command.py:204` (outside the package boundary).
- The stale docstring in `src/specify_cli/post_merge/retrospective_terminus.py:216-221` (describes a "thin `runtime_bridge` compat delegate" and a live `runtime_bridge` lookup that no longer exist; outside the package boundary, C-001).
- Pre-existing, order-dependent failure #5817: `Unknown mission type None` in `test_owned_next_runtime.py`, `test_next_advance_first_contact_5310.py` and `test_next_command_integration.py::TestNextCommandImplementState` when co-scheduled after the polluter `tests/specify_cli/next/test_runtime_bridge_composition.py::test_composition_success_skips_legacy_dispatch`. Present at the mission base; classified, not fixed here.
- The tracker's `#2561 blockedBy #2560` link.
- #2560 (query/answer seam extraction) and #2562 (composition-advance dedup); `provide_decision_answer`'s `# noqa: C901` belongs with #2562.
