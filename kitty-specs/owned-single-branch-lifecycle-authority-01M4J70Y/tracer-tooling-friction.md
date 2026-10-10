# Tracer: Tooling friction — owned single-branch lifecycle authority

Seeded at planning (2026-10-10). Append as friction is hit.

## Observations
- Repo is a shallow single-squashed-snapshot clone (depth 50): `git merge-base` with the codex repair branches returns nothing (base `28a262f00`/`e7456138e` outside the window). Assess FIT by per-file blob comparison, not merge-base.
- Repair branches stack sequentially and carry large unrelated histories; only each branch's tip fix+test commits are relevant.
- `spec-commit` takes individual file paths, not directories (enumerate ledger/checklist files).
- `uv run` prints a deprecated `UV_NATIVE_TLS` warning (harmless).

## Running notes
- (append during implement)
