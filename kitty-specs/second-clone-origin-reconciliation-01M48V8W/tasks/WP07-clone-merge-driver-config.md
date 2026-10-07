---
work_package_id: WP07
title: init / upgrade install clone-local merge drivers (#5759)
dependencies:
- WP01
requirement_refs:
- FR-011
- FR-012
- SC-003
- NFR-004
planning_base_branch: claude/happy-keller-r38xig
merge_target_branch: claude/happy-keller-r38xig
branch_strategy: Planning artifacts for this mission were generated on claude/happy-keller-r38xig. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/happy-keller-r38xig unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-second-clone-origin-reconciliation-01M48V8W
base_commit: 823ac378c636a6483fbae6f99a4941508de9b8ba
created_at: '2026-10-06T16:13:12.893909+00:00'
subtasks:
- T033
- T034
- T035
- T036
- T037
phase: Phase 3 - Gates
history:
- at: '2026-10-06T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/terminus/test_clone_init_installs_merge_drivers.py
- tests/upgrade/test_finalize_merge_driver_config.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/init.py
- src/specify_cli/upgrade/finalize.py
- src/specify_cli/upgrade/outcome.py
- src/specify_cli/cli/commands/upgrade.py
- tests/terminus/test_clone_init_installs_merge_drivers.py
- tests/upgrade/test_finalize_merge_driver_config.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – init / upgrade install clone-local merge drivers (#5759)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log; address every feedback item before handing back.

---

## Objectives & Success Criteria

A teammate's fresh clone gets the per-clone `merge.*` driver git config (FR-011, FR-012, SC-003; closes #5759, P1):
- `spec-kitty init` on an already-initialized project (the "Already initialized" path, and the resumed-command-delivery path) installs the config idempotently and still exits 0 with "Already initialized".
- `spec-kitty upgrade` installs it even when every migration is recorded as applied; the install is reported through `UpgradeOutcome` (ADR 2026-10-04-3), not a separate print.
- Re-running either changes nothing.

## Context & Constraints

- Read `spec.md` US3, FR-011/012; `research.md` R-8; `traces/approach.md` (reproducer evidence: B had 0 keys vs A's 14; the 7 drivers in `.gitattributes` are all covered by `_ensure_merge_driver_git_config`).
- Installer: `src/specify_cli/lanes/consolidation.py::_ensure_merge_driver_git_config(repo_root)` (~:545) — call only, do not edit, do not make it public (3 importers).
- `init`: `src/specify_cli/cli/commands/init.py`; idempotency branch ~:845-878 exits 0 before the fresh-init call at ~:1387-1395 (which already wraps the call in `try/except (OSError, subprocess.CalledProcessError, UnicodeError)` with a dim warning). `init` is ~800 lines: helper only.
- `upgrade`: `src/specify_cli/upgrade/finalize.py::finalize_upgrade` (~:27) — add an injected step independent of `repair_preflight` gating, skipped on dry run, kept out of `commit_churn` (it writes `.git/config`, not tracked files). `src/specify_cli/upgrade/outcome.py` (~:153): add an informational field (e.g. `merge_driver_config: Literal["installed","present","skipped","failed"]`) that does NOT enter `reasons` (or only as warning-only on failure). Read ADR `docs/adr/4.x/2026-10-04-3-upgrade-reports-one-outcome.md` and `2026-10-04-4-...` first.
- `upgrade/runner.py` skips recorded migrations — that is correct and stays; the fix is the always-run finalizer.

## Branch Strategy

- **Strategy**: lanes; worktree allocated by `spec-kitty implement WP07`.
- **Planning base / merge target**: `claude/happy-keller-r38xig`.

## Subtasks

### T033 — Red-first regression (#5759) — FIRST commit

`tests/terminus/test_clone_init_installs_merge_drivers.py` (`regression`, `integration`, `git_repo`; docstring cites #5759):
- A: real `spec-kitty init --ai claude --non-interactive` in a git repo (or reuse an init fixture from `tests/init/`), commit, push to a bare remote (`two_clone_support`).
- B: `git clone` + real `spec-kitty init --ai claude --non-interactive` → assert "Already initialized" exit 0 AND `git config --local --get-regexp '^merge\.'` count equals A's (> 0).
- Pull arm: create a mission artifact `kitty-specs/m/status.events.jsonl` + `meta.json` committed in A and pushed; both clones append a different line / change different meta fields and commit; B pulls → no conflict markers in `status.events.jsonl` or `meta.json` (the drivers need `spec-kitty` on PATH — the test env must put `.venv/bin` first; mirror how existing merge-driver tests do it: grep `merge-driver-` in tests).
- Upgrade arm: a third clone C runs `spec-kitty upgrade --yes` (check flags) instead of init → config installed.
Prove red, commit.

### T034 — Campsite (separate commit)

Extract `_wire_merge_driver_best_effort(project_path) -> bool` from init.py ~:1387-1395 (the import, the call, the try/except and the dim warning); the fresh-init path calls it; behaviour identical. Run `tests/init/test_init_idempotent.py` + `tests/agent/test_init_command.py` before/after.

### T035 — Already-initialized path

Call `_wire_merge_driver_best_effort(project_path)` on both early-exit branches (resumed delivery and "Already initialized") before `raise typer.Exit(0)`. Add one dim line ("Installed clone-local merge-driver settings") only when it installed something (compare a before/after snapshot via `lanes.consolidation._merge_driver_config_snapshot` if convenient, else `git config --get-regexp`), so an already-configured clone prints nothing new.

### T036 — Upgrade finalizer + outcome

New `finalize_upgrade` parameter + a `_finalizer_step_merge_driver_config` in `src/specify_cli/cli/commands/upgrade.py` (where the other `_finalizer_step_*` callables and the `finalize_upgrade(...)` call at ~:1893 live), calling `_ensure_merge_driver_git_config(project_path)`; record result in the new `UpgradeOutcome` field; render through the existing outcome renderer (one line, informational). Unit test `tests/upgrade/test_finalize_merge_driver_config.py`: missing config → installed; present → present; dry run → skipped; installer raising OSError → failed + warning-only (upgrade still succeeds).

### T037 — Sweep

```bash
.venv/bin/python -m pytest -q tests/terminus/test_clone_init_installs_merge_drivers.py tests/upgrade/test_finalize_merge_driver_config.py
.venv/bin/python -m pytest -q tests/init/ tests/agent/test_init_command.py tests/upgrade/
.venv/bin/python -m pytest -q $(grep -rl "UpgradeOutcome" tests --include=*.py | sort -u | tr '\n' ' ')
make test-fast
```
Plus ruff/format(`--force-exclude`)/mypy on touched files.

## Definition of Done

- [ ] Regression red first, green after (init, pull and upgrade arms).
- [ ] Idempotent; no new output for an already-configured clone.
- [ ] `UpgradeOutcome` contract additive; ADR 2026-10-04-3 respected.

## Risks

- Tests that snapshot init output exactly (grep "Already initialized" in tests).
- Merge drivers invoke `spec-kitty` from PATH during `git pull` in the test.

## Reviewer Guidance

Verify on a clone with zero `merge.*` keys; verify a second run prints nothing extra.

## Post-tasks squad folds (binding — supersede conflicting text above)

- Pull arm must be able to fail on the base: `git pull --no-rebase` (or `-c pull.rebase=false`) and assert exit 0; assert BOTH clones' appended event lines are present (positive control); make the two `meta.json` edits on ADJACENT lines and assert (in a base-behaviour control with the drivers unset) that they DO produce conflict markers without the drivers.

## Activity Log

- 2026-10-06 — prompt generated.
