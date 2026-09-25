# Tracer 01 — Grounding & alignment/scope squad

## Alignment (still real on current main `2864622117`)
- `tests/terminus/test_repro_4997.py` still `xfail(strict)`. Confirmed with `--runxfail`:
  WP01's already-consolidated lane commit is NOT reachable from the target after
  `--resume` (the lane was reverted / never landed).
- Instrumented run of the fixture: `merge --resume --yes` → `rc=1`,
  `MERGE_UNSAFE_PRIMARY_DIRTY` listing `D README.md`, generic LOCAL_CHANGES remedy,
  nothing consolidated, target never advanced.

## Supersession / scope
- **#4982 CLOSED 2026-09-24** (PR `7da1750ebb` "feat(merge): resume honors persisted
  strategy + preserves pre-interrupt lane tips"). That fix's own commit message names
  **"#4997 (staged-deletion/LOCAL_CHANGES behind-HEAD window) remains a tracked xfail
  follow-up."** → #4997 is a DISTINCT, still-open primary-checkout sibling. Not superseded.
- #4982 fixed the *clean-primary* behind-own-HEAD window at the lane-consolidation site.
  #4997 = same window but primary carries staged deletions + the merge-strategy no-op gap.
- Scope: ONE mission, two coupled defects, both inside `src/specify_cli/merge/` +
  `lanes/merge.py`. No other issues fold in.

## Squad verdicts (opus, profile-loaded: architect-alphonso + reviewer-renata)
- **Defect A locus:** `executor.py:3373-3375` `except DestructiveOpRefused` handler
  (advisory-only today via `_report_pre_mutation_refusal`). Must recover + continue on
  resume, not just print.
- **Renata's load-bearing safety hole:** gating auto-`reset --hard HEAD` on lane-ancestry
  ALONE is UNSAFE — ancestry proves the lane is integrated but says nothing about *what*
  is dirty. A genuine coexisting edit / intentional non-mission deletion would be
  destroyed. Recovery MUST be gated on a **phantom-only proof**.
- **Phantom-only proof (sound + testable):** the primary's working tree AND index are
  byte-identical to the persisted `pre_mutation_target_sha` and HEAD is its descendant →
  `reset --hard HEAD` is provably non-destructive. Any deviation → REFUSE. This closes
  Renata's hole AND correctly refuses the current (unfaithful) fixture.
- **Fixture correction is the defensible path; product-loosening is greenwash + data loss**
  (both agents, firm). Current fixture models a genuine LOCAL_CHANGES state.
- **Defect B is real** (alphonso's "already covered" missed that `mission_already_applied`
  gates the whole FR-037 condition and is `False` for the merge no-op). Fix
  `_merge_branch_into` merge branch to report `changed=False` on a no-op.
- **Fail-closed backstop:** reconciliation gate catches a *skipped* lane under merge but is
  BLIND to a *merged-then-content-reverted* lane under merge (reachability unbroken) →
  Defect B's `_branch_trees_equal` adjudication is the real guard; merge-axis blob blind
  spot recorded as a residual (C-002).
