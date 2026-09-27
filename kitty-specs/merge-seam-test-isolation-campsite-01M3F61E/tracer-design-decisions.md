# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->
- 2026-09-26 — Census allowlist keyed on content-anchored (file, qualname, kind) + exact count via `specify_cli.contracts.anchoring.composite_key` (on main) rather than the ratchet mission's unmerged `_content_identity`, so the gate is not born line-keyed/stale and does not depend on 01M3EW3Z.
- 2026-09-26 — `try/finally`-restored mutations are offenders (64% of the census); scoped facilities are the only non-offending form. Existing-gate sub-classes (`patch.dict(sys.modules)`, `SPEC_KITTY_HOME`) are excluded to keep one verdict per site.
- 2026-09-26 — #5117 verdict owner is the Pydantic canonical source (`schema_models.py`) + regenerated YAML; the contradicting `_inert_slots_baseline.yaml` row is left to ratchet WP05 (C-002).
- 2026-09-26 (WP02) — The single-blob-reader guard matches an adjacent `FormattedValue, Constant(':'), FormattedValue` f-string triple, not "any colon"; the looser rule over-matched `merge/conflict_resolver.py::_read_conflict_sides` (stage-index `:2:`/`:3:` text reads — a genuinely different reader), now a negative control.
- 2026-09-26 (WP01) — Over-count = actual > recorded (shrink the row to provoke it); under-count = actual < recorded (bump the row). Easy to invert; the self-mutation tests pin both directions.
- 2026-09-26 (WP08 review) — `monkeypatch.delitem(sys.modules, name)` must not be used as a *teardown* purge: monkeypatch's undo restores what each call removed, so the teardown removal is reversed and the module leaks past the test (junit + census cannot see it; caught by a post-file probe). Pattern: before import, `monkeypatch.setitem(sys.modules, name, None)` then `monkeypatch.delitem(sys.modules, name)` so undo leaves the key absent; drop the teardown purge.
- 2026-09-26 (operator ruling) — The sweep fully formatted 19 files on the #473 `[tool.ruff.format].exclude` ratchet (explicit-path `ruff format` ignores the exclude list), turning `test_ruff_format_exclude_ratchet.py` red on lanes h/i/g. Operator chose to KEEP the formatting and shrink the ratchet in one consolidated closeout commit (folded into the sweep snapshot so no commit is red) instead of reverting — sweep lanes never touch `pyproject.toml` (avoids 8-lane conflicts). WP07/WP09 rejections on this ground alone are overturned.
- 2026-09-26 (WP11) — Seven files consume a by-path-loaded module as a bare module-level singleton across 10–30+ call sites; converted with a module-scoped autouse fixture using `pytest.MonkeyPatch.context()` + `global X; X = module` rather than threading `monkeypatch` through every call site.
- 2026-09-26 (WP11) — `test_real_typer_app_visible_count_within_tolerance` needed a block-scoped `MonkeyPatch.context()`, not the fixture: a sibling test calls it directly and asserts synchronous env restore on return. Lesson: grep for direct callers before converting any helper/non-fixture site to fixture scope.
- 2026-09-26 (WP11) — `untrusted_path_audit/audit.py` lost its module-level sys.path bootstrap (D1); bare `python audit.py` no longer works, docstring now says `python -m tests.architectural.untrusted_path_audit.audit`. `RULESET.md`/`inventory.md`/a suggestion string in `test_untrusted_path_containment.py` still show the old form → closeout doc fold. Line shifts in `test_quality_gate_decision.py` stale two line-keyed rows of `tests/release/pinning_rule_inventory.json` → closeout regeneration via `scripts/ci/derive_pinning_inventory.py`.
- 2026-09-27 (WP13 review, operator ruling) — `_capture_nudge` in tests/audit/test_no_legacy_path_literals.py: operator chose "convert"; the reviewer showed a monkeypatch conversion breaks `test_fr010_runtime_home_alias_is_measured_inert_and_refused_on_both_limbs` (it asserts the helper keeps a raw SPEC_KITTY_HOME write) and that the site was never a home-pin census member (regeneration is a no-op). Applied the reviewer's alternative: wrap in `mock.patch.dict(os.environ)` and drop the manual try/finally restore — no home-pin re-baseline, zero transitional rows left.
- 2026-09-27 (WP14) — Sealed caps came out exactly at (not below) 3 of 4 plan ceilings — process-bootstrap 6/6, leak-sentinel 2/2, deferred-01M3EW3Z 16/16 — with only subprocess-entry landing under its ceiling (12 of 13). `test_caps_are_tight` (exact-equality shrink-only ratchet) still holds because the caps are frozen at the *actual* measured totals, not the ceilings.
