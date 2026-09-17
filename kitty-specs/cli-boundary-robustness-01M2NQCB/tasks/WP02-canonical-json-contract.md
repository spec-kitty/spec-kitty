---
work_package_id: WP02
title: Promote the canonical JSON error contract and project-root boundary
dependencies: []
requirement_refs:
- C-001
- C-003
- C-006
- FR-005
- FR-007
- FR-008
- NFR-004
- NFR-006
planning_base_branch: fix/cli-boundary-robustness
merge_target_branch: fix/cli-boundary-robustness
branch_strategy: Planning artifacts for this mission were generated on fix/cli-boundary-robustness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-boundary-robustness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-boundary-robustness-01M2NQCB
base_commit: 25f33493ca755f339d90984a3dc91c93cae286f7
created_at: '2026-09-16T19:52:09.336853+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Implementation
history:
- at: '2026-09-16T19:28:18Z'
  actor: codex:planner-priti
  action: Prompt generated via canonical tasks workflow
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/json_contract.py
create_intent:
- src/specify_cli/cli/json_contract.py
- tests/specify_cli/cli/commands/test_cli_boundary_json_seam.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/json_contract.py
- src/specify_cli/cli/commands/_doctor_shared.py
- src/specify_cli/cli/helpers.py
- tests/specify_cli/cli/commands/test_cli_boundary_json_seam.py
- src/specify_cli/cli/commands/doctor.py
- src/specify_cli/cli/commands/_command_surface_doctor.py
- src/specify_cli/cli/commands/_coordination_doctor.py
- src/specify_cli/cli/commands/_env_file_doctor.py
- src/specify_cli/cli/commands/_provenance_doctor.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 — Promote the canonical JSON error contract and project-root boundary

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

One shared error-envelope definition drives doctor and CLI helpers, while existing human output and per-command exit codes remain stable.

Priority: P1. Requirement refs: FR-005, FR-007, FR-008, NFR-004, NFR-006, C-001, C-003, C-006.

- Error payload: {"ok": false, "error": {"code": "nonempty-stable-code", "message": "nonempty-message"}} on stdout. Use existing CliConsole.emit_json/print_json transport, not another serializer or console authority.
- get_project_root_or_exit gains a defaulted json_output=False parameter. Its JSON not-in-project path emits code not_in_project and retains exit 1; calls with only start continue working.
- Promote _json_error and any shared JSON guard from _doctor_shared; retain re-export compatibility for its existing callers. Do not duplicate the envelope body.
- exit_git_resolution_failure currently emits a divergent payload on stderr. Converge to the shared stdout envelope, code git_resolution_failed, retaining exit 1 and human messages.
- The frozen doctor tests own exits: most exit 1; skills/shim-registry/contracts/tool-surfaces exit 2. Do not homogenize them. Success payloads retain their command-specific shapes.

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
- Dependencies: none. An approved dependency is sufficient; do not wait for done.
- WP01 is the independent P0 and is scheduled first; WP02 remains structurally independent.
- Claim with `spec-kitty agent action implement WP02 --mission cli-boundary-robustness-01M2NQCB --agent codex:<model>:python-pedro:implementer`.
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

### T006 — Commit failing contract acceptance tests

**Purpose:** Commit failing contract acceptance tests.

Drive existing helper/doctor entry points, including missing project and git resolution failure. Add failing #4532 shared-guard adoption coverage for both resolver-raised and resolver-returned-None branches before the refactor. Assert independent stdout/stderr, canonical shape and exit fidelity; baseline must fail on actual output, not solely because a new module cannot import. Commit the red tests before creating json_contract.py.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

### T007 — Promote the shared envelope without a duplicate authority

**Purpose:** Promote the shared envelope without a duplicate authority.

Move the existing doctor error builder into cli/json_contract.py with typed signatures. Re-export from _doctor_shared.py so doctor callers keep working. Preserve warning/logging guard restoration even when the guarded command raises.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

### T008 — Opt the shared root helper into JSON output

**Purpose:** Opt the shared root helper into JSON output.

Add the defaulted parameter and route only opted-in errors through the promoted builder/console transport. Preserve all non-JSON behavior and success return values. No caller changes belong here; WP03/04/05 own adoption.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

### T009 — Unify git failure and doctor resolver guards

**Purpose:** Unify git failure and verify doctor compatibility.

Close #4532 by promoting one resolve-root-or-exit guard into _doctor_shared, with a per-command exit_code parameter, and adopting it in doctor.py, _command_surface_doctor.py (including tool-surfaces), _coordination_doctor.py, _env_file_doctor.py, _provenance_doctor.py and the mission_state shell. Preserve patchable resolver seams by explicit dependency injection if needed; do not leave duplicate try/except/None guard bodies disguised as wrappers. Add a non-vacuous delegation/behavior test proving each JSON doctor uses the shared guard. The non-JSON sparse-checkout guard is outside this issue. Route exit_git_resolution_failure through the same error builder and stdout seam. Exercise both git error classes and existing doctor family frozen tests, including exits 1 versus 2. Confirm no additional JSON envelope definition remains in owned surfaces.

**Files:** the owned surface and dedicated test files listed in frontmatter.
**Sequence:** follows the preceding subtask; no implementation before the red-test commit.
**Validation:** preserve exact command, exit status, failing/passing node IDs and
the commit that establishes the result. A passing synthetic payload is insufficient.
**Review evidence:** state what pre-existing entry point reaches the changed
behavior and which negative case would fail if that behavior were removed.

### T010 — Validate and publish the adoption seam

**Purpose:** Validate and publish the adoption seam.

Run focused CLI helper and doctor tests, lint/format/type checks, and inspect live imports. Handoff the exported symbol names and exact signature to downstream WPs; do not rewrite their files.

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
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/test_helpers.py tests/specify_cli/cli/commands/test_cli_boundary_json_seam.py tests/specify_cli/cli/commands/test_doctor_shared.py tests/specify_cli/cli/commands/test_doctor_json_not_in_project.py tests/specify_cli/cli/commands/test_doctor_shim_reexports.py tests/specify_cli/cli/commands/test_doctor*.py tests/specify_cli/cli/commands/test_env_file_doctor.py tests/specify_cli/cli/commands/test_provenance_doctor.py tests/specify_cli/cli/commands/test_coordination_doctor.py -q
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
  `spec-kitty agent tasks mark-status T006 T007 T008 T009 T010 --status done --mission cli-boundary-robustness-01M2NQCB`.
- Move WP02 to for_review using the runtime-generated handoff instruction;
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
