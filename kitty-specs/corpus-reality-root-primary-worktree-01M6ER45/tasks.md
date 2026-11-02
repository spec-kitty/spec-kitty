# Work Packages: Corpus reality check resolves the repository root (#6966)

**Inputs**: Design documents from `/kitty-specs/corpus-reality-root-primary-worktree-01M6ER45/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: The subject *is* a test module. The change adds one pinning test and one root expression;
no assertion, floor, ceiling or skip in the corpus suite changes (NFR-002).

**Organization**: One work package. The fix is a single root decision plus the proof that it
changes nothing else; splitting it would put the pin in a different lane from the expression it pins.

**Prompt Files**: `tasks/WP01-corpus-root-primary-worktree.md`

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/`, `tests/`, `docs/` at the repository root. This mission touches only
  `tests/contract/` and `docs/`.

---

## Work Package WP01: One root, resolved once (Priority: P1) 🎯 MVP

**Goal**: The corpus reality check scans the repository's primary worktree, so a linked-worktree
checkout reads one tree instead of enumerating one and reading Missions out of another, and the
`500 drift_scan_unreadable` / `KeyError: 'findings'` / `project fallbacks` reds disappear without
any assertion, floor, ceiling or skip being touched.
**Independent Test**: `uv run pytest tests/contract/test_mission_status_reality.py -q -m "corpus and
not windows_ci"` from (a) the primary checkout and (b) a linked worktree of the same commit: both
green, and `git diff` on the module shows only the one root expression plus the new test.
**Prompt**: `/tasks/WP01-corpus-root-primary-worktree.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003

### Included Subtasks

T001 Red-first: add the pinning test (real repository + linked worktree in `tmp_path`; both entry points answer the primary root; a non-repository path answers itself) and see it fail before the helper exists
T002 Add `primary_worktree_root(repo_root)` to `tests/contract/_mission_status_oracles.py` on the existing `run_git` seam, failing soft to the given path
T003 Point the reality module's `REPO_ROOT` at that helper and keep every other line of the module byte-identical
T004 Prove the linked-worktree red is gone: run the corpus-marked suite inside a linked worktree of the same commit (before: 5 failed; after: green)
T005 Prove nothing was weakened: run the same suite from the primary checkout and compare pass/skip counts and the module diff against `origin/main`
T006 Note the tree the check reads in `docs/development/reference/ci-gate-mechanics.md`
T007 Add the per-PR changelog fragment `docs/changelog/unreleased/<pr>.internal.md` once the PR number exists

### Implementation Notes

- `git worktree list --porcelain` lists the primary worktree first; take that entry, `Path.resolve()` it.
- Fail soft on: no git, not a repository, non-zero exit, `OSError`, `subprocess.SubprocessError`.
  `REPO_ROOT` is evaluated at import, so a raise there would break collection on such hosts.
- Do not touch `tests/contract/_mission_status_drift.py` or `_mission_status_project.py`: their
  outside-root behaviour is contract behaviour (plan D-4). The mixed tree is the defect.
- Keep the helper in the oracle module: it already owns the module's git seam (`run_git`) and the
  worktree listing (`worktree_branches`).

### Parallel Opportunities

- T001 must come first (red before green). T006 can be written at any point; T007 needs the PR number.
