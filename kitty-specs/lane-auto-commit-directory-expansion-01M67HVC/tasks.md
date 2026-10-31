# Work Packages: Lane auto-commit takes exact paths, never a collapsed directory

**Inputs**: `spec.md`, `plan.md`, `research.md` in `kitty-specs/lane-auto-commit-directory-expansion-01M67HVC/`
**Issue**: spec-kitty/spec-kitty#6750

**Tests**: Every [build] requirement gets a regression test written RED first through
the production entry point (charter ATDD-First Discipline; DIRECTIVE_034). The two
halves of the fix (expansion, truthful reporting) and the seam refusal each need an
assertion that goes red when that half alone is reverted.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows; record completion with
`spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Commit seam refuses a directory request before mutation (Priority: P0)

**Goal**: `preflight_commit` becomes the enforcing owner of the "requested paths are
exact files" invariant: a directory argument raises a typed
`SafeCommitDirectoryArgument` (`SAFE_COMMIT_DIRECTORY_ARGUMENT`) before any HEAD or
index mutation, with a truthful files-only message.
**Independent Test**: call `safe_commit` on a git fixture with a directory in `paths`;
assert the typed refusal, byte-identical HEAD/refs/index, and no hook wording; the same
fixture with explicit file paths still commits.
**Prompt**: `tasks/WP01-preflight-refuses-directory-paths.md`
**Requirement Refs**: FR-002, NFR-002, C-001, C-002, SC-003

### Included Subtasks

T001 Write the RED regression first: `safe_commit` with a directory path on a real git fixture, asserting the refusal type/code and zero mutations (HEAD, refs, `git status`)
T002 Add `SafeCommitDirectoryArgument(SafeCommitError)` next to `SafeCommitPathPolicyError`, with `SAFE_COMMIT_DIRECTORY_ARGUMENT` and `offending_path` in `to_dict()`
T003 Raise it in `preflight_commit` after absolute→relative normalization and before the `.worktrees/` policy / protection checks; skip symlinked directories and nonexistent (deleted-file) paths
T004 Positive control on the same fixture: explicit child file paths commit normally, and the public `safe-commit` CLI directory expansion still lands the same file set (C-001)

### Dependencies

- None.

### Risks & Mitigations

- A directory-shaped path that is a symlink must never be refused (single `120000`
  entry); pin it in T003's test.
- Keep the message truthful and actionable: name the path, say `safe_commit` commits
  exact file paths, and point at the expansion rule (`git status --untracked-files=all`).

---

## Work Package WP02: Lane collector requests exact files and reports the truth (Priority: P0)

**Goal**: the `move-task --to for_review` auto-commit collector never passes a
collapsed directory to the commit seam, and when a commit lands before a
recovery-class failure it says so, naming the SHA.
**Independent Test**: drive the real collector on an untracked-directory fixture with an
empty hooks dir — one commit, exactly the children, clean tree, no hook text; a real
`pre-commit` hook that sweeps an unrelated tracked edit still raises the unrequested-path
warning naming only that path, reported as landed.
**Prompt**: `tasks/WP02-collector-exact-paths-and-truthful-report.md`
**Requirement Refs**: FR-001, FR-003, FR-004, NFR-001, C-003, SC-001, SC-002

### Included Subtasks

T005 Write the RED #6750 regression through the real `_mt_commit_lane_deliverables`: untracked directory + empty hooks dir; assert commit contents, clean tree, and that no "pre-commit hook" text is printed
T006 Read untracked entries expanded (`untracked="all"`) in `_mt_commit_lane_deliverables`, and align `_mt_pre_review_dirty_paths` so both callers of `_lane_deliverable_paths` see files, not collapsed directories
T007 Catch `SafeCommitRecoveryFailed` first in the collector's failure arm and render "commit <sha> landed on <ref>, but …"; keep the advisory wording for pre-mutation failures
T008 Hook negative control: a real `pre-commit` hook staging an unrelated modified tracked file must still raise `SafeCommitUnrequestedPaths`, naming only the swept path, and the collector must report the landed SHA (FR-003, SC-002)
T009 Invocation-count probe for NFR-001: a clean auto-commit keeps its git round-trip count, and the seam refusal adds no git call

### Dependencies

- Depends on WP01 (the refusal contract and its exception type).

### Risks & Mitigations

- The collector stays best-effort: the readiness guard remains authoritative after a
  failed auto-commit, so a landed-commit warning must not abort the move.
- The `.zig-cache/`-style out-of-scope sweep is unchanged by design (C-003); record the
  finding in the PR's `## Deferred` section rather than filtering here.
- Keep the rename/copy two-sided handling in `_lane_deliverable_paths` intact (#5401).

---

## Dependency Graph

```
WP01 → WP02
```

## Phase Notes

- Phase 1 (WP01) is the seam: it is independently shippable and closes the class for
  every future caller.
- Phase 2 (WP02) is the reported defect: expansion plus truthful reporting, proven by
  the issue's own fixture and a genuine-hook negative control.
- Documentation work rides in the code WPs: `docs/changelog/CHANGELOG.md` is owned by
  WP02 (`docs/` is not a planning-only surface and no `kitty-specs/` path is owned by
  a code WP). No separate planning-artifact WP is needed for this mission.
