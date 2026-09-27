# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-27 · claude-orchestrator · Seed: pip install -e . into the system interpreter fails (debian-owned PyJWT); used uv sync --frozen --all-extras into .venv instead. gh CLI unavailable; issue reads via the public REST API.

2026-09-27 · python-pedro · WP01: monkeypatching the locked read-modify-write critical section moved with it. Tests that patched av_command.feature_status_lock/read_acceptance_matrix/write_and_commit_acceptance_matrix to spy on the #4858 critical section went silently vacuous once that section moved into acceptance.matrix.locked_reread_splice_and_write (the seam calls its own module-global names, never av_command's) -- caught only because the WP prompt pre-named the exact patch sites to re-point. A refactor that relocates a critical section should always grep test suites for monkeypatch.setattr(<old_module>, ...) targeting the moved names, not just run the moved-from test file and see it pass for unrelated reasons.

2026-09-27 · claude-orchestrator · move-task --to approved refuses until every issue-matrix row has a verdict, including context-only rows the spec cites (#4858, sibling issues); review verdicts land uncommitted under --no-auto-commit and need a manual commit.
