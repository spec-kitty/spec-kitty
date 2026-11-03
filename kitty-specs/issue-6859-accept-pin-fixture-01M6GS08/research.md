# Research: #4891 accept pin fixture repair (#6859)

Recorded during the governed Mission `issue-6859-accept-pin-fixture-01M6GS08`. The step ran
after implementation and review in this run, so this file also records the decisions the
implementation settled, with the evidence each rests on.

## D1 — The fixture is wrong, not the assertion (fix the subject)

**Decision.** `accept`'s refusal of the fixture is correct product behaviour; the standing pin's
*fixture* predates three gates and is what changes. No assertion, marker or production line is
touched.

**Evidence.** `src/specify_cli/consolidation/wp_evidence.py` (:func:`_scan_lane`, :func:`_judge`,
:func:`has_owned_change`, :func:`_owned_patterns_by_wp`) and
`src/specify_cli/consolidation/preflight.py` (:func:`_independent_reviewer_confirmed`) implement
#6715/#5939 fail-closed landing evidence. Reproduced on a pristine `origin/main` clone before any
change: `1 failed, 1 passed`, the positive control failing on
`assert result.exit_code == 0` with `IMPLEMENTATION_UNREADABLE` (the lane branch
`kitty/mission-…-lane-a` never existed).

## D2 — All three axes must be satisfied by the fixture, not just the first one reported

**Decision.** The builder states authored `owned_files`, an implementation commit on WP01's lane
branch, and an approval by an identity distinct from the implementer.

**Evidence.** Measured, one part removed at a time on the final structure:
- no lane implementation commit → `IMPLEMENTATION_UNREADABLE`;
- no `owned_files` in the WP frontmatter → `IMPLEMENTATION_MISSING`;
- approving as the implementer → `REVIEW_NOT_INDEPENDENT`.
Each is load-bearing, so a fixture that satisfies only the first would have been red at the next
gate.

## D3 — One builder for both controls (the same-fixture positive control)

**Decision.** `_build_accept_ready_mission(tmp_path)` builds everything both controls need; only
the positive control adds `lanes.json` and the acceptance matrix. The lane implementation commit
is cut in the builder, using the canonical `tests/lane_test_utils.commit_lane_implementation`
(write the manifest → cut the lane → remove the manifest), because a real Mission cuts its lanes
from the planning commit the manifest records.

**Evidence.** After the change the negative control's blocked checks are exactly
`['lanes_manifest']`, measured with an instrumented run. That is the strongest available proof
that the positive control differs in one thing only.

## D4 — Do not touch the shared `_create_test_feature` helper

**Decision.** Call it with `omit_status_events=True` and seed the lifecycle locally.

**Evidence.** `git grep -n "_create_test_feature" tests/` finds ~35 call sites across four test
modules; editing it would move every one of their fixtures.

## Open questions

None for this Mission. Two out-of-scope observations are recorded in the PR's `## Deferred`:
the pre-existing `_create_test_feature` name is a `feature*` alias the Terminology Canon
discourages (renaming ~35 call sites is a separate mission), and `mypy` on the pin reports two
pre-existing errors (one in `tests/lane_test_utils.py:96`, one in the pin's untouched
`_run_accept` return annotation).
