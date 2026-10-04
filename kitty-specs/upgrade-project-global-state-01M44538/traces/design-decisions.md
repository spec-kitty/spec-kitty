# Design decisions — upgrade-project-global-state-01M44538

- 2026-10-04 — Owner of the "primary-owned bookkeeping" fact is the state contract (`state/contract.py` STATE_SURFACES), not `coordination/coherence.py`: coherence owns "ignorable dirty churn", a different fact (grounding §3).
- 2026-10-04 — Classified set is only fully generated do-not-edit surfaces (`.kittify/metadata.yaml`); operator-editable files (`.gitattributes`, `.gitignore`, `config.yaml`) are covered only by a path-agnostic content-identical overlap rule (#4933/#4978 data-loss precedent). Decision `01M4457XEN4YFYVKVT40HX047P`.
- 2026-10-04 — Upgrade skips integrating worktrees (mission/lane/coordination branches) rather than aligning their contents; alignment can never make per-record `applied_at` identical. Decision `01M4457T2HTWW5XGWA55TWYVNT`.
- 2026-10-04 — Plan: explicit shared resolver at the git-merge sites chosen over a merge driver (git skips drivers on modify/delete); auto-rebase leg in the managed-artifact arm, not RULES (post-specify disposition #5/#10).
- 2026-10-04 — Resolution side is fixed per merge site, not "incoming wins": stage 2 for lane→mission, mission→target and dependency merges (the receiving checkout), stage 3 for auto-rebase (incoming coordination/mission side). Recorded in ADR 2026-10-04-2.
- 2026-10-04 — Content-identical overlaps (mode + object id) are not staleness, for every path; operator-editable files are never auto-resolved by path.
