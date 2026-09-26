---
work_package_id: WP07
title: Atomic lane-naming signature cutover
dependencies:
- WP03
- WP04
- WP05
- WP06
requirement_refs:
- FR-001
- FR-002
- NFR-001
planning_base_branch: claude/charter-load-mission-q9ajcz
merge_target_branch: claude/charter-load-mission-q9ajcz
branch_strategy: Planning artifacts for this mission were generated on claude/charter-load-mission-q9ajcz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/charter-load-mission-q9ajcz unless the human explicitly redirects the landing branch.
subtasks:
- T048
- T049
- T050
- T051
phase: Phase 4 - Close the defect class (wave 4)
task_type: implement
execution_mode: code_change
owned_files:
- src/specify_cli/lanes/worktree_allocator.py
- src/specify_cli/lanes/merge.py
- src/specify_cli/lanes/implement_support.py
- src/specify_cli/workspace/context.py
- src/specify_cli/orchestrator_api/commands.py
- src/specify_cli/coordination/status_transition.py
- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
- src/specify_cli/cli/commands/mission_type.py
- tests/lanes/test_branch_naming_seam.py
- tests/specify_cli/lanes/test_branch_naming_ssot_entrypoint.py
- tests/core/test_branch_naming_human_slug.py
- tests/lanes/test_lanes_worktree_routing.py
- tests/lanes/test_worktree_allocator_atomicity.py
- tests/lanes/test_issue_4827_allocator_orphan_pin.py
- tests/specify_cli/lanes/test_predict_lane_worktree.py
- tests/integration/test_coord_read_residuals_proof.py
- tests/integration/test_lanes_core_coord_read.py
- tests/integration/test_merge_lane_worktree_safety.py
- tests/integration/test_colliding_mission_flow.py
- tests/orchestrator_api/test_worktree_cleanup_guard.py
- tests/specify_cli/cli/commands/agent/test_2861_causation_repro.py
- tests/specify_cli/test_read_seam_migration_core.py
- tests/specify_cli/lanes/test_lane_naming_signature.py
authoritative_surface: src/specify_cli/lanes/worktree_allocator.py
create_intent:
- tests/specify_cli/lanes/test_lane_naming_signature.py
agent_profile: python-pedro
role: implementer
agent: claude
model: ''
assignee: ''
shell_pid: ''
history:
- at: '2026-09-26T13:17:07Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
---

# Work Package Prompt: WP07 – Atomic lane-naming signature cutover

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

This WP removes the only way to request a lane-naming form (DIRECTIVE_043: close the class by construction). The gate that keeps it closed is **WP11**; this WP must leave the **existing** gate untouched and green.

1. **FR-002 / PD-1**: the public lane-naming surface offers no way to request a naming form:
   - `lane_branch_name(mission_slug, lane_id, planning_base_branch=None)`
   - `worktree_dir_name(mission_slug, *, lane_id)`
   - `worktree_path(repo_root, mission_slug, *, lane_id)`

   Each body is today's `mission_id is None` branch, **byte-identical**. `mission_branch_name`, `mission_branch_name_required`, `coord_branch_name`, `resolve_branch_name` and `resolve_transaction_mid8` **keep** `mission_id`: they name Mission and coordination branches, not lanes.
2. **Atomic cutover** (tasks.md deviation 2): the parameter removal, every residual caller in `src/` and `tests/`, and the golden re-pins land in **ONE commit**. At HEAD, `worktree_*` require the keyword, so removing it piecemeal breaks the tree.
3. **PD-3 / NFR-001**: re-pin to the created name the lane and worktree golden columns that encode identity-injected names creation never produces. Mission-branch, coordination and Mission-dir columns stay **byte-identical**. Add rows asserting that divergent shapes compose the created name.
4. **Existing gate unchanged and green**: `tests/architectural/test_no_worktree_name_guess.py` is **not edited** by this WP (WP11 owns it) and passes after the cutover commit. So does `tests/architectural/test_no_dead_symbols.py`.

## Context & Constraints

- **Spec**: FR-001, FR-002, NFR-001, SC-004, and US4 AS3 (the signature half of US4; the gate half is WP11).
- **Plan**: PD-1, PD-3, and the Gate Baseline rows "Lane-naming calls passing `mission_id`" (6 non-None, 18 `None` at mission start → 0).
- **Research Part A**: §1.1–§1.4 (signatures, all callers, the golden conflict) and ADJ-1 (the golden reading).
- **tasks.md**: deviation 2 (atomicity), deviation 7 (module docstring), and the ownership table.
- **Upstream state you rely on**:
  - WP01 (`merge/reconciliation.py`, `tests/merge/test_reconciliation.py`), WP02 (`merge/executor.py`, `tests/merge/test_executor_terminus_integrity.py`, `TestRetentionConstraintSurvivesCleanup`), WP03 (`tests/merge/test_mid8_embedded_preflight.py`) and WP04 (`lanes/lifecycle_sync.py`, `lanes/recovery.py`, `acceptance/__init__.py`, `tests/specify_cli/acceptance/test_accept_candidate_source_tree_4254.py`) already removed the `mission_id` keyword from lane-naming calls in their own files, or routed them through `predict_lane_worktree`.
  - WP05 finished `lanes/branch_naming.py` (additive parsers and `_LANE_ID_RE`).
- **Not in this WP** (all moved to **WP11**): `core/vcs/detection.py`, the `_coordination_doctor.py` drift matcher, the `lifecycle_sync.py` `-unknown` placeholder, the allow-list shrink, the four new gate legs, the self-test, `_baselines.yaml`. Do not touch any of them.
- **Layer rules**: no new cross-layer imports (C-003). `src/runtime` has no lane-naming call today; the scan below confirms it.

### Bounded out-of-map edits (explicit list; nothing else)

The inventory below was computed at HEAD `8900c2cb` with an alias-aware AST scan (it follows `import … as` names from `branch_naming`: `_worktree_path`, `_seam_worktree_path`, `_wt_path`, `_worktree_dir_name`, `_worktree_path_helper`) of calls to `lane_branch_name` / `worktree_dir_name` / `worktree_path` that pass a `mission_id` keyword. At HEAD it found **14 src files** (13 callers with 24 calls, plus `lanes/branch_naming.py` itself) and **19 test files** (64 calls).

| File | Owner | HEAD calls | Who removes the keyword |
|---|---|---|---|
| `src/specify_cli/lanes/branch_naming.py` | WP05 | internal `worktree_dir_name` → `lane_branch_name(..., mission_id=mission_id)`, plus the `mission_id=None` keywords WP05's new parsers pass to `worktree_dir_name` | **WP07, out-of-map** (signature removal, those internal keyword tokens, and the module docstring only) |
| `src/specify_cli/lanes/worktree_allocator.py` | WP07 | 1 (`None`) | WP07 |
| `src/specify_cli/lanes/merge.py` | WP07 | 1 (`None`) | WP07 |
| `src/specify_cli/lanes/implement_support.py` | WP07 | 1 (`None`) | WP07 |
| `src/specify_cli/workspace/context.py` | WP07 | 5 (`None`) | WP07 |
| `src/specify_cli/orchestrator_api/commands.py` | WP07 | 2 (`None`) | WP07 |
| `src/specify_cli/coordination/status_transition.py` | WP07 | 1 (`None`) | WP07 |
| `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py` | WP07 | 1 (`None`) | WP07 |
| `src/specify_cli/cli/commands/mission_type.py` | WP07 | 1 (`None`) | WP07 |
| `src/specify_cli/merge/reconciliation.py` | WP01 | 1 (id) | WP01 |
| `src/specify_cli/merge/executor.py` | WP02 | 4 (3 id, 1 `None`) | WP02 — **except** a single `mission_id=None` inside `_created_lane_worktree` if WP02's Activity Log records that import-cycle fallback: then **WP07, out-of-map**, that one keyword token only |
| `src/specify_cli/acceptance/__init__.py` | WP04 | 1 (id) | WP04 — **except** a `mission_id=None` in `_approved_lane_source_roots` if WP04's Activity Log records the fallback: then **WP07, out-of-map**, that token only |
| `src/specify_cli/lanes/lifecycle_sync.py` | WP04 | 2 (1 id, 1 `None`) | WP04 — same conditional fallback rule |
| `src/specify_cli/lanes/recovery.py` | WP04 | 3 (`None`) | WP04 — same conditional fallback rule, for the three worktree lookups only |
| 14 test files in this WP's `owned_files` | WP07 | 42 | WP07 (T050/T051) |
| `tests/merge/test_reconciliation.py` | WP01 | 15 | WP01 |
| `tests/merge/test_executor_terminus_integrity.py`, `tests/integration/test_merge_lane_planning_data_loss.py` | WP02 | 1 + 3 | WP02 |
| `tests/merge/test_mid8_embedded_preflight.py` | WP03 | 2 | WP03 |
| `tests/specify_cli/acceptance/test_accept_candidate_source_tree_4254.py` | WP04 | 1 | WP04 |

**STOP rule**: re-run the scan (T049 step 1) at your base. **Any hit outside the rows marked "WP07" above** (a file not listed, a non-fallback site in an upstream-owned file, or a hit in `src/runtime`) ⇒ **STOP and report to the orchestrator**. Do not edit it. Each out-of-map edit you do make gets a one-line Activity Log entry.

**Implementation command**: `spec-kitty agent action implement WP07 --agent <name>`. It depends on WP03, WP04, WP05 and WP06.

## Branch Strategy

- **Strategy**: Planning artifacts for this mission were generated on `claude/charter-load-mission-q9ajcz`. During `/spec-kitty.implement` this WP may branch from a dependency-specific base, but completed changes must merge back into `claude/charter-load-mission-q9ajcz` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `claude/charter-load-mission-q9ajcz`
- **Merge target branch**: `claude/charter-load-mission-q9ajcz`

> Execution worktrees are allocated per computed lane from `lanes.json`. Use the workspace `spec-kitty agent action implement` resolves.

## Subtasks & Detailed Guidance

### Subtask T048 – Red-first signature test

- **File**: `tests/specify_cli/lanes/test_lane_naming_signature.py` (new).
- **Tests**:
  - For each of `lane_branch_name`, `worktree_dir_name`, `worktree_path` and `predict_lane_worktree`: `"mission_id" not in inspect.signature(fn).parameters` (US4 AS3).
  - Byte-identity goldens for the created form, written as literals: `lane_branch_name("057-foo", "lane-a") == "kitty/mission-057-foo-lane-a"`; the NNN-plus-mid8 slug `057-foo-01KV6510` → `kitty/mission-foo-01KV6510-lane-a` (idempotent body); `worktree_dir_name("057-foo-01KV6510", lane_id="lane-a") == "057-foo-01KV6510-lane-a"` (verbatim); `lane-planning` → the planning base.
- **Red on HEAD**, since the signature still has `mission_id`. Record the run in the Activity Log.

### Subtask T049 – Atomic cutover: parameter + every residual src caller

- **Step 1: inventory.** Run the alias-aware AST scan over `src/` and `tests/` and compare it with the table in Context & Constraints. Apply the STOP rule. The scan (run ad hoc; do not commit):

```python
import ast, pathlib
TARGETS = {"lane_branch_name", "worktree_dir_name", "worktree_path"}
for base in ("src", "tests"):
    for p in pathlib.Path(base).rglob("*.py"):
        if p.as_posix() == "src/specify_cli/lanes/branch_naming.py":
            continue
        t = ast.parse(p.read_text())
        names = {a.asname or a.name: a.name for n in ast.walk(t) if isinstance(n, ast.ImportFrom)
                 and n.module and n.module.endswith("branch_naming") for a in n.names if a.name in TARGETS}
        for n in ast.walk(t):
            if isinstance(n, ast.Call):
                f = n.func
                hit = (isinstance(f, ast.Name) and f.id in names) or (isinstance(f, ast.Attribute) and f.attr in TARGETS)
                if hit and any(k.arg == "mission_id" for k in n.keywords):
                    print(p, n.lineno)
```

- **Step 2: `branch_naming.py`** (out-of-map, WP05-owned):
  - Remove `mission_id` from the three signatures.
  - Bodies:
    - `lane_branch_name`: the planning-lane return, then `f"{_MISSION_PREFIX}{_idempotent_legacy_body(mission_slug)}-{lane_id}"`.
    - `worktree_dir_name`: `f"{mission_slug}-{lane_id}"` (verbatim, **no** delegation to `lane_branch_name`).
    - `worktree_path`: joins `worktree_dir_name(mission_slug, lane_id=lane_id)`.
  - `_mid8` and `_human_slug_for_mid8_branch` stay, used only by `mission_branch_name`. If one becomes unused, `test_no_dead_symbols.py` will say so; delete it rather than allow-list it.
  - Update the docstrings and **the module docstring** (PD-15): "lane branch and worktree names are keyed on the creation input (slug + lane id); the Mission identity is not an input (I-1); mid8 appears in a lane name only when the slug embeds it". Also update the examples.
  - Remove the "introducing a mission_id here would … rename every existing lane worktree" commentary in `predict_lane_worktree`, since it is now impossible.
  - Do **not** change `_LANE_ID_RE`, the parsers or `is_lane_branch` (WP05's).
- **Step 3**: drop every residual `mission_id=` keyword on the three functions in the WP07 rows of the table (plus any logged fallback token). Re-wrap lines per `ruff format`. That is the only change in each of those files.
- **Step 4**: run the full owned test set, the **unchanged** `tests/architectural/test_no_worktree_name_guess.py`, `tests/architectural/test_no_dead_symbols.py` and `make test-fast` before committing. Commit src plus tests together, with T050 and T051, in **one commit**.
- **Validation**:
  - [ ] The AST scan reports 0 lane-naming calls with a `mission_id` keyword in `src/` and `tests/`.
  - [ ] T048 is green.
  - [ ] Pinned-byte goldens for Mission, coordination and Mission-dir are unchanged.
  - [ ] `git diff` shows no change to `tests/architectural/test_no_worktree_name_guess.py`, and it is green.

### Subtask T050 – Re-pin the identity-injected lane/worktree goldens (PD-3)

- **Files** (owned):
  - `tests/specify_cli/lanes/test_branch_naming_ssot_entrypoint.py`, `_PARITY_CASES` rows 1, 2 and 5 (research §1.4):
    - `mission-id-canonical-identity-migration` with `_OTHER_ID`;
    - `083-my-feature` with `_OTHER_ID` → today `my-feature-01KNXQS9-lane-a`;
    - `plain-slug` with `_FULL_ID` → today `plain-slug-01KV6510-lane-a`.

    Row 3 (embedded, matching id) gives identical bytes; row 4 is unchanged.
  - `tests/lanes/test_branch_naming_seam.py`, `GOLDEN_ROWS["legacy-NNN-with-mid8-1589"]`: `lane_branch="kitty/mission-test-01COORD0-lane-a"` and `worktree_dir="test-01COORD0-lane-a"`. This is literally #5108 shape (a).
  - `tests/core/test_branch_naming_human_slug.py`: the lane cases (HEAD lines 93, 100, 108, 114, 119, 138, 139, 264, 306, including the mismatched-mid8 lane).
- **Rule**:
  - Re-pin **only** the lane and worktree columns of rows whose value encodes an identity-injected name. Set the expected value to the created name, and write it as a **literal**.
  - Add a comment: `# PD-3 / ADJ-1: re-pinned to the created name; the identity-injected form pinned the #5108 defect`.
  - Mission-branch, coordination and Mission-dir columns stay byte-identical. Diff-review every changed literal.
  - Add new rows per divergent shape (backfilled legacy, mismatched mid8, invalid ≥ 8, invalid < 8), asserting the created name. The invalid-identity rows show lane naming never raises (spec edge case).
- **Record in the Activity Log**: the list of re-pinned (row, column) pairs, and the list of unchanged columns verified (NFR-001 / SC-004 evidence).

### Subtask T051 – Migrate residual test call sites

- **Files** (owned; HEAD counts): `test_lanes_worktree_routing.py` (6), `test_worktree_allocator_atomicity.py` (3), `test_issue_4827_allocator_orphan_pin.py` (1), `test_predict_lane_worktree.py` (1), `test_coord_read_residuals_proof.py` (3), `test_lanes_core_coord_read.py` (3), `test_merge_lane_worktree_safety.py` (1), `test_colliding_mission_flow.py` (1), `test_worktree_cleanup_guard.py` (1), `test_2861_causation_repro.py` (2), `test_read_seam_migration_core.py` (1). Recount with the scan.
- **Rule (FR-012)**:
  - A `mission_id=None` keyword: delete it (mechanical).
  - A non-None identity: check whether the fixture **creates** a branch or worktree under that name.
    - If it does, move it to the allocator or `predict_lane_worktree`.
    - If the slug embeds the same mid8 (the bytes are equal), drop the keyword.
    - If the test pinned the identity-injected form as expected behaviour, re-express it as the created name and log it.
- **No test file outside `owned_files` is edited.** A scan hit in any other test file ⇒ STOP rule.
- **Validation**: the AST scan over `tests/` reports 0, and every touched test file passes.

## Test Strategy

- **Red-first**: T048 is red on HEAD (the signature still has `mission_id`). Record the run.
- **Goldens**: literals only. The re-pins are listed in the Activity Log (NFR-001 evidence).
- **Commands**:

```bash
.venv/bin/python -m pytest tests/specify_cli/lanes/test_lane_naming_signature.py -q
.venv/bin/python -m pytest tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_no_dead_symbols.py -q   # UNCHANGED file, must be green
.venv/bin/python -m pytest tests/lanes/ tests/specify_cli/lanes/ tests/core/test_branch_naming_human_slug.py tests/merge/ tests/integration/ tests/orchestrator_api/ tests/specify_cli/cli/commands/ tests/specify_cli/coordination/ tests/specify_cli/workspace/ -q
make test-fast
```

- **NFR gates** (every touched src file, including `branch_naming.py`):

```bash
FILES="src/specify_cli/lanes/branch_naming.py src/specify_cli/lanes/worktree_allocator.py src/specify_cli/lanes/merge.py src/specify_cli/lanes/implement_support.py src/specify_cli/workspace/context.py src/specify_cli/orchestrator_api/commands.py src/specify_cli/coordination/status_transition.py src/specify_cli/cli/commands/agent/tasks_parsing_validation.py src/specify_cli/cli/commands/mission_type.py"
.venv/bin/ruff check $FILES tests/specify_cli/lanes/test_lane_naming_signature.py
.venv/bin/ruff check --select C901 $FILES
.venv/bin/ruff format --check $FILES tests/
.venv/bin/mypy $FILES tests/specify_cli/lanes/test_lane_naming_signature.py
```

## Definition of Done

- [ ] The three lane functions have no `mission_id`. The bodies are byte-identical to the former `None` path.
- [ ] 0 lane-naming calls with `mission_id` in `src/` and `tests/` (AST scan), with no edit outside the explicit table.
- [ ] Signature removal, residual callers and golden re-pins are in **one commit**.
- [ ] Goldens re-pinned per PD-3 only, and the Mission/coord/dir columns are unchanged (evidence logged).
- [ ] `tests/architectural/test_no_worktree_name_guess.py` is **unchanged** and green; `test_no_dead_symbols.py` is green.
- [ ] `make test-fast` is green; ruff, ruff format, mypy and C901 are clean on touched files.
- [ ] Out-of-map edits are listed in the Activity Log with a one-line rationale each.

## Risks & Mitigations

- **Atomicity**: stage src plus tests in one commit; run `make test-fast` before committing.
- **Scope creep into the gate**: the gate work is WP11. If the unchanged gate goes red after the cutover, STOP and report; do not edit it.
- **`test_no_dead_symbols.py` shifts** after helpers become unused: delete the dead code. Do not grow the allow-list.
- **Golden re-pin overreach**: reviewers diff every literal. Only lane and worktree columns of identity-injected rows change.

## Review Guidance

- Check the `inspect.signature` evidence and the AST-scan evidence (0/0).
- Confirm the commit is atomic and that every edited file is in the explicit table.
- Review each golden change against the PD-3 list.
- Confirm `tests/architectural/test_no_worktree_name_guess.py` has no diff and is green.
- mypy was run.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-09-26T13:17:07Z – system – Prompt created.
- 2026-09-26T13:47:00Z – planner-priti – Post-tasks squad split: T052–T055 (gate legs, gate-pinned sites, allow-list shrink) moved to WP11; out-of-map clause bounded to an explicit file table.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
