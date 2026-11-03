## Issue

closes #7065

## Change

`SemanticCheckEvaluated` events now record the glossary strictness the generation gate actually enforced, instead of always publishing `medium`. If you configure `glossary.strictness: off` or `max` in `.kittify/config.yaml`, or pass `--strictness`, the semantic-check event carries that value and the gate's real blocking decision — so `spec-kitty glossary conflicts --strictness off` and any replay of the event log describe the run that happened.

**Before:** the semantic-check middleware emitted the event before the generation gate resolved strictness, so the emitter substituted `"medium"` and derived `blocked` from `strictness != "off"`. A configured `off` run was logged as a blocking `medium` run; a configured `max` run was under-stated as `medium`; and under `medium` a medium-severity conflict was logged as blocked although the gate let it through.

**After:** one resolution path. `resolve_context_strictness()` in `src/glossary/strictness.py` owns the global → mission → step → runtime chain; `GenerationGateMiddleware`, `SemanticCheckMiddleware` and the emitter all call it, and the emitter derives `blocked` from `should_block()`, the same predicate the gate applies. The gate's decisions themselves are unchanged (same inputs, same function, same predicate).

Grouped by area:

- `src/glossary/strictness.py` — new `coerce_strictness()` (enum/string/unknown normalisation) and `resolve_context_strictness()`; `resolve_strictness()`, `load_global_strictness()` and `should_block()` are untouched.
- `src/glossary/middleware.py` — `SemanticCheckMiddleware` accepts `runtime_override`, resolves once before emitting and stores the value on the context; `GenerationGateMiddleware` delegates to the shared helper instead of re-implementing the chain.
- `src/glossary/events.py` — `emit_semantic_check_evaluated` loses the `or "medium"` fallback, takes an optional `runtime_override`, and computes `blocked` with `should_block()`.
- `src/glossary/pipeline.py` — `create_standard_pipeline` threads `runtime_strictness` into the semantic-check layer as well as the gate.
- `docs/guides/how-to/governance/manage-glossary.md` — a "What the Event Log Records" subsection states that the event carries the resolved value and that `blocked` mirrors the gate; `docs/development/docs-retrieval-index.yaml` gains that one anchor (surgical edit, not a full rebuild).

Behaviour kept on purpose: clarification still runs after the check and before the gate, so `blocked` records the gate's decision for the conflicts present at check time; a conflict you resolve interactively is recorded as found-and-then-resolved. The event contract (`off`/`medium`/`max`, never `None`) is unchanged, and a malformed context value falls back to the configured policy rather than raising.

Red-first proof: `tests/agent/glossary/test_strictness_parity.py` drives the pre-existing entry points (`emit_semantic_check_evaluated`, `create_standard_pipeline` + `SemanticCheckMiddleware`, `GenerationGateMiddleware`). On the pre-fix tree it fails with `assert 'medium' == 'off'` and `assert True is False`; it passes after the fix. The removed test `test_unresolved_strictness_is_written_as_medium` asserted the defect itself and is replaced by `test_unresolved_strictness_resolves_from_config`.

## Tests run

```
uv run pytest tests/agent/glossary -q  # 583 passed, 9 skipped (skips pre-existing)
uv run pytest tests/agent/glossary/test_strictness_parity.py -q  # 14 passed
uv run pytest tests/agent/glossary/test_middleware.py -q  # 47 passed
uv run pytest tests/charter_offering/missions/test_glossary_hook.py -q  # 33 passed
uv run pytest tests/specify_cli/cli/commands/test_cli_boundary_glossary.py tests/specify_cli/cli/commands/test_glossary_show.py tests/specify_cli/cli/commands/test_glossary_validate.py -q  # 40 passed
uv run ruff check src/glossary tests/agent/glossary  # All checks passed
uv run ruff format --check src/glossary tests/agent/glossary  # clean
uv run mypy src/glossary/strictness.py src/glossary/events.py src/glossary/middleware.py src/glossary/pipeline.py  # Success: no issues found in 4 source files
uv run python -m scripts.docs.check_docs_freshness --ci  # exit=0 errors=0 (warnings listed under Deferred)
uv run --frozen python -m scripts.docs.check_changelog_style  # passes on the fragment
```

Self-review:
- Re-read every changed line: the gate still resolves and blocks exactly as before (same helper, same predicate); only the emitter's source of the value changed.
- Confirmed no second copy of the precedence chain remains — `grep -rn "resolve_strictness(" src/` shows only `strictness.py`.
- Checked the `or`-chained enum resolution: `Strictness` values are non-empty strings, so no real value can fall through; an unrecognised value falls to the policy chain by design (covered by a test).
- Verified the removed test asserted the bug, and that no new `skip`/`xfail`/weakened assertion was added anywhere in the diff.
- Checked the docs regeneration is surgical: the index diff is the single new anchor for the page this PR edits. The three remaining index warnings pre-date this branch.

## Blast radius

Discovery: `git grep -n "emit_semantic_check_evaluated\|resolve_strictness\|effective_strictness" -- src tests`

Files:
- `src/glossary/strictness.py`
- `src/glossary/middleware.py`
- `src/glossary/events.py`
- `src/glossary/pipeline.py`
- `tests/agent/glossary/test_strictness_parity.py`
- `tests/agent/glossary/test_event_emission.py`
- `tests/agent/glossary/test_middleware.py`
- `docs/guides/how-to/governance/manage-glossary.md`
- `docs/development/docs-retrieval-index.yaml`
- `docs/changelog/unreleased/<pr>.fixed.md`
- `kitty-specs/semantic-check-strictness-parity-01M6GRFQ/**` (mission record)

## Deferred

- `check_docs_freshness --ci` reports three pre-existing warnings on `main` that this PR does not touch and does not fix, because the post-merge regeneration bot owns the committed index: `DOCS-INDEX-DRIFT` for `docs/adr/4.x/2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md` and `docs/development/reference/ci-gate-mechanics.md`, and `INVENTORY-INCOMPLETE`/`LEAK-MISSING-INVENTORY` for `docs/development/testing/ci-performance.md`. errors=0.
- `HELP-DRIFT migrate activation-ledger` and `LINK-HEALTH-FAILED` (HTTP 403 from refactoring.guru and docs.claude.com) are also pre-existing on `main` and unrelated to this diff.
- `recommended_action` keeps its severity-only derivation (`block` on a high-severity finding) even when strictness is `off`. Making it strictness-aware is a separate semantic decision about the event contract, not part of #7065.
- SonarCloud review: none expected to need the web interface; the diff adds no new duplicated block and no new branch without a test.
