---
work_package_id: WP03
title: Repair context defaults and adopt JSON error handling
dependencies:
- WP02
requirement_refs:
- C-001
- C-003
- C-005
- C-006
- FR-005
- FR-006
- FR-007
- FR-009
- FR-011
- FR-012
- NFR-002
- NFR-006
planning_base_branch: fix/cli-boundary-robustness
merge_target_branch: fix/cli-boundary-robustness
branch_strategy: Planning artifacts for this mission were generated on fix/cli-boundary-robustness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-boundary-robustness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-boundary-robustness-01M2NQCB
base_commit: 25f33493ca755f339d90984a3dc91c93cae286f7
created_at: '2026-09-16T21:06:26.575726+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Implementation
history:
- at: '2026-09-16T19:28:18Z'
  actor: codex:planner-priti
  action: Prompt generated via canonical tasks workflow
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/context.py
create_intent:
- tests/specify_cli/cli/commands/test_cli_boundary_context.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/context.py
- tests/specify_cli/cli/commands/test_cli_boundary_context.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 — Repair context defaults and adopt JSON error handling

## ⚡ Do This First: Load Agent Profile

Use `/ad-hoc-profile-load` to load `python-pedro` before parsing the rest of this prompt.
Profile: `python-pedro`. Role: `implementer`. Agent/tool: `codex`.
The current CLI exposes profiles through `spec-kitty profiles show` and governed
work through `spec-kitty dispatch --profile`; use the installed canonical surface,
not the retired `ask` command. Read the project charter before changing code.

## Review Feedback

Read the current review reference from `spec-kitty agent tasks status` and the
event log. Address every returned blocker before resubmission. Never overwrite
a reviewer artifact or synthesize an approval. This prompt starts with no review.

## Objectives & Success Criteria

context with no subcommand behaves exactly like context info, and every context JSON sibling emits parseable output on errors and empty success.

Priority: P1. Requirement refs: FR-005, FR-006, FR-007, FR-009, FR-011, FR-012, NFR-002, NFR-006, C-001, C-003, C-005, C-006.

- context and context info must have identical content and exit status in the same fixture; no OptionInfo/ArgumentInfo repr in either stream.
- Exercise context info outside project, inside project with no current worktree, and unknown --workspace. Each JSON error uses WP02 shape and its existing non-JSON exit.
- Audit context list, resolve, show and any other same-file --json sibling through actual Typer registration. Empty lists remain successful [] (or the established command payload), never an error envelope.
- Resolve defaults at the off-binding call site or use a real declared default. Do not introduce a generic sentinel-coercion framework or AST style gate.

## Context & Constraints

Audience: software engineers implementing and independently reviewing this WP.
Read these canonical mission inputs before coding:

- `.kittify/charter/charter.md` and repository `AGENTS.md`.
- `../spec.md`: requirements, constraints, non-goals and ratified decisions.
- `../plan.md`: concern map, amendments A/B and dependency graph.
- `../data-model.md`, `../research.md` and `../quickstart.md`.
- `../contracts/json-envelope-contract.md` and `../contracts/enumeration-gate-contract.md`
  for the machine contract and bounded enumeration refinement.

The spec and contracts take precedence over suggestive line numbers in the plan.
No dependency, release-version, hosted API, tracker transport or schema change is
authorized. Keep `SPEC_KITTY_ENABLE_SAAS_SYNC` untouched: do not set, unset, or
override it. The root venv is warm; use direct binaries. A separate lane worktree
must verify its own environment before running tools; never assume a shared venv.

## Branch Strategy

- Planning base branch: `fix/cli-boundary-robustness`.
- Merge target branch: `fix/cli-boundary-robustness`.
- Strategy: computed execution lanes from `lanes.json`; consume the workspace
  returned by the CLI rather than constructing a worktree path.
- Dependencies: WP02. An approved dependency is sufficient; do not wait for done.
- WP01 is the independent P0 and is scheduled first; WP02 remains structurally independent.
- Claim with `spec-kitty agent action implement WP03 --mission cli-boundary-robustness-01M2NQCB --agent codex:<model>:python-pedro:implementer`.
- `spec-kitty next` controls sequencing; the orchestration agent owns scheduling.
- Local lane consolidation targets the topic branch. Publication is a PR to
  origin/main; neither this implementer nor the orchestrator publishes to main.

## Ownership & Safeguards

Only the frontmatter `owned_files` are assigned to this WP. Tests use distinct
new files to avoid parallel collisions. `create_intent` lists every planned new
literal path. No code-change WP owns `kitty-specs/` artifacts. Send tracer updates,
issue evidence and planning corrections to the orchestrator, who owns those writes.

A minimal out-of-map edit needs a recorded rationale and an overlap check with
the orchestrator before proceeding. Do not change a sibling WP file silently.
Do not rewrite a shared conftest, packaging config, or global lint suppression.
Keep successful payload shapes and non-JSON exit behavior stable.

## Subtasks & Detailed Guidance

### T011 — Commit #4597 and #4601 context reproductions

**Purpose:** Commit #4597 and #4601 context reproductions.

Use actual Typer CLI invocation in initialized and non-project fixtures. Pin the issue numbers and desired no-subcommand equivalence. Capture red failure output and commit tests before touching context.py.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

### T012 — Apply tidy-first cleanup and resolve default forwarding

**Purpose:** Apply tidy-first cleanup and resolve default forwarding.

Inspect the no-subcommand callback and its command call. Pass real workspace/json defaults through the existing behavior; update touched operator prose to Mission. Keep cleanup local and preserve workspace detection.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

### T013 — Adopt canonical errors across context JSON siblings

**Purpose:** Adopt canonical errors across context JSON siblings.

Route missing root, missing workspace/context/token, and same-file JSON error branches through WP02. Use command-layer format decisions and the existing console transport. Preserve successful payload schemas and non-JSON exits.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

### T014 — Cover empty results and stream separation

**Purpose:** Cover empty results and stream separation.

Add empty list/orphaned list and representative successful context tests. Capture stdout and stderr independently and assert json.loads on stdout alone. Ensure helpful human hints cannot contaminate stdout.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

### T015 — Verify invocation wiring and hand off

**Purpose:** Verify invocation wiring and hand off.

Run context subsystem and owned regression tests, frozen transport gate, lint/type/format checks. Confirm the registered main CLI actually reaches the changed callback and commands, not only direct helper tests.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

## Test Strategy

Tests are required by C-003 and the charter. Do not use production state or
credentials in fixtures. Preserve installed behavior through realistic temporary
git/config/mission fixtures. Explicitly select regression tests: make test-fast
excludes the regression marker and therefore cannot substitute for them.

Mandatory targeted command:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/context/ tests/specify_cli/cli/commands/test_context_info.py tests/specify_cli/cli/commands/test_cli_boundary_context.py tests/specify_cli/integration/test_context_lifecycle.py -q
```

Also run every test file that exercises a touched module and the full directory
of each owning subsystem per AGENTS.md. Discover callers/test ownership before
handoff and record any additions to the blast radius. The root orchestrator runs
the shared `make test-fast` baseline and whole-repo format gate on integration;
do not launch duplicate broad runs while parallel lanes are active.

New and changed Python must pass these direct-binary checks (substitute the
actual diff paths, including committed changes since the lane planning base):

```bash
.venv/bin/ruff check <changed-python-files>
.venv/bin/ruff format --check <changed-python-files>
.venv/bin/mypy --strict <changed-python-files>
```

Respect the repository mypy config; do not blanket-ignore diagnostics. If the
package-level quickstart check reports inherited errors, compare the same command
against the baseline and report exact provenance; fix new diagnostics. The final
integrated format check is `.venv/bin/ruff format --check .`. No whole-repo pytest
run or `make test-full`: CI owns the whole-repo suite. Architectural scope follows
the charter and the mission review policy, not arbitrary repeated full test runs.

## Risks & Mitigations

- Exit-code drift: compare identical conditions in human and JSON mode.
- False-positive coverage: use the registered production entry point and real
  fixture state; patch external side effects only, never the behavior under test.
- Stream masking: inspect stdout and stderr separately; combined output is only
  used for the negative traceback/placeholder assertion.
- Latent base failures: reproduce on the original base before attribution.
  Never retry-to-green or remove honest red-main reproduction coverage.
- Scope creep: preserve domain-matched cleanup only; record deferred issues and
  residual JSON convergence under https://github.com/spec-kitty/spec-kitty/issues/4664.

## Definition of Done

- Acceptance tests were committed before implementation and red evidence retained.
- All subtasks satisfy the declared requirements through live command paths.
- Tests cover success, relevant errors and empty data, with no hidden traceback.
- Focused tests, diff-scoped lint, format and strict type checks pass; inherited
  failures are explicitly separated with base evidence.
- No overlapping ownership, duplicate contract authority or unused new module.
- Implementer gives the orchestrator issue-to-test evidence, red/green commits,
  test counts and tracer notes; no premature fixed verdict for unfinished issues.
- Commit functional changes separately from the red tests and tidy-first cleanup.
- Record subtasks with the event-sourced CLI, not markdown checkboxes:
  `spec-kitty agent tasks mark-status T011 T012 T013 T014 T015 --status done --mission cli-boundary-robustness-01M2NQCB`.
- Move WP03 to for_review using the runtime-generated handoff instruction;
  never self-approve or manually force done.

## Review Guidance

An independent reviewer checks the actual diff against this contract, the red-test
commit, and the recorded baseline. Verify each mapped FR and all applicable C/NFR
clauses, including forbidden behavior. Confirm live caller wiring and assert that
removing the implementation would break the claimed acceptance tests.

Reject undocumented envelope divergence, human text on JSON stdout, placeholder
leaks, swallowed config corruption at a required-content boundary, and weakened
test assertions. Changes to issue-matrix verdicts are the orchestrator’s work;
the reviewer supplies evidence rather than marking unrelated issues complete.

## Activity Log

- 2026-09-16T19:28:18Z – codex:planner-priti – Prompt authored from the mission contract; no implementation yet.

Status and subtask completion are event-sourced in `status.events.jsonl`.
Append later entries chronologically using actual UTC timestamps.
