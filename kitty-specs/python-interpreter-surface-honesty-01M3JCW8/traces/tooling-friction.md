# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->

- 2026-09-27 — `pip install -e .` into the system interpreter fails on Debian-managed `PyJWT`/`cryptography` (no RECORD file). Worked around with `uv sync --frozen --all-extras` into `.venv` and an editable install there.
- 2026-09-27 — A pytest run over a list of node IDs where one ID no longer exists (renamed on `main`) printed only `no tests ran` under `-n 4`, with no "not found" error. It took a per-ID `--co` sweep to find the stale ID.
- 2026-09-27 — The bundled `uv 0.8.17` only knew CPython 3.14.0rc2, and `uv self update` hit the GitHub API rate limit. Installed a newer `uv` with pip to get the final 3.14.7.
- 2026-09-27 — Re-running `finalize-tasks` after folding the post-tasks squad left `lanes.json` pointing at the first finalize commit (`planning_commit_sha`). `implement WP01` then failed with "cannot auto-merge the recorded planning commit … into lane-a", and no lane worktree existed to merge in. Worked around by creating the lane-a worktree on its branch, merging the old planning commit (the only conflict was the derived `status.json`, resolved to ours), and re-running `implement`.

- 2026-09-27 — `agent action implement WP04` hit the same stale-planning-commit allocation failure for lane-d. Workaround as for lane-c: manual `git worktree add` on the existing lane branch, merge 17b8e1c9 (took ours for `status.json` and `decisions/*`, which carry the newer resolved DM), then merged the dependency lanes b and c (ours for `status.json`) so the gate scans the fixed sources.
## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->

- 2026-09-27 — `pip install -e .` into the system interpreter fails on Debian-managed `PyJWT`/`cryptography` (no RECORD file). Worked around with `uv sync --frozen --all-extras` into `.venv` and an editable install there.
- 2026-09-27 — A pytest run over a list of node IDs where one ID no longer exists (renamed on `main`) printed only `no tests ran` under `-n 4`, with no "not found" error. It took a per-ID `--co` sweep to find the stale ID.
- 2026-09-27 — The bundled `uv 0.8.17` only knew CPython 3.14.0rc2, and `uv self update` hit the GitHub API rate limit. Installed a newer `uv` with pip to get the final 3.14.7.
- 2026-09-27 — Re-running `finalize-tasks` after folding the post-tasks squad left `lanes.json` pointing at the first finalize commit (`planning_commit_sha`). `implement WP01` then failed with "cannot auto-merge the recorded planning commit … into lane-a", and no lane worktree existed to merge in. Worked around by creating the lane-a worktree on its branch, merging the old planning commit (the only conflict was the derived `status.json`, resolved to ours), and re-running `implement`.
## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->

- 2026-09-27 — `pip install -e .` into the system interpreter fails on Debian-managed `PyJWT`/`cryptography` (no RECORD file). Worked around with `uv sync --frozen --all-extras` into `.venv` and an editable install there.
- 2026-09-27 — A pytest run over a list of node IDs where one ID no longer exists (renamed on `main`) printed only `no tests ran` under `-n 4`, with no "not found" error. It took a per-ID `--co` sweep to find the stale ID.
- 2026-09-27 — The bundled `uv 0.8.17` only knew CPython 3.14.0rc2, and `uv self update` hit the GitHub API rate limit. Installed a newer `uv` with pip to get the final 3.14.7.
