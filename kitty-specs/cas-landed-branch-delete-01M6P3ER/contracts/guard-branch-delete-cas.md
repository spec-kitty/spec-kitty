# Contract — `guarded_branch_delete(..., expected_tip=...)`

**Module**: `src/specify_cli/git/destructive_guard.py`
**Mission**: `cas-landed-branch-delete-01M6P3ER` (issue #7212)

## Signature

```python
def guarded_branch_delete(
    repo_root: Path,
    branch: str,
    *,
    creation_base: str | None,
    operator_intent: str | None = None,
    expected_tip: str | None = None,
    env: dict[str, str] | None = None,
) -> str | None:
```

Returns the SHA whose tip was recorded under
`refs/spec-kitty/discarded/<branch>` (unchanged), or `None` when no record was
needed. Raises `DestructiveOpRefused` for every expected refusal and `ValueError`
for an invalid call.

## Preconditions

| Call | Precondition |
| --- | --- |
| `operator_intent=None` | unchanged: refuses when the branch holds commits outside `creation_base` and no other ref reaches them (`BRANCH_HAS_UNIQUE_COMMITS`). |
| `operator_intent=FORCE_RECREATE_INTENT` | unchanged. |
| `operator_intent=DISCARD_INTENT` | unchanged (`_ALL_REF_NAMESPACES` keep scan, then `branch -D`). |
| `operator_intent=LANDED_INTENT` | **`expected_tip` is required**, else `ValueError` before any git call. The caller has proven the tip's absorption; the guard binds the delete to that tip. |
| any intent, `expected_tip` given | the delete is compare-and-swap at `expected_tip`; a moved branch is refused. |

## Postconditions

- **Deleted**: the ref is gone only if it held `expected_tip` at the moment of
  the atomic `git update-ref -d <ref> <expected_tip>`. The keep-record, when
  written, holds `expected_tip` and was written before the delete.
- **Refused (`BRANCH_TIP_MOVED`)**: the ref is unchanged and still holds the tip
  that replaced `expected_tip`; every commit past `expected_tip` is reachable.
- **Refused (`BRANCH_CHECKED_OUT`)**: nothing deleted; the worktree that holds
  the branch is named in the refusal.
- **Refused (`BRANCH_DELETE_REFUSED_BY_GIT`)**: nothing deleted; git's message is
  in the refusal.
- **Refused (`DESTRUCTIVE_OP_ONLY_COPY`)**: nothing deleted; the keep-record
  could not be written.
- No raw `GitCommandError`/`RefDelete*Error` escapes the guard for an expected
  race.

## Pinned call sites

The destructive-op routing gate pins the only callers allowed to pass an
operator intent. It additionally asserts that the LANDED caller
(`workspace/landed_worktrees.py::_delete_landed_branch`) passes `expected_tip`,
so a LANDED delete cannot be issued unbound. The guard's own `ValueError` is the
runtime backstop.

## Out of scope

`ref_advance.delete_branch_ref` is reused. It gained one hardening this
Mission needed: `git update-ref --no-deref -d`, so a branch that is a
symbolic ref is deleted as itself and its target (possibly a checked-out
primary branch) survives, as `git branch -D` always did. Its checked-out
protection, CAS semantics and exception types are the contract this guard
maps.
