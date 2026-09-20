# Tracer — Tooling Friction

Mission: Merge/Git Destructive-Operation Safety (#4752, #4753, #4754)

## Seed (planning)

- Bash cwd resets to the primary repo between calls in this harness; every command
  must `cd` into the clone (`SHADOW_CLONES/spec-kitty_THREE`). Low friction, noted.
- Clone-three `main` was 353 commits behind canonical `skupstream/main` at session
  start; the clone's `upstream` remote points to the pre-move Priivacy-ai line, not
  the canonical `spec-kitty/spec-kitty`. Added `skupstream` and fast-forwarded.

## Appended during implement

_(to be filled per WP — record any red-first harness friction, mock-seam surprises,
venv/test-tier gotchas)_
