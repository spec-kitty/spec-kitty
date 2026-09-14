# WP01 Review — Changes Requested (1 blocker)

Reviewer: reviewer-renata. The design is correct and every functional gate
passes. One minor-but-real quality blocker prevents approval: a dead
`# type: ignore` with a factually-wrong justification in the new test file,
which fails strict mypy and the explicit "mypy clean on ... the test"
acceptance criterion (WP DoD T005 + review standard checks + the charter's
prohibition on unnecessary suppressions).

## Blocker 1 — unnecessary `# type: ignore[arg-type]` in the new test (fails strict mypy)

`tests/core/test_mission_create_idempotency_guard.py:81`

```python
    # `kwargs` mixes str/bool/Path/MissionTopology values by design (a test
    # helper's convenience **overrides passthrough); mypy cannot narrow a
    # dict[str, object] splat against create_mission_core()'s precise
    # per-keyword signature.
    return create_mission_core(repo, slug, **kwargs)  # type: ignore[arg-type]
```

The justifying comment is factually incorrect: mypy does **not** emit an
`arg-type` error at that call, so the ignore is dead. Under the project's
strict config it therefore reds as an `unused-ignore`:

```
$ .venv/bin/python -m mypy tests/core/test_mission_create_idempotency_guard.py
tests/core/test_mission_create_idempotency_guard.py:81: error: Unused "type: ignore" comment  [unused-ignore]
```

Reproduces identically with `--follow-imports=normal` (i.e. it is not a
narrow-check artifact of the `specify_cli.*` `follow_imports = "skip"`
override). `strict = true` implies `warn_unused_ignores`, so this is a hard
strict-mode error on new code.

Charter: "New code MUST pass mypy with zero issues and zero warnings. Do NOT
disable, suppress, or relax checks (no blanket `# noqa`, `# type: ignore`
…). Narrowly-scoped, individually-justified suppressions are allowed only
when the check is genuinely wrong about correct code." Here the check is not
wrong — there is no error to suppress.

**Fix:** delete the `# type: ignore[arg-type]` and its now-incorrect 4-line
justification comment (lines 77–81). No functional change; the file is
mypy-clean without it. Then re-run:
`PWHEADLESS=1 SPEC_KITTY_ENABLE_SAAS_SYNC=0 .venv/bin/python -m mypy tests/core/test_mission_create_idempotency_guard.py`
(the remaining `tests/status/conftest.py:178` error is pre-existing, not in
this WP's diff — ignore it).

## Everything else — PASS (recorded so the fix stays scoped to Blocker 1)

Design adjudication (the load-bearing question):
- `_prior_mission_is_abandoned` implements genesis as an **AND**
  (`snapshot.event_count == 0 and not _path_is_tracked_by_git(... spec.md)`)
  and canceled as an independent **OR** (early `return True` when every
  recorded WP is in `CANCELED`). Correct — genesis is not accidentally an OR.
- "Spec never committed" is a git-tracked check (`git ls-files`) via
  `_path_is_tracked_by_git`, not a file-presence check. Correct.
- Both stories are pinned: `test_second_live_duplicate_create_is_refused_4033`
  (committed spec + zero WP events → REFUSE) and
  `test_genesis_prior_auto_allows_recreate_with_no_flag` (uncommitted spec +
  zero WP events → AUTO-ALLOW). Plus canceled-only auto-allow,
  `allow_duplicate=True` override, same-slug/different-type allowed, and
  corrupt-meta fail-closed refuse.

Functional gates:
- Guard invoked on the live path (`_create_mission_core_impl` step 2.5,
  before scaffold/branch write); `_find_live_duplicate_mission` /
  `_prior_mission_is_abandoned` both have live callers (no dead code).
- Escape hatch reachable from `agent mission create` (`--allow-duplicate` /
  `--allow-dup`) and threaded through `create_mission → _run_create_core_phase
  → create_mission_core → _create_mission_core_impl`; `/spec-kitty.specify`
  calls the same path.
- Tests: `tests/core/test_mission_create_idempotency_guard.py` +
  `test_mission_cli_golden_contract.py` → 25 passed; full `tests/core` →
  381 passed, 4 skipped.
- ruff check: clean; ruff format --check: clean; mypy on both **source**
  files (`mission_creation.py`, `mission_create.py`): clean; complexity ≤15
  (no C901).
- NFR-002 no-orphan-on-refusal asserted; C-002 fail-closed on unreadable
  meta.json asserted. No `--feature` regressions in new CLI surface. Golden
  contract amended in-place as documented (`--allow-duplicate` / `--allow-dup`).

Once Blocker 1 is removed, this WP is approvable.
