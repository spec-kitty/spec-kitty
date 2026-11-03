---
work_package_id: WP01
title: Owned fact decides the tracer write surface
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Owned routing
history:
- at: '2026-11-03T08:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- tests/specify_cli/cli/commands/agent/test_tracer_append_owned_checkout_7081.py
execution_mode: code_change
model: deepseek-v4.1-flash-1017
owned_files:
- src/specify_cli/cli/commands/agent/tracer_append.py
- src/specify_cli/retrospective/tracer_writer.py
- tests/specify_cli/cli/commands/agent/test_tracer_append_owned_checkout_7081.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7081'
---

# Work Package Prompt: WP01 – Owned fact decides the tracer write surface

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave according
to its guidance before parsing the rest of this prompt.

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting; if
this WP was returned from review, resolve every feedback item first and record each with
`spec-kitty agent tasks add-history WP01 --note "..."`.

## Objectives & Success Criteria

- `spec-kitty agent tracer-append` exposes `--owned-checkout` and validates it exactly once through
  `resolve_owned_or_refuse`, which also adopts a flagless invocation made from an owned checkout.
- With a validated fact, the write root, target branch, protection policy and the `owned` handed to
  the write seam all come from the fact; the repository root is not the write surface.
- An invalid owned target exits 1 with the C2 owned refusal **before** `append_tracer_finding` is
  called, so nothing is written under either checkout.
- `append_tracer_finding` accepts `owned` (default `None`) and threads it into `write_artifact` and
  its two `placement_seam` calls.
- The non-owned invocation's JSON payload keys, refusal shapes and exit codes are unchanged.

## Context & Constraints

- Read first: `kitty-specs/tracer-append-owned-checkout-01M6G9FW/spec.md`, `research.md`
  (decisions D1–D4), `data-model.md`, `contracts/tracer-append-owned-selector.md`, `quickstart.md`.
- The defect: `src/specify_cli/cli/commands/agent/tracer_append.py:105-125` on `main` resolves
  `get_main_repo_root()` unconditionally (issue #7081).
- Charter rules that bind this WP: single canonical authority (`_owned_checkout.py` is the one owned
  CLI seam, G2/G5), ATDD-first (red test first), DIRECTIVE_034 (test-first bug fixing).
- `NO_FULL_HEAVY_SUITES_IN_MISSION`: run targeted suites and the architectural gates, not the full
  matrix.

## Branch Strategy

- **Strategy**: single_branch mission (`owned-checkout-lifecycle-authority` topology set)
- **Planning base branch**: `kitty/mission-tracer-append-owned-checkout-01M6G9FW`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### T001 – Red-first owned-routing test

- **Purpose**: pin the reported scenario through the real command before the fix exists.
- **Steps**: create `tests/specify_cli/cli/commands/agent/test_tracer_append_owned_checkout_7081.py`
  with a two-checkout fixture:
  1. a real git repository `R` with a commit on `main`, and a linked worktree `P` on
     `kitty/mission-<slug>` (a `single_branch` owned checkout);
  2. the Mission's `kitty-specs/<slug>/meta.json` present in `P` with `target_branch: main` and the
     single_branch topology, so `adopt_owned_checkout` validates it;
  3. invoke the command found via `importlib.import_module("specify_cli.cli.commands.agent.tracer_append")`
     (the package attribute is rebound by `agent/__init__.py`; see
     `tests/mission_runtime/test_coord_read_seam_callers.py`), registered on a local `typer.Typer()`,
     with cwd inside `P`.
  Assert: exit code 0, the entry present in `P/kitty-specs/<slug>/traces/approach.md`, no
  `traces/` under `R`, no new commit on `R`'s `main`, and no `PROTECTED_BRANCH_REFUSED` in the
  output.
- **Files**: `tests/specify_cli/cli/commands/agent/test_tracer_append_owned_checkout_7081.py` (new).
- **Notes**: if materialising the real commit path is too heavy for a unit test, drive the same
  fixture and assert on the arguments the writer receives **plus** the filesystem outcome of the
  staging thunk; do not mock the command's own resolution. Mark the module `pytest.mark.fast`.

### T002 – Red-first refusal test

- **Purpose**: the issue asks for a refusal *before* writing.
- **Steps**: same module: invoke with `--owned-checkout <R>` and assert exit 1, an
  `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` code in the JSON payload (stdout), no `traces/` file created
  under `R` or `P`, and that `append_tracer_finding` was never called (patch it on the imported
  module and assert not called).
- **Files**: same module.

### T003 – Declare and validate the owned selector

- **Purpose**: one flag, one validation.
- **Steps**: add
  `owned_checkout: OwnedCheckoutOption = None` as the last parameter of `tracer_append`; after
  `repo_root = get_main_repo_root(cwd_repo_root)`, call
  `resolve_owned_or_refuse(repo_root, owned_checkout, mission, cwd=Path.cwd(), allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES, json_output=json_output)`
  (import `LIFECYCLE_OWNED_TOPOLOGIES` lazily inside the function, matching `record_analysis`).
  Do not re-implement claim parsing or rename the parameter (G5 `CLI_CLAIM_INPUT_RULE`).
- **Files**: `src/specify_cli/cli/commands/agent/tracer_append.py`.

### T004 – Fact-derived write inputs

- **Purpose**: the fact, not the root, decides the write.
- **Steps**: when the fact is not `None`, set `repo_root = owned.owned_root`,
  `target_branch = owned.write_branch`, and
  `policy = ProtectionPolicy.resolve_for_owned(owned, mission)`; otherwise keep today's
  `ProtectionPolicy.resolve(repo_root)` and the best-effort `get_feature_target_branch(...)`
  fallback. Pass `owned=owned` to `append_tracer_finding`.
- **Files**: `src/specify_cli/cli/commands/agent/tracer_append.py`.
- **Notes**: update the module docstring, which currently states the command resolves the primary
  checkout "exactly like `record-analysis` does" — that is now true in a different sense, and the
  stale sentence is what led to the defect.

### T005 – Thread the fact into the writer

- **Purpose**: no second ownership interpretation below the CLI.
- **Steps**: add `owned: OwnedCheckout | None = None` to `append_tracer_finding`; pass it to
  `write_artifact(..., owned=owned)`; add the same parameter to `_local_staging_path` and
  `_read_current_coord_content` and pass it to their `placement_seam(repo_root, mission_slug,
  owned=owned)` calls. Delete the "has no `owned` parameter" rationale in `_local_staging_path`'s
  docstring and replace it with the threading contract. Import `OwnedCheckout` from `mission_runtime`
  (already imported there).
- **Files**: `src/specify_cli/retrospective/tracer_writer.py`.

### T006 – Pin the non-owned path and the gates

- **Purpose**: prove the change is additive.
- **Steps**: add cases asserting the non-owned invocation's JSON key set and exit code (compare to a
  literal set, not to a snapshot of `main`), the existing `{ok: false}` shapes for a blank actor and
  for an unmaterialised coordination worktree on the owned path, and run:
  `tests/architectural/test_owned_checkout_single_authority.py` (empty allowlist),
  `tests/specify_cli/cli/commands/test_owned_refusal_format_unified.py`,
  `tests/mission_runtime/test_coord_read_seam_callers.py`,
  `tests/specify_cli/cli/commands/agent/test_tracer_append_outcome.py`,
  `tests/retrospective/test_tracer_writer_write_dir.py`.
- **Files**: the new test module plus any existing test that must be updated for the new signature.

## Test Strategy

```bash
uv run pytest tests/specify_cli/cli/commands/agent/test_tracer_append_owned_checkout_7081.py -q
uv run pytest tests/specify_cli/cli/commands/agent/test_tracer_append_outcome.py \
              tests/retrospective/test_tracer_writer_write_dir.py \
              tests/specify_cli/cli/commands/test_owned_refusal_format_unified.py \
              tests/mission_runtime/test_coord_read_seam_callers.py \
              tests/architectural/test_owned_checkout_single_authority.py -q
uv run ruff check src/specify_cli/cli/commands/agent/tracer_append.py src/specify_cli/retrospective/tracer_writer.py
uv run mypy src/specify_cli/cli/commands/agent/tracer_append.py src/specify_cli/retrospective/tracer_writer.py
```

## Risks & Mitigations

- **Swallowing the writer's structured refusals** → the owned refusal exits inside
  `resolve_owned_or_refuse` before the writer `try` block; T006 pins the existing shapes.
- **A second ownership interpretation creeping in** → T006 runs the single-authority gate with an
  empty allowlist; no new caller of `resolve_owned_mission` / `adopt_owned_checkout`.
- **Mocks hiding the defect** → T001 drives the real resolution and the real staging thunk; only the
  commit plumbing may be observed rather than mocked.

## Review Guidance

- Confirm the owned refusal happens before any write or coordination-surface materialisation.
- Confirm `owned.write_branch` is used on the owned path and the non-owned path is untouched.
- Confirm no new exemption or allowlist entry was added anywhere.

## Progress & Status

Start by running
`spec-kitty agent action implement WP01 --agent pi:deepseek-v4.1-flash-1017:python-pedro`
from the repository root, and record progress with
`spec-kitty agent tasks add-history WP01 --note "..."`.
