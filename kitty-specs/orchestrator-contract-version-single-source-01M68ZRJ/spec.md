# Mission Specification: Orchestrator contract version, one source of truth in tests

**Mission Branch**: `kitty/mission-orchestrator-contract-version-single-source-01M68ZRJ`
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6578 — `tests/orchestrator_api/test_origin_freshness_envelopes.py` pins `contract_version` to a literal while the envelope has moved; the pin must read the exported constant so a version bump cannot leave a stale pin behind"

## Problem

`tests/orchestrator_api/test_origin_freshness_envelopes.py` exists to prove that
`accept-mission` and `consolidate-mission` refuse on stale origin evidence. It also pins the
envelope's `contract_version` to a **literal** — `_CONTRACT_VERSION = "1.21.0"` at line 29,
compared at lines 122 and 176. That literal is a second source of truth for a value that
`specify_cli/orchestrator_api/envelope.py` already exports as `CONTRACT_VERSION`.

The cost is already measured. `git log -L 29,29` on that file shows the constant hand-re-pinned
**eleven** times — 1.11.0, 1.12.0, 1.13.0, 1.14.0, 1.15.0, 1.16.0, 1.17.0, 1.18.0, 1.19.0, 1.20.0,
1.21.0 — each bump forcing an edit to a file whose subject is origin freshness and never the
contract version. #6578 was filed at the moment the pin was one bump stale (`_CONTRACT_VERSION`
was `"1.14.0"` while the envelope emitted `1.15.0`), and it went red:

```text
E   AssertionError: assert '1.15.0' == '1.14.0'
FAILED tests/orchestrator_api/test_origin_freshness_envelopes.py::test_accept_mission_refuses_stale_status_evidence
FAILED tests/orchestrator_api/test_origin_freshness_envelopes.py::test_consolidate_mission_refuses_stale_status_evidence
```

The transient red is gone because the literal was re-pinned to `1.21.0` (commit `c678037c8b`). The
**defect class is not**: the same file will go red again on the next `CONTRACT_VERSION` bump unless
someone remembers. Nothing in the tree makes the next re-pin unnecessary, and nothing detects a
stale pin.

The repository already knows the right shape. Three sibling test modules read the exported
constant instead of spelling a version — `tests/agent/test_envelope_unit.py:34`,
`tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py:46,174` and
`tests/agent/test_orchestrator_commands_integration.py:382` all compare against
`CONTRACT_VERSION`. `test_origin_freshness_envelopes.py` is the outlier.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A contract-version bump never edits an origin-freshness test (Priority: P1)

A maintainer adds a verb or an error code and bumps `CONTRACT_VERSION` in
`envelope.py`. They run the orchestrator-api tests. The origin-freshness envelope tests compare the
emitted envelope against the exported constant, so they stay green without being touched: the bump
touched one place, and only one place.

**Why this priority**: This is the reported defect. The pin has already cost eleven re-pins and one
filed issue; the value is that a future bump cannot leave a stale pin behind.

**Independent Test**: On a tree where `tests/orchestrator_api/test_origin_freshness_envelopes.py`
imports `CONTRACT_VERSION`, change nothing else and run
`pytest tests/orchestrator_api/test_origin_freshness_envelopes.py -q` — it passes; then grep the
file for a quoted semver next to `contract_version` — there is none.

**Acceptance Scenarios**:

1. **Given** the origin-freshness envelope tests, **When** the module is read, **Then** its
   `contract_version` assertions compare the envelope to
   `specify_cli.orchestrator_api.envelope.CONTRACT_VERSION` and the module declares no literal
   contract version.
2. **Given** a hypothetical `CONTRACT_VERSION` bump, **When** only `envelope.py` changes, **Then**
   the origin-freshness envelope tests need no edit and still pass.

---

### User Story 2 - A stale pin fails a fast test instead of drifting silently (Priority: P1)

A contributor (or an agent) reintroduces a literal contract-version pin in a test. A fast unit test
in the module that owns the canonical pin fails immediately, names the offending file and line, and
says what to import instead — before the literal can rot for a release.

**Why this priority**: Fixing today's literal only moves the problem to the next contributor. The
durable half of #6578 is detection: the invariant "only the canonical pin test spells a contract
version" has to be enforced, not remembered.

**Independent Test**: On the pre-fix tree the guard test is RED naming
`tests/orchestrator_api/test_origin_freshness_envelopes.py:29`; after the fix it is GREEN, and
re-inserting a literal makes it RED again (mutation).

**Acceptance Scenarios**:

1. **Given** any test module outside the canonical pin module spells a contract version next to
   `contract_version` (an assignment or a comparison), **When** the guard test runs, **Then** it
   fails naming every offending `path:line`.
2. **Given** the tree after this mission, **When** the guard test runs, **Then** it passes with the
   canonical pin module as the only file that spells a version.
3. **Given** the guard test, **When** it scans a legitimate reference — `CONTRACT_VERSION`
   interpolated into a string, or the unrelated `CONTRACT_VERSION_MISMATCH` error code — **Then**
   it does not flag it.
4. **Given** a checkout where the scan finds no test files at all (a broken root, a moved tree),
   **When** the guard runs, **Then** it fails on a scanned-file floor instead of passing
   vacuously.

---

### User Story 3 - The canonical pin is the only place, and its prose cannot drift (Priority: P2)

The one intentional literal stays in `tests/specify_cli/orchestrator_api/test_contract_version.py`,
where bumping it is the point of the test. Its docstring stops asserting a *different* version
(```CONTRACT_VERSION`` is currently ``"1.3.0"```, `it read ``1.13.0```, …), so a reader is not told
a version the file no longer pins.

**Why this priority**: The canonical module is where a maintainer looks to answer "what version is
the contract?". Stale prose there is the same drift in a place no test can see.

**Independent Test**: Read the module docstring after the change: every version it states is either
the current pin or explicitly historical narrative tied to the commit it describes, and no sentence
claims a current value the assertion contradicts.

**Acceptance Scenarios**:

1. **Given** the canonical pin module, **When** it is read, **Then** exactly one assertion states
   the current contract version, and prose that names a *current* value matches it.

---

### Edge Cases

- A test that must carry a *different* version to exercise `CONTRACT_VERSION_MISMATCH` builds it
  from the constant (`f"{CONTRACT_VERSION}-bogus"`); a spelled literal next to `contract_version`
  is flagged by design, because that is the same second source of truth #6578 is about. A payload
  that only sets `"api_version": "3.0.0"` (`tests/specify_cli/orchestrator_api/test_fail_message_preserved.py:67`)
  names no contract version and stays untouched and unflagged.
- The guard scans `tests/` only. `src/specify_cli/orchestrator_api/envelope.py` legitimately spells
  the version in its constant and its changelog comment block; it is out of the scan's scope.
- A future `docs/` test that quotes a version in prose is out of scope; the invariant is about
  test *assertions* on the emitted envelope, not documentation.
- Nested test directories (`tests/**/`) and non-`.py` files: the scan is `tests/**/*.py`, so a
  fixture JSON is not scanned.
- The exemption is derived from `__file__`, so renaming the canonical pin module re-homes the
  exemption with it; nothing fails, and that is accepted — the guard's job is to keep every *other*
  test module honest, and the pin module is identified by being the file the guard lives in.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Origin-freshness assertions read the exported constant | As a maintainer, I want the origin-freshness envelope tests to compare against `envelope.CONTRACT_VERSION` so that a version bump never needs an edit in that file. | High | Open | [build] | no — the pre-fix module declares `_CONTRACT_VERSION = "1.21.0"`, asserted by FR-002's guard on the same tree |
| FR-002 | A stale or reintroduced literal fails a fast guard test | As a maintainer, I want a fast unit test that fails when any test module outside the canonical pin spells a contract version, so that the drift class is closed by detection rather than memory. | High | Open | [ratchet] | no — RED on today's tree (`test_origin_freshness_envelopes.py:29`), GREEN only after FR-001 |
| FR-003 | The guard names the offender, the remedy, and cannot scan nothing | As a contributor, I want the guard's failure to name every offending `path:line` and the import to use instead, and I want a scan that found no files at all to fail rather than pass, so that the fix is obvious and the gate cannot go vacuous. | Medium | Open | [build] | no — the message is asserted on a synthesized offending line, and a scanned-file floor makes a zero-file scan red |
| FR-004 | The canonical pin's prose carries no stale current version | As a maintainer, I want the canonical pin module to state the version it actually asserts, so that the one place that owns the pin cannot mislead. | Medium | Open | [build] | no — the stale sentence is quoted by the acceptance check |
| FR-005 | The existing assertions keep their strength | As a reviewer, I want the envelope's `contract_version` still asserted (not deleted) so that a hand-built payload omitting or hardcoding the field still fails. | High | Open | [ratchet] | no — deleting the two assertions is the cheap cheat; the guard and the retained assertion both refuse it |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Fast guard | The guard reads `tests/**/*.py` once (4,282 files, 69 MB) and completes in single-digit seconds — measured 0.4 s idle and 0.9–4.1 s under load on a shared 20-agent host, matching the existing source-scanning gates under `tests/architectural/` — with no fixture, no git operation, no subprocess, and the module's existing `pytest.mark.fast` marker. | Performance | High | Open |
| NFR-002 | Zero false positives at the tip | After the fix, the guard's scan over `tests/**/*.py` skips exactly one file (the canonical pin module, exempt not reported) and yields 0 offenders on today's tree; every other file that mentions `CONTRACT_VERSION` is a legitimate reference the scan does not flag. | Reliability | High | Open |
| NFR-003 | No product change | `src/` is byte-identical apart from nothing at all — this mission changes tests only. `CONTRACT_VERSION` stays `"1.21.0"`. | Technical | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Do not bump the contract | The mission must not change `CONTRACT_VERSION`, `MIN_PROVIDER_VERSION`, or the envelope changelog block; a version bump is a separate, deliberate change. | Technical | High | Open |
| C-002 | Do not weaken the origin-freshness tests | The two tests keep their `success`, `error_code`, `preflight_error_code(s)` and `origin_freshness` assertions; only the source of the compared version changes. | Technical | High | Open |
| C-003 | Keep the canonical pin in one place | The literal version stays in `tests/specify_cli/orchestrator_api/test_contract_version.py`; the mission must not move it into a shared fixture (that would make the pin untestable against a real bump). | Technical | High | Open |

### Key Entities

- **Exported contract constant**: `CONTRACT_VERSION` in
  `src/specify_cli/orchestrator_api/envelope.py` — the single source of truth for the wire contract
  version, stamped into every envelope by `make_envelope`/`fail_envelope`.
- **Canonical pin**: the one intentional literal, in
  `tests/specify_cli/orchestrator_api/test_contract_version.py`, which pins the exact value so a
  forgotten bump cannot pass.
- **Guard test**: the fast test in the canonical pin module that enforces "no other test module
  spells a contract version".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A scan of `tests/**/*.py` for a quoted semver on a line naming a contract version
  returns exactly one file, `tests/specify_cli/orchestrator_api/test_contract_version.py`, and 0
  hits in `tests/orchestrator_api/test_origin_freshness_envelopes.py` (today: 1 hit at line 29). — [build] · no-op passable: no
- **SC-002**: The guard test is RED on the pre-fix tree, naming
  `tests/orchestrator_api/test_origin_freshness_envelopes.py:29`, and GREEN after the fix — both
  runs recorded in the work package's review cycle. — [ratchet] · no-op passable: no — the RED run is the positive control for the GREEN one
- **SC-003**: `pytest tests/specify_cli/orchestrator_api/test_contract_version.py
  tests/orchestrator_api/test_origin_freshness_envelopes.py -q` passes with 0 failures, the
  origin-freshness file still asserting `contract_version` on both refusal tests. — [build] · no-op passable: no
- **SC-004**: A mutation check — re-inserting a literal pin into a scratch copy of the
  origin-freshness test makes the guard fail — is recorded, so the guard is proven non-vacuous. — [ratchet] · no-op passable: no

## Out of Scope

- Bumping `CONTRACT_VERSION` (nothing in this issue asks for a new version).
- The `MIN_PROVIDER_VERSION` pin and its `test_min_provider_version_unchanged` narrator.
- Rewriting `test_contract_version.py`'s historical superseded-narrative blocks beyond the one
  sentence that claims a *current* version.
- Any source change under `src/`.
- Any other test module's handling of `contract_version` (the three that already import the
  constant are correct as they stand).

## Traceability

| Source | Requirement |
|--------|-------------|
| #6578 "Cause" (`_CONTRACT_VERSION = "1.14.0"` vs `CONTRACT_VERSION = "1.15.0"`) | FR-001, SC-001 |
| #6578 "The two assertions need to read the exported `CONTRACT_VERSION` … so a version bump cannot leave a stale pin behind" | FR-001, FR-002, SC-002 |
| #6578 reproduction (2 failed, 11 passed) | SC-003 |
| `git log -L 29,29` — eleven hand re-pins | FR-002, SC-002, SC-004 |
| Sibling precedent (`test_envelope_unit.py:34`, `test_wp_lifecycle_structured_actor_6400.py:46`) | FR-001, C-003 |
| Charter, single canonical authority + DIRECTIVE_041 (judge the test; stale → re-pin) | FR-004, C-002 |
