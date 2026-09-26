# Operator ruling — spec phase HALT (round 2)

Date: 2026-09-23. Recorded by the orchestrator from the operator's answers. These rulings
REPLACE the original acceptance bar for the findings named below.

## Ruling 1 — skip-regression gate (SPEC-FRESH-002, SPEC-FRESH2-001, SPEC-FRESH2-002)

Question put: keep FR-006/SC-006 (a new CI gate blocking re-application of
`@pytest.mark.skip`/`xfail` to budget-guarded tests) in this PR?

Operator answer: **Cut it.** Remove FR-006/SC-006. The "never silently re-skip or
re-quarantine" rule stays as prose in the spec (C-005). The active 120s timeout is what makes a
budget miss loud. The PR stays a test + CLI-startup change.

Acceptance bar for these findings: resolved when FR-006/SC-006 and their authorization note
are gone, and nothing else in the spec depends on them.

## Ruling 2 — closure margin (SPEC-FRESH2-003, SPEC-FRESH2-004)

Question put: what GitHub Actions number closes #4213/#4211?

Operator answer: **Hard ≤110s on Actions.** The mission is not closed until a real GitHub
Actions e2e run shows the golden path at ≤110s with the 120s timeout active. There is **no
exception band**: a measurement at 110–120s means the mission stops and returns to the
operator. It is not closable by a documented exception.

Acceptance bar for these findings: resolved when NFR-002/SC-003 state the hard ≤110s rule with
no 110–120s exception path, and the three differently named exception patterns are gone (not
just cross-referenced).

## Attribution correction (orchestrator)

The spec's Clarifications section attributes more to the operator than they decided. The
operator's actual decisions are: (1) scope — #4213 canonical, one PR closes #4213 and #4211;
(2) lever — A+C (fixture redesign + residual Typer command-surface trim); (3) Ruling 1;
(4) Ruling 2. The remaining constraints come from the issues' own acceptance text or the
readiness probe: 120s cap not loosened, test stays on its current gate, skip removed, lever B
(in-process substitution) rejected on the issue thread, and CI evidence required. The
Clarifications must attribute each constraint to its real source. The phrase "not just barely
under" is not an operator quote and must not be presented as one.

## Ruling 3 — SPEC-VERIFY-003 (added 2026-09-23, after the round-4 HALT on SPEC-FRESH4-001)

Question put: does Ruling 1 also settle SPEC-VERIFY-003 (round 1's demand for a mechanical,
self-mutation-testable gate enforcing C-005)?

Operator answer: **Yes — Ruling 1 covers it.** SPEC-VERIFY-003 is added to Ruling 1 by name:
C-005 stays prose with no enforcing gate; the active 120s timeout makes a budget breach loud.

Acceptance bar: SPEC-VERIFY-003 and SPEC-FRESH4-001 are resolved when the tracer's disposition
cites this ruling (Ruling 3) as its authority instead of the phase agent's inference.

## Ruling 4 — round-5 HALT (SPEC-FRESH5-001/002/003) and one authorized round past the cap

Recorded 2026-09-23.

**SPEC-FRESH5-001 (sev 4).** Question put: the `tests (e2e)` shard is selected pre-merge only by
pushes touching `tests/e2e/**` or `tests/cross_cutting/**` (`.github/workflows/ci-router.yml`
`e2e` filter). How should the spec handle a CLI-source-only PR never running the golden path?
Operator answer: **Correct the claim only.** The spec must state accurately which pushes select
the e2e shard. It drops the "a regression is caught before merge on any CLI change" premise and
relies on lever C's own startup regression guard (in the CLI's test surface) to catch startup
regressions. No CI or router changes; the mission stays test + CLI-startup only. Acceptance
bar: resolved when no statement in the spec claims the e2e shard runs on CLI-source-only
pushes, the P1 rationale is restated on true premises, and the startup-guard responsibility is
explicit.

**SPEC-FRESH5-002 (sev 3)** and **SPEC-FRESH5-003 (sev 2):** fix as filed, with no operator
decision needed. NFR-002's rationale must say that the cited CI/VM numbers pre-date #4417 and
that the post-#4417 CI gap is unmeasured. The hard ≤110s Actions rule (Ruling 2) is unchanged.
FR-004's stray "Clarifications" cross-reference is corrected.

**Round cap.** The operator authorizes exactly **one** more R4→R5 round past the protocol cap,
to apply this ruling. If that round's verify or fresh sweep leaves any finding of severity ≥3,
the phase HALTs to the operator again. No further self-extension.

## Ruling 5 — round-6 HALT (SPEC-FRESH6-001) and phase close

Recorded 2026-09-23.

**SPEC-FRESH6-001 (sev 3).** Question put: FR-002's example lever (`clone_template`) would hand
`spec-kitty init` a repo with pre-existing history, not the zero-commit repo the test uses
today. Operator answer: **Pin zero-commit.** FR-002 must not name `clone_template` or any other
concrete mechanism as an example; the plan chooses the mechanism. C-006 is made explicit:
whatever the redesigned fixture does, `spec-kitty init` must run against a repository with
**no commits and no `.kittify` content**, as it does today. Acceptance bar: resolved when
FR-002 names no concrete mechanism and C-006 states the zero-commit + no-`.kittify`
precondition explicitly.

**Phase close.** The operator authorizes a closing pass: one fresh fixer, then one fresh
verifier on SPEC-FRESH6-001 only. There is **no fresh sweep** this time, a deliberate operator
decision to end a non-converging loop, since the plan phase's squad reviews the spec again as
reference. If the verifier confirms the finding resolved, commit. If it does not, HALT.
