# Data model

- **Upgrade baseline** — set of paths dirty or untracked before the run, plus (new) paths ignored before the run. Commit candidates = paths changed by the run that are not in the baseline, not equal to or under an ignored-at-baseline entry, and not held for review; plus deletions the migration itself staged.
- **Held-for-review file** — a file a migration preserved because it lacks Spec Kitty's version marker (operator-authored). Named in the output, never committed by the upgrade.
- **Upgrade outcome → commit decision** — commit only when the run succeeded, the baseline is available, `auto_commit` allows it, and HEAD is attached; otherwise print exactly one reason (failed run, baseline unavailable, `metadata.yaml` dirty at baseline, activation/preparation errors, detached HEAD, auto_commit disabled) and say the changes were left uncommitted.
- **Written-path list** — for claim and bake, the exact files the operation changed; a file the operation would rewrite but the operator had already modified is left uncommitted with a warning.
- **Merge conclusion** — a commit that finishes an in-progress merge/revert/cherry-pick/squash in a spec-kitty-managed worktree; only the owner function may perform it.
- **Commit path (safe-commit)** — a path whose parents are resolved and whose final component is kept as given; a looping final component is refused; a symlinked directory is a single path.
