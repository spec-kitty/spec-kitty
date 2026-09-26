# Tracer: Tooling Friction

Seeded at planning; appended during implementation.

- 2026-09-26 (specify): `spec-kitty agent decision open` raised `CoordinationWorktreeUnmaterialized`
  on first coord-branch write (coord-topology mission). Resolved by materializing THIS mission's
  coord worktree via `CoordinationWorkspace.resolve(repo_root, slug, mid8)` — NOT
  `doctor coordination --fix` (flattens other missions). This matches the existing agent-memory
  gotcha; the CLI's own error hint suggests `doctor workspaces --fix`, which is broader than needed.
  Candidate friction to report: `decision open` on a fresh coord mission could self-materialize the
  coord worktree (the error even says it "will self-materialize on first write" — but `decision open`
  is that first write and it hard-failed instead).
