# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · pi:deepseek-v4.1-flash-1017:python-pedro · The accessor answers a TOTAL mapping over the requested ids (False for unknown / sentinel:false / language-scoped-out), not 'absent key'. Review cycle 1 caught the split between code and contract; total-over-request is safer for callers and is now the pinned semantics 0 of the contract.

2026-11-01 · pi:deepseek-v4.1-flash-1017:python-pedro · Restored #6462's lazy _graph() accessor: the shipped 358-node DRG had crept back into AgentProfileRepository.__init__ during a later lineage refactor, so every profile-map reader paid 0.54s for edges it never traverses. A sentinel read must not pay it, and the restoration is behaviour-preserving (explicit drg= authoritative).

2026-11-01 · pi:deepseek-v4.1-flash-1017:python-pedro · build_agent_profile_sentinels skips PackContext deliberately: sentinel is structural (same rationale as agent_profile_repository/get_provenance), so no activation key may gate it; the layer resolution still reads config, which keeps the malformed-config fail-closed contract.
