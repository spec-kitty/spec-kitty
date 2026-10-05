# Tracer: Tooling Friction

## Observed during setup
- `agent mission create` (single_branch, protected target `main`) refused on a
  dirty write checkout caused by PRE-EXISTING untracked cruft (`.kiro/settings`,
  `.mcp.json`, `GEMINI.md`, stray `kitty-specs/*/*-matrix.json`). Set aside with
  `git stash --include-untracked` (stash@{0}, "pre-mission-5669 untracked cruft")
  — RESTORE at mission end.
- The first (failed) `mission create` left a half-baked mission dir (empty
  gitignored `status.events.jsonl`, no `meta.json`) that then tripped the
  duplicate-name guard; removed the stub dir and re-created cleanly.
- Umbrella epic #5797: GitHub single-parent rule blocked native sub-issue links
  (#5669/#4898→#2017, #5310→#2720, #5670→#3897 already parented); priti used a
  task-list + relates-to comment fallback (acceptable).

## Appended during implement
- (append here)
