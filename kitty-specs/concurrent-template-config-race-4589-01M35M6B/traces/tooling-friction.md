# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->

- 2026-09-22 — `spec-kitty agent mission create` produced a mission slug
  with an appended ULID suffix
  (`concurrent-template-config-race-4589-01M35M6B`) rather than the exact
  slug string passed on the command line
  (`concurrent-template-config-race-4589`). This is expected/documented
  disambiguation behavior, not a defect, but it means any downstream
  reference to "the mission directory" must resolve the actual created path
  from the command's JSON output rather than assuming the literal slug
  string names the directory.
- 2026-09-22 — The `mission-tracer-files` doctrine procedure's own prose
  (`packs/built-in/procedures/mission-tracer-files.procedure.yaml`) cites a
  stale template source path
  (`src/doctrine/templates/mission-tracer-files/`) that does not exist on
  this checkout; the real path is
  `src/charter/offering/templates/mission-tracer-files/`. Worth a doctrine-doc
  fix in a future mission so the procedure's own text does not mislead the
  next agent who follows it literally.
- 2026-09-23 — Plan round-5's item 4 (core_misc baseline extension +
  packaging-parity re-run) was dispatched twice by the phase agent. The
  first author's long-running background test batch (`tests/specify_cli/
  tool_surface`, ~17 min) meant its final `SubagentHandback` report was
  delayed and did not re-invoke the phase agent's turn; the orchestrator's
  own process-level visibility (watching for the pytest PID) was needed to
  notice the first author had actually finished (plan.md diff static,
  +133/-24, item 4 absent at that point) before the phase agent could tell
  from its own tool results alone. Acting on that read, the phase agent
  dispatched a second, narrowly-scoped author for item 4 — which turned out
  to be redundant: the first author's report, also delayed, had in fact
  completed item 4 in full (plan.md diff now +239/-34, all 9 `core_misc`
  test_dirs covered) but the report simply hadn't surfaced yet. The phase
  agent stopped the second author immediately (its in-flight
  `test_packaging_parity.py` run was killed via `pkill`, and a SendMessage
  STOP was sent) upon learning of the duplicate dispatch; the second author
  made **zero** file edits (confirmed via `git status`/`git diff --stat`
  before and after), so no reconciliation of conflicting content was
  needed — only ~2 minutes of a redundant `test_packaging_parity.py`
  re-run, which incidentally cross-confirmed the first author's recorded
  "3 passed" result (22.19s vs. 21.90s, same pass count). Root cause: no
  reliable signal in this harness distinguishes "subagent still running a
  long background command" from "subagent finished but its handback has
  not yet drained" — a phase agent watching only its own conversation
  cannot tell the two apart without an outside process check. Worth a
  tooling improvement: a lighter-weight "is this background agent still
  alive" probe that doesn't require inspecting OS-level process lists.
- 2026-09-23 — The design-pipeline doc's literal text for the tasks-finalize
  step names the command `spec-kitty agent tasks finalize-tasks`. That is a
  legacy command family that requires `tasks.md` to already exist on disk
  (it errors `tasks.md not found` when it doesn't) — it does **not** generate
  `tasks.md` from `wps.yaml`. The current, correct command for a mission
  whose `tasks.md` does not yet exist is `spec-kitty agent mission
  finalize-tasks` (confirmed via `--help` and its own docstring, matching
  `packs/built-in/missions/mission-steps/software-dev/tasks-finalize/prompt.md`'s
  own text): `--validate-only` first for preflight, then without the flag to
  regenerate `tasks.md`, update WP frontmatter, compute lanes, and commit —
  all in one call. This is a generally-useful, non-mission-specific finding:
  any doc or prompt still citing the bare `agent tasks finalize-tasks` name
  for first-time `tasks.md` generation is stale and should be corrected to
  `agent mission finalize-tasks`.
- 2026-09-23 — During the tasks-phase R4 round-2 fix, a `spec-kitty
  safe-commit` invocation failed once with an unrelated transient error
  ("Global asset input changed:
  `~/.agent/workflows/spec-kitty.analyze.md`") surfaced from
  the CLI's own global-agent-command sync step
  (`ensure_global_agent_commands`) — most likely a concurrent-peer race
  against another agent process in this multi-agent session touching the
  same shared `~/.agent/` install surface at the same moment, not a defect
  in this mission's own artifacts or branch. An immediate retry of the
  identical `safe-commit` command succeeded cleanly with no other change.
  Worth a tooling note: `ensure_global_agent_commands`'s freshness check
  appears not to be safe against concurrent invocations from independent
  agent processes sharing one `~/.agent/` install.
- 2026-09-23 — **Confirmed live instance of the tracked `record-analysis`
  verdict-drift defect (#3133, ledger SK-06).** `spec-kitty agent mission
  record-analysis` silently wrote `verdict: unknown` on the first analyze
  attempt for this mission even though the submitted report body explicitly
  said "Verdict: READY" and carried zero findings. Root cause, read directly
  from `src/specify_cli/analysis_report.py`
  (`parse_structured_findings`/`_split_carrier`, lines ~320-463): the
  recorder derives the verdict **only** from a leading YAML frontmatter
  block whose top-level key is literally `schema: analysis-findings/v1`
  (plus `findings: [...]` and, optionally, `counts`/`verdict_hint`) —
  **never** from prose, and never from any other carrier field name. The
  the orchestrator's design-pipeline guidance (external) §4a text this
  mission followed says only "Produce an analysis report with the
  analysis-findings/v1 YAML carrier" without giving the exact required key
  names, and a real precedent report already committed in this repo
  (`kitty-specs/doctrine-glossary-architecture-consolidation-01KTNWFC/analysis-report.md`)
  uses a *different*, non-matching frontmatter shape (`schema_version: 1`,
  `artifact_type: spec-kitty.analysis-report`, top-level `verdict:` and
  `issue_counts:` keys) that also silently recorded as `verdict: unknown` —
  confirming this is a repeatable trap, not a one-off authoring slip: an
  agent copying the closest available precedent in-repo reproduces the same
  silent-unknown outcome. Fix applied here: re-submitted with the literal
  `schema: analysis-findings/v1` + `findings: []` + `counts: {...}` +
  `verdict_hint: ready` shape; `record-analysis --json` then correctly
  returned `"verdict": "ready"`. Two throwaway commits
  (`d4c476655`, `87eb2397d`) recorded the wrong-schema/malformed-body
  attempts before the clean one (`dd1c0fb9f`) landed — left in mission
  history rather than rewritten, per this pipeline's no-amend discipline.
  Worth a doctrine/tooling fix: either the design-pipeline references should
  state the exact required carrier keys (`schema`, `findings`, `counts`,
  `verdict_hint`) verbatim with a copy-pasteable example, or
  `record-analysis` should reject an unrecognized-but-frontmatter-shaped
  block loudly (as it already does for a *malformed* v1 carrier) instead of
  silently downgrading it to legacy/`unknown` (C-FIND-3's current behavior
  makes "wrong key names" indistinguishable from "no carrier at all").
- 2026-09-23 — WP01 claim (`spec-kitty agent action implement WP01 --mission
  ... --agent claude`) failed with "the recorded planning commit
  '...' is orphaned (no longer reachable from the mission's target-branch
  tip)". Root cause: the orchestrator rebased this branch onto a fresher
  `origin/main` before implementation started (29 commits moved), which
  rewrote the SHA `lanes.json`'s `planning_commit_sha` pointed at. The CLI's
  own error message named the exact recovery command: `spec-kitty agent
  mission finalize-tasks --refresh-planning-commit --allow-orphaned`. Ran it
  once, it re-pointed `lanes.json` to the current tip (one small commit,
  `e7e862712`), and the claim succeeded on retry. Matches SK-245's own
  corroboration entry (2026-09-23) exactly: a `topology: single_branch`
  mission's `agent action implement` still allocates a per-WP lane worktree
  (`.worktrees/<slug>-lane-a` on `kitty/mission-<slug>-lane-a`) that this
  workflow never merges — implementation stayed entirely on the mission
  branch (`fix/concurrent-template-config-race-4589`) in the primary
  checkout per this run's own instructions, never in the lane worktree; the
  lane worktree/branch were left untouched and confirmed inert
  (`git log fix/concurrent-template-config-race-4589..kitty/mission-
  concurrent-template-config-race-4589-01M35M6B-lane-a` empty) at close.
- 2026-09-23 — Also hit the same transient "Global asset input changed:
  ~/.agent/workflows/spec-kitty.analyze.md" error the
  2026-09-23 entry above describes, at the very first `spec-kitty` CLI
  invocation of this WP (even a bare `--help`) — confirms it is a real,
  reproducible cross-agent-process contention on the shared `~/.agent/`
  install, not a one-off. `SPEC_KITTY_NO_UPGRADE_CHECK=1
  SPEC_KITTY_NO_NAG=1` (CONTRIBUTING.md's own documented env pair for
  testing unreleased `main`) sidesteps the global-command-sync step
  entirely and was used for every `spec-kitty` invocation this WP made
  after the first failure.
- 2026-09-23 — Two of `src/charter/offering/missions/mission_step_repository.py`,
  `mission_type_repository.py`, and `tests/core/test_mission_creation_identity.py`
  (all three, actually) are listed in `pyproject.toml`'s `[tool.ruff.format]
  exclude` formatter-debt ratchet (issue #473) — `ruff format --check .`
  (the real `make format-check` gate) silently skips all three. Running
  `ruff format --check <exact-file-path>` DIRECTLY (bypassing the
  directory-walk exclude) reports "Would reformat" for all three, which is
  easy to misread as a gate failure. Actually running `ruff format` (write)
  on the excluded test file reformatted several PRE-EXISTING, untouched
  lines (a `purpose_context` string join, an `assert` message join) as a
  side effect — reverted by hand before committing, since the real gate
  never touches these files and a bystander reformat is unwanted diff
  noise / could break the ratchet's own shrink-only test (`test_ruff_format_
  exclude_ratchet.py`), which the file's continued non-compliance is
  actually correct for its own ratchet entry to still exist. Lesson: check
  `pyproject.toml`'s `[tool.ruff.format] exclude` list BEFORE running `ruff
  format` (write) on any owned file, not just `ruff format --check`.
- 2026-09-23 — A real, non-obvious test-isolation bug discovered only by
  running the WP's OWN new tests alongside neighbouring, unrelated test
  files (`tests/core` + `tests/specify_cli/core` together) rather than in
  isolation: two of the new concurrency tests (OBL-2, both sites) had each
  racing thread call the existing `_run_create` helper, which itself
  enters/exits a process-global `unittest.mock.patch` via
  `_patched_mission_creation_context`. Two threads concurrently
  entering/exiting `mock.patch` on the SAME target attributes is not
  thread-safe — each patcher snapshots "the current value" as ITS OWN
  restore point, so overlapping enter/exit from two threads can leave the
  WRONG value installed globally after both exit. This silently broke FOUR
  unrelated tests in `tests/specify_cli/core/test_mission_creation_placement.py`
  and `tests/core/test_mission_creation_unborn_head.py` (both pass cleanly
  in isolation) whenever they ran AFTER the buggy construction in the same
  pytest process — a genuinely hard-to-diagnose failure mode, since the
  stack trace points entirely at the VICTIM test, with no hint the actual
  cause is a DIFFERENT test file's thread-safety bug. Running each new test
  file in isolation during initial red-first verification was not enough to
  catch this; only running the FULL declared gate-set surface (as the WP's
  own instructions require) surfaced it. Worth a general lesson for any
  future concurrency-test authoring in this repo: never let two racing
  threads both independently enter/exit the SAME `unittest.mock.patch`
  target — patch once, outside the thread spawn, if both threads need the
  same mocked environment (mirrors this file's own pre-existing OBL-4
  test's shape, which was already correct).

- 2026-09-23 (orchestrator, implementation phase) — `spec-kitty agent status emit WP01 --to approved`
  from `for_review` is refused ("Illegal transition: for_review -> approved"); the legal path is
  `for_review -> in_review -> approved` (`src/specify_cli/status/wp_state.py`, review-claim guard).
  The sk-implement doctrine's "approved -> record the lane transition with `status emit`" does not
  mention the intermediate `in_review` hop. Recorded both hops through the CLI; no state hand-edit.
- 2026-09-23 (orchestrator) — the `in_review -> approved` emit carrying `--review-result-json`
  printed a pydantic `value_error` (errors.pydantic.dev/2.13/v/value_error) to the console, yet
  reported `OK` and persisted a complete event (review_ref + review_result recorded, force=false).
  A validation failure that is printed but does not fail the command is a silent-success shape;
  the rejected payload/field was not identified by the output.
- 2026-09-23 (orchestrator) — rebasing the mission branch onto current `main` before
  implementation (29 upstream commits; branch carried only kitty-specs/ commits) orphaned the
  planning commit `lanes.json` referenced; `agent action implement` then required the CLI's own
  `finalize-tasks --refresh-planning-commit --allow-orphaned` recovery (commit `e7e862712`).
  The recovery path worked, but a sanctioned pre-implementation rebase silently invalidates
  lanes.json until an implement attempt fails.
