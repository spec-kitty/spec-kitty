# Tooling friction: test-suite-remediation-01M3SSDW

Running log, with dated entries of 1–3 sentences each.

**Tooling this mission touches:**
- the static test-quality scanner (`packs/internal/assets/test-quality-scan.py`);
- the architectural gates under `tests/architectural/` (dead-symbol, ratchet baselines, census machinery);
- pytest skip, xfail and quarantine markers and the CI lanes that collect them;
- the spec-kitty mission CLI.

- 2026-09-30: `decision open/resolve` during specify wrote the DM files and events to the primary checkout while the coordination branch was still empty. `setup-plan`, run only as a readiness probe, also started the plan phase (it emitted `PlanStarted`) and scaffolded `plan.md`.
- 2026-09-30: The masked-green lens noted a quarantine-visibility gap: deleting the `quarantine-visibility` CI lane (`e8cc2f444f`) orphaned every `quarantine`-marked test, and nothing flags a marker that no lane collects.
- 2026-09-30: `spec-commit` silently dropped `decisions/*`, `traces/*` and `status.events.jsonl` from its argument list without a warning. They were committed directly on the topic branch instead. The decision records exist only on primary, because `decision open` ran before the coordination surface held the mission.
- 2026-09-30: The issue-matrix approval gate parses every `#NN` in the mission's planning and research artefacts as an issue reference, including quickstart break ids (`Break #19`) and research row ids (`#10`). 24 rows had to be recorded as `not-applicable` before the first approval (10 of them false positives).
- 2026-10-01: The tracer files diverged across two surfaces. `spec-kitty agent tracer-append` writes the tracer files on the coordination worktree, while the orchestrator appended to the primary copies. Closeout must merge both into the committed record.
- 2026-10-01: `tracer-append`'s internal `safe_commit` repeatedly failed with "failed to stage requested files" in the coordination worktree (WP04, WP13). The implementers committed the appended entry manually.
- 2026-10-01: `move-task` in this repo runs with `--no-auto-commit` (auto-commit disabled in config), so every verdict needs a manual commit on both surfaces. The orchestrator used a helper script after each transition.
2026-09-30 · claude-sonnet-5 · WP03: tests/architectural/*.py initially failed with 'No module named ruff' -- stale venv in the lane worktree, not a real failure. uv sync --frozen --all-extras fixed it; all 35 architectural gate tests passed afterward. Also: F401 ignore for the moved file could be shrunk (not just relocated) because the only unused import (os) was independently dead regardless of the T012 json.loads fix -- removed it and dropped the ruff.toml entry entirely.
