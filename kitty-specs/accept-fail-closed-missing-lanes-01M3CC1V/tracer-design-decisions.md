# Tracer: Design Decisions

Mission: `accept-fail-closed-missing-lanes-01M3CC1V` — fix P0 #4891.

## DD-1: Fail closed by mirroring the corrupt-lanes branch (not by raising)

`collect_feature_summary` returns an `AcceptanceSummary`; the lane-gate helpers *record
diagnostics*, they do not raise. The existing `CorruptLanesError` arm already models the exact
shape we want: append to `activity_issues` (flips `.ok`), record a `blocked_checks` diagnostic, and
skip the downstream matrix checks. We mirror that arm for the genuine-absence case rather than
raising `MissingLanesError` up through the summary path — raising would break the summary contract
its two callers (`accept`, `orchestrator_api`) depend on. We DO reuse `MissingLanesError`'s
remediation *wording* so the operator guidance is single-sourced.

**Why `activity_issues` and not just `skipped_checks`:** `AcceptanceSummary.ok`
(`acceptance/__init__.py:437-448`) consults `activity_issues` but **never** `skipped_checks` /
`blocked_checks`. Recording only skipped/blocked would leave `ok=True` — the bug would persist.
The `activity_issue` is load-bearing.

## DD-2: REJECTED — making the lanes read coord-aware

The root-cause grounding lens recommended making `_resolve_lanes_manifest_or_stop` coord-aware
(mirroring the closed #3439 fix), on the theory that a coord mission's `lanes.json` lives on the
coord surface and the primary read spuriously sees it absent.

**Rejected — contradicted by the canonical partition authority.**
`src/mission_runtime/artifacts.py:158-186` classifies `LANE_STATE` (`lanes.json`) as a
**PRIMARY-partition** artifact ("travels with tasks.md → PRIMARY", read+write symmetric for every
topology). `ACCEPTANCE_MATRIX` is COORD; `lanes.json` is not. Reading `lanes.json` off the primary
`read_feature_dir` is therefore correct for all topologies, and an absent-on-primary manifest is
*genuinely absent*. This is exactly the distinction the #4891 author drew from #3439 ("here accept
reads the correct surface and the file is absent"). A coord-aware read would introduce a partition
confusion and a second authority — a regression, not a fix. The Ivan-Melck reachability path
(3.2.0-era coord mission upgraded) is a *legacy* shape where the 3.2.0 coord copy is residue and
the primary copy is genuinely absent; the correct 4.0 behaviour is to fail closed and point at
`finalize-tasks` (which writes it to primary) — precisely the recovery Ivan documented.

## DD-3: Scope = `accept` only; `merge` untouched

The root-cause lens confirmed `merge` does not independently re-verify the acceptance matrix
(`policy/merge_gates.py`, `merge/executor.py`) — so `accept` is the single chokepoint and fixing
it closes the release risk. `merge`'s `--skip-lanes` / `--no-lanes` is a deliberate operator opt-in
(T021/FR-012), not a silent bypass, and is left alone. Optional defense-in-depth — `merge`
independently asserting mission acceptance state before landing — is genuine future architecture,
noted in the PR body, **not** implemented here and **not** ticketed (per close-out guidance:
prefer folding; note future architecture in the PR body).

## DD-4: No legitimate absent-lanes shape on 4.0 → fail-closed is safe

`is_planning_artifact_only` requires lanes present; every finalized mission writes `lanes.json`;
implement/review/merge/move-task already fail closed via `MissingLanesError`;
`is_execution_wedged` treats "execution begun + lanes absent" as a repair-only state. Failing
closed in `accept` breaks no legitimate mission.
