# Operator ruling — plan phase HALT

**Mission**: `reconcile-flake-family-01M34HR7` (epic #4882)
**Phase**: plan
**HALT raised at**: commit `f53b298fa`, findings in `reviews/plan-fresh-2.yaml`
**Ruled**: 2026-09-22
**Ruled by**: operator, relayed by the mission orchestrator

## Ruling

**Both surviving findings are ACCEPTED. Fix both, then verify and resume to the tasks phase.**

### PLAN-FRESH2-001 (severity 4) — ACCEPTED

The finding is upheld. The orchestrator independently verified all three of its factual
claims against the checkout before escalating:

- `scripts/ci/fleet_verdict.py:142` reads `token = os.environ["GH_TOKEN"]` — a bare
  subscript, so an absent variable raises `KeyError` rather than degrading.
- `.github/workflows/ci-aggregate.yml:107-112` and `:146-150` — the two `run:` steps
  `plan.md` cites as the pattern to copy — both declare
  `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` alongside the three `SOURCE_*` variables.
- `plan.md:480-493` enumerates only `SOURCE_RUN_ID` / `SOURCE_RUN_ATTEMPT` /
  `SOURCE_REPOSITORY`, and states the new step "cannot inherit them from anywhere else in
  the job" — phrasing that presents the list as exhaustive.

The aggravating factor is that the plan does not merely omit `GH_TOKEN`; its
"cannot inherit" sentence actively misleads. An implementer following it literally produces
a step that raises `KeyError` on its first API call and fails the `collect` job on every PR
— worse than the flake being fixed — and NFR-003's mocked unit tests cannot catch it,
because they never exercise a real workflow `env:` block.

**Remediation required**: add `GH_TOKEN` to the enumerated `env:` list and state explicitly
that it is required by the reused `GitHub`/`GitHubCLI` client.

### PLAN-FRESH2-002 (severity 2) — ACCEPTED

Upheld as written. Add a sixth item to the "Deviations, Blockers, and Judgment Calls for
Reviewers" section summarising the round-2 WP4 re-scoping and its C-011 exemption rationale,
so a reviewer reading only that summary is not misled about what was decided.

## Constraints on the fix round

1. Both are **plan-prose corrections**. Neither changes the architecture, the retry seam,
   the gate set, or the work-package split. A fix that alters design is out of scope and is
   itself a finding.
2. **Fresh subagents only.** The fixer must not be the author, and the verifier must not be
   the fixer. Independence is the property under protection.
3. Do **not** reopen the two binding operator decisions in `spec.md`
   (`## Clarifications / Decision Record`): epic scope, and unit-tests-plus-post-merge-watch
   verification. Those are settled.
4. Verify against the artifact, not against this ruling — confirm the corrected text matches
   what `ci-aggregate.yml` actually declares.
