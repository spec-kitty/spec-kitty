# Implementation Plan: Accept fails closed on a stale or pending acceptance matrix

**Branch**: `claude/project-thread-zj01ct` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/accept-fails-closed-01M3HS4V/spec.md`

## Summary

`acceptance-matrix.json` has one locked read-modify-write today, in the verdict command (#4858). Accept's gate writes back an unlocked pre-check snapshot (#4974), and orchestrator-api `accept-mission` never looks at the readiness verdict (#4934). The plan:

1. Lift the verdict command's locked re-read/splice/write into one shared seam in `acceptance/matrix.py` (#4887).
2. Route the verdict command and the accept gate through it. The gate splices only the rows it owns, per the spec's row ownership rule, and judges the fresh matrix.
3. Add a locked pre-stamp verdict re-check around the acceptance record, shared by host accept and accept-mission.
4. Make accept-mission refuse on a not-ok summary.
5. Add a call-site gate so no production writer bypasses the seam.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (existing); no new dependencies, so the supply-chain checks have nothing to assess.
**Storage**: files: `kitty-specs/<mission>/acceptance-matrix.json` and `meta.json`, on the placement surface the gate context resolves (primary or coord)
**Testing**: pytest. Issue-pinned `@pytest.mark.regression` tests are written RED first through the CLI entry points (`spec-kitty accept`, `spec-kitty orchestrator-api accept-mission`, `spec-kitty agent mission acceptance-verdict`), then kept as focused tests. The architectural call-site gate carries a self-mutation test.
**Target Platform**: Linux, macOS, Windows (file lock via the existing `machine_file_lock`)
**Project Type**: single (the `src/specify_cli` CLI package)
**Performance Goals**: The locked span covers re-read, splice and write only; checks run outside it (NFR-001). The bounded 10 s lock wait is reused (NFR-002).
**Constraints**: C-001 through C-006 in the spec. Complexity ≤ 15 per function. ruff, ruff format and mypy clean.
**Scale/Scope**: about 6 production modules, 1 architectural gate, 2 contract docs and 1 skill reference.

## Charter Check

- **Single canonical authority**: one matrix RMW seam replaces the command-local copy. accept-mission reuses `collect_feature_summary`/`summary.ok` (C-001) and the shared guarded record (FR-010). Pass.
- **ATDD-first / red-first**: every [build] FR gets a regression test RED on the planning base first (SC-004). Pass.
- **Close defect class by construction (DIRECTIVE_043)**: FR-006 is a non-vacuous call-site gate with a self-mutation test and a shrink-only allowlist. Pass.
- **Locality / smallest viable diff**: `issue_verdict.py` convergence, post-consolidation routing and matrix authoring are deferred (C-005). Pass.
- **Terminology canon**: Mission, never feature, in all new prose and messages. The orchestrator skill is touched, so run `tests/architectural/test_no_legacy_terminology.py`. Pass.
- **No full heavy suites in mission work**: targeted test files plus the named architectural gate files only. Pass.

## Project Structure

### Documentation (this mission)

```
kitty-specs/accept-fails-closed-01M3HS4V/
├── spec.md
├── plan.md          # this file
├── research.md      # design decisions + squad dispositions
├── tasks.md         # /spec-kitty.tasks
└── tasks/           # WP prompt files
```

### Source Code (repository root)

```
src/specify_cli/acceptance/
├── matrix.py            # NEW seam: locked_reread_splice_and_write(); NEW owned-row splice helper; NEW locked pre-stamp guard
├── gates_core.py        # accept gate routes its write through the seam; judges the fresh matrix; records the matrix dir
└── __init__.py          # AcceptanceSummary carries the matrix dir; _commit_acceptance_meta records under the guard
src/specify_cli/cli/commands/
├── accept.py                    # lock-timeout diagnostic (fail closed)
└── agent/acceptance_verdict.py  # private copy removed; calls the shared seam
src/specify_cli/orchestrator_api/
├── commands.py          # accept_mission: summary.ok guard + guarded record
└── envelope.py          # CONTRACT_VERSION 1.7.0 + ledger
docs/api/orchestrator-api.md
src/charter/offering/skills/spec-kitty-orchestrator-api-operator/{SKILL.md,references/orchestrator-api-contract.md}
tests/architectural/test_acceptance_matrix_write_seam.py      # NEW call-site gate
tests/specify_cli/acceptance/ ...                             # seam, splice, guard tests + #4974 regressions
tests/orchestrator_api/test_issue_4934_accept_mission_readiness.py
tests/specify_cli/cli/commands/ (accept CLI #4891 pin)
```

**Structure Decision**: Everything stays inside `specify_cli` (top layer). The seam lives next to the writers it guards, in `acceptance/matrix.py`, because putting an acceptance type in `status/` would invert ownership. Lock primitives are imported from `specify_cli.status`.

## Implementation Concern Map

### IC-01 — Shared locked matrix write seam

- **Purpose**: Make the locked re-read, splice, write and optional commit the one way to read-modify-write the acceptance matrix.
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-002, C-004
- **Affected surfaces**: `acceptance/matrix.py`, `cli/commands/agent/acceptance_verdict.py`
- **Sequencing/depends-on**: none
- **Risks**:
  - The #4858 tests spy on `feature_status_lock` at the verdict module's import site. Keep the spy targets working, or re-point them at the seam module.
  - `commit=True` keeps committing under the lock. That is existing behaviour, not a regression.

### IC-02 — Accept gate owns only the rows it judged

- **Purpose**: Stop accept from erasing concurrent verdicts and judge the fresh matrix.
- **Relevant requirements**: FR-003, FR-004, FR-005, C-003
- **Affected surfaces**: `acceptance/gates_core.py` (`_evaluate_acceptance_matrix`), `acceptance/matrix.py` (owned-row splice helper), `cli/commands/accept.py` (lock-timeout mapping)
- **Sequencing/depends-on**: IC-01
- **Risks**:
  - `--no-commit` must stay commit-free, so the seam is called with `commit=False`.
  - Diagnose mode writes nothing and takes no lock.
  - `_evaluate_acceptance_matrix` is near the complexity ceiling; extract helpers.

### IC-03 — Locked pre-stamp verdict re-check

- **Purpose**: Close the window between the gate's write and `record_acceptance`.
- **Relevant requirements**: FR-010, SC-005
- **Affected surfaces**:
  - `AcceptanceSummary`: a new optional `acceptance_matrix_dir` field, set by the gate.
  - `acceptance/matrix.py`: a new guard that is a context manager. It takes the lock, re-reads, refuses unless the verdict is `pass` or `pass_pending_consolidation`, and yields.
  - `_commit_acceptance_meta`: `record_acceptance` is called inside the guard; the git commit stays outside it.
- **Sequencing/depends-on**: IC-02 (the gate populates the dir)
- **Risks**:
  - Nothing inside the guard may take the lock from a subprocess. Only the in-process `record_acceptance` / `write_meta` run inside it.
  - A summary with no matrix dir (gate not run) skips the guard. That is only reachable when `summary.ok` already required the gate, so assert it.

### IC-04 — accept-mission applies the host readiness verdict

- **Purpose**: One readiness authority for host accept and orchestrator accept.
- **Relevant requirements**: FR-007, FR-009, SC-003, C-001, C-002
- **Affected surfaces**: `orchestrator_api/commands.py` (`accept_mission`), `orchestrator_api/envelope.py`, `docs/api/orchestrator-api.md`, the orchestrator-api operator skill and its contract reference, `tests/specify_cli/orchestrator_api/test_contract_version.py`
- **Sequencing/depends-on**: IC-03 (the guarded record)
- **Risks**:
  - Two positive fixtures (`test_all_done_accepted`, `test_all_approved_accepted`) need a real acceptable mission: a lanes manifest, spec and plan, claim events with an agent, convention dirs, a passing matrix and a real git repo.

### IC-05 — Call-site gate and #4891 CLI pin

- **Purpose**: Make the lock structurally unavoidable, and pin #4891 at the CLI.
- **Relevant requirements**: FR-006, FR-008, SC-002
- **Affected surfaces**:
  - New `tests/architectural/test_acceptance_matrix_write_seam.py`. It is an AST scan of `src/` for Name, Attribute and aliased calls to `write_acceptance_matrix` and `write_and_commit_acceptance_matrix`.
  - Per-function allowlist: the seam itself, `matrix.py::scaffold_acceptance_matrix` (and its commit wrapper, if separate), and `post_consolidation.py::verify_deferred_invariants`, which has no production caller and is deferred.
  - The accept CLI regression test.
- **Sequencing/depends-on**: IC-02 (the gate's raw call must be gone first)
- **Risks**:
  - Copy the census style of `tests/architectural/test_guard_capability_call_sites.py`.
  - The self-mutation test must plant both an alias and an attribute call.
