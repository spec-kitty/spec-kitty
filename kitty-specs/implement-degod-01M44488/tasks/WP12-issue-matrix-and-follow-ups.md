---
work_package_id: WP12
title: Issue matrix and follow-ups
dependencies:
- WP11
requirement_refs:
- FR-017
planning_base_branch: issue-5635-implement-degod
merge_target_branch: issue-5635-implement-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5635-implement-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5635-implement-degod unless the human explicitly redirects the landing branch.
subtasks:
- T052
- T053
phase: Phase 5 - Tracker hygiene
history:
- at: '2026-10-04T20:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: planner-priti
authoritative_surface: kitty-specs/implement-degod-01M44488/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/implement-degod-01M44488/issue-matrix.json
role: planner
tags: []
task_type: plan
tracker_refs: []
---

# Work Package Prompt: WP12 – Issue matrix and follow-ups

## ⚡ Do This First: Load Agent Profile

Load the agent profile named in the frontmatter through the canonical path, and work according to
its guidance before you read the rest of this prompt:

```bash
spec-kitty agent profile show planner-priti
spec-kitty charter context --action plan --json
```

- **Profile**: `planner-priti`
- **Role**: `planner`
- **Agent/tool**: `claude`

State, in your first activity-log entry, which directives and tactics of the profile you applied.

---

## ⚠️ IMPORTANT: Review Feedback

Before you start, read the `review_ref` in the event log (`spec-kitty agent tasks status --mission implement-degod-01M44488`)
and the Activity Log below. Treat any review feedback as your TODO list.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Binding rules for this mission (read once, apply throughout)

- **Behaviour preserved (C-001).** Refusal texts, error codes, exit codes, console and `--json`
  output (including print order), commits and state files stay byte-identical.
- **Move, then adjust (C-002 / NFR-005).**
  - Commit 1 of each extraction is a verbatim move: `git diff --color-moved=zebra` must show only
    moved blocks plus the minimal import lines.
  - Commit 2 adjusts callers and imports, deletes the moved names' re-exports from `implement.py`
    (research R-3: keep a re-export only where *production* imports it from there), and applies
    typing-only fixes.
  - Never edit logic inside the move commit.
- **Existing packages only (C-004).** Lower packages (`lanes`, `workspace`, `coordination`,
  `status`, `core`) never import `specify_cli.cli`, `typer` or the console. They return typed
  results or raise typed errors; only the command package prints.
- **Gates follow the code (FR-012).**
  - Every census or scan list that names `implement.py` gains the module the code moved to; pins
    are re-pointed and never loosened.
  - Prove each widened scan by planting a violation in the new module, running the gate red, then
    removing the plant (never committed).
  - Record the commands and the red output in your activity log.
  - Record every local out-of-matrix test run (NFR-006) with its command and counts.
  - Checklist: research/code-grounding.md §1.5 and research/test-remediation.md §5 ("Gate/census edits").
- **Tests (charter SO 4, brief).**
  - Never edit an assertion to make a move pass.
  - Re-point imports and patches to the module that now *looks the name up*.
  - Add seam unit tests before trimming any end-to-end test, and keep at least one smoke test per
    behaviour family.
  - The characterization suite (`test_implement_characterization.py`) must stay green **unedited**.
    Only its dispatch-map fixture may change, when a collaborator's dispatch site moves.
- **Call style for moved collaborators (one rule, every WP).** Code in the command package calls a
  moved collaborator as an attribute of its owner module (`implement_claim.commit_wp_claim_status(...)`,
  `implement_support.resolve_base_ref(...)`), not through a `from … import name` binding.
  - One patch on the owner module then intercepts.
  - The widened liveness gate (WP01) treats `<alias-of-M>.<name>` reads as live.
  - Tests patch the owner module.
- **Ownership leeway for mechanical re-points.** A moving WP may edit any test or gate file only to
  re-point an import path, a patch target, a dispatch-map entry or a gate scan list for the names
  it moves (charter: ownership-map leeway; the no-overlap rule is the real guard, and this chain is
  sequential).
  - List every such out-of-map file in the activity log.
  - Assertion changes are never "mechanical".
- **Dispatch map scope.** `tests/specify_cli/cli/commands/_implement_dispatch.py` may only be used by
  the characterization suite and the F-50 alloc-failure test. Every `patch_collaborator(...)` call
  counts as a patch site in the SC-002 counter.
  - Never build an implement-family patch target dynamically (f-strings, concatenation) to evade
    the counter or the liveness gate.
- **Characterization suite immutability (SC-003).** At every review,
  `git diff <WP02 tip>..HEAD -- tests/specify_cli/cli/commands/test_implement_characterization.py`
  must be empty. Only `_implement_dispatch.py` may change.
- **Known red #5699.** Run `tests/specify_cli/cli/commands/test_commit_recipes.py` in every WP and
  compare its failing set with the base commit. It must be exactly
  `test_no_unallowed_git_commit_recipe_strings_in_src`, failing only on `_commit_message.py`.
  Any new entry is yours (for example the `silently demotes` allow-list row when that message moves).
- **No-CLI import guard for seams (C-004).** Every lower-package module that receives moved code
  (`coordination/planning_commit.py`, `lanes/implement_support.py`, `workspace/context.py`,
  `core/dependency_graph.py`) must be covered by an import gate forbidding `specify_cli.cli` /
  `typer` imports.
  - Extend `tests/coordination/test_commit_router_layering.py`, or the `test_layer_rules.py` rule,
    in the WP that first moves code into that module.
  - Prove it with a plant.
  - `lanes/implement_support.py`'s pre-existing lazy `cli.console` import (~L400) is the one
    recorded exception. Name it in the gate with the same carve-out `test_layer_rules.py` already
    grants consolidation for `cli.console`, plus a pointer to the follow-up issue the orchestrator
    files to drain it (charter SO 5).
- **NFR-003 per WP.** Time the regression subset (quickstart.md §2 plus the seam and phase unit
  tests) in every WP; the budget is ≤ 30 s. The characterization and reachability suites are timed
  separately (≤ 60 s each).
- **Quality (NFR-001/002/004).**
  - Complexity ≤ 15.
  - `mypy --strict` clean on new and receiving modules; nothing added to the mypy quarantine.
  - `ruff check` + `ruff format --check --force-exclude` clean on changed files.
  - No new `noqa` or `type: ignore` without an inline rationale.
- **Commits.** Every commit message ends with
  `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model identifier anywhere
  (C-008).
- **Tracer files.** Append dated 1–3 sentence entries for friction, approach changes or design
  decisions to `kitty-specs/implement-degod-01M44488/traces/` (via the orchestrator, if your
  worktree cannot write the mission dir).
- **No heavy suites.** Never run `make test-full` or a whole `tests/architectural/` sweep. Run the
  targeted files and the specific gate files (quickstart.md §2–§3).


## Objectives & Success Criteria

- `kitty-specs/implement-degod-01M44488/issue-matrix.json` is the canonical matrix. The orchestrator
  seeded all 18 gating rows at task time through `spec-kitty agent issue-verdict`. Update it **only**
  through that CLI, never by hand. Final verdicts:
  - #5635: `in-mission` → `fixed`; closed by the PR.
  - #5232: `in-mission` → `fixed` (B2\*, seam-owned typed placement); closed by the PR.
  - Every row must be terminal before merge: `in-mission` is rejected at `done`.
  - #5673: shaped, not fixed (`implement_claim.claim_commit_paths`); stays open.
  - #5676: out of scope (`core/mission_creation.py`, sibling mission #5634).
  - #5669 and #3931: out of scope.
- The orchestrator files the follow-up issues through the GitHub tooling; you draft them. Their
  numbers are recorded in the matrix and in the PR body:
  1. The planning-artifact commit lands before late validation (`resolve_workspace_for_wp`, lane
     lookup), so a validate failure leaves a landed commit.
  2. An unmaterialized coordination worktree surfaces as a misleading "WP not finalized" refusal.
  3. A shared implement application service for `implement`, `agent action implement` and
     `orchestrator_api`. It needs an ADR, and includes deduping the dependency-gate glue with
     `status/dependency_verdict.py`.
  4. The #5232 single-path end state (B1). This is an operator decision, because it changes four
     reachable outcomes (research.md R-1).
  5. **Deferred test-remediation items**, if WP10/WP11 did not take them: injectable
     `ImplementPorts`, a presenter `render()` returning text, the remaining console couplings and
     private-name imports (with the counter's final numbers).

## Subtasks & Detailed Guidance

### Subtask T052 – Issue matrix
Use `spec-kitty agent issue-verdict --mission implement-degod-01M44488 --issue "#N" --verdict <v> --actor <you> --wp <WPxx> --evidence-ref "<evidence>"`.
Flip #5635 and #5232 to `fixed`, and confirm every row is terminal.

### Subtask T053 – Follow-ups
Draft each follow-up: title, plus a body covering why / for whom / intended effect / evidence with
file:line. End each body with the standard GitHub attribution footer (`Generated by Claude Code`). It names the tool, not a model, so it is compatible with C-008. Hand the drafts to the
orchestrator and record the returned numbers in the matrix.

## Definition of Done

- [ ] All 18 matrix rows terminal (no `in-mission`), with #5635 and #5232 `fixed`.
- [ ] Follow-ups filed and their numbers recorded.

## Branch Strategy

- **Strategy**: lanes topology. Execution worktrees are allocated per computed lane from `lanes.json`.
  This mission's WPs form one dependency chain, so they run sequentially in one lane.
- **Planning base branch**: `issue-5635-implement-degod`
- **Merge target branch**: `issue-5635-implement-degod`. `spec-kitty consolidate` lands the lanes
  there, locally only. The branch then reaches `main` through a PR that the operator merges.
- Prepare the workspace only with `spec-kitty agent action implement WP12 --agent claude --mission implement-degod-01M44488`
  (or `spec-kitty implement WP12 --mission implement-degod-01M44488`), and work in the path it prints.

## Validation (run and record in the activity log: command + pass/fail counts)

1. `make test-fast`
2. The implement-direct regression subset (quickstart.md §2), plus every new or touched test file.
3. The owning subsystem directories of every source module you touched (CLAUDE.md blast radius),
   targeted files only.
4. The specific gate files you widened or re-pointed (quickstart.md §3).
5. `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check --force-exclude <changed files>`,
   `uv run --frozen mypy --strict <new/receiving src modules>`, and the C901 check.
6. The counter: `uv run --frozen python kitty-specs/implement-degod-01M44488/tools/count_patch_sites.py`
   (before/after numbers in the activity log).
7. Classify every red against the base commit (CLAUDE.md baseline-red gotcha). Charter rule:
   a pre-existing failure other than #5699 must get a GitHub issue. Record the command and the
   failure in the activity log and hand it to the orchestrator, who files it.
   `test_commit_recipes.py::test_no_unallowed_git_commit_recipe_strings_in_src` is a known
   pre-existing red (#5699); do not chase it.

## Activity Log

- 2026-10-04T20:45:00Z – system – Prompt created via /spec-kitty.tasks.


- 2026-10-05 — WP12 (orchestrator).
  - **Verdicts:** #5635 → fixed (WP09 evidence), #5232 → fixed (WP06, B2\*\*). All 18 seeded rows are terminal.
  - **Follow-ups filed:**
    - #5733: the planning commit lands before late validation.
    - #5734: an unmaterialized coordination worktree gets the misleading "not finalized" refusal (related to #5410).
    - #5735: a shared implement application service (needs an ADR).
    - #5736: the #5232 B1 single-path end state (operator decision).
    - #5737: the remaining test remediation (ports, presenter, last couplings, GitPort timeout seam).
    - #5738: implement exits 1 silently on the claim-commit `SafeCommitHeadMismatch` (operator-approved fold, milestone 11).
    - #5739: dead `_INSCOPE_FILES` list.
    - #5740: `test_doctrine_asset` fails from a worktree (pre-existing red).
  - **No new issue for the `--no-auto-commit` second-claim refusal.** It duplicates #3471; the fresh reproduction is posted there. It is an operator-approved fold.
  - **Rows still to add after consolidation:** #5699, #5738 and #3471 are recorded as `fixed` once their folds land.
- 2026-10-05 — Review finding: the attribution footer is missing on the issue bodies. I re-sent the full body with the footer on #5739 and read it back. The footer was stripped again, so the posting tool removes it from issue bodies; comments keep theirs, as on #3471. The footer could not be kept through the tooling, and the miss is recorded here.
