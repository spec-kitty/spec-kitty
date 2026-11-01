# Implementation Plan: Orchestrator contract version, one source of truth in tests

**Branch**: `issue-6578-orchestrator-contract-version-single-source` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/orchestrator-contract-version-single-source-01M68ZRJ/spec.md`
**Input**: Mission specification from `kitty-specs/orchestrator-contract-version-single-source-01M68ZRJ/spec.md`

## Summary

`tests/orchestrator_api/test_origin_freshness_envelopes.py:29` declares
`_CONTRACT_VERSION = "1.21.0"` and compares the emitted envelope against it at lines 122 and 176.
That literal is a second source of truth for a value
`src/specify_cli/orchestrator_api/envelope.py:176` already exports as `CONTRACT_VERSION`, and it has
been hand-re-pinned eleven times (1.11.0 → 1.21.0); #6578 was filed on the occasion it had been left
one bump stale. The transient red is gone (the literal was re-pinned in `c678037c8b`); the drift
class is not.

The change is three parts, all in tests:

1. **Read the exported constant** in the origin-freshness module — `from
   specify_cli.orchestrator_api.envelope import CONTRACT_VERSION`, used by both assertions, and no
   literal contract version declared in the file.
2. **Detect the reintroduction** — a fast, fixture-free guard in
   `tests/specify_cli/orchestrator_api/test_contract_version.py` (the module that owns the canonical
   pin) that scans `tests/**/*.py` for a quoted semver on a line naming a contract version and fails,
   naming every `path:line`, for any file except itself. It is RED on today's tree at
   `test_origin_freshness_envelopes.py:29` and GREEN after part 1.
3. **Remove the prose drift** in the canonical pin module: its docstring claims
   "``CONTRACT_VERSION`` is currently ``"1.3.0"`` (envelope.py:28)" while the pin asserts 1.21.0.

`src/` is untouched; `CONTRACT_VERSION` stays `1.21.0`.

## Technical Context

**Language/Version**: Python 3.11 (`.python-version` = 3.11; the CLI targets 3.11+)
**Primary Dependencies**: `pytest` only — the guard reads files with `pathlib` and `re` from the
standard library, and imports `specify_cli.orchestrator_api.envelope.CONTRACT_VERSION` (already
exported; `envelope.py`'s `__all__` lists it)
**Storage**: none — the guard reads source text from the working tree; no fixtures, no git, no
subprocess
**Testing**: pytest. The touched integration module is marked `integration` + `git_repo` and drives
the real CLI through `tests/terminus/conftest.run_terminus`; the guard is marked `fast` (matching
`test_contract_version.py`'s existing module-level `pytestmark`)
**Target Platform**: Linux/macOS developer and CI checkouts (pure Python, no OS-specific code)
**Project Type**: single project (Python CLI)
**Performance Goals**: the guard reads `tests/**/*.py` once (4,282 files, 69 MB) and stays in
single-digit seconds — **0.4 s idle, 0.9–4.1 s under load on this shared host** — the same order as the
existing `tests/architectural/` source-scanning gates — NFR-001
**Constraints**: `src/` byte-identical (NFR-003); the two origin-freshness refusals keep every
non-version assertion (C-002); the canonical literal stays in exactly one file (C-003)
**Scale/Scope**: 2 test modules touched, 1 of them by 3 lines plus a 20-line guard; 0 production
lines; 0 new modules

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status | Note |
|---|---|---|
| Single canonical authority | PASS | The version keeps exactly one authority (`envelope.CONTRACT_VERSION`); the guard makes the second copy impossible instead of documenting the rule again. |
| Architectural alignment | PASS | Tests only; no module boundary, no new fixture, no shared helper that would hide the pin. |
| ATDD-first / DIRECTIVE_034 (red-first) | PASS | The guard is written first and is RED on today's tree for the reported reason (line 29), then part 1 turns it GREEN. The RED run is recorded. |
| DIRECTIVE_041 (judge the test; stale → re-pin, valid → fix the product) | PASS | The pin is judged stale-and-misplaced: the assertion is valid but its right-hand side must not be a literal. The assertion is kept, the literal is removed. |
| DIRECTIVE_044 canonical-source-unification | PASS | Converges on the shape three sibling modules already use (`test_envelope_unit.py:34`, `test_wp_lifecycle_structured_actor_6400.py:46,174`). |
| DIRECTIVE_024 Locality of Change / smallest-viable-diff | PASS | Two test modules, no source change, no new file. The guard lands in the module whose stated purpose is pinning the version, not in a new gate package. |
| DIRECTIVE_025 Boy Scout (inside the touched set) | PASS | The stale "currently ``1.3.0``" sentence in the touched module is corrected as part of the same goal (it is the same defect — a second place spelling a version). |
| DIRECTIVE_043 gate non-vacuity | PASS | The guard carries a self-mutation check (a synthesized offending line must be reported), a scanned-file floor (a zero-file scan fails, matching `tests/architectural/test_no_assert_swallowed_by_own_handler.py`'s `MIN_SCANNED_FILES`), and a re-inserted literal must be detected. Its RED-on-today proof is the pre-fix tree itself. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS | Targeted suites only: the two touched modules plus the three sibling envelope modules. |
| Pre-existing Failure Reporting Rule | PASS | Any suite red that is not caused by this diff is cited in the PR's `## Deferred`, never papered over. |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/orchestrator-contract-version-single-source-01M68ZRJ/
├── plan.md              # This file
├── research.md          # Discovery grounding (reproduction, eleven re-pins, decisions)
├── spec.md              # Mission specification
├── tasks.md             # /spec-kitty.tasks output
└── tasks/               # Work-package files
```

### Source Code (repository root)

```
tests/orchestrator_api/
└── test_origin_freshness_envelopes.py        # - _CONTRACT_VERSION literal
                                             # + `from specify_cli.orchestrator_api.envelope import CONTRACT_VERSION`
                                             #   used by the two refusal assertions (122, 176)
                                             # ~ module docstring: the "(contract 1.11.0)" claim goes

tests/specify_cli/orchestrator_api/
└── test_contract_version.py                 # + guard test (fast, no fixture): no test module but
                                             #   this one may spell a contract version
                                             # ~ docstring: drop the stale "currently 1.3.0" claim
```

**Structure Decision**: single project. The guard belongs to the module that owns the canonical pin
because that module already reads `envelope.py`'s source text (`inspect.getsource`) and is already
`pytestmark = [pytest.mark.fast]`; a new gate package or a `conftest` fixture would add a file and
still leave the allowlist rule outside the pin's owner.

## Implementation Concern Map

### IC-01 — Origin-freshness assertions read the exported constant

- **Purpose**: Remove the second source of truth so a `CONTRACT_VERSION` bump never edits this file.
- **Relevant requirements**: FR-001, FR-005, C-002, C-003, SC-001, SC-003
- **Affected surfaces**: `tests/orchestrator_api/test_origin_freshness_envelopes.py` (import,
  lines 29/122/176, module docstring's `(contract 1.11.0)` claim)
- **Sequencing/depends-on**: none
- **Risks**: the module is `integration` + `git_repo` and takes ~150 s, so the fix must not disturb
  the fixtures; only the compared value changes. Deleting the assertion is the tempting cheat —
  refused (FR-005): the subprocess-built envelope must still be shown to carry the constant.

### IC-02 — The guard that detects a reintroduced literal

- **Purpose**: Close the drift class by detection: any test module outside the canonical pin that
  spells a contract version fails a fast test naming `path:line`.
- **Relevant requirements**: FR-002, FR-003, NFR-001, NFR-002, SC-001, SC-002, SC-004
- **Affected surfaces**: `tests/specify_cli/orchestrator_api/test_contract_version.py` (new test)
- **Sequencing/depends-on**: written and RED **before** IC-01; GREEN after it
- **Risks**: false positives on legitimate references. The scan matches only a quoted `X.Y.Z` on a
  line that also names a contract version, so `f'CONTRACT_VERSION = "{envelope_module.CONTRACT_VERSION}"'`
  (line 101), the `CONTRACT_VERSION_MISMATCH` error code, and the `"api_version": "3.0.0"` fixture
  payload in `test_fail_message_preserved.py:67` stay unflagged. The `tests/`-only scope keeps
  `envelope.py`'s constant and its historical changelog comment block out.

### IC-03 — The canonical pin's prose states only what it owns

- **Purpose**: A maintainer reading the pin's module docstring must not be told a version the
  assertion contradicts.
- **Relevant requirements**: FR-004, SC-003
- **Affected surfaces**: `tests/specify_cli/orchestrator_api/test_contract_version.py` (module
  docstring: the "currently ``1.3.0``" sentence and the superseded-narrative lead-in)
- **Sequencing/depends-on**: IC-02 (same module, one commit boundary is fine)
- **Risks**: the docstring is long historical narrative that other missions rely on as a record.
  Keep every superseded entry; change only the sentence that claims a *current* value.

### IC-04 — Red-first evidence, mutation proof, and the record

- **Purpose**: Make the mission's claim checkable: the guard RED before, GREEN after, and RED again
  under a re-inserted literal (non-vacuity), recorded in the WP review cycle.
- **Relevant requirements**: SC-002, SC-004, DIRECTIVE_043
- **Affected surfaces**: the WP's `review-cycle-*.md`, the mission tracers
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: a mutation check that edits the real file must restore it (verify `git diff` is clean
  afterwards) or the tree ships the mutation.

## Phase 0 / Phase 1 notes

Phase 0 research is `research.md` (grounding, the eleven re-pins, sibling precedent, scan dry run,
the five decisions). Phase 1 has no data model, no API contract and no quickstart: this is test
remediation, so per the plan prompt the mission records `"contracts": "none"` with a rationale in
`meta.json` rather than creating an empty `contracts/` directory.
