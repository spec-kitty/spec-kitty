# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->
2026-09-27 — `python3 -m pip install -e .` failed on the Debian-managed PyJWT (no RECORD file); `--ignore-installed PyJWT` unblocked it. Environment friction, not a spec-kitty defect.
2026-09-27 — `ruff format <file>` on an explicitly named file ignores `[tool.ruff.format].exclude`, so it silently reformatted the whole ratchet-excluded `_read_path_resolver.py` (190-line diff). Restored and re-applied the edit; use `ruff format --check .` (repo-wide, honours excludes) as the gate instead of per-file formatting on excluded files.
2026-09-27 — Targeted pytest runs are slow here (~30 s per-test setup on git fixtures; 78 tests took ~7 min at -n 6).
2026-09-27 — `move-task --to approved` refused until every issue-matrix row (including context-only citations #154, #5024 auto-harvested from the spec) had a verdict; the heads-up at specify time is easy to miss. The `--no-auto-commit` default also left status/review-cycle files dirty so `implement WP02` refused until they were committed by hand.
2026-09-27 — The `[spec-kitty guard] ACTIVE_WP_SCOPE_VIOLATION` warnings fired on legitimate out-of-map edits (gate companion, docstring references); informative, non-blocking.
