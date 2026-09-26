---
work_package_id: WP02
title: 'Closeout: changelog, reproducer evidence, tracers'
dependencies:
- WP01
requirement_refs:
- FR-009
- NFR-001
planning_base_branch: issue-3998-startup-assess-cold-concurrency
merge_target_branch: issue-3998-startup-assess-cold-concurrency
branch_strategy: Planning artifacts for this mission were generated on issue-3998-startup-assess-cold-concurrency. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3998-startup-assess-cold-concurrency unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
phase: Phase 2 - Closeout
history:
- at: '2026-09-26T12:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/changelog/
create_intent:
- kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/evidence-fresh-home-repro.md
execution_mode: planning_artifact
model: claude-sonnet-5
owned_files:
- docs/changelog/CHANGELOG.md
- kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/evidence-fresh-home-repro.md
- kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/tracer-approach.md
- kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/tracer-design-decisions.md
- kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/tracer-tooling-friction.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Closeout: changelog, reproducer evidence, tracers

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. (CLI equivalent: `.venv/bin/spec-kitty profiles show python-pedro`.)

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then run `spec-kitty charter context --action implement`.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission startup-assess-cold-concurrency-01M3EQ9S`) or the Activity Log below.

---

## Objectives & Success Criteria

- **CHANGELOG:** `docs/changelog/CHANGELOG.md` carries an impact-first `### Fixed` entry for #3998 under `## [Unreleased]`. The root `CHANGELOG.md` is a symlink, so edit the canonical file.
- **Evidence:** the fresh-home concurrency reproducer is run against **WP01's code** and recorded in `kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/evidence-fresh-home-repro.md`. It must show 0 non-zero exits and 0 tracebacks across 10 runs (5 × N=16 including one CPU-pinned run, 5 × N=32). This covers NFR-001 and SC-001.
- **Tracers:** the three tracer files are closed with an assessment.

Requirements: FR-009 (the tracker text is prepared here; the orchestrator posts the comments and the PR body closes the issues) and NFR-001.

## Context & Constraints

- **Spec/plan:** `kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/{spec,plan,research}.md`.
- **Scope:** WP01 must be approved and its lane present. This WP changes no code.
- **Terminology canon:** say Mission, never feature. Name the overloaded terms precisely: serialization point, owner lock, cold-install sentinel.

## Branch Strategy

- **Planning base branch**: `issue-3998-startup-assess-cold-concurrency`
- **Merge target branch**: `issue-3998-startup-assess-cold-concurrency`
- **Execution worktree:** allocated per computed lane from `lanes.json`. It depends on WP01, so the lane must contain WP01's commits. If it does not, rebase onto WP01's lane before starting.

## Subtasks & Detailed Guidance

### Subtask T010 – CHANGELOG entry

- **File**: `docs/changelog/CHANGELOG.md`, under `## [Unreleased] - …` → `### Fixed`. Create the `### Fixed` subsection only if it is missing, and add the entry at the top of that list.
- **Format**: match the neighbouring entries. Start with a bold, impact-first lead sentence and the `(#3998)` ref, then **Before:** / **After:** prose.
  - **Lead:** "Concurrent spec-kitty commands no longer crash at startup on a fresh machine or CI runner (#3998)."
  - **Before:** on a cold, shared Spec Kitty home, commands that ran startup asset preparation at the same moment (a new CI runner, a new machine, an orchestrator starting several agents) intermittently crashed with a traceback: `RuntimeError: Asset changed during preparation: …`. It happened to 1–5 of 16–32 processes. The losing processes read a peer's half-written install, re-raced it three times without waiting, then aborted.
  - **After:** such a read now waits for the installing peer and re-checks once under that peer's own lock. The command then runs normally. A warm start is unchanged: lock-free, one check. Source-asset drift is still refused. When startup preparation genuinely cannot complete, the command prints one `Error:` line (or a JSON error object with `--json`) and exits 1, with no traceback.
  - **Close with:** also closes the stale #4017, which PR #4174 fixed but never linked.

  Keep it to one paragraph like its neighbours.
- **Validation**: run `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`, which must pass.

### Subtask T011 – Fresh-home reproducer evidence

- **Purpose**: NFR-001 / SC-001 live evidence, which does not replace the deterministic test.
- **Steps**:
  1. Create a wrapper so the reproducer runs **the lane's code**, not the main checkout's. The global `spec-kitty` and `.venv/bin/spec-kitty` both resolve the main checkout `src` via the editable install. Put the wrapper at `<scratch>/sk`:
     ```bash
     #!/usr/bin/env bash
     PYTHONPATH=<LANE_WORKTREE>/src exec <repo>/.venv/bin/python -c 'import sys; from specify_cli import main; sys.exit(main())' "$@"
     ```
     Verify that it runs the lane code: `PYTHONPATH=<lane>/src python -c "import specify_cli.runtime.asset_preparation as m; print(m.__file__, hasattr(m, 'build_serialized'))"` must print the lane path and `True`.
  2. Take the reproducer from the #3998 comment (`unset GITHUB_TOKEN; gh issue view 3998 --repo spec-kitty/spec-kitty --comments`). Alternatively use the copy at `<scratch>/align/repro.sh`. Adapt `SK=` to point at your wrapper. Scratch goes under the session scratchpad, never the repo.
  2b. Note that the scratch `repro.sh` also needs `SPK_QA_SOURCE` (and any `REPRO_BASE`) exported, and it hard-codes `SK=$SRC/.venv/bin/spec-kitty`. Edit your scratch copy so that `SK` points at the wrapper.
  3. Run N=16 ×5 (one of them under `taskset -c 0-3`) and N=32 ×5, all against the lane.
  4. For a baseline contrast, run N=32 ×3 against the planning base: use `git worktree add` on the base commit in the scratchpad, or `PYTHONPATH` to a checkout of it. This shows the reproducer still hits on the base (it is intermittent; record whatever it shows honestly).
  5. Write `evidence-fresh-home-repro.md`: the host (CPU count), the commands, a per-run table (N, pinned?, fresh exit-code tally, tracebacks, warm tally), the base contrast, and a verdict. Do not overclaim. If any lane run fails, **stop and report it**; that is a WP01 defect, not something to retry-to-green.

### Subtask T012 – Close the tracer files

- Append closing sections to `tracer-approach.md` (what was actually done vs planned), `tracer-design-decisions.md` (the WP decomposition merge DD: the 3→2 WPs forced by `owned_files` no-overlap, plus anything WP01's Activity Log recorded), and `tracer-tooling-friction.md` (friction from WP01/WP02, with a closing assessment of which items deserve an upstream gap).
- **Drafted tracker text** (for the orchestrator to post): add a short `## Tracker closeout text` section at the end of `tracer-approach.md` with three items:
  - a one-paragraph #4885 comment saying the torn read is distinct from the reassess gate and the gate is untouched;
  - #4017 closing evidence: nightly run 36215053547 passed all 20 params of `test_installed_cli_keeps_two_owned_worktrees_isolated`; the fix was PR #4174;
  - the #3998 resolution summary.

## Test Strategy

No code changes. Validation is the terminology guard (T010) plus the evidence tallies (T011).

## Risks & Mitigations

- **Running the reproducer against the main checkout instead of the lane.** Mitigated by the wrapper plus the `hasattr(build_serialized)` check.
- **A flaky single clean run misread as proof.** Mitigated by 10 runs plus the base contrast, reported honestly.

## Review Guidance

- The CHANGELOG entry is under `[Unreleased]` → `### Fixed`, impact-first, with the `(#3998)` ref and no "feature" wording.
- The evidence file names the wrapper and the lane path and shows 10 lane runs, all 0 failures.
- The tracers are closed, and the drafted tracker text is present.

## Activity Log

- 2026-09-26T12:10:00Z – system – Prompt created.
