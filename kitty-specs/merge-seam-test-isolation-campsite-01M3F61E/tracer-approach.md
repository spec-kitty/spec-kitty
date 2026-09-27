# Approach Evolution

> Track how your approach changed as the mission progressed.

**Prompting questions**
- What approach did you start with (as stated in the spec or plan)?
- What changed during implementation, and why?
- What would you try differently on a similar mission?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what approach was tried and what shifted. -->
- 2026-09-26 — Grounding squad (alignment + scope lenses) split the four issues: #5116 parked (blocked on #2633 + ratchet WP11), #5117 re-framed from "wire or remove" to KEEP (already wired end-to-end), #5118's Sonar target found inactive (0 on live project, 41 on legacy). Operator chose "actionable-now" + full local-detector sweep (474 sites).
- 2026-09-26 — Post-spec squad reshaped #5119: the guard targets `specify_cli.cli.commands` (7 merge modules legitimately use `cli.console`), and all six driver *bodies* incl. serialization move so replay and subprocess share one body (equivalence by construction) instead of relocating only pure reconcilers.
- 2026-09-26 (WP01) — The RED commit carries only the "unallowlisted sites" verdict (471 sites / 278 keys); the drop-one-row / over / under / wrong-shard vacuity tests ride in the GREEN commit because they need a populated allowlist — keeps the red signal single-cause.
- 2026-09-26 (WP09) — Three pre-sweep helpers (`_run_setup_plan_from`, `_run_setup_plan`, `_run_research`) shared a latent leak: the `finally` restore was skipped when the prior env value was unset, so the var leaked past the test. Converting to `monkeypatch`/`mock.patch.dict` fixed it as a side effect — hand-written try/finally restores are exactly the fragility the census targets.
- 2026-09-27 (WP14) — Sealed test reuses WP01's own `load_allowlist`/`AllowlistRow`/`Allowlist` by importing them from `test_no_manual_global_state_mutation.py` rather than re-parsing the YAML shards, per the module's "only allowlist reader" docstring claim. Each seal check is a pure `rows -> list[str]` verdict function so T067's self-mutation tests assert on the returned violation list, never on pytest's own failure signal.
