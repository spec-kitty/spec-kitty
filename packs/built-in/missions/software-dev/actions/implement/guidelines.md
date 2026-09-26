# Implement Action — Governance Guidelines

These guidelines govern the quality and correctness standards for work package implementation in the software-dev mission. They are injected at runtime via the charter context bootstrap.

---

## Working Directory Discipline

- After running `spec-kitty implement WP##`, change into the worktree directory shown in the output.
- ALL file operations (Read, Write, Edit) must target files inside the worktree workspace.
- NEVER write deliverable files to the repository root checkout — this causes review failures and merge conflicts.

---

## Pre-Read Checks

Before any file operation, run:

```bash
pwd
ls -la
test -f kitty-specs/<mission>/tasks/<wp-file>.md && echo "wp prompt exists"
```

If a file or path is uncertain, verify with `ls` or `test -f` before reading it.

---

## Commit Discipline

- Commit all implementation changes before moving to `for_review`.
- Uncommitted changes will block the `move-task` command.
- Commit message format: `feat(WP##): <describe your implementation>`
