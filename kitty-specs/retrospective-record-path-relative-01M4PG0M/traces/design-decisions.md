# Trace: Design Decisions

- DM `specify.scope.migration` → forward-only (no historical backfill of append-only logs).
- `relative_to(repo_root).as_posix()` chosen over `os.path.relpath` (stricter, fails loud on invariant break) and over kernel `GitPath` (no gain for a known-descendant Path; keeps change minimal).
- `contracts: none` in meta.json — bug fix to an existing field, no new interfaces.
