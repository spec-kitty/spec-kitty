# Contract — runtime_bridge module layout (FR-001..FR-005, FR-010)

Two gates enforce this contract, and each property has one authority:

| Property | Authority |
|---|---|
| Moved-name table (which seam owns which name) | `tests/runtime/test_bridge_no_compat_delegates.py` `REMOVED` (#2561's canonical gate, extended by #2560) |
| The bridge neither defines, exposes nor loads a moved name; no seam and no `src/` module reads one back off the bridge | same gate, checks A′ / B / B′ / D |
| Public re-exports are the owning seam's own objects | same gate, check C (`_KEPT_RE_EXPORT_OWNERS`) |
| Each moved name is *defined* in its owner (not re-imported) | `tests/runtime/test_runtime_bridge_query_seam_layout.py` §1 |
| The bridge's `__all__` is unchanged (8 names) | layout gate §1 |
| Import direction | layout gate §4 |

1. **Ownership.** Each name in the `REMOVED` rows `decision_mapping`, `decision_log`, `query` and `guards`, plus `identity._resolve_runtime_feature_dir`, is defined at the top level of its owning module, and its callables' `__module__` names that module.
2. **Re-export identity.** `get_or_start_run`, `build_operational_context_for_claim` (io), `query_current_state`, `answer_decision_via_runtime`, `QueryModeValidationError`, `MissionNotFoundError` (query) and `DecisionGitLogUnavailable` (decision_log) are bound on the bridge by a plain `from runtime.next.runtime_bridge_<owner> import <name>`, and `runtime_bridge.<name> is runtime_bridge_<owner>.<name>`.
3. **No delegates.** The bridge defines no moved name, exposes none except the re-exports in §2, and loads none.
4. **Import direction.** By AST over the live files, function-local imports included:
   - no `runtime_bridge_*` module imports `runtime_bridge` (empty-set invariant);
   - decision_mapping imports none of query, engine, decision_log, composition, guards, io;
   - decision_log imports none of query, decision_mapping, engine, guards;
   - guards imports none of io, composition, engine, query, decision_log;
   - engine imports not query.

   A planted forbidden import is reported (self-mutation tests).
5. **No stale bridge imports.** `ruff check` (F401) is clean on `runtime_bridge.py`, so a stale `runtime_bridge.<moved name>` patch raises AttributeError.
