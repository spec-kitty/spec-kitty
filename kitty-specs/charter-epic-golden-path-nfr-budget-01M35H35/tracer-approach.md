# Tracer: Approach

## Scoping method

This spec was authored from a fully-gathered readiness package rather than fresh
investigation — the dispatch supplied the readiness report, measured-results log, and
raw pytest log, plus verbatim operator decisions on scope, lever selection, and
constraints. The job was to ground those decisions in the spec template's structure
(FR/NFR/Constraint tables, User Scenarios, Success Criteria), not to re-litigate them.

Concretely:

1. Read `.kittify/charter/charter.md` first (binding), then `AGENTS.md` and
   `CONTRIBUTING.md`, to pick up the ATDD-first (C-011) discipline, the
   `§Pre-existing Failure Reporting Rule`, the `§Performance` <2s CLI standard, and the
   `§Agent Push Authorization` branch-naming clause — all of which the dispatch had
   already flagged as relevant but left me to apply correctly in spec language.
2. Read both GitHub issues (#4213, #4211) with every comment, plus #4409 and PR #4417,
   to get the actual investigation trail in the investigators' own words rather than
   relying solely on the readiness report's paraphrase. This surfaced the exact
   mechanism of the "hang" misdiagnosis (pytest-timeout kills wherever the run
   currently is inside a `run_cli` subprocess call; the reported site moved between
   runs — `_run_charter_flow:488` then `_scaffold_minimal_mission:589` — which a real
   block would not do) directly from robertDouglass's #4213 comment, so the spec could
   cite it precisely instead of summarizing.
3. Read the readiness report, measured-results.md, and golden_path_run.log in full,
   and cross-checked the measured numbers (127.55s total, 73.58s call + 29.36s setup)
   against both files — they agree exactly, so both are cited in the spec as
   corroborating sources rather than picking one.
4. Read the actual test file (`tests/e2e/test_charter_epic_golden_path.py`) and fixture
   (`tests/e2e/conftest.py`) to get exact line numbers for the skip decorator and the
   fixture. Correction (post-review, R4): my first pass here mis-stated the skip
   decorator's range as "797-806", overriding the dispatch's correct approximate
   "797-805" with a wrong "correction" of my own — the decorator opens at line 797 and
   its closing paren is at line 805; line 806 is `@pytest.mark.timeout(120)` (the NFR-007
   enforcement marker, which C-001/NFR-001 forbid touching) and line 807 is the `def`.
   The dispatch's "~797-805" was right; C-004 now cites 797-805 for the decorator only,
   with an explicit caveat that line 806 must remain untouched (see the confirmed
   adversarial finding SPEC-VERIFY-001, which caught this before it reached an
   implementer). The fixture range (390-452, confirmed via grep that `fresh_e2e_project`
   has exactly one consumer) was correct as originally read.
5. Read PR #4417's own description for the "Deferred" section, which precisely quotes
   the lever-C target ("Making the command modules lazy would shave more, but it is a
   structural change... it deserves its own measurement rather than riding along
   here") and the guard pattern #4409 already established (structural check in the
   fast tier + wall-clock check in the nightly `performance` lane) — this became the
   concrete precedent cited in FR-005/SC-002 for how to build the lever-C regression
   guard without violating the charter's caution against flaky wall-clock assertions
   in fast unit tiers.

## Evidence leaned on

- Primary: the readiness report's own measured numbers (not re-run by me — the
  dispatch explicitly said not to re-derive what was already measured).
- Primary: the issues' comment threads, read verbatim via `gh issue view --json
  ...,comments`, not summarized secondhand.
- Primary: direct file reads of the test and fixture to ground line numbers and the
  fixture's single-consumer claim rather than trusting the readiness report's
  paraphrase uncritically (it turned out accurate, but I verified rather than assumed).
- Secondary: PR #4417's description, for the lever-C precedent pattern and its own
  "Deferred" scoping language, which this spec's FR-003/FR-005 build directly on.

## What I did not do

- Did not re-run the golden-path test myself (the dispatch said the measured numbers
  were already gathered; re-running would duplicate work and risk drifting from the
  cited evidence).
- Did not open, comment on, or otherwise touch GitHub (read-only per the dispatch).
- Did not run `spec-kitty spec-commit` (explicitly reserved for the orchestrator after
  adversarial review).

## 2026-09-23 — Plan phase scoping method

This entry is the plan-authoring pass (author-only; no self-review of this plan, per the
dispatch's explicit rule). Confirmed HEAD at `7024671b7` on
`issue-4213-golden-path-nfr-budget` and a clean working tree before any edit, matching the
dispatch's ground-truth requirement exactly (it did not match by accident — I ran `git log
--oneline -1` and `git status --porcelain` as the first two commands of this pass, before
reading anything else).

Concretely:

1. Read the binding inputs in the order the dispatch specified: `.kittify/charter/charter.md`
   first, then `AGENTS.md`/`CONTRIBUTING.md`, then this mission's own `spec.md` and
   `reviews/spec.ruling.md` (all five operator rulings), then both existing tracer files.
2. Read the actual fixture (`tests/e2e/conftest.py:390-452`) and the actual skip-decorator/
   timeout region (`tests/e2e/test_charter_epic_golden_path.py:797-807`) directly, confirming
   the exact line ranges spec.md and the dispatch both cite are still accurate against this
   checkout's current state (they were).
3. Read the CLI startup seam (`src/specify_cli/__init__.py`, `src/specify_cli/cli/commands/
   __init__.py`, `src/specify_cli/cli/commands/init.py`) and the `#4409`/`#4417` precedent
   (`tests/performance/test_cli_startup_budget_4409.py`) in full, per the dispatch's ground
   truth section.
4. Read every `.github/workflows/*.yml` file the dispatch named (`ci-router.yml`,
   `ci-aggregate.yml`, `module-tests.yml`/`ci-modules.yml`, `ci-nightly.yml`,
   `ci-quality.yml`, `packs.yml`) directly rather than trusting the CLAUDE.md/spec.md
   summaries of them, to verify current line numbers, current gate thresholds
   (`--fail-under=90`, confirmed), and which gates are always-on vs. filter-group-gated vs.
   effectively non-blocking (`|| true` on `markdownlint`/`commit-msg`).
5. Rather than choosing Lever A/Lever C mechanisms from code-reading alone, ran a hands-on
   timing/profiling investigation of `spec-kitty init` in an isolated environment (matching
   `run_cli_subprocess`'s own env-var contract, `HOME` overridden to a scratch directory) —
   see `tracer-design-decisions.md`'s "Plan phase: Lever A/Lever C mechanism choice" entry for
   the full reasoning and findings. This is the one place this pass went beyond reading and
   into direct investigation, and I judged it necessary given how binary Ruling 2's ≤110s bar
   is (no partial credit, no self-authorized exception band) — committing to a mechanism
   without checking it targets the actual dominant cost risked a wrong bet the mission
   couldn't afford.
6. Ran `.venv/bin/spec-kitty plan --help` first (per the dispatch's mechanics section),
   confirmed the option set matched what the orchestrator had already verified, then ran
   `.venv/bin/spec-kitty plan --mission charter-epic-golden-path-nfr-budget-01M35H35 --json`
   — non-interactive, no prompt, `scaffold_only: true`. The scaffolded `plan.md` used a stale
   template (see `tracer-tooling-friction.md`); I discarded its content and wrote `plan.md`
   against the canonical `packs/built-in/missions/software-dev/templates/plan-template.md`
   structure instead, per CLAUDE.md's "Use Canonical Sources, Never Improvise" rule.
7. Wrote `research.md` and `data-model.md` (the plan-template's own Phase 0/Phase 1 outputs)
   populated with the CI-gate verification and profiling findings; skipped `quickstart.md`
   and `contracts/` with an explicit rationale in `plan.md`, since this mission ships no new
   public contract or operator-facing workflow for either to meaningfully document.

## What I did not do (plan phase)

- Did not implement any of the mechanisms described in `plan.md` — this is a planning pass
  only, no `src/` or `tests/` file (other than this mission's own `kitty-specs/` documents)
  was edited.
- Did not run the full golden-path test (`test_charter_epic_golden_path`) or any part of the
  `tests/e2e/` suite — the dispatch's own baseline/blast-radius instructions are written for
  the implementing pass, and this planning pass's one hands-on investigation was scoped
  narrowly to timing `spec-kitty init` in isolation, not to running the test suite.
- Did not review this plan myself, and did not run the adversarial squad — both are
  explicitly out of scope for the author role, per the dispatch.
- Did not touch `reviews/`, `meta.json`, or hand-edit `status.events.jsonl` (the one change to
  that file is the `spec-kitty plan` command's own lifecycle-event side effect, left as the
  tool produced it).

## 2026-09-23 — WP08 closing pass: how the implementation phase went relative to the plan

**Important scope note first**: everything below is measured in a throwaway integration
worktree I built from the current WP08 workspace branch (`issue-4213-golden-path-nfr-budget`,
shared "lane-planning" workspace). Building that worktree surfaced a real deviation from the
orchestrator's own dispatch premise, recorded in `tracer-tooling-friction.md` — the short
version: this branch already has all six code lanes merged into it via spec-kitty's own
dependency-lane mechanism, so no manual diff re-application was actually needed or possible.

**Lever C (freshness pre-check, primary) — delivered, evidence from CI.** Comparing the two
orchestrator CI runs cited in this mission's own evidence (readiness signal only, not the
NFR-002/SC-003 closure measurement, which is the orchestrator's PR-stage job):
- Run 35853033595 (un-skip only, no levers): 51.31s setup + 69.99s call = 121.30s → TIMEOUT.
- Run 35872503133 (all levers WP02–WP07): 52.78s setup + 49.78s call = 102.56s → PASS (≤110s).

The **call** phase dropped 69.99s → 49.78s (-20.21s, ~29%) between those two runs — the
freshness pre-check's own target, since most of the golden path's 12 subprocess calls go
through `assess_global_agent_commands()`. This is consistent with the plan's own attribution
of ~55-65% of a bare invocation's cost to that one code path. The lazy-import trim (secondary,
~0.2s/call × ~10 calls ≈ 2s estimated) is not separable from the freshness-check's contribution
in these two runs (both landed together in run 35872503133), but the combined call-phase drop
is well beyond what the lazy-import trim alone could produce, so the freshness check reads as
the dominant contributor, matching the plan's own framing.

**Lever A (fixture redesign) — did NOT deliver the setup-phase savings the plan estimated, and
this is the plan's own risk materializing, not a WP03 defect.** The **setup** phase did *not*
drop between the two CI runs (51.31s → 52.78s, essentially flat, if anything very slightly up).
Plan.md's own Lever A section predicted this could happen: it explicitly said the (a)
freshness-inherited savings on `fresh_e2e_project`'s own `spec-kitty init` call were "untested
until the real measurement," and this mission's own known-facts record (see WP08 dispatch)
independently names the reason — **CI setup cost is dominated by the session-scoped `test_venv`
fixture's one-time `pip install -e`, which no lever in this mission addresses.** Lever A's part
(b) (git-config batching, cutting 2 of 5 fixture subprocess spawns) was explicitly estimated at
"well under 1 second," so its absence from a ~1.5s *increase* in setup between the two runs is
expected noise, not a missing win. Net: the mission still cleared the bar (121.30s → 102.56s
total, -18.74s) entirely on the strength of lever C's call-phase savings; lever A's own
contribution is real (per-call `spec-kitty init` cost inside the call/setup split is smaller
than it would be without the freshness fix, since the fixture's `init` call shares that same
code path) but is not visible as an isolated setup-phase reduction in these two runs, because
the dominant setup cost is a class of cost (`test_venv` install) neither lever touches.

**Local re-run (T026, this WP, in the throwaway integration worktree)**: 3 consecutive runs of
`test_charter_epic_golden_path` alone, PYTHONPATH pointed at the integration worktree's `src/`,
main checkout's `.venv/bin/python`, real `@pytest.mark.timeout(120)` active:
- Run 1: 28.70s setup + 20.24s call = 48.94s (pytest wall 74.82s, cold).
- Run 2: 14.88s setup + 20.14s call = 35.02s (pytest wall 35.78s, warm).
- Run 3: 14.87s setup + 20.84s call = 35.71s (pytest wall 35.88s, warm).

All three pass comfortably inside the 120s local budget. **This local number is NOT the
NFR-002/SC-003 closure evidence** — it is explicitly caveated per the WP file's own
instruction. No local "before" number exists to compare against (WP01's baseline confirms the
golden path was `SKIPPED`, not measured, at the merge-base — 0 real local timing samples exist
before this mission's levers landed), so the only real before/after comparison available is the
two CI runs above.

**Risk flag for the orchestrator (T029)**: the known PASS run (102.56s) clears the hard ≤110s
Actions bar by only **7.44s of margin**. Given (a) that margin sits inside the ~12-32s
local-to-CI gap NFR-002's own rationale cites as the kind of variance a different runner/day can
produce, and (b) that ~53s of the 102.56s total is setup cost dominated by the untouched
`test_venv` one-time install (a cost this mission's levers do not reduce and that could plausibly
vary run to run on a shared Actions runner), the real PR-stage Actions measurement (the actual
NFR-002/SC-003 closure evidence, not this WP's own output) should not be assumed to reproduce
102.56s exactly — it could land closer to or even past the 110-120s STOP band plan.md's own
"Actions evidence path" section names. This is not a finding that blocks this WP (T026/T027 both
pass locally with no new regressions — see `tracer-tooling-friction.md` and this mission's own
review artifacts for the full failure classification), but it is exactly the kind of
uncomfortable-margin signal T029 instructs this WP to surface rather than imply confidence the
local number does not support.
