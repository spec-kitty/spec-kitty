---
work_package_id: WP01
title: The landing proof and consolidate adoption
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-009
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-004
- SC-001
- SC-003
planning_base_branch: fix/7747-lane-cleanup-landing-proof
merge_target_branch: fix/7747-lane-cleanup-landing-proof
branch_strategy: Planning artifacts for this mission were generated on fix/7747-lane-cleanup-landing-proof. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7747-lane-cleanup-landing-proof unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-cleanup-landing-proof-01M81KHJ
base_commit: 8f162f0f0d23d31d8e8651e79364818e2b6524bf
created_at: '2026-11-23T18:20:15.412900+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T014
phase: Phase 1 - Landing proof
history:
- at: '2026-11-23T18:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/lanes/test_lane_tip_mission_bookkeeping.py
- tests/integration/test_lane_cleanup_landing_proof_7747.py
execution_mode: code_change
owned_files:
- src/specify_cli/lanes/lane_tip.py
- src/specify_cli/consolidation/lane_cleanup.py
- tests/lanes/test_lane_tip_mission_bookkeeping.py
- tests/consolidation/test_lane_cleanup_auto_rebase_6736.py
- tests/integration/test_lane_cleanup_landing_proof_7747.py
- docs/adr/4.x/2026-11-06-1-a-destructive-git-operation-discharges-named-proof-obligations.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The landing proof and consolidate adoption

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address every feedback item; record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- `specify_cli.lanes.lane_tip.is_absorbed_but_for_mission_bookkeeping(repo_root, tip, landing_ref, mission_slug) -> bool` exists, is public (`__all__` if the module declares one) and is the only absorption proof `GuardedLaneRemover` uses when it knows the Mission slug.
- A real `lanes_with_coord` squash landing reports every lane `Removed` (today all `Kept NOT_LANDED_ON_NAMED_REMOTE`, #7747).
- Negatives stay kept: own WP body edit; product code beside the status log (`test_unlanded_work_beside_the_status_log_is_not_absorbed` stays green); merge-driver case; a deleted bookkeeping file; a lane-only status event.
- ADR 2026-11-06-1 records the set-aside (O3 amendment), including the earlier #6736 status-log set-aside and the Option A residual.

## Context & Constraints

- Spec FR-001..FR-006, FR-009; research R2/R3; contract `contracts/landing-proof.md`. Operator rulings 2026-11-22 (ledger R68) and 2026-11-23 Option A (R71).
- **Never trust a merge or merge-driver result on `kitty-specs/**`** (#7302 item 3). The destructive guard is unchanged (C-001). #7767 is out of scope (C-002).
- Complexity ≤ 15 per function (Sonar S3776 / ruff C901). No suppressions.
- `src/specify_cli/lanes/*` is a diff-cover critical path: every new branch needs a direct unit test in `tests/lanes/` (in-matrix). `tests/integration/` is nightly-only: the acceptance test there is evidence, not coverage.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: fix/7747-lane-cleanup-landing-proof
- **Merge target branch**: fix/7747-lane-cleanup-landing-proof

Implement with `spec-kitty agent action implement WP01 --agent claude --mission lane-cleanup-landing-proof-01M81KHJ`; the lane worktree comes from `lanes.json`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first acceptance (real CLI)

- **Purpose**: pin #7747 through the pre-existing entry point (`spec-kitty consolidate`).
- **Steps**:
  1. Create `tests/integration/test_lane_cleanup_landing_proof_7747.py`. Reuse `build`, `consolidate`, `_quiet`, `_lane_worktree`, `git` from `tests/integration/test_default_mission_consolidate_lands_primary.py` (three lanes; finalize settles ≤ 2 WPs to `single_branch`, so three is the smallest `lanes_with_coord` shape).
  2. Module-scoped fixture: `build(tmp)`, then `consolidate(built)`; assert exit 0.
  3. Assert the `Lane cleanup` block lists `Removed` for `lane-a`, `lane-b`, `lane-c`, no `Kept`; each lane worktree is gone; `git branch --list kitty/mission-<slug>-lane-*` is empty.
  4. Markers as the source module: `integration`, `git_repo`, `non_sandbox`, `slow`.
- **Commit it alone first** (red on the base), message `test(lane-cleanup): red-first — a squash landing removes every lane (#7747)`.

### Subtask T002 – Red-first unit rules

- **File**: `tests/lanes/test_lane_tip_mission_bookkeeping.py` (new, in-matrix).
- **Fixture** (synthetic, real git): `main` with a base commit → a coordination branch `kitty/mission-<slug>` with `kitty-specs/<slug>/{meta.json,status.json,status.events.jsonl,tasks/WP01-work.md,tasks/WP02-work.md,spec.md}` → a lane branch forked from it, which merges the coordination branch after a claim commit on coordination (`--no-ff`, the `implement` sync shape) and commits its own `src/lane.py`. The coordination branch then rewrites `meta.json`, `status.json`, appends to the log, adds claim frontmatter to `WP02-work.md`; the target squash-merges the coordination tip plus `src/lane.py` (`git merge --squash` of the lane into a target branch that already holds the coordination squash, or build the target commit by checking out paths), then appends a done event.
- **Cases** (each a separate test):
  - positive: the predicate is `True`; plain `is_absorbed` is `False` (the #7747 refusal);
  - lane edits its own `tasks/WP01-work.md` body in its own commit → `False`;
  - lane's own commit adds product code not on the target (beside the older status log) → `False`;
  - lane-only status event line → `False`;
  - lane deletes `meta.json` in its own commit → `False`;
  - lane's sync merge resolves a `kitty-specs` file to bytes equal to neither parent (simulate an evil merge: merge with `--no-commit`, edit the file, commit) → `False`;
  - merge-driver case: `.gitattributes` `kitty-specs/** merge=keeptarget`, `git config merge.keeptarget.driver true`; the lane's own commit edits `tasks/WP01-work.md`, the target edits it differently; assert plain `is_absorbed` is `True` (control: the driver hides the lane edit) and the predicate is `False`;
  - another Mission's slug → `False`;
  - unknown tip `"0"*40` → `False` (git error fails closed);
  - lane tip already an ancestor of the landing ref → `True`;
  - lane version of a bookkeeping file found in the target's history (merge-strategy shape) → `True`;
  - a non-bookkeeping `kitty-specs` file (e.g. `spec.md`) the lane holds older than the target → `False` (C-004);
  - the lane lacks a `kitty-specs` file the target added (retrospective) → still `True`.
- Commit with T001 or right after, before any `src/` change.

### Subtask T003 – Lane-own commits and authored paths

- **File**: `src/specify_cli/lanes/lane_tip.py`.
- `_lane_own_commits(repo_root, tip, landing_ref) -> tuple[str, ...]`:
  - `git rev-list --first-parent --parents <tip> ^<landing_ref>` → each line `c p1 [p2...]`; collect every non-first parent `S`.
  - own = `git rev-list --first-parent <tip> ^<landing_ref> ^S1 ^S2 ...` (pass the exclusions as separate args; use `kernel.git.run_git`).
- `_authored_paths(repo_root, own, parents) -> frozenset[str]`:
  - for each own commit with first parent `fp`: `git diff-tree -r --no-commit-id --name-only -z --no-renames fp c` (a root commit: `--root c`);
  - non-merge: every listed path is authored;
  - merge: a listed path is authored unless the merge's version equals one of its non-first parents' versions (compare tree-entry oids via `kernel.git.tree_entry`; both absent counts as equal).
- Keep each helper ≤ 15 complexity; return immutable types.

### Subtask T004 – The public predicate

- `is_absorbed_but_for_mission_bookkeeping(repo_root, tip, landing_ref, mission_slug) -> bool`, wrapped so any `GitCommandError` (and `OSError`) returns `False`:
  1. `merge-base --is-ancestor tip landing_ref` → `True`.
  2. own / authored (T003).
  3. `kernel.git.merge_tree(repo_root, landing_ref, tip)`: no tree → `False`; any conflicted path outside `kitty-specs/` → `False`; `changed_paths(landing_ref, merged.tree)` outside `kitty-specs/` non-empty → `False`. Results for `kitty-specs/` paths are ignored.
  4. For each path in `changed_paths(landing_ref, tip)` under `kitty-specs/`, apply research R3 rules 1–4 (helper `_mission_path_accounted(...)`). The status log rule is the moved `_status_log_contained`. The bookkeeping kinds: `kitty-specs/<slug>/status.json`, `.../meta.json`, `.../tasks/WP*.md` (match `tasks/` direct child, name `WP*.md`, use `fnmatch` on the basename and require the parent to be exactly `kitty-specs/<slug>/tasks`). "Found in the target's history" = the lane blob's oid is among `git log --full-history -m --raw --no-abbrev --format= <landing_ref> -- <path>` old/new oids.
- Import the file names from where `lane_cleanup.py` gets them (`specify_cli.status.EVENTS_FILENAME`, `SNAPSHOT_FILENAME`, `specify_cli.core.constants.KITTY_SPECS_DIR`) — use a function-local import if a top-level one is circular (the module already does this for `policy`).
- Docstring: name the rules, the rulings and the residual.

### Subtask T005 – Consolidate adoption

- `lane_cleanup.GuardedLaneRemover._absorbed`: with `mission_slug` → the predicate only; without → plain `is_absorbed` (unchanged, `AbsorptionUnsupported` → `False`).
- Delete `_status_log_contained` and `_absorbed_but_for_status_log` from `lane_cleanup.py`; drop now-unused imports. Update the class docstring.
- `tests/consolidation/test_lane_cleanup_auto_rebase_6736.py`: re-pin only the import (`is_absorbed_but_for_mission_bookkeeping as _absorbed_but_for_status_log` or rename the call sites); every test there stays green unmodified otherwise. Disclose the change in the PR.

### Subtask T006 – ADR amendment

- `docs/adr/4.x/2026-11-06-1-...md`: add `## Amendment 2026-11-23: Mission bookkeeping in the O3 absorption proof` (keep the O3 row; append a pointer sentence to it). Record: the #6736 status-log set-aside (never recorded before); the #7747 extension to `status.json`, `meta.json`, `tasks/WP*.md` of the lane's own Mission under the never-authored rule (Option A, lane-own graph); no merge/driver result on `kitty-specs/**`; doctor uses it only for released Mission lanes; the residual (a version merged in from a non-coordination branch); the #7325 kept legs (`LANDING_PROOF_UNAVAILABLE`, WP03). Also update the paragraph at the Scope section ("a caller whose proof is not a remote-tracking ref ... needs an amendment to O3 first") only if it is now inaccurate.

### Subtask T014 – `accept --mode pr` adopts the proof (G1, operator ruling 2026-11-23, 3A)

- **Purpose**: the pr-mode lane cleanup (`src/specify_cli/acceptance/__init__.py::pr_mode_lane_cleanup`) built `GuardedLaneRemover` without a Mission slug, so it kept the plain proof and the #7747 symptom.
- **Red-first test**: `tests/consolidation/test_pr_mode_landing_proof_7747.py` (in-matrix: the `consolidation` row's roots include `src/specify_cli/acceptance/**`; `tests/acceptance/` is nightly-only). A pushed PR head that squashed the coordination tip and the lane's product: today the lane is kept `NOT_LANDED_ON_NAMED_REMOTE`; after, removed. Negative: a lane with product code the head lacks stays kept.
- **Change**: pass `mission_slug=manifest.mission_slug` to `GuardedLaneRemover`.
- **Out-of-map edit (rationale)**: both files are outside WP01's `owned_files`; the operator placed G1 in this Mission after finalize, and WP01 owns the adoption concern. No other WP touches them.

## Test Strategy

```bash
uv run --frozen pytest tests/lanes/test_lane_tip_mission_bookkeeping.py tests/lanes/test_lane_tip.py -q
uv run --frozen pytest tests/consolidation/ -q -n auto --dist loadfile
uv run --frozen pytest tests/integration/test_lane_cleanup_landing_proof_7747.py -q   # nightly-only dir: disclose
uv run --frozen pytest tests/architectural/test_destructive_op_routing.py -q            # out-of-matrix: disclose
make test-fast
uv run --frozen ruff check <changed> && uv run --frozen ruff format --check --force-exclude <changed>
uv run --frozen mypy src/specify_cli/lanes/lane_tip.py src/specify_cli/consolidation/lane_cleanup.py
```

## Risks & Mitigations

- History walk cost (NFR-001): only run it for a bookkeeping file the lane authored.
- `rev-list` with many `^S` args: S is small (one per sync merge).

## Review Guidance

- Red-first: T001/T002 commits precede the `src/` commit and fail on the base.
- Check no merge result is read for a `kitty-specs/` path, and that the predicate never calls plain `is_absorbed`.
- mypy and ruff (format with `--force-exclude`) clean, no suppressions.

## Progress & Status

Progress lives in the status event log. Use `spec-kitty agent tasks add-history WP01 --note "..."`, `spec-kitty agent tasks move-task WP01 --to <status>`, `spec-kitty agent tasks status`.
