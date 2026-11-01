# Aggregate review — upgrade-seeded-list-hint-01M6BV1A (#6684)

**Verdict: LAND.** Reviewed on the integrated branch `issue-6684-upgrade-seeded-list-hint` before
consolidation. Scope: the whole branch diff against `origin/main` at `287a226cfe`.

This review was performed by the mission's implementation agent (the run is a single sub-agent; no
separate reviewer agent was dispatched, and the PR records that). It is a second, adversarial read of the
integrated diff rather than a restatement of the per-WP reviews.

## What was checked

| # | Check | Result |
|---|-------|--------|
| 1 | The change is report-only: no write, narrow or reset path added anywhere | Pass — the only new code formats a warning string; every test asserts the activation surface is byte-identical (`_bytes`) |
| 2 | The ruling's refused alternative (a reset migration) is absent, and the decision is recorded | Pass — no migration added or re-registered; ADR amendment `2026-11-01 (#6684)` states the refusal and the mechanism |
| 3 | The new provenance cannot shadow the existing one | Pass — one hint per kind, today's in-force branch first |
| 4 | The provenance claim is true for what it matches | Pass — bounded superset `preset ⊆ listed ⊆ preset ∪ selection`, plus `listed ⊆ today's in-force`; guards cover a subset of the preset and an id no longer in force |
| 5 | A hand-picked list is not nagged | Pass — the two-id operator list test and the preset-minus-one test stay silent |
| 6 | Identity space (declared id vs file stem) is consistent | Pass — both sides through `resolver.stems` |
| 7 | The frozen comparand stays single-owner, no second copy | Pass — `DEFAULT_SNAPSHOTS` imported, never duplicated; the existing cutover-snapshot test still guards its shape |
| 8 | Downstream behaviour unchanged (absent key, promotion, deny guard, supersession) | Pass — `tests/upgrade/test_upgrade_keeps_absent_activation_6629.py` and the full migration module green |
| 9 | Docs tell an operator what changes and what to do | Pass — changelog fragment (US spelling, style gate 0 errors), ADR amendment, module docstring |
| 10 | No gate weakened to reach green | Pass with one recorded exception — see "Pre-review gate" below |

## Findings

- **F-1 (fixed).** The helper first returned the matched preset set, which no caller used. It is now a
  bool predicate (`_accounts_for_a_released_preset`), so there is no dead return value.
- **F-2 (fixed).** The new message asserted "the catalogue has grown since". That is not the only reason
  a list can be smaller than today's in-force set (another layer can add artifacts), so it now says "while
  more `<token>`s are in force today".
- **F-3 (added coverage).** A paradigms case pins the per-key rule and the pluralised message for a kind
  other than directives.
- **F-4 (accepted, documented).** A list seeded from a *whole-catalogue* effective set is matched only
  while the catalogue is unchanged; recorded in the ADR as the residual with the condition that makes it
  reachable (not reachable with any released CLI today) and the follow-up shape.
- **F-5 (pre-existing, untouched).** The hint needs an interview selection for that kind to be considered
  at all (candidate filter). A seeded list on a kind the interview never selected stays unreported. This
  is the pre-existing shape of the step, out of this issue's scope, and is named in the PR's Deferred
  section.

## Pre-review gate

`move-task --to for_review` timed out twice at the gate's 300 s budget. The gate runs
`review.test_command` (`make test-fast`), which takes ~6 minutes on an idle host and far longer at this
host's load average (~197). The same scope was run by hand to completion: **2678 passed, 18 failed**, and
every failing family reproduces on pristine `origin/main` in a clean worktree (shared
`/tmp/spec-kitty-pytest-tmp` pollution producing `FileExistsError`/project-root assertions, plus one
240 s pytest-timeout in an architectural scan). The transition therefore used the documented
`--skip-pre-review-gate` flag with the reason recorded in the WP history, and the fleet-known issue is
#6865. No test was skipped, xfailed or weakened.

## Development-assist tests

Five tests were added, all inside the module that owns the behaviour
(`tests/upgrade/migrations/test_m_4_0_0rc8_promote_interview_selections.py`). Verdict for each: **keep,
folded** — they guard the new provenance contract and a standing invariant (no write), not a moment in
this mission's slicing; none is a characterization oracle, a parity gate or a `__module__`/delegate shape
check. No issue-named (`test_issue_*`/`test_repro_*`) file was added, so no fold-or-keep rename applies.

## Cross-WP integration

WP01 (behaviour) and WP02 (decision record) touch disjoint files; the only shared claim is the module
docstring, owned by WP01, so the two cannot conflict. The consolidated tree carries the ADR amendment,
the fragment and the code together, which is what the maintainer reads as one change.
