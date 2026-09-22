# Contract — No Silent Destructive Write

Every WP in this mission must satisfy the shared bar plus its seam-specific clause.

## Shared bar (all WPs)
- A documented operation MUST NOT destroy healthy input while reporting success.
- On a destructive/authoritative rewrite: read the SSOT (or prove the discarded content
  redundant) first; otherwise preserve, warn, or exit non-zero.
- Never report exit-0 / errors-0 for a run that quarantined or dropped canonical content.

## WP01 (#4908) — charter recompile
- GIVEN a project with recorded mission type M, WHEN any recompile path runs
  (`activate` / `deactivate` / `pack apply --compile`), THEN `catalog.mission == M`,
  `catalog.template_set == M-default`, and `catalog.references ⊇ prior ∪ {activated}`.
- The #2940 malformed-`answers.yaml` guard is preserved (no `from_interview=True` flip).

## WP02 (#4897) — mission-state repair
- `is_non_lane_event` and `_is_preserved_non_lane_row` derive from ONE registry (INV-2).
- `doctor mission-state --fix` on a healthy mission with Decision Moments: DecisionPoint row
  count delta == 0; `doctor decisions clean:true`; `agent decision list` count unchanged.
- A repair that quarantines a canonical row does NOT report errors=0/success.
- Already-preserved classes (retrospective/annotation/WPStatusChanged/review_result) unchanged.

## WP03 (#4894) — traces merge driver
- INV-3 holds for every resolved merge.
- Dedup granularity is whole section/block, not line.
- Driver is NOT fail-closed on ordinary repeats (distinct from the verdict-authority rule).
- `_union_acceptance_history` (record-granularity dedup) is left unchanged.
