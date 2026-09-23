# Tracer: Tooling Friction

## No command failures encountered

All tooling used during this spec-authoring pass worked as expected:
- `git log --oneline -2` / `git branch --show-current` / `git status --short` — clean,
  confirmed HEAD at `bd3d62922` and branch `issue-4213-golden-path-nfr-budget` before
  any edits, as the dispatch required.
- `gh issue view` / `gh pr view` (all four issues + the one PR) — returned full JSON
  with comments on the first try, no auth or scope issues.
- `.venv/bin/spec-kitty safe-commit --help` — resolved cleanly, confirming the exact
  flag set (`--message`/`-m`, `--to-branch`, `--json`) before using it for the commit.

## No pre-existing-failure discovery

Per the charter's `§Pre-existing Failure Reporting Rule`, I want to record explicitly
that I did **not** encounter any pre-existing test failure, broken command, or other
defect unrelated to this mission's scope while authoring this spec. I read test/fixture
source files (`tests/e2e/test_charter_epic_golden_path.py`,
`tests/e2e/conftest.py`) but did not execute the test suite myself (the readiness
package's measurements were treated as authoritative and not re-derived, per the
dispatch's instruction) — so there is nothing here that needs escalation to the
orchestrator for issue-filing consideration.

The one adjacent defect class that *is* visible in the issue history — #4017's
`ensure_runtime()` "Global asset input changed" concurrency failure — is not something I
discovered; it is a pre-existing, already-filed, already-claimed issue (Mission B,
epic #1931) that the dispatch explicitly named as out of scope. I did not treat it as
mission-scope baseline or attempt to fold it in; it is noted in spec.md's evidence
section only as context for why the golden path's current clean pass does not currently
exhibit that symptom.

## Note for the implementing mission (not friction, but worth flagging)

Nothing found during spec authoring suggests the FR-002 (`fresh_e2e_project` redesign)
or FR-003 (CLI-surface trim) work will be mechanically easy — both require real
engineering, not configuration changes, which is exactly why the dispatch called lever A
"a real redesign, not amortisation." This is not tooling friction; it is scope
difficulty already acknowledged in the spec's own FR-002 description and Edge Cases.

## 2026-09-23 — `spec-kitty plan --mission ... --json` scaffolded a stale template

**Command**: `.venv/bin/spec-kitty plan --mission
charter-epic-golden-path-nfr-budget-01M35H35 --json` (run per the dispatch's mechanics
section, after first confirming `--help`'s option set matched what the orchestrator had
already verified: `--mission`, `--json`, `--help`, no positional arg).

**Expected**: the command is non-interactive (confirmed — no prompt appeared, exited with
a JSON success envelope, `scaffold_only: true`) and should populate `plan.md` from the
canonical template, `packs/built-in/missions/software-dev/templates/plan-template.md`
(the file CLAUDE.md's "Template Source Location" section names as the one SOURCE template
to edit, and the one the dispatch's own mechanics section pointed at for the
"Documentation (this mission)" section contract).

**Actual**: the scaffolded `plan.md` used a *different*, apparently retired template. Its
own header note read "See `src/doctrine/missions/software-dev/command-templates/plan.md`
for the execution workflow" — but `src/doctrine/` was absorbed into
`src/charter/offering/` per CLAUDE.md's own "Shared Package Boundary" section (that path
no longer exists in this checkout as a real source location for mission templates). The
scaffolded content also used a `## Constitution Check` section name, not the canonical
template's `## Charter Check` — a naming drift consistent with an older, pre-charter-vocab
template being used instead of the current one.

**Evidence**: `git status --porcelain` immediately after the command showed the new
`plan.md` plus a `status.events.jsonl` modification (the command's own lifecycle-event
side effect, left as-is — not hand-edited); the scaffolded `plan.md`'s literal first-five-
lines text is reproduced in the git history of this commit for direct comparison against
`packs/built-in/missions/software-dev/templates/plan-template.md`.

**What I did**: per CLAUDE.md's "Use Canonical Sources, Never Improvise" rule, I did not
fill in the stale-templated scaffold. I read the canonical
`packs/built-in/missions/software-dev/templates/plan-template.md` directly and wrote
`plan.md`'s actual content against that template's structure (section names, the
"Documentation (this mission)" file list, the Charter-Check gate framing) instead,
overwriting the scaffold's stale-template content entirely. I recorded this as a plan.md
note (its own opening section) so a reviewer sees the discrepancy without needing to diff
against the scaffold's original content.

**Not filed upstream**: per the dispatch's mechanics, this pass reports friction here
rather than filing a GitHub issue itself (issue-filing for a tooling gap is the
orchestrator's call, not a phase agent's, mirroring the same non-self-authorization
posture the charter's `§Pre-existing Failure Reporting Rule` applies to test failures).
The orchestrator should decide whether this is worth an upstream spec-kitty issue (the
`plan` command's scaffold source resolving to a retired template path is very plausibly a
real defect in the CLI's own template-resolution chain, not specific to this mission).

## 2026-09-23 — WP08 closing pass: implementation-phase tooling friction

### Orchestrator dispatch premise vs. observed reality — the lanes ARE already merged into WP08's own workspace

WP08's orchestrator dispatch stated "The lanes are NOT merged yet... Do NOT run `spec-kitty
merge`" and instructed building a throwaway integration worktree by manually re-applying each
lane's `git diff` (scoped to its owned paths) on top of `HEAD`. **Confirmed by orchestrator
after the fact, this instruction's premise was correct about the mission-level merge (that
step genuinely has not run) but did not anticipate a separate, real mechanism: spec-kitty's own
lane-dependency system had already merged all six code lanes into the shared `lane-planning`
workspace branch** (`issue-4213-golden-path-nfr-budget`, the same branch WP01 and WP08 both run
on) before WP08 was even claimed. Evidence:
- `git log --oneline` on the workspace branch shows six real merge commits: "Merge dependency
  lane lane-a into lane-planning" through "...lane-f...", predating WP08's own "chore(spec-kitty):
  status transition batch WP08" commit.
- `git merge-base --is-ancestor <lane-X HEAD> <workspace HEAD>` returned true for all six lanes.
- Attempting the dispatch's prescribed `git diff 6b4164dbf <lane HEAD> -- <paths> | git apply
  --index` against a fresh `git worktree add --detach` of the workspace `HEAD` failed for
  **every one of the six lanes** with "patch does not apply" / "already exists in index" — not
  a tooling bug, but the expected symptom of trying to re-apply a patch whose target content is
  already present verbatim.
- `git diff 6b4164dbf HEAD --stat` on the workspace branch shows exactly the 10 functional
  files the dispatch's own per-lane path list named (`pytest.ini`,
  `src/specify_cli/cli/commands/__init__.py`, `src/specify_cli/runtime/agent_commands.py`, and
  seven test files under `tests/e2e/`, `tests/cli/`, `tests/performance/`,
  `tests/specify_cli/runtime/`, `tests/specify_cli/cli/`) — no extras, no omissions — confirming
  the already-merged tree is the correct union, not some other unrelated drift.

**What I did**: rather than force the (impossible, already-satisfied) manual patch step, I used
the throwaway worktree I had already created (`git worktree add --detach
<checkout-parent>/4211-integration HEAD`) directly as the integration worktree
— its content already equals the verified-correct union of all six lanes — ran T026/T027 inside
it, then removed it as instructed. No lane content was skipped, duplicated, or hand-edited; the
substitution is that the "assembly" step was unnecessary because spec-kitty had already
performed the equivalent assembly via real 3-way git merges (a more reliable mechanism than
manual diff concatenation would have been anyway). Nothing in this WP's `owned_files` scope
(tracer files only) was used to implement this substitution — no `src/`/`tests/` file was
touched, and no spec-kitty state was hand-edited to make this work.

**Recommendation to the orchestrator (not an action taken by this WP)**: dispatches for a
mission's final-integration WP should account for the fact that a `planning_artifact` WP
sharing a lane with an upstream `planning_artifact` WP (both collapsed into the same
`lane-planning` node per `src/specify_cli/lanes/compute.py`) will observe its dependency lanes
already merged into its own workspace branch by the time it is dispatched, once every
dependency WP has been approved — this is a `spec-kitty` mechanism, not an accident, and the
"lanes are NOT merged yet" framing should be scoped explicitly to "the mission-level merge to
the target branch," not to the WP08 workspace's own branch state.

### Friction items observed by WP agents during implementation (confirmed at WP08 close)

Per the dispatch's explicit list, tagging each as observed-by-WP-agents (already recorded in
earlier WP tracer entries / review-cycle records this pass read) or confirmed-by-orchestrator
(this WP's own direct observation):

- **SK-250** (move-task/mark-status leave status files dirty after their auto-commit) —
  observed by WP agents; consistent with the residual-cleanup commits visible throughout this
  branch's own `git log` (e.g. "chore(spec-kitty): status transition batch WP08" following the
  implement-start auto-commit).
- **The #4017-class `Global asset input changed` race** — not hit by this WP directly (no
  concurrent agents were running against this checkout during WP08's own execution; the
  dispatch itself notes other agents are idle now), but recorded here per the dispatch's
  instruction as a known, recurring friction class other WPs in this mission hit.
- **The issue-matrix gate blocking every WP approval until all rows have verdicts** —
  ledger-worthy per the dispatch, not yet ledgered; recorded here, not actioned (ledgering is
  the orchestrator's call).
- **A rejection resets all subtasks, requiring re-marking** — recorded per the dispatch; visible
  in this branch's own history (WP04's and WP06's rejection-cycle commits both show subtask
  re-marking after their respective cycle-1 rejections).
- **`record-analysis` carrier trigger 3 (SK-06)** — recorded per the dispatch.
- **`.kittify/overrides` shadowing the plan template (SK-248)** — recorded per the dispatch.
- **`test_marker_registry_single_source.py` stale references (SK-251)** — recorded per the
  dispatch.

### Confirmed-in-$W: pre-existing failures and the known ratchet defect

- The 3 linked-worktree artifacts in `tests/cli/commands/test_charter_json_error_contract.py`
  DID fail inside the integration worktree, exactly as predicted (same "Refusing charter write
  from linked git worktree" error, same 3 test IDs as WP01's baseline).
- The 6 `tests/specify_cli/cli` failures WP01's baseline classification and #4916/#4669/#4986
  predicted were confirmed present, unchanged, in the integration worktree's targeted-surface
  run — see `tracer-design-decisions.md`'s T027 results table for the full list.
- `tests/architectural/test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats`
  failed exactly as the dispatch predicted: `src/specify_cli/cli/commands/__init__.py` is now
  format-clean but still listed in `pyproject.toml [tool.ruff.format].exclude`. Not fixed here —
  `pyproject.toml` is not this WP's owned file, per the dispatch's explicit instruction.

No new tooling failure (beyond the lane-merge premise correction above) was hit during WP08's
own execution — no command errored unexpectedly, no spec-kitty state transition failed, no
`RuntimeError: Global asset input changed` retry was needed.
