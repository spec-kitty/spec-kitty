# Contract: planning-artifact staging uses Git's clean view

Applies to `resolve_planning_artifact_staging` and its predicate `_files_changed_vs_ref` (`src/specify_cli/cli/commands/implement_cores.py`), reached from `spec-kitty implement`.

## Invariants

1. A planning artifact is changed versus a ref if and only if the object id Git would store for the working file (`git hash-object --stdin-paths`, which applies each path's clean filter) differs from the object id at `<ref>:<path>`, or the path is absent in the ref.
2. On a checkout where `git status --porcelain` is empty, `files_to_commit` is empty. `implement --no-auto-commit` does not refuse, and `implement` with auto-commit does not create an empty commit.
3. A real text change stays changed, including when it is saved with the checkout's line endings (C-004). Only the changed path is staged.
4. Any git failure while computing either object id keeps the path as changed (fail closed).
5. `show_blob` keeps returning raw blob bytes; other callers are unaffected.
