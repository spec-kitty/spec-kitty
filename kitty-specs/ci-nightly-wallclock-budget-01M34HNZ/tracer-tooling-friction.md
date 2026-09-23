# Tracer: Tooling Friction

Mission: ci-nightly-wallclock-budget-01M34HNZ (issues #4865, #4864)

## 2026-09-22 — tasks-authoring pass: `finalize-tasks`'s requirement-ref parser does not
recognize `SC-###` (Success Criteria) ids at all

While authoring `tasks.md`, `spec-kitty agent mission finalize-tasks --mission
ci-nightly-wallclock-budget-01M34HNZ --validate-only --json` rejected WP01 with
`"missing_requirement_refs_wps": ["WP01"]` even though WP01's `**Requirement Refs**:` line named
`SC-008` (a real, spec.md-declared id — spec.md's Success Criteria are numbered `SC-001` through
`SC-008` exactly like its `FR-###`/`NFR-###`/`C-###` sections). Direct inspection of
`src/specify_cli/cli/commands/agent/mission_parsing.py::_parse_requirement_refs_from_tasks_md`
(line ~108) shows the extraction regex is hardcoded to
`r"\b(?:FR|NFR|C)-\d+\b"` — it has no `SC` alternative at all, so any WP whose ONLY requirement
trace is to a Success Criterion is silently treated as having ZERO requirement refs, then hard
rejected by `_classify_wp_requirement_refs` as `missing_requirement_refs_wps`, with no warning
that the reason is an unrecognized ID *prefix* rather than a genuinely absent citation. This is a
real gap between spec.md's own requirement-ID vocabulary (which this mission's own dispatch
brief explicitly told us includes `SC-001` through `SC-008` as citable ids) and the tool's
parsing vocabulary.

**Not routed around by hand-editing state.** Fixed by adding a genuinely-applicable `NFR-###`
anchor (`NFR-006`, "durably recorded, not just claimed" — WP01's baseline record is exactly that)
alongside the `SC-008` citation in WP01's `Requirement Refs` line, so the WP has a real,
machine-recognized trace in addition to the human-readable `SC-008` one. `SC-008` is KEPT in the
line for human traceability even though the tool ignores it. This is a genuine spec-kitty defect
(the tool's own vocabulary is a strict subset of spec.md's own declared ID space) worth filing
upstream — not fixed in this mission's scope, since `packs/built-in/` tooling source is outside
this mission's `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/` + `finalize-tasks`-writes
boundary.

## 2026-09-22 — tasks-authoring pass: two self-inflicted line-wrap bugs in `tasks.md`, both
self-corrected before `finalize-tasks` ran clean (documented for the next mission's author, not a
tool defect)

Two `**Requirement Refs**:` lines (WP03's and WP08's) were originally hand-wrapped across two
physical lines when first written (a normal prose-wrapping habit). Both
`_parse_requirement_refs_from_tasks_md` (tasks.md path) and the underlying
`re.findall(r"\*?\*?Requirements?\s*(?:Refs)?\*?\*?\s*:\s*(.+)", section_content, re.IGNORECASE)`
capture group use `.` without `re.DOTALL`, so the captured value silently truncates at the first
physical newline — WP03 lost its trailing `C-005` and WP08 lost its trailing `SC-008, C-006,
C-007`, with NO error or warning (the truncated set still validated as "some real ids present").
Confirmed via a direct Python repro
(`_parse_requirement_refs_from_tasks_md(open('tasks.md').read())['WP08']` returned only
`['FR-009', 'NFR-006']` before the fix, dropping four legitimately-cited ids). This is *not* being
filed as a spec-kitty defect — a metadata line silently truncating at a line-wrap with zero
diagnostic is arguably tool-side fragility worth hardening (the FR-010-authorship guidelines say
"ERROR on... tasks that exceed the size guidance — do not silently generate a degraded plan," and
a silently-truncated requirement-ref set is the same failure shape), but the fix here was simply
to keep every `**Requirement Refs**:` line on ONE physical line, which the validate-only pass
confirmed clean afterward. Noted here so a future WP-author knows this line specifically must
never be prose-wrapped, and flagging the silent-truncation behavior itself as worth a defensive
fix upstream (e.g. warn when a `Requirement Refs` line's captured value looks truncated by a
trailing comma with no following id).

## 2026-09-22 — tasks-authoring pass: `finalize-tasks --validate-only` rejects an 8-WP shape with
`LANE_DEPENDENCY_CYCLE` when a `planning_artifact` WP sits both upstream and downstream of a code
lane

The first `tasks.md` draft used 8 WPs: a standalone Phase-0-baseline WP (`execution_mode:
planning_artifact`, owning `kitty-specs/.../tracer-approach.md`, depended on by the first code
WP) and a standalone PR-assembly/evidence WP (also `planning_artifact`, depending on the last
several code WPs). `.venv/bin/spec-kitty agent mission finalize-tasks --mission
ci-nightly-wallclock-budget-01M34HNZ --validate-only --json` rejected this with:

```
{"error": "Execution-lane dependency cycle detected: lane-a -> lane-planning -> lane-a",
 "error_code": "LANE_DEPENDENCY_CYCLE",
 "cycle_path": ["lane-a", "lane-planning", "lane-a"],
 "cycle_lanes": [{"lane_id": "lane-a", "wp_ids": ["WP02", "WP03", "WP04"]},
                 {"lane_id": "lane-planning", "wp_ids": ["WP01", "WP08"]}]}
```

Root cause, confirmed by direct inspection of `src/specify_cli/lanes/compute.py`: **every**
`execution_mode: planning_artifact` WP in a mission is force-collapsed into ONE canonical lane
(`PLANNING_LANE_ID = "lane-planning"`), regardless of where in the dependency chain it sits. The
module's own comment anticipates exactly this failure mode ("a planning-artifact WP that depends
on a code WP must put PLANNING_LANE_ID downstream of that code [lane]... a planning-artifact WP a
code WP depends on must put PLANNING_LANE_ID upstream") — but nothing stops an author from
creating BOTH relationships in the same mission, which is precisely what the standalone-baseline +
standalone-evidence 8-WP shape did: the baseline WP put `lane-planning` upstream of the code lane,
and the evidence WP put it downstream, producing an unresolvable single-lane two-direction cycle.

**Not routed around by hand-editing state.** Fixed by changing the DECOMPOSITION, not the tool or
its state: folded the Phase-0-baseline WP's subtasks into the opening subtasks of the first code
WP (now `WP01`, mixing a baseline-recording step with the campsite-clean commit — baseline results
recorded in that WP's own Activity Log instead of a `kitty-specs/` file edit, since the Activity
Log does not require `execution_mode: planning_artifact` or a declared `owned_files` entry), and
kept the PR-assembly/evidence WP as the mission's ONLY `planning_artifact` WP, positioned last
(`WP07`) so `lane-planning` is purely downstream of the code lane. Re-running `--validate-only`
after this restructuring passed cleanly with no lane-related error. See `tasks.md`'s "A note on
this decomposition's shape" section and `WP01`'s prompt-file frontmatter `history` entry for the
in-context explanation. Worth a defensive fix upstream: `finalize-tasks --validate-only` could
detect this exact bidirectional-planning-lane shape earlier (at requirement-ref/dependency-parse
time) and suggest the fold, rather than surfacing only as a post-hoc lane-graph cycle after the
full WP set is authored.

## 2026-09-22 — `finalize-tasks` (real run) writes a `lanes.json` for a `single_branch`-topology
mission, with a `mission_branch` that does not exist and `predicted_surfaces` unrelated to this
mission — reproduces a predicted defect, not fixed here

Running `.venv/bin/spec-kitty agent mission finalize-tasks --mission
ci-nightly-wallclock-budget-01M34HNZ --json` (the real, committing run, after `--validate-only`
passed clean) wrote `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/lanes.json` — this mission's
`meta.json` declares `"topology": "single_branch"` with no `lanes.json` expected. Direct
inspection of the written file shows:

- `"mission_branch": "kitty/mission-ci-nightly-wallclock-budget-01M34HNZ"` — confirmed via `git
  branch -a` and `git rev-parse --verify` that NO branch by this name exists anywhere in this
  checkout (`git rev-parse --verify` fails with `fatal: Needed a single revision`). This mission
  has only ever worked on `issue-4865-ci-nightly-wallclock-budget` (per `meta.json`'s
  `target_branch`); a `kitty/mission-...` branch was never created and is not part of this
  mission's `single_branch` design.
- `"predicted_surfaces"` values per lane include `"api"`, `"artifact-rendering"`,
  `"legacy-cleanup"`, `"tracker-integration"`, `"dashboard"`, and `"planning"` — none of which
  describe this mission's actual domain (CI workflow YAML timeout/job-split, a registry shard
  count, two architectural test files). These are keyword-substring false positives from
  `src/specify_cli/lanes/compute.py`'s `SURFACE_TAXONOMY`/`_SURFACE_KEYWORDS` table matching
  incidental prose in the WP prompts (e.g. "artifact" from "xunit artifact"/"uploaded artifact",
  "cleanup" from "campsite cleaning"/Standing Order #2 prose, "tracker" from "GitHub issue
  tracker"/"Tracker Ticket Assignment Rule") rather than anything about the mission's real
  write-scope.

This is EXACTLY the defect class the dispatch brief warned about verbatim ("It can write a
`mission_branch` into `lanes.json` that does not exist, plus `predicted_surfaces` unrelated to the
mission... if one gets created, that itself is worth noting"). **Not routed around by hand-editing
state**: `lanes.json` is left exactly as `finalize-tasks` wrote it — not deleted, not hand-edited
— since this mission's own dispatch brief explicitly said the fix is to report the finding, not
silently repair the file. The mission's real execution model remains the `single_branch` one
declared in `meta.json` (`target_branch: issue-4865-ci-nightly-wallclock-budget`); the spurious
`lanes.json` should be treated as informational metadata `finalize-tasks` generated as a side
effect of its lane-computation pass (which runs regardless of mission topology), not as evidence
this mission gained a second, real branch/lane structure. Flagging for upstream: `finalize-tasks`
could skip lane-file generation entirely for `single_branch`-topology missions (checking
`meta.json`'s `topology` before running the lane-computation phase), and/or the
`SURFACE_TAXONOMY` keyword matcher could require a stronger signal (e.g. matching against
`owned_files` path segments, not free-text WP prose) before asserting a domain surface.

## 2026-09-22 — spec-authoring pass: no spec-kitty tooling friction encountered

The mission directory was already scaffolded (`meta.json`, `spec.md`
placeholder, `tasks/`, `research/`, `checklists/`) and untracked as expected
per the RESUME instructions — no scaffold command was run, none was needed.
Reading `.kittify/charter/charter.md`, `AGENTS.md`, and `CLAUDE.md` worked
without incident. Grounding the spec in real line numbers required direct
reads of `.github/workflows/ci-nightly.yml`, `.github/ci-module-registry.yml`,
`scripts/ci/capture_shard_timings.py`, and
`tests/architectural/test_module_shard_registry.py` — all present, readable,
and consistent with the dispatch prompt's line-number ranges (the
`performance-and-e2e` job starts at line 68 with `timeout-minutes: 60` at line
71; `nightly-summary`'s `needs:` list is at line 337; the `charter` registry
row starts at line 143 with `shard_count: 5` at line 151 — close to, and
consistent with, the prompt's "around line 150/151" estimate).

Confirmed `module_capture_provenance["charter"]` is `None` in
`.github/ci-shard-timings.json` by direct inspection (not by trusting the
dispatch prompt's claim) — this matched exactly, and `auth`'s populated
provenance record was used as the reference shape for what a real capture
looks like (see FR-006's acceptance criterion).

No broken command, no missing skill, no stale-venv surprise was hit during
this spec-authoring pass. If `.venv/bin/spec-kitty safe-commit` behaves
unexpectedly when committing this pass's files, that will be appended here
before commit, per the reflexive-failure/report-don't-route-around
instruction.

## 2026-09-22 — plan-authoring pass: `gh run view --json jobs` gives real
step-level timestamps, worth reusing

While sizing FR-002's three new `timeout-minutes` values, ran
`unset GITHUB_TOKEN && gh run view 35683539593 --repo spec-kitty/spec-kitty
--json jobs -q '.jobs[] | select(.name | contains("Performance")) | ...'`
against the spec's own cited run and got exact per-step start/end timestamps
(including the truncated `stress` step's `in_progress` status at
cancellation) — this turned a qualitative spec claim ("ran 65 minutes,
stress never reported") into three concrete, citable durations
(`performance` 23m41s, `e2e` 24m44s, `stress` >=16m18s truncated) without
needing to download or grep any log artifact. Worth reusing whenever a plan
needs to ground a CI-timing claim in a specific already-run workflow: `gh run
view <id> --json jobs` is cheaper and more precise than `gh run view --log`.
No friction — `gh auth status` was already authenticated via keyring per
CLAUDE.md's documented `unset GITHUB_TOKEN` pattern, first try.

`.venv/bin/spec-kitty plan --mission ci-nightly-wallclock-budget-01M34HNZ
--json` ran non-interactively and scaffolded `plan.md` cleanly on the first
call — no prompt, no stall.

## 2026-09-22 — plan-review fix pass: canonical `plan-template.md:4` boilerplate
still says "Feature specification" — a Terminology-Canon violation at the
template source, not this mission's plan.md

Confirmed adversarial finding PLAN-GOV-002: `plan.md`'s line 4 ("**Input**:
Feature specification from `kitty-specs/...`") is byte-for-byte the
boilerplate emitted by the canonical
`packs/built-in/missions/software-dev/templates/plan-template.md:4`, which
still reads "Feature specification" — a direct hit against the charter's
Terminology Canon (`.kittify/charter/charter.md`, Terminology Canon section:
"Feature"/"Features" are prohibited in canonical/operator/user-facing
language for active systems; canonical term is "Mission").

Per the finding's own remediation, this is **not** fixed inline in this
mission's `plan.md` — editing just this mission's copy would desync it from
the canonical template shape it is meant to mirror, and the drift is
root-caused in the template, not authored by this plan. Flagging here for
ledgering/fixing at the template source
(`packs/built-in/missions/software-dev/templates/plan-template.md:4`) so a
future maintenance pass updates the canonical wording once, instead of every
mission patching around it per-instance.

## 2026-09-22T15:47:11Z — WP01 `implement` dispatch: the announced lanes.json
hazard did NOT reproduce as a failure — it silently diverged from the
declared `single_branch` topology instead

The WP01 dispatch prompt flagged, verified moments earlier by the operator,
that `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/lanes.json` declares
`"mission_branch": "kitty/mission-ci-nightly-wallclock-budget-01M34HNZ"` — a
branch the operator confirmed did not exist yet — while
`kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/meta.json` carries
`"topology": "single_branch"` and no `mission_branch` field at all (i.e.
`None`), and WP01's own prompt frontmatter states `branch_strategy:
single_branch` with `planning_base_branch` / `merge_target_branch` both
`issue-4865-ci-nightly-wallclock-budget`. The dispatch instructed: if
`implement` fails on this (MissingLanesError, a worktree-allocation error, or
anything about the nonexistent branch), STOP and report BLOCKED rather than
working around it.

Ran exactly: `.venv/bin/spec-kitty agent action implement WP01 --mission
ci-nightly-wallclock-budget-01M34HNZ --agent claude` from
`/home/jeroennouws/dev/SK-missions/4865`. It did **not** fail. Instead it:

1. Silently created `kitty/mission-ci-nightly-wallclock-budget-01M34HNZ` (the
   mission branch lanes.json declared) at the current HEAD (`e864b4563`),
   despite `meta.json` declaring `single_branch` topology and carrying no
   `mission_branch` field.
2. Created a second branch, `kitty/mission-ci-nightly-wallclock-budget-01M34HNZ-lane-a`,
   and a lane worktree at
   `.worktrees/ci-nightly-wallclock-budget-01M34HNZ-lane-a`, i.e. the
   multi-lane worktree topology — not what `single_branch` (per meta.json)
   or WP01's own frontmatter (`branch_strategy: single_branch`, target =
   `issue-4865-ci-nightly-wallclock-budget`) describes.
3. Rewrote WP01's own prompt frontmatter in place, adding `base_branch:
   kitty/mission-ci-nightly-wallclock-budget-01M34HNZ` and a `base_commit`
   pinned to `e864b4563`, fields that were absent before the command ran.
4. Recorded two coordination commits (`chore(spec-kitty): status transition
   batch WP01`, `chore: Start WP01 implementation [claude]`) directly onto
   `issue-4865-ci-nightly-wallclock-budget` (the primary checkout branch) —
   i.e. status/coordination writes landed on the declared single-branch
   target as expected, while the *code* workspace it printed
   (`.worktrees/ci-nightly-wallclock-budget-01M34HNZ-lane-a`) sits on the
   undeclared lane-branch tree instead.

Net effect: two parallel, inconsistent branch topologies now coexist for one
mission — the coordination/status layer honors `single_branch` (writes land
on `issue-4865-ci-nightly-wallclock-budget`), but the code-workspace resolver
silently manufactured a full lane-topology branch pair that nothing in
`meta.json` or WP01's frontmatter asked for, and did so without any warning,
error, or diagnostic — not even the `MissingLanesError` the operator
predicted as the failure mode. This is a **live instance of ledger SK-91/
SK-199 territory** (lane-computation defects for `single_branch` missions)
distinct from and worse than the hypothesized failure: rather than blocking
cleanly, the resolver produced *silently divergent* branch state. Per the
dispatch's explicit rule ("Do NOT hand-edit lanes.json, meta.json, WP
frontmatter... Do NOT create the missing branch... A transition with no
sanctioned CLI command is a BLOCKED report, not a workaround"), this was not
a transition I initiated by hand — the canonical `agent action implement`
command did it unprompted as part of a successful (zero-exit, no error text)
run. Since the command itself did not fail, WP01's dispatch does not
literally trigger its own BLOCKED clause; I am proceeding by consuming the
resolved workspace path exactly as instructed ("consume the resolved
workspace path it gives you — do not reconstruct or guess it"), and flagging
this divergence here rather than silently accepting it as unremarkable. This
belongs in `SPEC-KITTY-LEDGER.md`'s SK-91/SK-199 entry as a concrete
reproduction: `single_branch` topology + a `lanes.json` written by an earlier
`finalize-tasks` run in multi-lane shape produces a *silent* lane-topology
fork on first `implement`, not a guard failure.

**Addendum, same pass — consequence for the push/PR handoff**: WP01's actual
campsite-clean commit (`chore(ci): remove inert fail-fast key from
performance-and-e2e`, `d1e7d5177`) landed on
`kitty/mission-ci-nightly-wallclock-budget-01M34HNZ-lane-a` (the undeclared
lane branch from point 2 above), NOT on `issue-4865-ci-nightly-wallclock-budget`
(WP01's own frontmatter `merge_target_branch`). Only the coordination/status
commits landed on `issue-4865-ci-nightly-wallclock-budget`, which is the
branch this WP pushed to `origin` per the dispatch's "push the branch"
instruction. **The pushed branch therefore does not yet contain WP01's code
change** — it is stranded on the local-only lane branch until a
`spec-kitty merge` (or equivalent lane-consolidation step) runs, which is the
standard mechanism for a genuine lanes-topology mission but is not what
`meta.json`'s declared `single_branch` topology or WP01's own
`branch_strategy: single_branch` frontmatter describes needing. WP02/WP03
share this same lane worktree/branch next, so the commit is not lost, only
deferred — but whoever assembles the mission's single PR must be aware the
target branch (`issue-4865-ci-nightly-wallclock-budget`) needs an explicit
lane-consolidation step before it carries any WP01-WP03 code, not just a
`git push` of that branch as it stands today.

**Second addendum, same pass — operator correction, applied directly to the
target branch instead of waiting for lane consolidation**: the operator
confirmed by direct inspection that `origin/issue-4865-ci-nightly-wallclock-budget`
did not carry the `fail-fast` removal (matching the first addendum above) and
directed applying the campsite-clean edit again, directly on the primary
checkout / target branch, rather than waiting on an unspecified future
lane-consolidation step. Done: `3fb1c8bb7` (`chore(ci): remove inert
fail-fast key from performance-and-e2e`) on
`issue-4865-ci-nightly-wallclock-budget`, identical 2-line removal,
independently red-first-checked (no `matrix:` key between `performance-and-e2e:`
at line 68 and the next job `interpreter-matrix:` at line 176). **Consequence
left unresolved and worth flagging forward**: the same functional change now
exists as two separate commits on two different branches —
`d1e7d5177` on `kitty/mission-ci-nightly-wallclock-budget-01M34HNZ-lane-a`
(the undeclared lane branch WP02/WP03 will continue in) and `3fb1c8bb7` on
`issue-4865-ci-nightly-wallclock-budget` (the pushed target branch). Content
converges (both remove exactly the same two lines), so a future
lane-consolidation merge of the lane branch into the target branch should be
a trivial/no-op hunk for this specific file, but whoever runs that
consolidation (or WP02, whose own diff starts from the lane branch's
`d1e7d5177`) should be aware two independent commits exist for the same
2-line change rather than one shared ancestor — do not be surprised if a
merge reports "already applied" or an empty diff for this hunk.

## 2026-09-22 — orchestrator, first-hand: `agent status emit` review-evidence flags

Two defects hit while recording WP01's reviewer-approved verdict. Neither was worked around;
both transitions were made only through sanctioned CLI calls, nothing hand-edited.

**1. The command's own `--help` example is an illegal transition.** `agent status emit --help`
documents:

    spec-kitty agent status emit WP01 --to approved --actor claude --review-result-json '{...}'

Run verbatim from the state the implement/review loop actually produces (`for_review`), it
fails: `Error: Illegal transition: for_review -> approved`. The 9-lane machine requires
`for_review -> in_review -> approved`, so the documented one-step example is unreachable from
the only state a reviewed WP is ever in. Cost: one failed call and a guess at the intermediate
lane; the error names the refusal but not the legal next hop.

**2. `--review-result-json` does not satisfy the payload's own `evidence` requirement —
silent-success.** With the two-step sequence, `in_review -> approved` and
`--review-result-json '{"reviewer": ..., "verdict": "approved", "reference": ...}'` supplied,
the local event was written and the CLI printed `OK WP01: in_review -> approved`. But it also
printed:

    WARNING Zeitgeist moment WPStatusChanged not broadcast: 1 validation error for
            StatusTransitionPayload
            Value error, to_lane in {'approved', 'done'} requires evidence
            input_value={'mission_slug': 'ci-nigh... None, 'evidence': None}

So the flag advertised for review evidence populates something other than the `evidence` field
the outbound payload validator requires. The result is a **local success with a dropped
broadcast**: the event log and Kanban show `approved`, while every downstream consumer of the
team relay is never told. It degrades to a warning on a path whose whole purpose is recording
review provenance, and it will do so for every `approved` and every `done` transition.

Related: **SK-218** (approved/done need differently-shaped evidence in different flags, and the
identical error message names neither) — this is the same family, now with the concrete
observation that `--review-result-json` is *accepted* yet does not populate `evidence`, so the
failure is invisible unless the operator reads a warning on a line that also says `OK`.

Verified first-hand, `spec-kitty-cli 4.0.0rc5`, mission `ci-nightly-wallclock-budget-01M34HNZ`.

### Correction to defect 2 above — narrower than first written, still real

The first draft of defect 2 said the review evidence "was never persisted into the local event
either". **That is wrong and is corrected here rather than edited away.** Reading the raw event
(`status.events.jsonl`, event `01M34XTTAPW2YFC8BZB483JZAZ`) shows the evidence IS persisted
locally, in a field named `review_result`:

    "review_result": {"reference": "e864b4563..5a28d1277",
                      "reviewer": "reviewer-renata",
                      "verdict": "approved"},
    "evidence": null,
    "review_ref": null,

So the local audit trail can answer who approved WP01 and against what diff. The accurate
finding is a **field-name mismatch across one seam**: `--review-result-json` writes
`review_result`, while the outbound `StatusTransitionPayload` validator requires a populated
`evidence` for `to_lane in {approved, done}`. Two names for the same concept, written by one
side and validated by the other, so the broadcast is dropped while the local write succeeds.

Impact stands as originally described for the outbound path: every `approved` and every `done`
transition loses its Zeitgeist moment, reported only as a WARNING on a line that also prints
`OK`. An operator skimming for failure sees success. The fix is presumably either to map
`review_result` onto `evidence` at the payload boundary, or to have the validator accept the
field the CLI actually writes — but which of those is correct is a maintainer call, not ours.

**A third observation from the same event, unrelated to evidence:** it records
`"execution_mode": "worktree"` for a mission whose `meta.json` declares
`topology: single_branch`. That is the same SK-91/SK-199 divergence WP01 already recorded from
the `implement` side, now visible in the status event log too — the worktree assumption is not
confined to workspace resolution; it is being stamped into the canonical event stream.

Verified first-hand, `spec-kitty-cli 4.0.0rc5`.

### WP02: `make test-fast` silently backgrounds past the harness's own tool timeout, and nothing wakes the agent

Running `make test-fast` (the mission's mandated baseline gate) inside a single Bash tool call
exceeded that call's default 120s timeout; the harness moved it to a background task
transparently rather than erroring. The agent then ended its turn expecting the background task
to notify it on completion — but a Bash `run_in_background` task's completion notification only
delivers if the agent's turn is still open to receive it; ending the turn to "hand back" the wait
(as the WP prompt's own "Waiting" section allows for a *dispatched subagent*) does not work the
same way for an agent's *own* backgrounded shell command inside a live session — the same failure
mode as WP01's "subagents strand on their own background work", now confirmed to apply to a
foreground-turned-background `Bash` call too, not only to dispatched subagents. Recovery required
the coordinator to intervene, confirm the PID (`1952095`) was still alive and not to be killed,
and instruct an explicit in-turn blocking loop (`while kill -0 <pid>; do sleep 15; done`). The
same thing then recurred one level down: `.venv/bin/python -m pytest tests/architectural/ -q`
(1261s / 21 minutes) exceeded first a 300s and then a 600s explicit `timeout` parameter on the
Bash tool and was auto-backgrounded twice more, each requiring another blocking `while kill -0`
loop rather than a single wait. **Lesson for future WPs**: a repo-directory-scale pytest run
(`tests/architectural/` in full, `make test-fast`, etc.) should be started with
`run_in_background: true` explicitly from the first call, immediately followed by an in-turn
`while kill -0 <pid>; do sleep 15; done` block in the SAME turn — never assume a bare foreground
Bash call will finish inside any timeout you pick, and never end a turn while your own gate
command is still running in the background, regardless of how the "Waiting" section's language
about dispatched subagents might read.

Verified first-hand, `spec-kitty` mission `ci-nightly-wallclock-budget-01M34HNZ`, WP02.

## 2026-09-22 — orchestrator, first-hand: a WP's code can land while its lane stays `planned`

**SK-175 reproduced, on 4.0.0rc5, from inside a live mission.** WP03's implementation commit
(`154a6c6e6`, `fix(ci): re-derive stress timeout from measured dispatch duration (Stage B)`)
was authored, committed via `spec-kitty safe-commit`, and pushed to origin while WP03's lane
was still `planned`. Its entire event history at that point was one row:

    WP03  genesis -> planned  | actor finalize-tasks

No `claimed`, no `in_progress`, no `for_review`. `safe-commit` accepted a commit for a work
package that the state machine has no record of anyone ever starting, and nothing anywhere
objected. The mission's canonical event log — which `CLAUDE.md` calls "the sole authority for
WP lane state" — therefore disagrees with git about whether WP03 was ever worked.

Contributing cause on our side, stated plainly rather than blamed on the tool: the dispatch
for WP03 asked for a `workflow_dispatch` run plus a `safe-commit`, and never instructed the
agent to route through `spec-kitty agent action implement WP03`, which is what claims the lane
(WP01 and WP02 both transitioned correctly because their dispatches did use it). So this is a
process gap that the tooling then failed to catch. The point stands regardless: **a commit
landing against a `planned` WP is exactly the hole SK-175 describes, and the only thing that
noticed was a human reading the Kanban.**

Consequence for reviewers: a per-WP verdict cannot be recorded against a lane that never left
`planned` — `agent status emit WP03 --to in_review` refuses with
`Error: Illegal transition: planned -> in_review`. So the review verdict for completed,
committed, pushed work had nowhere sanctioned to go until the WP was claimed retroactively.

## 2026-09-22 — orchestrator, first-hand: `agent status emit` leaks a raw RuntimeError

Attempting the rejection transition surfaced an unhandled exception through the CLI's error
surface, with a truncated message and a traceback frame:

    │ ❱ 492 │   │   raise RuntimeError("; ".join(d.message for d in result.diagnos
    RuntimeError: Global asset input changed:

The message is cut off exactly where the diagnostics would have been, so the operator is told
that some "global asset input changed" and nothing about which asset, which input, or what to
do. Compare SK-16 (`charter status --json` leaking a raw `AttributeError` through its error
envelope) — same family: an internal diagnostic escaping as a traceback instead of an
actionable, enveloped error. Verified first-hand, `spec-kitty-cli 4.0.0rc5`.

## 2026-09-22T17:35Z — WP03 rejection-fix pass: the same `RuntimeError: Global asset input
changed: /home/jeroennouws/.agent/workflows/spec-kitty.analyze.md` hit `agent action implement
WP03`, and a bare retry cleared it

Claiming WP03 to close the SK-175 gap (see the entry above) required `.venv/bin/spec-kitty agent
action implement WP03 --mission ci-nightly-wallclock-budget-01M34HNZ --agent claude`. The first
invocation raised the identical `RuntimeError` documented above (same traceback frame,
`_apply_command_assessment` -> `raise RuntimeError("; ".join(d.message for d in
result.diagnos[tics]))`), this time on the `implement` verb rather than `status emit` — confirming
the defect is not scoped to one CLI subcommand but to `ensure_global_agent_commands()`, which
every `main_callback` invocation runs on startup. A bare re-run of the exact same command,
seconds later, succeeded cleanly with no error (though it then separately reported `Error:
--mission <slug> is required` because the first attempt's argument, `--agent claude` positioned
before `--mission`, was itself fine — the real second retry, with `--mission` supplied, claimed
WP03 without incident). This is consistent with a transient race against a concurrently-running
process on this machine touching the shared global asset directory
(`~/.agent/workflows/spec-kitty.analyze.md`), not a defect in this mission's own state — but it
means EVERY `spec-kitty` CLI invocation on this host is presently subject to an intermittent,
unhandled `RuntimeError` that a bare retry silently clears, with no diagnostic pointing at the
concurrency cause. Not routed around by hand-editing state; not filed as a new defect (same root
cause as the entry immediately above) — recorded here as confirmation that "retry once" is a
viable, non-state-mutating recovery for this specific failure shape.

### Correction + refinement: the `Global asset input changed` RuntimeError is NOT truncated

My earlier entry said the message was "cut off exactly where the diagnostics would have been."
That was wrong — it was cut off in *my terminal capture*, not in the CLI's output. The fix
agent hit the same error on `agent action implement WP03` and captured it in full:

    RuntimeError: Global asset input changed: /home/jeroennouws/.agent/workflows/spec-kitty.analyze.md

So the message does name the offending asset. Two refinements that matter more than the
original complaint:

1. **It is cross-subcommand, not specific to `agent status emit`.** Reproduced on
   `agent action implement` as well, so it fires at a startup/asset-validation layer shared by
   the CLI's subcommands rather than inside one command's logic.
2. **It is transient — a bare retry clears it, with no state mutation in between.** That makes
   it a race, not a corrupted-state condition. It still surfaces as an unhandled `RuntimeError`
   with a traceback frame instead of an actionable enveloped error, and it still blocks the
   first attempt at a legitimate sanctioned command, so the defect stands; but the remedy is
   "retry once", not "repair something."

**Hypothesis worth recording for whoever fixes it** (stated as a hypothesis, not a finding —
we did not prove it): the named path is an **installed global asset** under `~/.agent/`, i.e.
outside this mission's repository entirely. A second spec-kitty mission was running
concurrently in a sibling workspace during this window (issue #4866,
`interpreter-matrix-3-13-env-and-divergence-01M34HVD`). If that mission's CLI invocations
regenerate `~/.agent/workflows/`, then two concurrent missions on one machine would race on a
shared global asset, and each would intermittently refuse the other's commands. That would
make this a **concurrency defect in the global asset layer**, not a per-mission problem — and
it would reproduce for any operator running two missions at once, which this workspace's own
doctrine explicitly permits (up to two lanes past triage).

## 2026-09-22 — a correctly-SKIPPED conditional subtask can only be recorded as `done`

WP03's T015/T016 are the widen-retry-ladder steps, and WP03's own prompt says of T015: *"Skip
entirely if T014 already shows a completed stress conclusion within 90 minutes — this is the
EXPECTED case."* Stress completed in 4m44s, so the expected case held and neither step ran.

There is no way to say that. `agent tasks mark-status --status` accepts exactly two values —
confirmed in source at `src/specify_cli/cli/commands/agent/tasks.py:907`, whose own help text
reads `Status: done/pending`. Meanwhile `move-task <WP> --to for_review` hard-blocks while any
subtask is unchecked. So a conditional subtask whose skip-condition was correctly satisfied has
only two representable outcomes, and **both are false**: `pending` (implying outstanding work
that will never be done, and which blocks the lane forever) or `done` (implying the step was
performed when it deliberately was not).

The mission recorded `done` plus an explicit Activity Log note stating the mark records "that
their skip-condition was correctly evaluated and satisfied, not that either ladder step or the
escalation was performed." A reviewer independently judged that defensible **because it was
disclosed** — but the disclosure lives in prose, while the machine-readable state says `done`.
Any consumer reading the event log or the checkbox rather than the prose is told the ladder ran.

This is small but it is the same defect family this mission exists to fix: a state surface that
cannot express a distinction that matters, so the honest answer has to live in a comment beside
it. A `skipped` (or `not_applicable`) status, with the lane gate accepting it as terminal, would
close it. Verified first-hand, `spec-kitty-cli 4.0.0rc5`.

## 2026-09-22 — ROOT CAUSE of #4864: the duration list is not merely stale, it is the wrong LENGTH, so the consumer ignores it entirely

Found while verifying WP04's recapture. This is a stronger and more general statement of #4864's
defect than the mission's own spec makes, and it is established by measurement, not inference.

**The mechanism, in the producer's own words.** `scripts/ci/capture_shard_timings.py`'s module
docstring states that `module-tests.yml` "cannot join durations to node ids (the committed file
drops node ids for compactness), so it pairs them **positionally** ... and falls back to
**uniform weights for the whole module** when `len(durations) != len(node_ids)`. That fallback
is silent and no gate notices it: the skew guard re-reads the same committed list, so a list of
the right length always passes whether or not it was ever measured."

**Measured, on this checkout, at HEAD before our recapture:**

| module | committed list | consumer collects (`not performance and not stress`) | used? |
|---|---|---|---|
| `charter` | 4211 | **6156** | NO — 1945 short, uniform fallback |
| `status`  | 1702 | **1758** | NO — 58 short, uniform fallback |

So charter's five shards were being balanced **by test count, not by time** — which is a complete
explanation for #4864's 32-minute long pole, and a better one than "the timings are near-uniform."
The timings were not being consulted at all. `status` is in the same state *today*, and `status`
is one of the seven modules that *does* carry a `module_capture_provenance` entry, i.e. one of the
ones someone already captured with the purpose-built tool. Being captured correctly once does not
keep the list usable.

**Two distinct causes, both verified:**

1. **Drift.** Every test added to a module's `test_dirs` after its capture lengthens the
   consumer's node-id list while the committed durations stay fixed. Nothing regenerates the file
   and nothing validates its length, so every module decays into the uniform fallback over time.
   `charter` drifted 4211 -> 6156 (+46%); `status` 1702 -> 1758.
2. **A permanent selection mismatch in the producer.** `SELECTION_MARKER_EXPR = "not performance"`
   (`scripts/ci/capture_shard_timings.py:76`) does not match the consumer's
   `-m "not performance and not stress"` (`.github/workflows/module-tests.yml:210`). For any module
   whose `test_dirs` contain `stress`-marked tests the producer measures a **longer** list than the
   consumer collects, so a freshly-captured module can be born mismatched. Measured on `status`:
   1760 (producer selection) vs 1758 (consumer selection). Modules whose dirs contain
   `pytest.mark.stress` today: `status`, `core_misc`.
   `charter` is unaffected by cause 2 — `tests/charter` and `tests/doctrine` contain no
   `stress`-marked tests, so both selections collect 6156. Our fix is sound; it is sound by luck of
   marker distribution, not by the producer being correct.

**What this means for this mission.** WP04's recapture makes `charter` correct *at this moment*
(6156 == 6156, provenance recorded, `exit_code: 0`, sub-2ms share 77.3% -> 36.3%, sum 410.8s ->
1134.2s). It does **not** install any mechanism that keeps it correct. The next test added under
`tests/charter` or `tests/doctrine` re-breaks the length match and silently returns charter to
uniform weighting, with every gate still green. Spec FR-008/NFR-003/SC-006 should be read with
that limit stated plainly rather than implying a durable fix.

**Out of scope to fix here** (operator ruled the other modules out of scope, and the producer's
selection constant is not this mission's file), but it is the strongest ledger candidate this
mission has produced: a length-agreement check between the committed list and the consumer's
collection — run in CI, per module — would close the whole family by construction, and is exactly
the "non-vacuous gate" charter Standing Order #5 asks for.

Verified first-hand, `spec-kitty-cli 4.0.0rc5`, commands recorded above.

## 2026-09-22 — the review verdict vocabulary differs between doctrine and the CLI

`agent status emit --review-result-json` accepts `verdict` values of **`approved`** or
**`changes_requested`** only. **`rejected` is refused.** Discovered when moving WP05 back out of
`for_review` to apply the operator's ruling.

This matters because the review doctrine this mission runs under says the opposite: a per-WP
reviewer returns `approved` or **`rejected`**, and "rejected → a FRESH WP agent dispatch with the
verdict quoted verbatim" is the sanctioned path. So the word every reviewer emits and every
dispatch quotes is not a word the state machine will accept. An orchestrator recording a real
rejection reaches for `"verdict": "rejected"`, is refused, and has to guess the CLI's synonym at
the exact moment it is trying to record an adverse finding.

Related: **SK-234** (native rejection drops the claimed reviewer identity and records `user`) —
same surface, same direction of loss. Together they mean the rejection path is the least
well-served transition in the lane machine, which is unfortunate, because it is the one whose
provenance matters most.

Low severity, trivially fixable by accepting `rejected` as an alias, and worth fixing because the
failure lands on the adverse path rather than the happy one. Verified first-hand,
`spec-kitty-cli 4.0.0rc5`.

## 2026-09-22 — `status emit`'s `--reason` never reaches `status.json`'s `notes`; only `move-task
--note` does, and it requires a real lane transition

Applying a rejection-fix that needed to append a corrective record beside an existing false
`status.json` `work_packages.<WP>.notes[]` entry (append-only ledger discipline — never silently
edit a materialized snapshot), I first assumed `agent status emit --reason "<text>"` (the command
this mission's own dispatch brief names as the sole lane-mechanics tool) would land that text in
`notes`. It does not: `--reason` is written only to the `StatusEvent.reason` field (visible in
`status.events.jsonl`, and surfaced via `review_result.reference` when paired with
`--review-result-json`) — never folded into the `notes` list. Confirmed by reading
`spec_kitty_events.diary` (the vendored reducer `status/reducer.py` delegates to): the ONLY event
shape that appends to `notes` is an off-axis `InnerStateChanged` annotation carrying
`delta.note` — `notes: list[str] = list(state.get("notes") or []); notes.append(delta.note)`
(explicitly append, never replace). `agent status emit` never constructs one.

The only CLI surface found that emits that annotation is `agent tasks move-task ... --note "<text>"`
— and `move-task` does not have a "note-only, no lane change" mode: `--to` is required and is
validated as a real FSM transition (same state machine `status emit` uses), with the note delta
folded in as a side effect of that transition. So getting a corrective note into `notes` requires
making a genuine lane move at the same time — there is no bare "annotate this WP" command. For this
mission, that was compatible with the required "return WP05 to `for_review` when done" hop (the WP
file's own `### Updating Status` footer independently names `move-task` as the canonical status
command), so `move-task WP05 --to for_review --note "<corrective text>"` supplied both the required
transition and the append in one call. A mission whose lane-mechanics constraints did not need a
transition at the moment a note had to be added would have no sanctioned way to attach one — the
gap is real, not just an inconvenience of phrasing.

Separately, `agent tasks add-history WP01 --note "..."` (the canonical command for appending to a
WP task file's own `## Activity Log`, distinct from the `status.json` `notes` array above) does not
insert before a trailing non-`##` subsection: `append_activity_log`'s section-boundary regex
(`task_utils/support.py::append_activity_log`) splits only on the next `\n## ` (level-2) heading, so
a WP file whose Activity Log section is followed by a level-3 `### Updating Status` footer (as
`WP05-rederive-charter-shard-count.md` is) gets the new entry appended AFTER that footer, not before
it — the "### Updating Status / Use `move-task`..." boilerplate ends up sandwiched between older and
newer Activity Log entries. Harmless here (the entries are still there, in order, just visually past
a stray subheading) but worth fixing: either treat `###`+ headings as boundaries too, or place
"Updating Status"-style footers outside the `## Activity Log` section in the WP template.

Verified first-hand, `spec-kitty-cli 4.0.0rc5`, mission `ci-nightly-wallclock-budget-01M34HNZ`,
WP05 rejection-fix pass.

## 2026-09-22 — BLOCKED: a `planning_artifact` WP cannot leave `doing` by any sanctioned command

Verified first-hand by the orchestrator, `spec-kitty-cli 4.0.0rc5`, mission
`ci-nightly-wallclock-budget-01M34HNZ`, WP07 (`execution_mode: planning_artifact`), topology
`single_branch`. WP07's work is complete and committed on `issue-4865-ci-nightly-wallclock-budget`
(`2de60dd27`, `ab6f1b1f1`, plus the tracer correction). The tree is clean. Both transition paths
still refuse:

**1. `agent action implement WP07` — refuses on a phantom lane merge.**

    Error self-healing workspace for WP07: cannot auto-merge dependency lane 'lane-a'
    (kitty/mission-ci-nightly-wallclock-budget-01M34HNZ-lane-a) into lane 'lane-planning':
    the merge conflicts. merge '...-lane-a' into lane 'lane-planning' manually, resolve the
    conflicts, commit, then re-run the implement command for this WP.

`lane-planning` **does not exist as a git ref** (`git rev-parse --verify` → `fatal: Needed a single
revision`). `lane-a` exists only because `agent action implement` provisioned it unasked under a
`single_branch` topology (SK-91/SK-199), and it is pinned at `d1e7d5177` — the orphaned duplicate of
WP01's campsite-clean that never belonged on the mission branch. So the CLI asks the operator to
merge a phantom lane into a nonexistent lane, and the prescribed manual remedy would inject that
orphaned commit into the mission and fork its history. Same shape as **SK-01** (the CLI prescribes a
remedy it cannot perform) and **SK-60** (the only escape hatch would corrupt the mission).

An earlier invocation, with one file uncommitted, failed differently and more misleadingly:

    Error self-healing workspace for WP07: Lane lane-planning worktree at
    /home/jeroennouws/dev/SK-missions/4865 has uncommitted changes.

— naming the **primary checkout** as the `lane-planning` worktree, which is the SK-138/SK-152
confusion stated outright.

**2. `agent status emit WP07 --to for_review` — refuses on the same phantom branch.**

    Error: WP07 cannot move to for_review: no implementation commit on lane

The guard looks for an implementation commit on the lane branch the topology never creates, while
the actual commits sit on the mission branch it was told to use. This is **SK-69** exactly ("under
`single_branch` topology, `agent status emit` demands an implementation commit on a lane branch the
topology never creates, so a completed WP can never leave `planned`") — reproduced here from
`doing` rather than `planned`, on 4.0.0rc5, for a `planning_artifact` WP.

**Consequence.** Finished, committed, reviewable work cannot be advanced to review through any
sanctioned surface. The only exits are `--force` (bypassing a guard whose premise is false) or a
hand-edit (forbidden, and doubly so here because the state format is the thing under test). The
mission's *deliverable* is unaffected — the PR body and all code are committed on the mission
branch — but its *bookkeeping* is stuck, so `accept`/`merge` and any gate keyed on lane state
cannot be truthful.

**Suggested fix:** resolve the implementation-commit guard against the mission's resolved
write branch rather than a derived lane ref, and do not run dependency-lane auto-merge for
topologies that never create lanes.

## Deviation to record honestly: a WP agent hand-appended one event rather than reporting BLOCKED

Commit `fa06a4899` ("claim WP07 (bypass broken lane-planning self-heal, SK-91/SK-199 class)")
appended a single well-formed identity annotation for WP07 to `status.events.jsonl`
(event `01M35D9EMBPHD8JTVRF63A5M6N`). Its values use the CLI's own documented sentinels
(`src/specify_cli/status/resolved_binding.py:37-40`) and its delta key set matches WP02's
CLI-written annotation, so the content is correct and carries true information.

It was nonetheless the wrong action: the agent hit the hard block documented above and worked
around it instead of reporting BLOCKED, which its dispatch expressly forbade. The orchestrator
asked the agent to account for it; the agent stranded before answering, and the block was then
reproduced independently — so the *substance* of its "broken self-heal" claim is confirmed even
though the response to it was not sanctioned.

**Disposition: left in place, disclosed.** Removing it would require either another hand-edit or a
history rewrite of ~60 commits (invalidating the review trail's commit-hash citations — the SK-179
hazard this mission already avoided once by merging rather than rebasing). Both remedies are worse
than the deviation. It is recorded here, and belongs in the PR body and the pre-merge squad's view
so a maintainer sees it rather than discovers it.

## Correction to the two entries immediately above (commit `ce5ed90de`)

Two claims in the preceding two sections do not hold up against direct re-verification just
performed, in the same checkout, on the same commit range. Recorded per this workspace's
append-only discipline — not editing the entries above, adding the correction beside them.

**1. The `for_review` block is not reproduced via the documented CLI surface.** The entry above
cites `agent status emit WP07 --to for_review` → `Error: WP07 cannot move to for_review: no
implementation commit on lane`. Running the actual canonical, documented command instead —
`spec-kitty agent tasks move-task WP07 --to for_review --agent claude --mission
ci-nightly-wallclock-budget-01M34HNZ` — on this same clean tree, same HEAD, produces a completely
different and entirely ordinary result:

    Error: Cannot move WP07 to for_review - unchecked subtasks:
      - [ ] T034
      - [ ] T035
      - [ ] T036
      - [ ] T039
      - [ ] T037
      - [ ] T038
    Mark these complete first: spec-kitty agent tasks mark-status T034 --status done ...

This is the expected, working subtask-completion gate (`mark-status`), not a lane/topology defect.
No SK-01/SK-60/SK-69 shape reproduces via `move-task`. `agent status emit` is a lower-level,
separately-documented command (`Records a lane transition in the canonical event log, validates
against the state machine...`) and may have its own gate shape, but it is not the command this
WP's own task-file footer names (`Status is managed via status.events.jsonl. Use spec-kitty agent
tasks move-task WP07 --to <status>`), and its failure has not been independently reproduced via the
documented path. The dramatic framing ("cannot leave `doing` by any sanctioned command", "the only
exits are `--force` or a hand-edit") is not supported by this direct test.

**2. Commit `fa06a4899` was not a hand-append.** Direct `git show` on all three commits in sequence
(`f1a1ad829`, `532181b56`, `fa06a4899`) shows: `spec-kitty agent tasks move-task WP07 --to claimed`
internally auto-committed `f1a1ad829` (the `planned→claimed` event plus its identity-annotation
delta); `move-task WP07 --to in_progress` internally auto-committed `532181b56` (a leftover
annotation delta from the first call, plus the `claimed→in_progress` event) but left its OWN
trailing annotation delta (`01M35D9EMBPHD8JTVRF63A5M6N`) uncommitted in the working tree — a
CLI-internal artifact of how `move-task` sequences its auto-commit relative to the annotation
append, reproducible on any `move-task` call. `spec-kitty safe-commit
kitty-specs/.../status.events.jsonl --to-branch issue-4865-ci-nightly-wallclock-budget -m "..."` —
a real, documented, sanctioned command, not `--force` and not a hand-edit — then committed exactly
that one pre-existing working-tree line as `fa06a4899`. No editor, shell redirect, or script ever
touched `status.events.jsonl` directly. This is not the "worked around a BLOCKED state instead of
reporting it" pattern the entry above describes — the claim transition itself (`agent action
implement`'s lane self-heal) is a separate, already-documented defect (SK-91/SK-138/SK-152/SK-199),
and the sanctioned `move-task` fallback used to get past it is not a hand-edit of any kind.

Verified first-hand, `spec-kitty-cli 4.0.0rc5`, mission `ci-nightly-wallclock-budget-01M34HNZ`,
WP07, same session that produced `fa06a4899`, immediately following the operator's own account
request.

### Orchestrator's correction to the two claims in `ce5ed90de` — both were mine and both were wrong

`ce5ed90de` was written by the orchestrator, not by a subagent. Two of its claims do not survive
checking, and it is corrected here rather than edited, per this workspace's append-only discipline.

**Wrong claim 1: that `fa06a4899` was a hand-append.** It was not. `agent tasks move-task` leaves its
own trailing identity-annotation event uncommitted in the working tree after each call; `fa06a4899`
is a plain `spec-kitty safe-commit` sweeping up that CLI-written line. Two agents established this by
reading `src/specify_cli/lanes/implement_support.py` and inspecting the surrounding commits
(`f1a1ad829`, `532181b56`); the orchestrator inferred a violation from the commit message's word
"bypass" and from content alone, which cannot distinguish authorship. **No hand-edit of spec-kitty
state occurred.** The claim is withdrawn.

Related correction: a report flagged a "hand-appended `{"actor": "user", ...}` subtask-delta event" as
a violation. Also wrong — `actor: "user"` is what the CLI itself records for `mark-status` /
`move-task` calls, and such events appear for **WP01 and WP02** (lines 24, 31-34) long before WP07.
This is the known SK-125 shape (the CLI labels every caller human); it is not evidence of a hand-edit.

**Wrong claim 2: that no sanctioned command can advance WP07.** Too strong. `agent status emit WP07
--to for_review` does refuse with `no implementation commit on lane` — the genuine SK-69-class
phantom-lane guard, and that part of the entry stands. But `agent tasks move-task WP07 --to
for_review` gets past it and refuses for a different, legitimate reason:

    Error: Cannot move WP07 to for_review - unchecked subtasks:
      - [ ] T037

T037 is "open the PR". So WP07's lane is not blocked by a tooling defect at all at this point — it is
blocked by a **template-versus-dispatch conflict**: the WP template assigns PR creation to the WP
agent, while this mission reserves it to the orchestrator (charter: the operator merges; the
orchestrator opens the draft PR as the last implementation step). The honest resolution is ordering,
not overriding: open the PR first, after which T037 is genuinely complete and the transition is true.

**What remains true from `ce5ed90de`:** `agent action implement WP07` does fail on a phantom-lane
auto-merge (`lane-a` into a `lane-planning` ref that does not exist), and its prescribed manual
remedy would inject the orphaned `d1e7d5177` duplicate into the mission. `agent status emit` does
refuse on the phantom lane. Those are real, reproduced, and remain ledger candidates. The
over-reach was in generalising them to "no sanctioned command" and in alleging a hand-edit.

**Process failure worth recording, and it is the orchestrator's.** The WP07 dispatch did not forbid
the WP agent from spawning its own subagents. It spawned two for "narrow evidence extraction"; both
inherited full context, exceeded that scope, and one wrote commits to the shared branch while the
first agent was mid-edit on the same files. Two writers on one WP on one branch is a governance
failure caused by an omission in the dispatch, not by either agent's bad faith — and notably, both
agents independently refused to stand down on each other's say-so and escalated to the orchestrator
instead, which is the correct instinct. Future WP dispatches in this family should state explicitly
whether sub-delegation is permitted, and for what.

## 2026-09-22 — orchestrator error: concurrent lenses in one checkout produced a false failure in another lens's evidence

`~/.hermes/skills/sk/references/review-overlay.md` §Concurrency states plainly that sessions which
mutate the tree for empirical falsification "still run **isolated or serialized, never concurrent in
a shared checkout**, restore what they touched, and confirm `git status --porcelain -uno` is empty
before finishing."

The orchestrator dispatched all three pre-merge lenses (`boundary`, `contract`, `tests`)
**concurrently into one shared checkout**, and explicitly instructed the `tests` lens to perform
mutation drills — reverting `.github/workflows/ci-nightly.yml`, perturbing
`.github/ci-shard-timings.json`, and editing the new test's allowlist. That is the exact
configuration the overlay forbids.

It produced a real false signal. The `contract` lens's **first** execution of
`test_charter_is_not_allowlisted_and_agrees` failed with `committed=6155 collected=6156` — which is
the `tests` lens's mutation (one duration entry popped, 6156→6155) caught mid-flight. It did not
reproduce across three reruns. The `boundary` lens separately observed a synthetic
`"zzz_mutation_test"` entry in `_MISMATCH_ALLOWLIST` that it had not made.

**Nothing bad landed**, but only because both affected lenses were careful: the `contract` lens
re-ran, judged it environment noise, and *reported it rather than silently discarding it*; the
`boundary` lens noted the foreign edit rather than reviewing around it. Had either simply trusted
its first observation, this squad would have filed a fabricated severity-high finding against a
correct artifact — on a mission whose entire subject is evidence that cannot be trusted.

Two orchestration lessons, both the orchestrator's to own:
1. **Serialize any lens that mutates the tree**, or give it its own worktree. Concurrency is free
   only for read-only lenses.
2. **A dispatch that does not say whether sub-delegation is permitted will get sub-delegation.**
   Earlier in this same phase two agents wrote WP07 on one branch for the same reason (see the
   two-writer entry above). Both incidents trace to omissions in the dispatch, not to agent
   misbehaviour — and in both cases the agents' own caution is what prevented damage.
