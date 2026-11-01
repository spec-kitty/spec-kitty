# Discovery: bind the @wip event-traceability acceptance scenario (#6260)

## Decisions

- **D1 — The mission is PR-bound and single-branch.** This is one harness binding on one branch
  (`issue-6260-bind-event-traceability-scenario`); a coordination topology would mint a branch for
  planning artefacts that no user reads. `single_branch` + `--pr-bound` matches the shape the last
  comparable mission used (`write-service-protocol-01M5Z6N5`).
- **D2 — Bind the drafted scenario's exact steps; do not rewrite the Gherkin.** The two scenarios in
  `tests/scenarios/status/event-traceability.feature` are QA's wording. The Mission adds step
  definitions and one positive-control scenario; it does not edit the drafted scenarios' Given /
  When / Then lines.
- **D3 — Arrange reuses the shipped builders.** `MissionLifecycle.planMission` + `advance(...,"approved")`
  already builds a Mission through the CLI and takes a work package to `approved` (with committed
  work, so the #6715 evidence rule is satisfied). No new builder primitive is needed for the
  approved state; only the clock-skewed approval restamp is new.
- **D4 — The clock-skewed approval is planted as a crafted status row, as the issue directs.** The
  production-equivalent shape: a teammate's approval row arrives through `git pull` + the status-log
  union driver with an `at` in the future. The JVM runner cannot monkeypatch `kernel.clock` and the
  CLI reads no clock environment variable, so the only black-box arrangement is to restamp the
  approval row in `status.events.jsonl`. This is a **narrow, documented exception** to ADR
  2026-10-15-1 decision 6 ("builders never write CLI-managed state"); #6260 authorises it explicitly
  and the scenario's maintainer notes record it. The reducer is the object under test, so the row
  must look exactly like a pulled one: no `lamport_clock`, real emitter timestamps elsewhere.
- **D5 — The rejection act is the real CLI.** `spec-kitty agent status emit WP01 --to in_progress`
  (the shipped `approved -> in_progress` rejection path; the pytest guard uses the same seam). The
  scenario asserts the resulting lane, so a CLI that refused the out-of-order rejection fails the
  scenario (it does not silently satisfy it).
- **D6 — Consolidation refusal is read from the CLI's own message.** `consolidate`'s unconditional
  merge-readiness gate prints `Mission is not merge-ready — WP(s) missing review approval: <ids>`
  (`src/specify_cli/consolidation/phase_claim.py::_assert_mission_terminal_ready`). The scenario
  asserts the refusal names `WP01`, not merely a non-zero exit.
- **D7 — The positive control is a same-fixture successful consolidation.** A Mission planned,
  approved and accepted by the same builders, with no rejection and no skew, consolidates and lands
  the work package's file on the target branch. This proves the fixture's approve/accept/consolidate
  path works, so the refusal assertion cannot pass because the fixture was broken.
- **D8 — No `@promise:<id>` is invented.** The tag is assigned by QA from the external promise
  registry (issue body; `tests/scenarios/README.md` "Drafted scenarios"). This Mission removes
  `@wip` without it and records the pending QA assignment on the issue and in the PR.

## Evidence

- `tests/scenarios/status/event-traceability.feature:15-31` is still `@wip` with two unbound
  scenarios on `origin/main` @ `287a226cfe`.
- `acceptance-jvm/src/test/java/kitty/acceptance/environment/MissionLifecycle.java:150-186`
  (`advance`) walks a work package through `planned -> in_progress -> for_review -> in_review ->
  approved` with the real CLI; `:300-360` builds the approved state.
- `acceptance-jvm/src/test/java/kitty/acceptance/steps/ArrangeSteps.java:164-175` already exposes
  the move-to-lane arrangement, and `:80-85` the planned-mission arrangement.
- `acceptance-jvm/src/test/java/kitty/acceptance/steps/ActSteps.java` has only the generic
  `When I run "<command line>"`; `AssertSteps` has no approved/consolidate vocabulary. New steps are
  needed for the promise's own nouns.
- `src/specify_cli/consolidation/phase_claim.py:107-160`: the merge-ready gate and its message.
- `tests/consolidation/test_wall_clock_claim_p0_repro.py` is the existing pytest guard for the same
  #4941 behaviour; it is not changed by this Mission (C-004).
- `acceptance-jvm/build.gradle:120-160`: the per-pass tag filter and the zero-scenario guard; a
  scenario that loses `@wip` joins the `gating` pass (`not @wip and not @manual`).
- `docs/development/testing/acceptance-scenarios.md`: binding + positive control + `@wip` removal
  is the documented engineer follow-up to a QA draft.
- `scripts/ci/scenario_contract.py` reports unbound steps in a non-gating scenario as `info` and in
  a gating one as `error`: `tests/architectural/test_scenario_contract.py::test_real_tree_is_non_empty_and_clean`
  fails the PR if `@wip` comes off before the steps are bound. That is the red-first lever.

## Open questions

- **Q1 (QA)** — the `@promise:<id>` for this behaviour belongs to the promise registry. Not
  resolvable in this repository; recorded as a pending QA assignment rather than invented.
- **Q2 (architecture owner)** — ADR 2026-10-15-1 decision 6 does not name the crafted-pull status row
  among the allowed Arrange writes. #6260 authorises this shape; the ADR text amendment is a
  maintainer call and is left out of this diff.
- **Q3** — whether `agent status emit` refuses the out-of-order rejection outright (an accepted
  remedy in the #4941 pytest guard) instead of recording it. If it refuses, the scenario is red and
  that is a product finding for the owner, not a reason to soften the assertion.
