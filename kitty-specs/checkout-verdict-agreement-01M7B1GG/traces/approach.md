# Approach

1. Reproduce live through the real CLI (`research.md` table), then commit a red
   integration test through the real `agent mission` commands on real default Missions.
2. One helper, `resolve_planning_checkout_verdict`, takes the expected checkout from
   `placement_seam(...).write_target(PRIMARY_METADATA).ref`. Both commands consume it.
3. Retire the two private operand helpers (`_resolve_branch_match_operands`,
   `read_minted_mission_branch`) and `_inject_branch_contract`'s `match_target_branch`.
