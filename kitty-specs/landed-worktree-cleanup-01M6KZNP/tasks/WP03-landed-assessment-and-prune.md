---
work_package_id: WP03
title: Landed-worktree assessment and prune
dependencies:
- WP01
- WP02
requirement_refs:
- C-001
- C-003
- C-004
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- SC-001
- SC-003
planning_base_branch: issue-7173-landed-worktree-cleanup
merge_target_branch: issue-7173-landed-worktree-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-7173-landed-worktree-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7173-landed-worktree-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-landed-worktree-cleanup-01M6KZNP
base_commit: 6198bc9f1baa9218619d49c9ee493592c81a71d1
created_at: '2026-11-05T00:33:55.024094+00:00'
subtasks:
- T008
- T009
- T010
- T011
- T012
- T013
phase: Phase 1 - Core behaviour
history:
- at: '2026-11-04T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/workspace/
create_intent:
- src/specify_cli/workspace/landed_worktrees.py
- src/specify_cli/workspace/process_probe.py
- tests/specify_cli/workspace/test_landed_worktrees.py
- tests/specify_cli/workspace/test_process_probe.py
execution_mode: code_change
owned_files:
- src/specify_cli/workspace/landed_worktrees.py
- src/specify_cli/workspace/process_probe.py
- tests/specify_cli/workspace/test_landed_worktrees.py
- tests/specify_cli/workspace/test_process_probe.py
- tests/architectural/test_destructive_op_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Landed-worktree assessment and prune

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback; record changes with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

- `assess_worktrees(repo_root, *, current_dir) -> WorktreeAssessment` returns one `WorktreeVerdict` per registered worktree (data-model.md), read-only.
- `prune_landed(repo_root, *, current_dir) -> list[PruneOutcome]` removes **only** worktrees whose verdict is `landed`, re-evaluating each one immediately before acting, through the guard (`force=False`, `NothingIsResidue`), then deletes its branch with `LANDED_INTENT`.
- SC-001: on the fixture (rebase-merged with SHA rewrite, open with unpushed commit, dirty, running process, Mission lane), exactly the rebase-merged worktree and its branch are removed.
- NFR-001: 0 removals for uncommitted change, untracked file, unpushed commit, running process, locked worktree, Mission worktree, missing `origin/<primary>`, unprovable process check.
- NFR-002: no fetch, no network, no GitHub lookup. Never import `kernel.git.remote` fetch helpers.

## Context & Constraints

- Read: `kitty-specs/landed-worktree-cleanup-01M6KZNP/data-model.md` (verdict rule, ordered), `research.md` §3, `contracts/doctor-workspaces-cli.md`.
- Reuse (charter: single canonical authority, C-003):
  - Worktree list: `kernel.git.listing.worktree_entries` (WP01).
  - Absorption: `specify_cli.lanes.lane_tip.is_absorbed(repo_root, tip, target, base=None)` and `AbsorptionUnsupported` (legs 2–3: ancestor, then `merge-tree --write-tree` no-op; covers merge, rebase and squash landings; raises below git 2.38).
  - Mission ownership: `specify_cli.lanes.branch_naming.parse_mission_slug_from_branch(branch) is not None` (same predicate as `upgrade/runner.py::_is_integrating_worktree`).
  - Dirty check: `specify_cli.git.destructive_guard.assert_worktree_clean(worktree, context=NothingIsResidue(), treat_untracked_as_dirty=True)`; catch `DestructiveOpRefused` → `UNCOMMITTED_CHANGES` with its `dirty_entries`. Do **not** write another dirty predicate.
  - Removal: `guarded_worktree_remove(worktree, retain=False, context=NothingIsResidue(), force=False)` (WP02).
  - Branch delete: `guarded_branch_delete(repo_root, branch, creation_base=None, operator_intent=LANDED_INTENT)` (WP02).
  - `NothingIsResidue`: `specify_cli.coordination.coherence`.
- Primary ref: `primary = resolve_primary_branch(repo_root, bias=False)` (`specify_cli.core.git_ops`; `bias=True` would return the current branch — wrong here). Target ref `refs/remotes/origin/<primary>`; if `git rev-parse --verify --quiet <ref>^{commit}` fails → every candidate is `unproven` (`PRIMARY_REF_MISSING`). This is a local ref read, not a remote contact.
- Mission lane / coordination worktrees are **report-only** (C-004): `consolidate`, `retain_worktrees`, `DESTROYED_LANE` / `LANE_WORK_TIP_UNKNOWN` own them.

## Branch Strategy

- **Planning base branch**: `issue-7173-landed-worktree-cleanup`
- **Merge target branch**: `issue-7173-landed-worktree-cleanup`

Run `spec-kitty agent action implement WP03 --agent claude --mission landed-worktree-cleanup-01M6KZNP` and work in the printed workspace.

## Subtasks & Detailed Guidance

### Subtask T008 – Verdict model

- `class Verdict(StrEnum)`: `LANDED`, `NOT_LANDED`, `MISSION_OWNED`, `UNPROVEN`, `EXCLUDED`.
- `class Reason(StrEnum)`: the codes in data-model.md (`UNCOMMITTED_CHANGES`, `CONTENT_NOT_ON_PRIMARY`, `PROCESS_RUNNING`, `LOCKED`, `PRUNABLE`, `MISSION_LANE`, `PRIMARY_REF_MISSING`, `PROCESS_PROOF_UNAVAILABLE`, `ABSORPTION_UNSUPPORTED`, `MAIN_WORKTREE`, `CURRENT_WORKTREE`, `LANDED`).
- Frozen dataclasses `WorktreeVerdict(path, branch, tip, verdict, reason, detail)` with `removable` property, `PruneOutcome(path, branch, tip, removed, branch_deleted, kept_ref, recreate, refusal)`, and `WorktreeAssessment(primary_ref, verdicts, error)` (error set when the worktree list cannot be read).
- Each has `to_json()` returning plain dicts (WP04 renders them). Keep field names identical to data-model.md.
- `recreate` text: branch → `git branch <branch> <tip>`; detached → `git worktree add --detach <path> <tip>`.

### Subtask T009 – Running-process probe (`process_probe.py`)

- `processes_with_cwd_under(paths: Sequence[Path]) -> ProcessProbeResult` where the result is either `available=False` (no `/proc` or not Linux) or `available=True` with `busy: frozenset[Path]` (each input path that some process has as cwd or under it).
- Scan `/proc/<pid>/cwd` once per call (`os.readlink`), compare with resolved input paths (`Path.is_relative_to`).
- Only processes owned by the current uid are considered (`os.stat(f"/proc/{pid}").st_uid == os.getuid()`); a same-uid pid whose cwd cannot be read (`PermissionError`, `FileNotFoundError` racing exit is fine to skip) is ignored only for `FileNotFoundError`/`ProcessLookupError`; a same-uid `PermissionError` makes the probe `available=False` (fail closed). Document the residual: another user's process inside the worktree is not detected.
- Exclude the probing process itself (`os.getpid()`), but **not** its parent shell: a shell left in the worktree is a real busy signal.
- Inject the proc root (`proc_root: Path = Path("/proc")`) so tests can fake it.

### Subtask T010 – `assess_worktrees`

- Ordered rule (first match wins), exactly as data-model.md:
  1. main worktree (first entry) or the worktree containing `current_dir` → `EXCLUDED`
  2. `prunable` → `EXCLUDED` (`PRUNABLE`)
  3. bare → `EXCLUDED`
  4. Mission branch → `MISSION_OWNED`
  5. `locked` → `NOT_LANDED` (`LOCKED`)
  6. dirty → `NOT_LANDED` (`UNCOMMITTED_CHANGES`)
  7. primary ref missing → `UNPROVEN`
  8. `is_absorbed` false → `NOT_LANDED` (`CONTENT_NOT_ON_PRIMARY`); `AbsorptionUnsupported` → `UNPROVEN`
  9. process probe unavailable → `UNPROVEN`; busy → `NOT_LANDED` (`PROCESS_RUNNING`)
  10. otherwise → `LANDED`
- Run the process probe once for all candidates that reach step 9 (NFR-003).
- Split into small helpers so each function stays at complexity ≤ 15.

### Subtask T011 – `prune_landed`

- Assess; for each `LANDED` verdict, **re-assess that single worktree** (fresh list entry, dirty check, absorption, process probe) and act only if still `LANDED` with the same tip (TOCTOU).
- Remove the worktree via the guard (`force=False`). On `DestructiveOpRefused` record `refusal=<error_code>`, keep going with the next worktree, do not touch the branch.
- After removal, if the entry had a branch, delete it with `LANDED_INTENT`; record `kept_ref` when a tip was recorded (use `discarded_ref(repo_root, branch, tip)` to name it). A refusal there leaves the branch and is recorded.
- Never call any git command with `--force`; never call `git worktree prune`.

### Subtask T012 – Routing-gate pin

- In `tests/architectural/test_destructive_op_routing.py` add `("src/specify_cli/workspace/landed_worktrees.py", "<qualname of the caller>")` to `_OPERATOR_INTENT_CALLERS`, update the module docstring item 4 ("Named-intent pin") to name the prune site, and keep the planted-caller non-vacuity test as is. No allowlist.

### Subtask T013 – Safety-matrix tests

- `tests/specify_cli/workspace/test_landed_worktrees.py` (`integration`, `git_repo`). Build a real repo with a bare `origin`, push `main`.
- **Rebase-merge fixture must rewrite SHAs**: create the commit on the landing branch, push it, then on `main` re-create it with a different committer date (`GIT_COMMITTER_DATE` env on `git cherry-pick`), push `main`, `git fetch`. Assert `tip != ` the main commit SHA in the fixture (non-vacuity).
- Cases (each beside the landed positive control on the same fixture where meaningful):
  - rebase-merged → `LANDED`; prune removes worktree + branch; `git branch <b> <tip>` from the printed recreate restores the same SHA (SC-003).
  - remote head deleted after merge (`git push origin --delete land-x`, `git fetch --prune`) → still pruned; tip recorded under `refs/spec-kitty/discarded/land-x`.
  - squash-merged (single squashed commit on main) → `LANDED`.
  - uncommitted change; untracked file → kept (`UNCOMMITTED_CHANGES`).
  - ignored `.venv/` only → still `LANDED` and removed.
  - unpushed commit with new content → `NOT_LANDED` (`CONTENT_NOT_ON_PRIMARY`), kept.
  - running process: `subprocess.Popen(["sleep", "30"], cwd=worktree)` → `PROCESS_RUNNING`, kept; kill it in teardown.
  - process probe unavailable (fake proc root missing) → `UNPROVEN`, kept.
  - locked worktree → kept.
  - Mission lane branch `kitty/mission-foo-01ABCDEF-lane-a` → `MISSION_OWNED`, kept even when absorbed.
  - no `origin` remote → `UNPROVEN` for all.
  - detached worktree at a main commit → removed, no branch deleted, recreate is `git worktree add --detach`.
  - the worktree containing `current_dir` → `EXCLUDED`.
  - TOCTOU: monkeypatch so a file appears between assess and act → kept.
- `tests/specify_cli/workspace/test_process_probe.py`: fake proc tree (symlinks) for busy / idle / other-uid / permission error / missing proc root; one real `/proc` smoke test guarded by `sys.platform == "linux"`.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/workspace/ tests/architectural/test_destructive_op_routing.py tests/architectural/test_layer_rules.py -q
uv run --frozen ruff check src/specify_cli/workspace/ tests/specify_cli/workspace/
uv run --frozen ruff format --check --force-exclude src/specify_cli/workspace/landed_worktrees.py src/specify_cli/workspace/process_probe.py tests/specify_cli/workspace/test_landed_worktrees.py tests/specify_cli/workspace/test_process_probe.py tests/architectural/test_destructive_op_routing.py
uv run --frozen mypy src/specify_cli/workspace/landed_worktrees.py src/specify_cli/workspace/process_probe.py
uv run --frozen pytest tests/architectural/test_remote_contact_owner.py -q
```

## Risks & Mitigations

- Data loss: re-assess before act; guard re-checks cleanliness; `force=False` lets git refuse a lock or dirt as a third net.
- False "landed" from a stale ref: impossible to over-report — a stale `origin/<primary>` is older, so absorption can only fail.
- Slowness on 50 worktrees: one `/proc` scan, one status per worktree, `merge-tree` only when not an ancestor.

## Review Guidance

- Walk the verdict order against data-model.md.
- Confirm no new dirty predicate, no `--force`, no fetch, no `git worktree prune`.
- Confirm the rebase fixture really rewrites SHAs (assertion present).
- Confirm the pin change is the only change to the routing test besides the docstring.

## Progress & Status

Record notes with `spec-kitty agent tasks add-history WP03 --note "..."`.
