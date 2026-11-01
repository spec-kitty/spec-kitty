---
title: Use Operation History
description: 'How to use operation history with Spec Kitty 3.2: The spec-kitty ops command group provides read-only access to your git operation history via git reflog..'
doc_status: active
updated: '2026-06-03T00:00:00Z'
audience: docs/context/audience/external/project-owner.md
kind: How-To
---
# Use Operation History

The `spec-kitty ops` command group provides read-only access to your git operation history via `git reflog`. Use it to review recent actions and understand what happened in your repository.

## View recent operations

Show the last 20 operations (the default):

```bash
spec-kitty ops log
```

## Limit the number of entries

Show only the last 5 operations:

```bash
spec-kitty ops log --limit 5
# or
spec-kitty ops log -n 5
```

## Show verbose details

Include full commit hashes and extended information:

```bash
spec-kitty ops log --verbose
# or
spec-kitty ops log -v
```

## Undo operations

Git does not have reversible operation history, so `spec-kitty ops undo` is not supported. The command will print guidance on the git alternatives you can use manually:

| Situation | Git command |
|---|---|
| Undo last commit, keep changes staged | `git reset --soft HEAD~1` |
| Undo last commit, discard changes | `git reset --hard HEAD~1` |
| Create a reverting commit | `git revert <commit>` |
| Find previous repository states | `git reflog` |

## Command reference

```text
spec-kitty ops log [OPTIONS]

Options:
  --limit, -n INTEGER   Number of operations to show (default: 20)
  --verbose, -v         Show full operation IDs and details
  --help                Show this message and exit
```

```text
spec-kitty ops undo

Not supported for git. Prints alternative git commands.
```
