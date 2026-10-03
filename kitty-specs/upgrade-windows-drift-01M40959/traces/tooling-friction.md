# Tooling friction

Tooling in play: `spec-kitty` 4.0.0rc6 (editable, `fb7c92d6f0`), git, uv, codegraph MCP, subagent squads.

## 2026-10-03 — Lifecycle commands ignore a linked worktree for `lanes_with_coord`

- **Symptom**: from a linked worktree on `kitty/upgrade-windows-drift`, `spec-kitty agent mission spec-commit` refused with "Refusing to commit planning artifacts to the protected branch 'main'" (`placement_ref: main`). With `--owned-checkout` it refused with `OWNED_TOPOLOGY_UNSUPPORTED`. `agent mission setup-plan` then failed with `PLAN_CONTEXT_UNRESOLVED` ("Mission not found").
- **Cause**: lifecycle and planning commands resolve the repository root checkout; `LIFECYCLE_OWNED_TOPOLOGIES` admits only `single_branch`, so a `lanes_with_coord` mission created in a linked worktree is invisible to them.
- **Workaround**: spec committed with plain `git add`/`git commit` in the worktree (improvised, logged here); then the worktree was replaced by a standalone local clone at the same path, which is its own repository root. All later commands ran through the CLI.
- **Follow-up**: candidate upstream issue — `agent mission create --owned-checkout` accepts `lanes_with_coord` but every later lifecycle command refuses it; either refuse at create time or support it.

## 2026-10-03 — Squash consolidation refused on diverged status files (self-inflicted)

- **Symptom**: `spec-kitty consolidate` refused twice ("projected coordination bookkeeping content did not land on the target"), rolling back cleanly each time.
- **Cause**: I committed `status.events.jsonl` (10 mission-lifecycle events: MissionCreated…TasksCompleted) and `status.json` to the target branch directly (`938d6e7388` plain commit, `2ef559d4d1` safe-commit of the whole mission dir). These are coordination-partition files; `finalize-tasks` had deliberately left them uncommitted on the target. The target copies then shared no event with the coordination log, so the squash content proof could not attribute them.
- **Fix**: set both target files byte-equal to the coordination branch copy (the squash would project that content anyway); lifecycle events stay in target git history.
- **Lesson / upstream candidate**: never `safe-commit` a whole mission directory on a `lanes_with_coord` mission; the `implement` "commit planning artifacts first" hint suggests exactly that command and should exclude coordination-kind files. The coordination log also never receives the mission-lifecycle events.

## 2026-10-03 — Squash proof refuses planning files edited on the target after lanes were cut

- **Symptom**: after aligning status files, consolidation still refused, first on `contracts/command-skill-drift.md`, then on `traces/approach.md` (found by wrapping `bookkeeping_projection._projected_path_content_matches`; the refusal message names no path).
- **Cause**: the coordination branch never received the planning artifacts, and I edited `traces/` on the target after lane creation; each lane's automatic planning-artifact sync carried a different intermediate copy, the lane→mission merges produced a garbled `approach.md`, and every kitty-specs path touched after the checkpoint is treated as projected bookkeeping with no driver.
- **Also**: a failed run's persisted `pre_mutation` snapshot is reused by `--resume` and re-runs, so the proof kept judging against the first run's target tip until `consolidate --abort`; `--abort` tears down the coordination worktree (re-materialized with `doctor coordination --fix`).
- **Fix**: merged the target into the coordination branch, then synced every lane's and the coordination branch's planning files to the target copy; consolidation then passed.
- **Upstream candidates**: (1) the squash refusal should name the failing path; (2) planning-kind files (contracts/, traces/) should not be projected-bookkeeping candidates; (3) document that tracer edits on the target after lane creation diverge the lanes.
