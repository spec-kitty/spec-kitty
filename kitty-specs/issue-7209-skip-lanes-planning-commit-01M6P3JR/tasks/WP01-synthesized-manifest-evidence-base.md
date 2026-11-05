---
work_package_id: WP01
title: Synthesized-manifest evidence base
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-004
- SC-001
- SC-002
- SC-003
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
planning_base_branch: issue-7209-skip-lanes-planning-commit
merge_target_branch: issue-7209-skip-lanes-planning-commit
branch_strategy: Planning artifacts for this mission were generated on issue-7209-skip-lanes-planning-commit. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7209-skip-lanes-planning-commit unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-issue-7209-skip-lanes-planning-commit-01M6P3JR
base_commit: f6da03e2b2db29712ac481d2616ee335ec4c4c86
created_at: '2026-11-05T15:06:10.354719+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - The evidence window
history:
- at: '2026-11-05T15:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/entry_preflight.py
- tests/consolidation/test_skip_lanes_evidence_window.py
- tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/entry_preflight.py
- tests/consolidation/test_skip_lanes_evidence_window.py
- tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7209'
---

# Work Package Prompt: WP01 – Synthesized-manifest evidence base

## Do This First: Load Agent Profile

Load `python-pedro` (implementer, `skills/spk-charter-profile-load`) and follow its guidance
before the rest of this prompt.

## Review Feedback

Check the `review_ref` in the status event log (`spec-kitty agent tasks status`); address every
item before calling the work complete.

## Objectives & Success Criteria

Deliver, red-first, the base that makes `consolidate --skip-lanes` judgeable:

1. `_synthesize_no_lane_manifest` records a `planning_commit_sha` resolved from the target
   branch's own history: the target tip immediately before the first commit that introduced
   `kitty-specs/<slug>/` (FR-001, FR-002).
2. The resolution never fabricates: a git error, or a Mission directory absent from target
   history, yields `None`, and the evidence axis keeps refusing `EVIDENCE_WINDOW_UNCOMPUTABLE`
   (NFR-003).
3. `wp_evidence.lane_evidence_window` then computes `base..target` for the synthesized planning
   lane, so the existing evidence and independence judgments run unchanged — and still refuse a
   work package whose `owned_files` the window never changed, or whose approval was recorded by
   the implementer (FR-004, SC-003).
4. The pre-existing CLI nodes in
   `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py` complete through the real
   `spec-kitty consolidate` command (SC-001, SC-002).

## Context & Constraints

- Mission spec `spec.md` FR-001..FR-004, plan `plan.md` §Design D-1/D-2/D-4.
- `_synthesize_no_lane_manifest` already resolves the target branch through
  `resolve_merge_target_branch`; resolve the base against that same branch so `--target` is
  honored.
- Use `kernel.git.run_git` and `specify_cli.consolidation.git_probes.commit_parents`. Do not add a
  subprocess helper.
- No new field on `LanesManifest`, no change to `lanes.json` persistence, no new git call when
  `lanes.json` is present (NFR-001).
- No change to `wp_evidence.py` (WP02 owns it) and none to the coordination-teardown modules.

## Branch Strategy

- Planning base and merge target: the branch the CLI reports for this mission
  (`issue-7209-skip-lanes-planning-commit`); the PR targets `spec-kitty/spec-kitty` `main`, which
  only the operator merges.

## Subtasks

### T001 – Red-first: make the CLI fixture faithful and confirm the red

- The `--skip-lanes` fixture's `_write_wp_file` omits `owned_files`, which a real Mission's task
  file always declares. Add the work package's owned path (`src/<code_filename>`) to the
  frontmatter, keep every assertion as it is, and run:

  ```bash
  uv run --frozen pytest tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py -q
  ```

  The three nodes must still fail with `EVIDENCE_WINDOW_UNCOMPUTABLE` — that is the RED state.
  Record the exact output.

### T002 – Red-first: focused module for the base and the axis

Create `tests/consolidation/test_skip_lanes_evidence_window.py` with a real git fixture (the
existing consolidation fixture idioms: `git init`, non-protected target branch — `main` is
protected by `git/protection_policy` defaults) building:

- commit 1 (root): repository scaffolding;
- commit 2: `kitty-specs/<slug>/meta.json`, `tasks/WP01-work.md` with
  `owned_files: [src/impl.py]`, and a reducer-valid `status.events.jsonl` chain to `approved`
  (`implementer-bot` implement, `reviewer-renata` review);
- commit 3: `src/impl.py`.

Then call `entry_preflight._synthesize_no_lane_manifest` directly and assert:

1. `planning_commit_sha` is commit 1 (the base), and `lane_evidence_window` for the synthesized
   lane is `(commit 1, target)`; `wp_evidence.evidence_paths` over it contains `src/impl.py`
   (positive control).
2. `evaluate_evidence` over that manifest and snapshot returns no refusal.
3. Same fixture, WP owning `src/other.py` (never changed) → refusal with `IMPLEMENTATION_MISSING`.
4. Same fixture, approval recorded by `implementer-bot` → `REVIEW_NOT_INDEPENDENT`.
5. Fixture where `kitty-specs/<slug>/` is never committed → `planning_commit_sha is None` and
   `evaluate_evidence` still refuses `EVIDENCE_WINDOW_UNCOMPUTABLE`.
6. Two builds on one repo return the same base (NFR-002).

Rows 3 and 4 are the same-fixture negative controls for the passing row 2: they prove the axis
discriminates through this window instead of passing everything. Commit RED.

### T003 – Implement the resolver

In `src/specify_cli/consolidation/entry_preflight.py`:

- Add `_resolve_planning_base_commit(main_repo, mission_slug, target_branch) -> str | None`:
  `git log --format=%H <target_branch> -- kitty-specs/<slug>`; the last line is the introducing
  commit; return its first parent, or the commit itself when it is a root commit; return `None`
  on empty output or any git probe error.
- Pass it into the `LanesManifest` that `_synthesize_no_lane_manifest` builds, with a docstring
  paragraph naming the topology, the boundary chosen, the root-commit case, and the fail-closed
  `None`.
- Keep the two git calls bounded and skipped entirely when `lanes.json` is present.

### T004 – Green

Run and record:

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py -q
uv run --frozen pytest tests/consolidation/test_skip_lanes_evidence_window.py -q
uv run --frozen pytest tests/consolidation/test_wp_evidence.py tests/consolidation/test_lane_evidence_axis.py tests/consolidation/test_single_branch_evidence_axis.py -q
uv run --frozen ruff check src/specify_cli/consolidation/entry_preflight.py tests/consolidation/test_skip_lanes_evidence_window.py tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py
uv run --frozen ruff format --check src/specify_cli/consolidation/entry_preflight.py tests/consolidation/test_skip_lanes_evidence_window.py tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py
```

If a node fails for a reason outside this WP's seam, diagnose it, do not weaken it, and report it.

## Definition of Done

- The resolver is the only new production surface, it is documented, and it never fabricates.
- The three CLI nodes complete; the new module passes; the evidence suites stay green.
- No assertion, marker or gate was relaxed; the fixture change is `owned_files` only.
- Tests exercise the production path (`_synthesize_no_lane_manifest`, `evaluate_evidence`, the
  real Typer `consolidate` command), not a hand-built manifest.
