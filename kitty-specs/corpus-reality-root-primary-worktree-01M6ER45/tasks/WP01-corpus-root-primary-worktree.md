---
work_package_id: WP01
title: One root, resolved once
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6966-corpus-reality-root
merge_target_branch: issue-6966-corpus-reality-root
branch_strategy: Planning artifacts for this mission were generated on issue-6966-corpus-reality-root. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6966-corpus-reality-root unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - The root decision
history:
- at: '2026-11-02T18:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/contract/_mission_status_oracles.py
- tests/contract/test_mission_status_reality.py
- docs/development/reference/ci-gate-mechanics.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6966'
---

# Work Package Prompt: WP01 – One root, resolved once

## ⚡ Do This First: Load Agent Profile

- **Profile**: `python-pedro`
- **Role**: `implementer`

## Objectives & Success Criteria

The corpus reality check currently takes its repository root from the checkout it is imported from
(`tests/contract/test_mission_status_reality.py:79`, `Path(__file__).resolve().parents[2]`), while the
Mission resolver answers each Mission's read directory from the **primary worktree** of the repository.
From a linked worktree (`git worktree add`, the report's own repro) the check therefore enumerates one
tree and reads Missions out of another. Two readers react differently to that mixed tree:

- the drift scan refuses the whole project-wide report with `500 drift_scan_unreadable`
  (`ReadDirOutsideRoot`), and five tests die with `KeyError: 'findings'`;
- the Project read invents an `outside root` fallback the independent oracle never derives.

Done means: one root decision, resolved once, at the module's `REPO_ROOT`, and **no** assertion, floor,
ceiling, allow-list or skip touched. The readers keep trusting the resolver.

## Subtasks

### T001 — Red-first pin (do this first, and see it fail)

Add to `tests/contract/test_mission_status_reality.py` a test that:

1. builds a real git repository in `tmp_path` (`git init`, one commit), adds a **linked worktree**
   (`git worktree add <path> -b other`), and
2. asserts `oracles.primary_worktree_root()` answers the primary root for **both** paths, and
3. asserts it answers the given path for a directory git cannot answer for (a plain `tmp_path` child,
   not a repository).

Run it before adding the helper: it must be red (`AttributeError`). Commit that red state separately so
the red→green trail is visible.

### T002 — The helper

`tests/contract/_mission_status_oracles.py`:

```python
def primary_worktree_root(repo_root: Path) -> Path:
    """The repository's primary worktree root for *repo_root* (itself when git cannot answer)."""
```

Use the module's existing `run_git` seam. `git worktree list --porcelain` prints the primary worktree
first; take the first `worktree ` line, `Path(...).resolve()`. Fail soft — the given path — when git is
absent (`OSError`), the directory is not a repository (non-zero exit), or the listing raises
`subprocess.SubprocessError`.

### T003 — The one changed expression

Replace line 79's expression with `REPO_ROOT = oracles.primary_worktree_root(Path(__file__).resolve().parents[2])`.
Nothing else in the module changes: no marker, no skip, no assertion, no floor.

### T004 — The linked-worktree proof

```
git worktree add --detach /tmp/wt-6966 origin/main   # inside a scratch clone, not this one
cd /tmp/wt-6966 && make sync-packs && make sync-services ARGS=--extras-only
uv run pytest tests/contract/test_mission_status_reality.py -q -m "corpus and not windows_ci" -p no:randomly
```

Before the change, five tests fail (three `KeyError: 'findings'`, `project fallbacks: only the reader
has [...]`, `DriftReport` schema). After it, all pass. Record both numbers in the PR body.

### T005 — The no-weakening proof

Same command from the primary checkout: `870 passed, 5 skipped` before and after on the base commit,
and `git diff origin/main -- tests/contract/test_mission_status_reality.py` shows the root expression
plus the new test only.

### T006 — Docs

`docs/development/reference/ci-gate-mechanics.md`, in the bullets that describe the reality check: say
that it reads the **repository's primary worktree** (the tree the resolver, the corpus and the oracle
mean), so running it from a linked worktree checks the primary worktree's corpus rather than the
worktree's.

### T007 — Changelog fragment

`docs/changelog/unreleased/<pr>.internal.md` (non-user-facing: test infrastructure), named from the
created PR number, per `docs/changelog/unreleased/README.md`.

## Constraints

- No `src/` change.
- Do not edit `_mission_status_drift.py` or `_mission_status_project.py`.
- Do not weaken, skip or xfail anything.
- Keep the diff to the two test-module files plus docs.

## Validation

```bash
uv run pytest tests/contract/test_mission_status_reality.py -q -m "corpus and not windows_ci" -p no:randomly
uv run pytest tests/ci/test_contracts_routing.py -q
uv run ruff check tests/contract/_mission_status_oracles.py tests/contract/test_mission_status_reality.py
uv run ruff format --check tests/contract/_mission_status_oracles.py tests/contract/test_mission_status_reality.py
```
