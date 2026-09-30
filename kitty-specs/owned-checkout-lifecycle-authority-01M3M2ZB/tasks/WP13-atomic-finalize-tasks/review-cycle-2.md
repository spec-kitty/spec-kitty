---
affected_files: []
cycle_number: 2
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T08:58:59Z'
reviewer_agent: claude
wp_id: WP13
---

# WP13 review, cycle 2: REJECTED (reviewer-renata)

Cycle-1 status: both HIGH findings are fixed and pinned. I re-ran my own repros on head and both pass:
- the foreign-meta post-commit failure keeps P's HEAD at the landed commit;
- the non-owned issue-ref ownership-overlap refusal leaves HEAD, porcelain and hashes identical.

The mutation run is strong. Every guard has at least one test that fails when it is disabled:

| Guard disabled | Tests failing (of 24) |
|---|---|
| byte restore | 12 |
| HEAD restore | 3 |
| both | 12 |
| `commit_landed` | 2 |
| `fold_into_caller_commit` | 2 |

The same pinning covers MEDIUM 3 (documented plus a pinning test), MEDIUM 4, MEDIUM 5 (finalize G5 now 0), MEDIUM 8, and the LOW items.

Three new problems block approval. All are small.

## Blocking

1. **[MEDIUM] `mission_finalize.py:162` (`_OWNED_ENVELOPE_EXTRAS`) with `:4058`/`:4068`. The ContextVar is never reset, so it leaks the owned key into later non-owned payloads.**
   - `finalize_tasks` clears the ContextVar at entry and sets it after resolution. It never restores the ContextVar on exit, on any path.
   - The ContextVar lives on in the calling thread after the command returns. Any later `mission_finalize._emit_json` call in the same process then gets the key.
   - `tasks_finalize.py:217` (`agent tasks finalize-tasks`) imports `mission_finalize._validate_dependency_graph`, which emits through `_emit_json`.
   - Repro: an owned `--validate-only` finalize through CliRunner, followed in the same process by `mf._validate_dependency_graph({"WP01": ["WP02"], "WP02": ["WP01"]}, json_output=True)`. The non-owned circular-dependency payload came out as `{"stale_repository_root_copy": {"path": ".../primary/kitty-specs/owned-fixture-01M2D900", ...}, "error": "Circular dependencies detected ..."}`.
   - This breaks the rule that non-owned payloads stay byte-identical. It is also the hidden-state smell the charter warns about.
   - **Fix:**
     - Scope the ContextVar: take `token = _OWNED_ENVELOPE_EXTRAS.set(...)` and call `reset(token)` in a `finally` that wraps the whole `finalize_tasks` body. A small `@contextmanager` works too.
     - Add a test that runs an owned finalize, then a non-owned `_emit_json` in the same process, and asserts the key is absent.
     - An explicit parameter would be the purer design, but I accept a *scoped* ContextVar here: the alternative is threading `owned` through roughly 30 gate emitters. State that rationale in the comment.

2. **[MEDIUM] G5 grew again, from 2 to 4 in `_owned_checkout.py`. The new `@overload`s narrow nothing at either live call site.**
   - `tests/architectural/_owned_checkout_scan.bare_owned_root_paths` flags the overload parameters `owned_checkout: Path` (`:102`) and `owned_checkout: Path | None` (`:137`).
   - Repo-wide, G5 is now 0 + 4 = 4 against a pre-WP total of 1 + 2 = 3. WP18 is a shrink-only ledger.
   - Both callers (`mission_finalize.py:3574`, `context.py:260`) pass an `OwnedCheckoutOption` (`Path | None`). They therefore resolve to the third overload and still get `OwnedCheckout | None`. The overloads close nothing: not at finalize, and not the latent gap at `context.py:260`.
   - There is also no runtime gap to close. The implementation's explicit branch returns `resolve_owned_mission(...)`, which mypy types as `OwnedCheckout`.
   - **Fix:** remove the three overloads. This reverts the `_owned_checkout.py` out-of-map edit. No change is needed at `context.py:260` (WP08), because the contract lives in one implementation line that mypy already checks.
   - If you want the contract pinned, add a test that `resolve_owned_or_adopt` with an explicit claim either returns a fact or raises. Don't add a signature.

3. **[MEDIUM] `mission_finalize.py:3523` (`_finalize_refusal_envelope`). The owned-claim refusal JSON drops `spec_kitty_version` and changes format.**
   - Every other finalize JSON payload goes through `mission._emit_json` → `_with_cli_version`/`_with_mission_aliases`. That output is compact and always carries `spec_kitty_version`.
   - `emit_owned_refusal` prints `json.dumps(payload, indent=2)` itself. The owned refusal is now `{"error": ..., "error_code": "OWNED_BRANCH_REFUSED"}`, indented, with no `spec_kitty_version`.
   - In cycle 1 the same refusal carried `spec_kitty_version`.
   - `indent=2` is `emit_owned_refusal`'s canonical style, shared by `context.py` (WP08) and `spec-commit`, so the indentation alone is acceptable.
   - The lost key is a regression in finalize's own JSON contract.
   - **Fix:** have `_finalize_refusal_envelope` include the version key via `mission_parsing._with_cli_version`, so the finalize contract keys survive. Pin it in `test_owned_refusal_is_routed_through_emit_owned_refusal`.

## Non-blocking

- **[LOW] `tests/specify_cli/tasks/test_issue_matrix_scaffold.py`.** This is WP17's file, and it is on the `pyproject.toml` ruff-format **exclude** list (`:2297`). The commit reformatted the whole file, a churn of about 60 lines across unrelated tests. Either revert the formatting noise and keep only the new tests, or declare the reformat and drop the file from the exclude list in the same commit. Right now it is neither.
- **[LOW] `issue_matrix.py:502-504`.** The fold branch duplicates `write_issue_matrix`'s serialization (`json.dumps(build_issue_matrix_document(rows), indent=2, sort_keys=True) + "\n"` plus `atomic_write`). Extract a tiny `_serialize_issue_matrix(rows)` or `_stage_issue_matrix(path, rows)` helper that both call, so there is a single authority for the on-disk bytes. **WP17 T090 must preserve `fold_into_caller_commit`** when it converts `scaffold_issue_matrix` to `owned=`. It is declared in 19a8bd6c3; the orchestrator should also note it in WP17's task file.
- **[LOW, carried] Red-first history.** 3372fa798 (fix and tests bundled) and the undeclared out-of-map edits in 3372fa798/a5a251528 remain in history. The new commits are properly red-first. Record these in the Activity Log as a known history deviation; a rewrite isn't required.

## Verified OK this cycle

- **HIGH-1:** `_FinalizeCommitLanded` is separate from the SK3466 flag. There is no double restore, and the order is SK3466, then bytes, then HEAD.
- **HIGH-2:** `fold_into_caller_commit` applies only when the home is `feature_dir`. A coord-routed home keeps the write-seam commit. The out-of-map edit is minimal and declared.
- **Coord residue:** documented in the guard comment and pinned by `test_coord_topology_lane_cycle_refusal_restores_the_mission_directory_only`. It is tracked in #5343.
- **Oracle:** `_take_p_oracle` now includes `hash_tree` content hashes.
- **G-gates:** finalize G2 0, G4 2 (both bridging), G5 0. `TRANSITIONAL(WP18)` count is 0.
- **Lint and types:** ruff check and format are clean, and complexity is ≤ 15. mypy `--strict` over 13 files (finalize, its callers and callees, plus `context.py`, `tasks_finalize.py` and `issue_matrix.py`) gives 5 errors on base and 5 on head, identical.
