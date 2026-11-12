# Research: Coordination closeout leftovers

Full grounding: `research/code-grounding.md` (§7 supersedes earlier proposals); fold discovery:
`research/foldable-issues.md`. Decisions are recorded under `decisions/`.

## D1 — #7491 resume late-window base
- **Decision**: persist `coord_tip_after_projection` at reconciliation PASS; on resume use it only when `landing_verified_for_resume` holds and it is an ancestor of the live coordination tip.
- **Rationale**: reproduced root cause is a resume window spanning the whole merge; the persisted tip is sound only once the landing was verified (challenger).
- **Alternatives**: narrow only the primary-artifact disposition (rejected by operator); attribute window paths to lane merges (more code, new attribution rule).

## D2 — #4041 reclaim surface
- **Decision**: `spec-kitty archive reclaim <mission>` (operator ruling).
- **Rationale**: scoped to archived Missions; reuses the teardown seam, the guarded branch delete and the marker primitive; keeps `_archive.py` record-only.
- **Alternatives**: extending `mission close`, `doctor workspaces --reclaim-archived`, automatic release in `archive create`.

## D3 — #5867 / #7600 text
- **Decision**: new code for the squash projection refusal with per-path reasons; neutral dirty-checkout error text, remedies appended by each caller.
- **Rationale**: the bare text drops the evidence and prescribes a command the caller may not be running.

## Supply-chain
No dependency is added, upgraded or removed; DIRECTIVE_051 controls not applicable.

## Adversarial evidence
Planning point-cut squad: three grounding agents + one fresh-context challenger (2026-11-12). Contested findings and dispositions:
| Finding | Disposition |
|---|---|
| Persisted tip unsound without verified landing | Adopted (FR-003) |
| Squash refusal does roll back (stale comment) | Adopted (FR-014 fold) |
| Flat lanes also get "No merge needed" | Adopted (FR-010) |
| Dirty-checkout text leaks into ~30 modules | Adopted (FR-012) |
| No-intent branch delete refuses after squash | Adopted (ruled intent caller; risk R1 on absorption) |
