# Tooling friction — implement-rework-resume

Tooling touched: `spec-kitty agent action implement`, `agent tasks move-task`, the status event log, the `_rework_loop_harness.py` real-CLI harness.

- 2026-09-29 — `pip install -e .` into the container's system Python fails on a Debian-owned `PyJWT` (no RECORD file); `--ignore-installed PyJWT` works around it.
- 2026-09-29 — Real-CLI repro setup: `finalize-tasks` refuses a literal `owned_files` path that does not exist yet unless `create_intent` lists it; `record-analysis` refuses a dirty tree left by the failed finalize.

- 2026-09-29 (WP01 implementer): Foreground pytest over the 9-file validation set takes ~130s and exceeds the 120s tool timeout, so it had to be backgrounded; the blast-radius set (555 tests) took ~207s. No other tooling friction; safe-commit worked as documented.
