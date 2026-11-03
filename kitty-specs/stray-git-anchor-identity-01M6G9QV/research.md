# Discovery findings — #7084: a stray `.git` name is not an identity refusal

Mission: `stray-git-anchor-identity-01M6G9QV` (issue spec-kitty/spec-kitty#7084).
Captured before `specify`, on `main` at `d18c4f1d58`.

## The reported symptom is real, but the diagnosis in the issue is not

The issue says the refinalize short-circuit reports `skip` where its test expects `wrote`, and
suspects "the backfill itself lands the field the refinalize compares against". The red assert is
the **earlier** one, and the call that skips is `backfill_mission`, not the refinalize:

```
tests/lanes/test_refinalize_mission_branch.py:117:
    assert result.action == "wrote"
E   AssertionError: assert 'skip' == 'wrote'
```

`result` there is `backfill_mission(feature_dir)` (`specify_cli/migration/backfill_identity.py`);
the refinalize `_finalize(...)` call comes after it and is never reached. Nothing in
`lanes/compute_and_persist.py` is involved.

## Reproduction (grounded on current `main`)

```bash
uv run pytest tests/lanes/test_refinalize_mission_branch.py -q     # 1 failed, 10 passed
```

The refusal reason the command reports is the #6673 tracked-metadata one:

```
meta.json: tracked meta.json has lost its mission_id and git could not produce its content;
no identity was minted — restore it with `git checkout -- meta.json` [TRACKED_META_UNAVAILABLE]
```

That message is false for this fixture: there is no tracked `meta.json`, and `git checkout --
meta.json` cannot restore anything. The fixture is a plain temp directory.

## Minimal reproduction of the cause

The fixture directory is inside `tmp_path`, which is *not* a git work tree. One extra empty
directory above `TMPDIR` flips the verdict:

```bash
mkdir -p /var/tmp/polluted/.git          # an empty directory named .git; not a repository
TMPDIR=/var/tmp/polluted uv run pytest tests/lanes/test_refinalize_mission_branch.py -q
# 1 failed, 10 passed   (same assertion)

TMPDIR=/var/tmp/clean uv run pytest tests/lanes/test_refinalize_mission_branch.py -q
# 11 passed
```

Cause: `specify_cli/mission_metadata.py::_has_no_git_anchor` walks the ancestors of the mission
directory and answers "a repository may hold a copy I cannot give back" as soon as **any ancestor
carries a `.git` name**, whatever that name is. It is consulted only after git has positively
answered `fatal: not a git repository (or any of the parent directories): .git`
(`_meta_checkout_prefix`), so the heuristic contradicts git's own answer for a directory that is
not a repository. `read_tracked_meta` then reports `unavailable=True`, `backfill_mission` returns
`action="skip"` with the refusal notice, and the mission never gets an identity.

This host demonstrates the shape that triggers it: `/tmp/.git` exists and contains only `hooks/`
and `spec-kitty-locks/` — no `HEAD`, no `objects/`, no `refs/`. It is not a repository; git
rejects it in the same breath as a bare directory.

The same cause reds a second test on this host, which the issue did not mention:

```bash
uv run pytest tests/specify_cli/upgrade/test_read_tracked_meta_6673.py -q
# 1 failed, 14 passed  -- test_nothing_tracked_is_not_a_refusal
```

## Decision 1 — the code is wrong, not the test

`backfill_mission` must mint an identity for a mission in a folder git holds nothing for. The
#6673 refusal exists to stop a *second* identity being minted over one git already holds
(`backfill_identity.py` module docstring, `_tracked_mission_id`). When git answers "not a
repository", git holds nothing, so there is no identity to preserve and nothing to restore; a
refusal there is a fail-closed gate with no escape hatch, because its own remedy
(`git checkout -- meta.json`) cannot be executed. The fixture asserts the correct behaviour.

## Decision 2 — the anchor predicate asks whether the `.git` name is a repository home

A `.git` name above the mission directory is an anchor ("git may hold a copy I cannot give you")
exactly when it can be a repository home:

| shape | verdict | why |
| --- | --- | --- |
| `.git` **file** (worktree/submodule/`gitdir:` pointer) | anchor → refuse | the repository lives elsewhere and may hold a copy; pinned by `test_a_git_that_refuses_to_answer_is_not_read_as_nothing_tracked` |
| `.git` **directory carrying `HEAD`** | anchor → refuse | a repository home git refused to read (dubious ownership, corrupt objects) |
| `.git` **directory without `HEAD`** | not an anchor | every repository has `HEAD`, even an unborn one; git itself skips a `.git` that is not a git directory and keeps walking, and nothing in it is recoverable |
| unreadable ancestor (`OSError`) | anchor → refuse | unchanged fail-closed behaviour |

`HEAD` is the decisive entry: a repository home always has one, and a directory holding only
`hooks/`/`spec-kitty-locks/` (what spec-kitty's own fallbacks leave behind) has none.

## Decision 3 — do not add ceiling-aware walking in this mission

`origin/issue-7056-ceiling-aware-ancestor-walk` (PR #7082, in flight) replaces this function's
hand-rolled loop with `kernel/ancestor_walk.find_ancestor` and bounds every root walk to
`GIT_CEILING_DIRECTORIES`, and adds an architectural gate against hand-rolled root walks. It keeps
this mission's subject: its `_has_git_anchor` predicate is still "`.git` exists". This mission
therefore changes **only the predicate**, adds no walk, and composes with #7082 instead of
competing with it. A ceiling bounds *where* the walk looks; #7084 is about *what counts as an
anchor once it is found* — a `.git` name above a temp tree is still above it whenever no ceiling
is configured, which is the default.

## Decision 4 — the `/tmp/.git` pollution source is a separate defect, reported not fixed

`/tmp/.git` was created by this test suite, not by the operator: `hooks/` (the policy hook
installer's `repo_root/.git/hooks`) and one `spec-kitty-locks/*.status.lock` per `tmp_path`
mission. `resolve_canonical_root` / `locate_project_root` also accept a bare `.git` *name* as a
repository (so once `/tmp/.git` exists, mission lock roots for unrelated temp missions resolve to
`/tmp` and pile into `/tmp/.git/spec-kitty-locks/`). That is the same class as #6957 ("the
placement port resolves its primary home to `/tmp/kitty-specs`") and belongs to the root-resolver
family, not to this file. Fixing the anchor predicate here makes the identity path independent of
the pollution; the pollution itself is reported and left alone.

## Evidence index

- `src/specify_cli/mission_metadata.py` — `_meta_checkout_prefix`, `_has_no_git_anchor`,
  `read_tracked_meta` (#6673's probe).
- `src/specify_cli/migration/backfill_identity.py` — `backfill_mission` (the skipping command).
- `src/specify_cli/upgrade/tracked_meta_notice.py` — the refusal notices and their codes.
- `git log -S "_has_no_git_anchor"` → `b3bd9c911a fix(upgrade): restore or take back the tracked
  identity on every entry point (#6673)`; the predicate's own docstring names the policy it
  implements ("a git that runs and refuses").
- Issue #6673 (closed) — the tracked-identity contract this must not weaken.
- PR #7082 / issue #7056 — the in-flight ceiling-aware walk refactor of this same function.
- `tests/lanes/test_refinalize_mission_branch.py:100-125` — the issue's failing test (misattributed).
- `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py` — the probe's contract, including the
  two fixtures this change must keep refusing.

## Open questions

- None blocking. One observation for the reviewer: with a `.git` directory that carries `HEAD` but
  no `objects/`, the probe still refuses (fail-closed). That shape is a broken repository, so a
  refusal is safe and a mint would be unrecoverable either way; no test changes it.
