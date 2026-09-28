# Tracer: spec-kitty tooling friction

Seeded at spec-authoring time per the mission-tracer-files procedure (charter Standing Order #3).

## Friction observed

1. **`spec-kitty agent mission create` auto-suffixed the slug with the mission's `mid8`.**
   Dispatched with `mission_slug=per-pr-shard-timings-recapture-friction`, the scaffold created
   `kitty-specs/per-pr-shard-timings-recapture-friction-01M3H7V8/` (mission_slug field in
   `meta.json` became `per-pr-shard-timings-recapture-friction-01M3H7V8`), not the plain
   `kitty-specs/per-pr-shard-timings-recapture-friction/` a naive read of the dispatch instructions
   would expect. This is expected, documented behavior under the Mission Identity Model (083+)
   described in this checkout's `CLAUDE.md` (`mission_slug` is a human handle, disambiguated by
   `mid8`; `mission_id`/`mid8` are the real identity) — not a defect — but it is worth recording
   because the dispatch's own path guidance (`kitty-specs/per-pr-shard-timings-recapture-friction/`)
   did not anticipate the suffix. No workaround needed; this tracer file, `tracer-approach.md`,
   and `tracer-design-decisions.md` were written to the actual scaffolded path.
2. **No other scaffold friction.** `uv sync --frozen --all-extras`, the venv resolution check
   (`specify_cli.__file__` resolved into this checkout's own `src/`, not `~/.local/`), and
   `spec-kitty agent mission create ... --start-branch ... --json` all completed cleanly on the
   first attempt, with the branch (`issue-5189-per-pr-shard-timings-recapture-friction`) checked
   out and the scaffold commit reachable at `git log --oneline -1` immediately after.
3. **The auto-generated scaffold commit message is non-conventional** ("Add scaffold for feature
   per-pr-shard-timings-recapture-friction-01M3H7V8") — this matches ledger entry SK-64's known
   tooling defect (dispatch flagged this in advance); left as-is, not amended, per instruction.

No spec-kitty CLI bug blocked spec authoring itself.

4. **Plan phase: transient `spec-kitty safe-commit` failure, `global_assets`-related, succeeded on
   retry.** Reported by a subagent during the plan-authoring phase (not verified first-hand by the
   tasks-phase agent writing this entry): the first `spec-kitty safe-commit` attempt at plan-commit
   time failed with an error whose message referenced `global_assets`; the exact error text was not
   preserved by the reporting subagent. A bare retry of the same `safe-commit` invocation succeeded
   immediately, with no other change to the tree between attempts. A search of this checkout
   (`grep -rn "global_assets"` across tracked and untracked files under this mission's workspace, and
   `src/specify_cli/`) found no matching error string or log capturing the original failure — only
   unrelated, pre-existing `global_assets`/`assess_global_assets` identifiers in other missions'
   planning artifacts (`kitty-specs/ci-suite-stability-test-isolation-01M22MM5/`,
   `kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/`) and in
   `src/specify_cli/runtime/asset_preparation.py` / `src/specify_cli/runtime/agent_skills.py` /
   `src/specify_cli/skills/installer.py` / `src/specify_cli/upgrade/assessment.py` — none of which is
   evidence of *this* mission's transient failure. Recorded here per instruction as **reported by a
   subagent**, not reproduced or verified first-hand; no workaround was needed since the retry
   succeeded. If this recurs, capture the full stderr/JSON output before retrying so a future entry
   (or a ledger entry) can carry the actual error text.

5. **Tasks phase: dispatch assumed a `tasks-outline -> tasks-packages -> finalize-tasks` flow; the
   checkout's actual active sequence is a single `tasks` authoring step + `finalize-tasks`.
   Verified first-hand by the tasks-phase agent.** The dispatch's own tooling-surface note asked
   this to be checked and recorded rather than treated as a blocker, and it is confirmed exactly as
   the dispatch suspected:
   - `packs/built-in/missions/mission-steps/software-dev/tasks/step.yaml` carries
     `sequence_index: 2` and `in_action_sequence: true` — this is the one active task-authoring step
     for the `software-dev` mission type on this checkout.
   - `packs/built-in/missions/mission-steps/software-dev/tasks-outline/step.yaml` and
     `.../tasks-packages/step.yaml` both carry `sequence_index: null` and
     `in_action_sequence: false` — neither is part of the active sequence.
   - `.venv/bin/spec-kitty tasks-outline --help` and `.venv/bin/spec-kitty tasks-packages --help`
     both fail with `Error: No such command 'tasks-outline'.` / `'tasks-packages'.` (exit code 2) —
     neither is registered as a top-level CLI command on this checkout at all, confirming the
     step-sequence finding operationally, not just via the YAML flag.
   - `.venv/bin/spec-kitty tasks --help` IS registered, but as a **different** action than the
     `software-dev/tasks` mission-step prompt: its own `--help` text is "Finalize tasks metadata
     after task generation" (exit 0) — i.e. this top-level `tasks` CLI command is a finalize-tasks
     equivalent, not the task-authoring step. `packs/built-in/missions/mission-steps/software-dev/
     tasks-finalize/step.yaml` (`in_action_sequence: false` there too, since `finalize-tasks`/`tasks`
     is invoked directly rather than through the mission-step sequence) confirms this shape.

   **Net effect on this mission's tasks-phase workflow**: this agent authored `tasks.md` and
   `kitty-specs/<mission>/tasks/WP##-*.md` directly by hand, following the `tasks` step's own
   `prompt.md`/`guidelines.md` (the canonical, currently-active task-authoring procedure), then ran
   `spec-kitty agent mission finalize-tasks --mission <handle> --json` (documented as "then commit
   to target branch") as the finalize entry point — never `tasks-outline`, `tasks-packages`, or the
   bare top-level `spec-kitty tasks` command. No workaround was needed; the dispatch's own
   fallback instruction (prefer `agent mission finalize-tasks`) was followed exactly.

## WP02: recapture decision-logic script

6. **`spec-kitty agent action implement WP02` hit the known "Global asset inventory changed"
   race (ledger SK-243) five times in a row before succeeding.** Each failure named a
   *different* global asset directory (`<home>/.kiro/prompts`, `<home>/.agent/workflows`,
   `<home>/.agent/workflows/spec-kitty.analyze.md`, `<home>/.config/llxprt-code/commands`),
   consistent with a concurrent WP01 agent's own `implement`/`upgrade` invocation racing this
   process's asset-inventory snapshot at the same moment (the dispatch explicitly warned WP01
   would start at the same time). The dispatch's "re-run, up to 3 attempts" guidance undersold
   the actual retry count needed under real concurrent-lane load; two more retries (5 total)
   were needed before the command succeeded and resolved the lane-b worktree.
7. **mypy strict flagged three real gaps the WP prompt's verbatim code snippets did not
   anticipate.** The T011 snippet's literal `list[dict]` signature (no type args) fails
   `mypy --strict`'s `type-arg` check; fixed by typing it `list[dict[str, object]]` (behavior
   unchanged). The narrowed dict type then made `pr.get("number")` return `object | None`,
   requiring an explicit `isinstance(number, int)` narrow before returning it as `int | None`.
   Separately, `mypy --strict` refuses `module.private_attr` access across a module boundary
   (`recapture.subprocess`) as "not explicitly exported" — the test file's spy setup had to
   `import subprocess` directly and monkeypatch that shared module object instead of reaching
   through `recapture_charter_shard_timings`'s own imported reference. None of this surfaced
   under plain `ruff check` — mypy is CLAUDE.md-required but not a CI gate, so these would have
   shipped unnoticed without running it locally as instructed.
8. **`mypy scripts/<file>.py tests/ci/test_<file>.py` (both files in one invocation) fails
   with "Source file found twice under different module names" (`recapture_charter_shard_timings`
   vs `scripts.ci.recapture_charter_shard_timings`)** — a namespace-package ambiguity from
   passing a bare script path alongside a path that resolves through the `scripts.ci` package.
   Running mypy on each file separately avoided it; not investigated further since mypy is not a
   CI gate here.

9. **WP01's `spec-kitty agent action implement WP01` failed 4 of 6 attempts with the known
   global_assets race (ledger SK-243) — each failure named a different agent's workflow dir
   (.kilocode/workflows, .agent/workflows, .agent/workflows/spec-kitty.analyze.md x2) before
   succeeding on a widened retry. WP01 had also committed a tracer entry on its lane
   (14a7ef69c), which the lane guard refused; it was undone on the lane by 90f6c2645, and the
   entry is relocated here.
