---
affected_files: []
cycle_number: 1
mission_slug: codex-home-gitignore-7729-01M7X1HA
reproduction_command:
reviewed_at: '2026-11-20T19:49:53Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review feedback (cycle 1): claude::reviewer-renata

**Verdict: changes requested (narrow fold).** The fix itself is correct for a project at the repository root. The shipped rc8 module is byte-identical, the ledger shows no drift, quality gates pass, and the red-first reproduction (now commit e50af97c) fails on pre-fix sources and passes after the fix.

## Blocking

1. **FR-006 is not met as written: the reproduction does not run per PR.** `tests/specify_cli/upgrade` and `tests/specify_cli/upgrade/migrations` are `out_of_matrix_test_dirs` in `.github/ci-module-registry.yml` (#4374 deferred promotion), so `test_p0_repro_7729_codex_home_exposed.py` and `test_m_4_0_0rc9_exclude_project_local_codex_home.py` run only in the nightly. Removing the `p0_repro` marker moved them from the p0-repro lane to the nightly full run, not to per-PR CI. The PR body says "so it now guards every PR". Fold one of:
   - (preferred, smallest) correct FR-006 and the PR body to say the guard runs in the nightly, and name the #4374/#4732 promotion as the route to per-PR; or
   - move or duplicate a per-PR guard for the migration half into a matrix directory (for example `tests/specify_cli/agent_utils/`, which the `agent` module already runs per PR).
   The committed-block half is already per-PR (`test_ignore_entries.py`, `test_codex_home.py`).

## Non-blocking (operator's call; fold or file)

2. **Medium: a project below the git top level is never protected.** `git status` paths are relative to the repository top level, so `_needs_codex_exclusion` (`path.startswith(".codex/")`) is False for `svc-a/.codex/...`. Probe: repo root with `svc-a/.codex/{version.json,config.toml}`, `apply(svc-a)` reports "No Codex home to exclude". If nested projects are supported, compare paths relative to the project, and write an anchored rule (`/svc-a/.codex/`); the unanchored `.codex/` would also hide another subproject's team `.codex/`.
3. **Low: the step settles before a Codex home exists.** `detect()` is True when any agent folder has an untracked file (for example `.cursor/rules/x.md`); `apply()` then succeeds with "No Codex home to exclude", the success record settles the clone-local step, and a Codex home created in that clone later is never excluded.
4. **Low: `apply()` reports "Added .codex/ to .git/info/exclude" without checking.** `exclude_from_git_index` swallows `OSError`. Re-reading the exclude file (or re-checking that git still shows `.codex/` files) before claiming the change would keep the record truthful.
5. **Low: the PR body cites commits that no longer exist after the rebase** (`b5c084a7`, `ecf17856`). The red-first commit is now `e50af97c`.
6. **Info:** `agent action review` reported "Review range unavailable (not_on_lane)": the recorded `lane_head` predates the rebase.

The re-pin of `test_wrapper_only_agent_has_no_skill_patterns` is justified: `.codex/skills/.system/` is a fixed Codex home row, not a generated skill pattern, and the test still checks every generated row.
