# Implementation Plan: CLI Boundary Robustness

**Branch**: `fix/cli-boundary-robustness` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/cli-boundary-robustness-01M2NQCB/spec.md`

## Summary

Harden three CLI boundary classes so the tool degrades gracefully and honors its
machine contract: (1) startup config-read (fail-soft at the import-time pointer
read; fail-loud with a named message at content-load; fold sibling unguarded
reads), (2) `--json` output integrity closed by construction (a shared
`cli/json_contract.py` error/empty envelope promoted out of doctor-private code, a
json-aware `get_project_root_or_exit`, and an enumeration gate — parse-universal +
shape-on-adopted), and (3) Typer default-leakage point-fixed with a behavioral
negative-assertion guard. ATDD-first throughout; red-first reproductions for the
P0 (#4600) and the exit-0-masking bug (#4643). Approach is a unification of
existing surfaces (the transport seam `CliConsole.emit_json` and the #4242 error
envelope already exist), not a greenfield build.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer (CLI), rich (console), ruamel.yaml (config parse) — **no new dependencies added or upgraded**
**Storage**: filesystem only — `.kittify/config.yaml`, `kitty-specs/`, `runtime` `version.lock`; N/A database
**Testing**: pytest; `CliRunner` for CLI integration + the new enumeration gate; `@pytest.mark.regression` issue-pinned red-first tests; existing frozen `tests/specify_cli/cli/commands/test_doctor_json_not_in_project.py` is the exit-code authority
**Target Platform**: cross-platform CLI (Linux, macOS, Windows 10+)
**Project Type**: single project (CLI library under `src/specify_cli/`)
**Performance Goals**: CLI ops < 2s for typical projects (charter); the added `except UnicodeDecodeError` is happy-path-free
**Constraints**: `bootstrap/` import purity (stdlib+kernel only, no import-time `os.environ`); honor the test-frozen #4242 envelope + per-command exit codes; single canonical error-envelope authority (DIRECTIVE_044); ruff + mypy clean, whole-repo `ruff format --check .`; client-repo — no zeitgeist/saas API-contract edits; Terminology Canon (Mission, never Feature)
**Scale/Scope**: ~100 `--json`-capable command files subject to the *parseability* contract; ~10–12 owned files for the *shape* contract + point-fixes; full cross-repo shape convergence (~12 residual shapes) deferred (spec Deferred Follow-ups)

## Charter Check

*GATE: Must pass before Phase 0. Re-checked after Phase 1.*

| Charter rule | Status | How this plan satisfies it |
|---|---|---|
| ATDD-first (C-011) | ✅ | Every WP opens with a failing-first acceptance test committed before implementation; reviewer verifies red-on-base / green-on-final. |
| Red-main & red-first (SO#9, ADR 2026-07-17-1) | ✅ | #4600 (P0) and #4643 land issue-pinned `@pytest.mark.regression` reproductions through the pre-existing entry point. |
| Single canonical authority (DIRECTIVE_044) | ✅ | One `cli/json_contract.py` error/empty envelope; `_doctor_shared` re-exports (no second authority); NFR-004. |
| Architectural integrity (DIRECTIVE_001) | ✅ | Envelope promotion is intra-`specify_cli` (no LayerRule/seam violation, verified by paula-patterns); WP01 preserves bootstrap import purity. |
| Tiered rigour + DDD | ✅ | Core boundary logic (envelope, config read, guard) gets full rigour + focused tests; display paths freeze as baseline. |
| Campsite / tidy-first (SO#2, DIRECTIVE_025) | ✅ | Domain-matched folds only (see Implementation Concern Map); orthogonal debt frozen as baseline; scout for `mission_type.py`. |
| Locality of change (DIRECTIVE_024) | ✅ | WPs sliced by owned-file, no overlap; deferred follow-ups filed rather than scope-crept. |
| Terminology Canon | ✅ | Mission-only language; no `feature*` identifiers introduced. |
| No version prescription | ✅ | Plan assigns no release/version number. |
| Supply-chain safety (DIRECTIVE_051) | ✅ N/A | No dependency added/upgraded/removed → no registry/lifecycle-script exposure. Recorded in research.md. |

**No violations → Complexity Tracking empty.**

## Project Structure

### Documentation (this mission)

```
kitty-specs/cli-boundary-robustness-01M2NQCB/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (json-envelope + enumeration-gate contracts)
├── research/            # post-spec-squad-findings.md (planning input)
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── bootstrap/env_file.py                     # WP01: import-time read fail-soft (+UnicodeDecodeError)
├── charter/activation/consistency_check.py   # WP01: config-mapping load guard
├── runtime/doctor.py                         # WP01: version-file read guard (+encoding)
├── core/{worktree,vcs/git,git_ops}.py        # WP01: encoding= on git-metadata reads (campsite)
├── cli/json_contract.py                      # WP02: NEW shared error/empty envelope + emit guards
├── cli/commands/_doctor_shared.py            # WP02: re-export envelope (docstring update)
├── cli/helpers.py                            # WP02: json-aware get_project_root_or_exit + converge exit_git_resolution_failure
├── cli/commands/context.py                   # WP03: #4597 OptionInfo + #4601 + context siblings
├── cli/commands/mission_type.py              # WP04: #4598 call-site + #4601 show + siblings (SCOUT)
├── cli/commands/charter/mission_type.py      # WP04: #4600 Instance-2 boundary + list error paths
├── cli/commands/agent/tasks_status_cmd.py    # WP05: #4643 empty path
├── cli/commands/glossary.py                  # WP05: error/empty paths
├── agent_utils/status.py                     # WP05: data-builder boundary (drop error key / prose)
├── cli/commands/{archive,materialize}.py     # WP05: #4533 AT-RISK adoption
├── cli/commands/{verify,validate_encoding,research,validate_tasks,dashboard}.py  # WP05: get_project_root_or_exit opt-in
└── ...
tests/
├── architectural/test_cli_console_single_seam.py  # WP06: extend with enumeration gate (or NEW test_json_contract_enumeration.py)
├── specify_cli/bootstrap/                          # WP01 red-first #4600
├── specify_cli/cli/commands/                       # WP02–WP05 adoption + red-first #4643
└── ...
```

**Structure Decision**: single-project CLI. Seams (`json_contract.py`, config-read
hardening) precede adoption; the enforcement gate lands last so it flips green only
once adoption is complete.

## Parallel Work Analysis

### Dependency Graph

```
WP01 (config-read P0, bootstrap layer) ─┐   [independent — lands FIRST as isolated hotfix]
                                        │
WP02 (cli/json_contract.py seam) ───────┼─→ WP03 (context.py)   ─┐
WP03depends WP02                        │   WP04 (mission_type.*) │
                                        │   WP05 (tasks/glossary/ ┼─→ WP06 (enumeration gate
WP02 also enables WP04, WP05            │        status/archive/  │        + OptionInfo guard)
                                        │        materialize/     │   [flips green after adoption]
                                        │        gpre-caller opt-in)┘
```

- **WP01** is fully independent (bootstrap layer, zero file overlap) and is the P0 — lands first, shippable alone.
- **WP02** is the seam; **WP03/WP04/WP05** each depend on WP02 (they import the promoted envelope + json-aware helper). WP03/WP04/WP05 are mutually independent (disjoint owned files) → parallel after WP02.
- **WP06** depends on WP03+WP04+WP05 (its enumeration/shape assertions and OptionInfo guard go green only once adoption completes).

### Work Distribution

- **Sequential-first**: WP01 (P0 hotfix), WP02 (seam).
- **Parallel streams (after WP02)**: WP03, WP04, WP05 — disjoint file ownership.
- **Agent assignments (no overlap)**: one implementer per WP owned-file set (see Project Structure). `mission_type.py` (1720 lines) → dispatch a campsite scout in WP04.
- **Terminal**: WP06 (arch/behavioral gates).

### Coordination Points

- Lane consolidation is `spec-kitty merge` into local `main` only (never origin); PR from `fix/cli-boundary-robustness` → `main` is operator-merged.
- Integration verification: WP06's enumeration gate is the cross-WP integration check (every adopted command's error/empty path honored).

## Implementation Concern Map → Work Packages

| WP | Concern | Owned files | Depends | Closes | ATDD red-first |
|----|---------|-------------|---------|--------|----------------|
| WP01 | Startup config-read robustness (P0) + sibling folds | bootstrap/env_file.py, charter/activation/consistency_check.py, runtime/doctor.py, core/{worktree,vcs/git,git_ops}.py + tests | — | #4600 (I1) | **YES** (#4600: import / `--version` in non-UTF-8 fixture) |
| WP02 | Shared `--json` contract seam | cli/json_contract.py (NEW), cli/commands/_doctor_shared.py, cli/helpers.py + tests | — | infra (#4532) | test-first for envelope + json-aware helper |
| WP03 | `context` adoption | cli/commands/context.py + tests | WP02 | #4597, #4601 (context) | test-first (OptionInfo + json error paths) |
| WP04 | `mission-type`/`mission` adoption (SCOUT) | cli/commands/mission_type.py, cli/commands/charter/mission_type.py + tests | WP02 | #4598, #4601 (show), #4600 (I2) | **YES** (#4600 I2: uncaught `CharterPackConfigError` via `existing_mission_types`, malformed-but-parseable config — Amendment A) |
| WP05 | Remaining `--json` adoption | cli/commands/agent/tasks_status_cmd.py, cli/commands/glossary.py, agent_utils/status.py, cli/commands/{archive,materialize,verify,validate_encoding,research,validate_tasks,dashboard}.py + tests | WP02 | #4643, #4533 | **YES** (#4643: `--json` on zero-WP mission, exit 0) |
| WP06 | Close the class by construction | tests/architectural/test_cli_console_single_seam.py (extend) or NEW enumeration test + OptionInfo guard test | WP03,WP04,WP05 | class (#4646 instances) | gate is red until adoption green |

*The `get_project_root_or_exit` json-awareness (WP02 signature, defaulted `json_output=False`) is opted-in by each adopting WP; the 5 otherwise-unowned caller files are assigned to WP05.*

**Amendment A (post-plan squad):** WP04 carries an issue-pinned `@pytest.mark.regression` red-first repro for #4600 Instance-2. Confirmed at source: `charter/mission_type.py` `charter_mission_type_list` calls `existing_mission_types(repo_root)` (~L175) OUTSIDE the `try/except ValueError` at ~L187-190, so a `CharterPackConfigError` from a malformed-but-parseable config escapes as a raw traceback (recurs in `show_mission_type` ~L1607). Not covered by WP01's import-time repro.

**Amendment B (post-plan squad):** WP06's FIRST step is a discovery/triage that structurally enumerates all `--json`-declaring commands (~70 files) and classifies each into {adopted-shape, already-parseable, non-parseable-deferred}. The gate's parse arm asserts ONLY over the allow-list (adopted ∪ already-parseable); non-parseable-deferred commands (confirmed: `cli/commands/events.py` emits error JSON to stderr with empty stdout → `json.loads("")` fails) are recorded and filed as a follow-up, excluded from the gate so it cannot red on an unowned command. This keeps WP06 deterministically flippable-to-green once WP03/04/05 adoption completes.

**FR-002 ownership:** the general content-load fail-loud message is realized in the command layer — WP04 owns the charter/mission_type content-load path (rendering the named message); the pre-existing `CharterPackConfigError` fail-closed path elsewhere already degrades. **NFR-005:** a lightweight latency non-regression assertion (startup under the 2s budget with a valid project) rides in WP01's test set.

## Complexity Tracking

*No Charter Check violations — none required.*

## Risks & Mitigations

- **Gate over/under-reach** (paula B1 / alphonso Amendment B): shape is bounded to adopted commands; parse is bounded to an allow-list (adopted ∪ verified-parseable), NOT universal — discovered-but-non-parseable commands (e.g. `events.py`) are triaged out and filed, so the gate stays deterministic. Residual shape+parse convergence filed as a follow-up.
- **Helper ripple to unowned files** (paula O1): mitigated by a defaulted `json_output` param (callers compile unchanged) + explicit WP05 assignment of the 5 caller files.
- **Import-purity regression** (paula L3): WP01 keeps env_file stdlib+kernel; loud message lives in the command layer (C-009); `test_bootstrap_import_purity.py` is the guard.
- **god-module churn** (`mission_type.py`): campsite scout in WP04; folds kept surgical, no function refactor of `status.py:show_kanban_status`.
- **Exit-code homogenization** (renata A): the gate asserts `--json` exit == the command's non-json exit; the frozen doctor tests catch regressions.
