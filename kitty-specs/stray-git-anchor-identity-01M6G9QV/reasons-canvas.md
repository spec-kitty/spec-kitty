# REASONS Canvas — `stray-git-anchor-identity-01M6G9QV`

Thin reasoning layer beside the spec and plan; it links to them rather than repeating them.
Sources: `<mission_dir>/spec.md`, `<mission_dir>/research.md`, issue #7084.

## Requirements

Identity backfill must mint where git holds nothing, and must keep refusing where git may hold the
identity.

- **Must** mint for a mission folder under a path whose `.git` entries are not repositories
  (FR-001) — the failure that reds `tests/lanes/test_refinalize_mission_branch.py`.
- **Must not** mint over an identity git can still give back: usable, corrupt, staged, index-only
  or un-readable real repository (FR-002, C-002).
- **Must** leave the issue's test unedited and make it green for the reason it is red (FR-003).
- **Must not** add a root walk or ceiling logic of its own (C-003); PR #7082 owns the walk.

## Entities

- **Anchor** — an ancestor `.git` entry that could be a repository home. Discriminated by shape:
  file pointer, directory with `HEAD`, directory without `HEAD`, unreadable.
- **Tracked metadata read** — `TrackedMeta`: usable copy / unavailable (fail closed) / nothing
  tracked. The mission changes only how "nothing tracked" is decided.
- **Backfill result** — `action` in `wrote` / `skip` / `error`, with `reason` carrying the coded
  refusal when it refuses.

## Approach

Ask the filesystem a cheaper question than "is there a `.git` name": "is there a `.git` that can be
a repository home".

- Keep the existing ancestor loop and the `OSError` fail-closed branch; change only the predicate.
- A `.git` directory counts as an anchor when it carries `HEAD` — every repository has one, even an
  unborn one, and git itself skips a `.git` that is not a git directory.
- A `.git` file always counts (worktree/submodule pointer): the repository lives elsewhere.

## Structure

- `src/specify_cli/mission_metadata.py` — `_has_no_git_anchor` plus one small helper that classifies
  an anchor shape. No other module changes.
- Tests: the #6673 probe contract (`tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`), the
  backfill entry point (`tests/specify_cli/migration/`), and the issue's own node in `tests/lanes/`.

## Operations

- Red first: the polluted-ancestor test fails on current `main` for this mission's reason.
- After the fix: the same files are green, and the paired refusal fixtures stay green (FR-002's
  positive control).
- Verification: targeted `uv run pytest` on the three affected areas plus `ruff` and `mypy` on the
  changed module; no full heavy suite.

## Norms

- Changelog: one per-PR fragment under `docs/changelog/unreleased/`, not an `[Unreleased]` edit.
- Diff discipline: smallest viable diff, locality of change — one predicate, one helper, tests that
  guard the widened branch and the retained refusals.

## Safeguards

- **Refusal is fail-closed**: an unreadable ancestor still refuses; nothing in this change can turn
  an unreadable state into a mint.
- **The issue's assertion is untouched**: the test is not weakened, xfailed, or edited to match the
  defect.
- **No pollution fix smuggled in**: `/tmp/.git` creation by the suite and the name-only root
  resolver are reported in the PR's Deferred section, not fixed here.
- **Composes with #7082**: if that PR lands first, this predicate change applies unchanged to
  `find_ancestor`'s predicate.
