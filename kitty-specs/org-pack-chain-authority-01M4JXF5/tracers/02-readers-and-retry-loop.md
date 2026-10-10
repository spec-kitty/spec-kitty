# Tracer 02 — Pack-1-only reader fixes + retry-loop retirement (IC-03, IC-04)

Append implementation notes here during implement. Seeded at planning.

- **list_cmd.py**: :88 templates + :197/:245 availability → full chain (mirror effective_set._scanned_ids). Updates TestListAllLayersBackCompat (SUPERSEDE pack-2-hidden; KEEP single-Path + no-crash).
- **invocation_context.py**: remove dead `ProjectContext.org_root` (:82 field, :106 `[0]`). Update test_invocation_context.py:69.
- **action_governance_bundle.py**: drop legacy `org_root` param (:211-215); lenient chain resolution preserved.
- **pack_manager.py**: widen activate/list_available/list_available_detailed/_scan_layer_dirs with org_root_chain; one ORG pair per chain root last-declared-first. Remove `_activate_cascade_target` (activate.py:236-303; collapse :1038).

## Trail
- (planning) seeded.
