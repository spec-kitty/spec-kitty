# Design decisions

| Decision | Rationale | Source |
|----------|-----------|--------|
| Docs WPs are normalised to `code_change` in lane topologies | Operator ruling; removes the planning-lane evidence class (#6851, #7759, #7809) instead of teaching every reader two branches | DM 01M8128ARWKN0AK2MVPDT4VE0C, 01M8128YH3KY94DPK85T0YQGXM |
| Mixed planning WP refused with a split remedy | kitty-specs files never travel on a lane branch; reuses the existing ownership refusal | DM 01M81293NR57KQENPSHCKQ65FF |
| Docs WPs count in settlement | Operator override of my "don't count" recommendation; settlement and lane computation agree | DM 01M81298MS97SQBQZ2612VFH3Z |
| Dual stamp (`lane_head_presync`) | Option A (refuse unpushed) would refuse almost every remote review; the bound drops merges, so stamping before the sync merge stays sound | DM 01M8128MH9KQHB5SJK4Z0MMSF5, architect squad |
| Remote-only lane created in `_reconcile_review_lane` via a kernel helper | One owning-remote rule for the coordination branch, lane and base lookup; keeps `lifecycle_sync` fail-closed and inside the destroyed-lane guard | DM 01M8128SDVVPS8X575JY9CGVFX, architect squad |
| Hex filter at `_matched_issue_number`, declaration form only | `issue_numbers_in_text` shares that filter; a keyword-anywhere filter would drop real 4-digit refs | researcher squad |
| Post-tasks squad skipped | The research-phase squad already covered architecture and evidence; the WPs map 1:1 to the reviewed design. Advisory per Standing Order #1 | orchestrator |
| #7808 / WP01 moved out | Operator ruling R68 (squad session, confirmed by dispatcher): one Slice 5 Mission owns #7808 + #5297 + #5516; WP01 was canceled before any work was committed | dispatcher 2026-11-22 |
