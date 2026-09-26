# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->

> **Honesty note:** these tracer files were seeded late, at closeout (2026-09-26), rather than at mission start. The entries were reconstructed from the session record and carry the time each event occurred. This is the procedure's "retroactive fill-in" anti-pattern, recorded here as the first friction item.

- 2026-09-26 — FR-009: the fresh-state clear on a pre-mutation exit was generalised from #4764, instead of writing the reconciliation marker at state creation. This keeps a single FR-012 stamp site, and a stopped run leaves no resume-looking state (research R-3).
- 2026-09-26 — FR-008: the refusal wording is single-sourced in `executor.py` (`render_coord_read_refusal`); the JSON error adds `error_code` and `remediation` to the existing dry-run error shape.
- 2026-09-26 — Reconciliation stubs are allowed only in tests whose subject is not the gate (26be43c804 precedent). Where the gate is the subject (C2), the fixture was corrected (`mission_id=None`) instead.
- 2026-09-26 — T020: the scaling check uses 1000 closes, because at 100 the one-time 10k-row closure read dominates the ratio (~4.4) on correct code. At 1000 the measured ratio is ~1.4, against the bound of 3.
- 2026-09-26 — The Guard4 residual (`resolve_feature_dir_for_mission` silently returns PRIMARY on an unmaterialized coord) is pinned as current behaviour, not fixed. It belongs to epic #5002.
- 2026-09-26 — Follow-ups: #5108 (lane-branch naming authority), #4516 (doctrine graph re-parse / lazy registry, which the sweep gate exposed), #5002 (Guard4 residual), #5100 (single_branch lane allocation).
