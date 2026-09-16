# Quickstart: verifying Stage 1 on the merged main tip

Stage 1 is a **main-tip behavior**. The change alters the very lane that would validate the PR carrying it, so it is only fully proven on `main` **after** the operator merges the PR ("a gate never run is not a gate"). This runbook is the acceptance test.

## Pre-merge (on the PR head — necessary but NOT sufficient)

```bash
# 1. Golden-YAML + dedup pins (the ci module shard)
PWHEADLESS=1 .venv/bin/python -m pytest tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py \
  tests/architectural/test_dual_mode_contract.py -q

# 2. Manual workflow lint (no CI gate exists for these) — PASTE THE RAW OUTPUT IN THE PR
actionlint .github/workflows/ci-router.yml .github/workflows/ci-fleet-verdict.yml
shellcheck $(…any changed inline shell…)   # both must report 0 findings

# 3. Never-green + aggregate guard untouched
PWHEADLESS=1 .venv/bin/python -m pytest tests/ci/test_reconcile_shards.py -q

# 4. Diff-scope check (NFR-001 file-scope, Renata) — must be EMPTY
git diff --name-only upstream/main...HEAD | grep -E 'ci-aggregate|reconcile_shards|aggregate_source' || echo "OK: no aggregate/source-eligibility files touched"
```

Record the passed/failed counts in the PR body, and **paste the raw `actionlint`/`shellcheck` invocation + full output** (not a bare "0 findings" — an anti-laziness self-report is not evidence).

## Post-merge (on the merged `main` tip — the real gate)

Run these against upstream after the operator merges. Use `/attempts/` (plural) for any jobs-API call.

```bash
# SC-001 — one coalesced fleet verdict per landed tip (was ~60)
gh run list --repo spec-kitty/spec-kitty --workflow "CI Fleet Verdict" --branch main -L 60 \
  --json headSha,status,conclusion,createdAt | \
  jq 'group_by(.headSha) | map({sha: .[0].headSha, runs: length})'
# EXPECT: each landed SHA shows a small, bounded count (≈1 coalesced), not dozens.
#   (Fix round 1: CI-Aggregate-triggered runs are singleton-scoped on the aggregate
#   run id — NOT coalesced into the tip group — because their head_sha is the current
#   main tip, not the subject they verified; each active PR's aggregate completion adds
#   one run to the tip it landed on. "Bounded, not dozens" is the criterion, and no
#   run's cancellation may be attributable to another subject's trigger.)

# SC-002 — no main tip landed without a terminal evaluation during a burst
gh run list --repo spec-kitty/spec-kitty --workflow "CI Router" --branch main -L 30 \
  --json headSha,status,conclusion | \
  jq 'map(select(.conclusion=="cancelled"))'
# EXPECT: [] for cancels caused by a superseding main push (per-SHA groups don't cancel siblings).

# SC-003 — #4208 router-gate correct under the new distribution
#   Inspect a landed tip's router-gate job conclusion; a legitimately cancelled dependency
#   still blocks, and no tip is falsely blocked by an external-cancel that 1a removed.
gh run view <run-id> --repo spec-kitty/spec-kitty --json jobs | jq '.jobs[] | {name, conclusion}'

# SC-006 — every landed main SHA carries a TERMINAL verdict (detects the survivor-no-successor wedge)
#   For each landed main SHA, confirm a terminal fleet verdict exists and is NOT stranded on running.
#   (main-push path posts to the from:ci incident issue / commit; inspect the ledger per SHA.)
gh api repos/spec-kitty/spec-kitty/commits/<sha>/comments --jq '.[].body' | grep -E '^\[ci\] (green|red) @'
#   EXPECT a match per landed SHA; a bare '[ci] running @<sha>' with no later terminal line is the
#   residual wedge (report it; the running-sweep self-heal lands in Stage 3 / ADR 4b).
```

## Acceptance ledger (fill on the merged tip)

| Criterion | Command | Expected | Observed |
|---|---|---|---|
| SC-001 coalesced verdict/tip | `gh run list … CI Fleet Verdict` | ≈1 per SHA (was ~60) | _to fill on merge_ |
| SC-002 no unevaluated landing | `gh run list … CI Router` | 0 superseding-push cancels | _to fill on merge_ |
| SC-003 #4208 classifier correct | `gh run view … jobs` | correct pass/block | _to fill on merge_ |
| SC-004 lint clean | `actionlint`/`shellcheck` (raw output in PR) | 0 findings | _pre-merge_ |
| SC-005 pins green | `pytest tests/ci …` | all green | _pre-merge_ |
| SC-006 terminal verdict/tip | `gh api …/commits/<sha>/comments` | `[ci] green\|red @sha`, never stranded `running` | _to fill on merge_ |

A main tip reported green on unproven content, or a permanently-wedged main verdict, is a **violation** of this ADR and of ADR `2026-07-17-1` — treat it as a finding, not a licence to improvise.

## If a stage-1 defect is found on main

Do not hot-patch around it. Open a finding against ADR `2026-09-15-1`, and (per the staged rollout) **do not start Stage 2** (`ci-aggregate-source-eligibility`) until Stage 1 is verified green on the merged main tip.
