# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-10 · claude:claude-opus-5-5:planner-priti · **[2026-11-10][plan] Seed: approach.** Seven issues fixed with the smallest change that converges core on the spec-kitty-events rulings (framing, byte rule, R25, R26, R29, decisions 9 and 16); red-first test commit then fix in every WP; five WPs with disjoint files, only WP05 (Mission 058 data repair) depends on WP02; targeted tests only, no make test-fast.

2026-11-10 · opencode:glm-5.3:python-pedro · **[2026-11-10][implement] #7463 (WP04): deterministic characterisation tests pin output (de-duplication control + scale counts at n=2000) and before/after timings recorded in the WP history instead of a wall-clock perf test (C-006, operator decision 01M72874ECYSTEJVVRZNCD2M7E); red-first exception per spec NFR-003 documented. Mutation check: removing existing_ids.add(cid) turns the de-duplication control red.**

2026-11-10 · claude:claude-opus-5-5:python-pedro · **[2026-11-10][implement] C0 separators cannot split a valid row.** json.dumps always escapes VT/FF/FS/GS/RS (raw C0 inside a JSON string is invalid JSON), so only U+0085/U+2028/U+2029 split rows in practice; the C0 cases in test_store_line_framing.py pass on base and stand as pins of the escaped form, not as red-first proof.
