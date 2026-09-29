# Tooling friction — mixed-lane-authorship-soundness-01M3M7Y0

Tooling touched: `spec-kitty agent mission create/decision/spec-commit/setup-plan/finalize-tasks/implement/consolidate`, `tests/terminus/` real-CLI harness, the reconciliation gate.

- 2026-09-28 — Fresh container had no `.venv`; the auto-mode classifier denied a combined `git reset --hard origin/main && uv sync` (the reset was a no-op). Recovered by operator approval of `uv sync --frozen --all-extras` alone.
- 2026-09-28 — Local `main` (ae0ff2fb) is a divergent pre-force-push history, not an ancestor of `origin/main` (dccf6aa7). Instead of resetting it (irreversible), the mission target is a local `issue-5046-mixed-lane-authorship` branch cut from `origin/main`; lanes consolidate there, not into local `main`.
- 2026-09-28 — `mission create` scaffold commit message still reads "Add scaffold for feature …" (terminology canon residue: Mission, not feature).
- 2026-09-28 — Tracker scout cited `src/specify_cli/merge/reconciliation.py` (from the PR #5040 diff); the live module is `src/specify_cli/consolidation/reconciliation.py`. Issue bodies #5046/#5047 carry the stale path.
- 2026-09-28 — Issue-reference gating is line-regex based: `see #N` only demotes at line start (a `- see #N` bullet stays gating), so context citations in plan/research need rewording (`issue N`) to avoid spurious matrix rows.
- 2026-09-28 — `tests/terminus/test_repro_5018.py` takes ~3 min wall locally (39 s setup + 32 s body + overhead), not the ~14 s recorded in #5047.
- 2026-09-28 — `move-task --to approved --actor reviewer-renata` is refused when the WP's `agent` is `claude` (agent mismatch); the reviewer identity only lands in the note. The approve step is also blocked by mission-wide issue-matrix rows (`unknown` verdicts) that a per-WP reviewer should not decide — the orchestrator must set `issue-verdict` before the first approval.
- 2026-09-28 — Editing spec.md/tasks.md after `record-analysis` silently makes the analysis report stale (input SHA pins); the next `implement` refuses with `analysis_report_required` rather than naming the stale input. Re-record after every planning-artifact edit.
- 2026-09-28 — Concurrent agents in lane worktrees still write status to the primary checkout; an orchestrator `spec-commit` racing their auto-commits hit a transient `index.lock`. A diagnostic `spec-commit` also committed a real file with a throwaway message ("x", 8279899) — to be squashed at closeout.
- 2026-09-29 — Operator instruction: no full e2e / architectural sweeps at mission close or review — they take hours in non-optimized environments; CI owns them. Closeout validation = targeted test files + specific named architectural gate files only.
