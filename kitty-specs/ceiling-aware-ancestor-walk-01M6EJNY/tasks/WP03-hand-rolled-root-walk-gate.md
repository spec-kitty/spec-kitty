---
work_package_id: WP03
title: The gate and the harness cleanup
dependencies:
- WP02
requirement_refs:
- FR-007
- FR-008
- FR-009
- SC-002
- SC-004
- C-004
- C-005
planning_base_branch: issue-7056-ceiling-aware-ancestor-walk
merge_target_branch: issue-7056-ceiling-aware-ancestor-walk
branch_strategy: Planning artifacts for this mission were generated on issue-7056-ceiling-aware-ancestor-walk. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7056-ceiling-aware-ancestor-walk unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 3 - Ratchet
history:
- at: '2026-11-02T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/_hand_rolled_root_walk_scan.py
- tests/architectural/test_no_hand_rolled_root_walks.py
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/_hand_rolled_root_walk_scan.py
- tests/architectural/test_no_hand_rolled_root_walks.py
- tests/unit/workspace/test_root_resolver.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – The gate and the harness cleanup

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objectives & Success Criteria

- `tests/architectural/test_no_hand_rolled_root_walks.py` fails on a hand-rolled
  `[p, *p.parents]` / `(p, *p.parents)` / `[p] + list(p.parents)` walk anywhere under
  `src/` outside `src/kernel/ancestor_walk.py`.
- The exemption census is file+function keyed with a stated reason per entry, and the
  gate fails when an exemption no longer matches a scan hit.
- The gate is not vacuous: it asserts a non-empty corpus and has a positive control.
- `no_git_ancestry_inside_tmp_path` is removed only if provably redundant, with the
  finding recorded either way.
- The deferred harness work (the `stop=` parameter and `TMPDIR` under basetemp) is filed
  as a follow-up issue so the PR can cite it.

## Context & Constraints

- `research.md` D-2 and D-6: the scan shape is the starred/concat idiom, not every
  `.parents` loop — the exemption list would otherwise be bigger than the census.
- Use `tests/architectural/_ast_scan.py`'s fail-closed read/parse helpers; a scanner
  that swallows a parse error silently drops files from the census.
- Architectural tests carry `pytestmark = pytest.mark.architectural` and are selected by
  the marker across CI; no workflow edit is needed.

## Branch Strategy

- **Strategy**: the mission's lane worktree, branched from the mission branch.
- **Planning base branch**: `issue-7056-ceiling-aware-ancestor-walk`
- **Merge target branch**: `main` (the operator merges; this mission never pushes it)

## Subtasks & Detailed Guidance

### Subtask T001 – The scanner and the census

- **Purpose**: one place that knows what a hand-rolled root walk looks like and which
  sites are legitimately not root walks.
- **Steps**: create `tests/architectural/_hand_rolled_root_walk_scan.py` with:
  `Exemption` (path, function qualname, reason), the `EXEMPTIONS` tuple (from research
  D-2's "not root walks" and "frozen migrations" classes, each with its one-line
  reason), `scan_source(text, label)` returning `Hit(path, line, qualname, snippet)`
  for `ast.List`/`ast.Tuple` containing a `Starred` attribute `.parents` and for
  `BinOp(Add)` of `[x] + list(x.parents)`, and `scan_tree(root)` over `src/**.py`.
  Attribute a hit to its enclosing function via `ast.walk` + a qualname map.
- **Files**: `tests/architectural/_hand_rolled_root_walk_scan.py`
- **Parallel?**: no.
- **Notes**: skip `src/kernel/ancestor_walk.py` by path, not by function name.

### Subtask T002 – The gate test

- **Purpose**: enforce it.
- **Steps**: assertions: (1) the corpus is non-empty and `src/kernel/ancestor_walk.py`
  was scanned; (2) zero unlisted hits (report file:line + qualname in the failure
  message); (3) positive control — `scan_source("for p in [s, *s.parents]: pass")`
  reports exactly one hit, and the concat form too; (4) stale exemptions — every
  exemption matches at least one current hit, else fail naming it for removal.
- **Files**: `tests/architectural/test_no_hand_rolled_root_walks.py`
- **Parallel?**: no.
- **Notes**: keep failure messages actionable: "add it to the primitive, not the
  exemption list".

### Subtask T003 – Evaluate the hermeticity fixture

- **Purpose**: item 3 of the issue, honestly.
- **Steps**: read `tests/unit/workspace/test_root_resolver.py`'s
  `no_git_ancestry_inside_tmp_path`; remove it and run the module with the harness
  ceiling active (the default) — if green, add a control test that proves the ambient
  protection still exists (an ambient repo above basetemp is not adopted), else restore
  the fixture. Record the finding in the WP history note and the PR body.
- **Files**: `tests/unit/workspace/test_root_resolver.py`
- **Parallel?**: yes — disjoint from T001/T002.
- **Notes**: the fixture's `.git` inside `tmp_path` is *below* the ceiling, so it is not
  redundant for that case; only its ancestry protection is. State this explicitly.

### Subtask T004 – File the follow-up issue

- **Steps**: `gh issue create --repo spec-kitty/spec-kitty` for the deferred harness
  items (the test-only `stop=` parameter of `locate_project_root`/`find_repo_root`, and
  pointing `TMPDIR`/`TEMP` under basetemp plus the from-scratch child environments and
  the ~54 `tempfile` call sites), body referencing #7056 and this mission, with the
  reason each is out of scope here. Record the issue number in the WP history note.
- **Files**: n/a.
- **Parallel?**: yes.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_no_hand_rolled_root_walks.py -q
uv run --frozen pytest tests/unit/workspace/test_root_resolver.py -q
uv run --frozen mypy tests/architectural/_hand_rolled_root_walk_scan.py
uv run --frozen ruff check tests/architectural tests/unit/workspace
```

## Risks & Mitigations

- Gate passes vacuously → the non-empty corpus assertion and the positive control.
- Exemption list rots → stale-exemption failure, plus the reason text.
- Removing the fixture loses protection → the control test; restore if it fails.

## Review Guidance

- Confirm the gate would have caught at least one of WP02's pre-migration sites (say
  which one, by file:line, in the review note).
- Confirm the exemption census has no `src/` root walk left in it.
- Confirm no gate was skipped/xfailed anywhere in this WP.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP03 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
