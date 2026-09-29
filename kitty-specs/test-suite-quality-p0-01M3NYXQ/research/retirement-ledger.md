# WP03 Retirement Ledger (issue #5353)

Audit source: `/mnt/project-files/test-review/2026-09-29-dev-assist-test-audit.md`.
All five retirements were verified against a covering guard (or a no-consumer grep) before deletion. Guards were re-run at the tip of lane-c after the last retirement; counts below are from that run.

| # | Audit item | Retired | Verdict | Commit |
|---|-----------|---------|---------|--------|
| 1 | #1 | `tests/missions/test_resolution_convergence.py` | RETIRE, covered | `b30d289a` |
| 2 | #6 | `tests/unit/test_symbol_identity_spike.py` + `tests/architectural/_symbol_identity.py` | RETIRE, covered | `611f2d8a` |
| 3 | #7 | `tests/coordination/test_surface_authority_goldens.py` | RETIRE, covered | `4cb254f0` |
| 4 | #8 | `tests/architectural/test_charter_owner_map_executed.py` | RETIRE, covered | `bedb5cce` |
| 5 | #10 | `tests/adversarial/test_infrastructure.py` + unused `tests/adversarial/conftest.py` fixtures | RETIRE, none needed (no consumers) | `8431be85` |

## 1. test_resolution_convergence.py (`b30d289a`)
- Covering guard: `tests/missions/test_write_placement_handle_canonicalization_2136.py:127-280`.
- Evidence: `pytest tests/missions/test_write_placement_handle_canonicalization_2136.py` -> 20 passed.
- References updated: `pyproject.toml` (one path entry removed).

## 2. Symbol identity spike (`611f2d8a`)
- Covering guards: `tests/unit/test_symbol_key.py` (whole file) and `tests/architectural/test_no_dead_symbols.py` (consumer of `_symbol_key.py`); `test_no_dead_modules.py` also green.
- Evidence: `pytest tests/unit/test_symbol_key.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py` -> 79 passed.
- References updated: `pyproject.toml` (two path entries removed); `tests/architectural/_symbol_key.py` docstring/comments re-pointed at the retired spike. The remaining `_symbol_identity.py` mention in `_symbol_key.py:16` is deliberate history text.

## 3. test_surface_authority_goldens.py (`4cb254f0`)
- Covering guards: `tests/specify_cli/cli/commands/agent/test_tasks_surface_authority.py:76,118,235,263`; `tests/coordination/test_commit_router.py`, `test_commit_router_fail_loud.py`; `tests/specify_cli/coordination/test_commit_router_placement.py` (note: lives under `tests/specify_cli/coordination/`, not `tests/coordination/`).
- Evidence: `pytest test_tasks_surface_authority.py tests/coordination/test_surface_authority.py test_commit_router.py test_commit_router_fail_loud.py test_commit_router_layering.py` -> 102 passed; `test_commit_router_placement.py` -> 6 passed.
- References updated: docstrings in `src/specify_cli/cli/commands/agent/tasks_mark_status.py` and `src/specify_cli/coordination/surface_authority.py`; comment in `test_tasks_surface_authority.py`.

## 4. test_charter_owner_map_executed.py (`bedb5cce`)
- Covering guard: `tests/architectural/test_glossary_authority_parity.py:136,147,165,260`.
- Evidence: `pytest tests/architectural/test_glossary_authority_parity.py tests/glossary/test_canonical_promotion.py` -> 13 passed, 2 skipped.
- References updated: `tests/glossary/test_canonical_promotion.py`.

## 5. tests/adversarial/test_infrastructure.py + fixtures (`8431be85`)
- Verdict: none needed. Repo-wide grep for `malicious_path`, `valid_unicode_path`, `case_insensitive_fs`, `adversarial_env`, `temp_git_project`, `kittify_project`, `_is_case_sensitive_filesystem`: the only hits outside the retired file are a same-named `parametrize` argument in `test_path_validation.py` (not the fixture) and a locally defined `kittify_project` in `tests/runtime/test_workspace_context_unit.py`. The only importer of `PATH_ATTACK_VECTORS`/`CSV_ATTACK_VECTORS`/`AttackVector` was the retired file (`test_csv_attacks.py:255` still uses `AttackVector`, retained).
- Evidence: `pytest tests/adversarial/test_csv_attacks.py test_path_validation.py test_distribution.py` -> 52 passed, 6 skipped; ruff check and ruff format clean on `tests/adversarial`.
- Residual: `PATH_ATTACK_VECTORS` and `CSV_ATTACK_VECTORS` constants remain in conftest with no consumers (audit scoped the item to fixtures). Candidate for a later campsite pass.

## Dangling-reference sweep
Repo-wide grep for every deleted file and symbol name (excluding `.git`, `.worktrees`, `.venv`) found only: historical `kitty-specs/**` records and `docs/reports/test-sanitation/**` snapshots (immutable, left as is), this mission's own planning files, and the deliberate history note in `_symbol_key.py`. No shrink-only baseline or ledger still pins a deleted path (`pyproject.toml` entries were removed in `b30d289a` and `611f2d8a`). No fix commit was needed.

## Review addendum (opus lens, folded)

# WP03 retirement-ledger addendum (corrections; kitty-specs/ not edited)

1. resolution_convergence row: add `tests/specify_cli/coordination/test_coord_status_commit_2155.py:199,259` as covering guards.
2. Numeric-prefix handle form is NOT in `ALL_HANDLE_FORMS` (note the gap in the affected row; coverage for it is not provided by that parametrization).
3. Commit 4cb254f0 message mis-states the placement test path: the real path is `tests/specify_cli/coordination/test_commit_router_placement.py`. It also overstates `test_commit_router.py:315` (test_idempotent_unchanged) as covering row 4; the reason-code assertion was actually added by fold fix 1 (see item 7).
4. Commit bedb5cce message cites historic commit `7b0c2d3`; the real pin is `73609a064a444fbec6d1bd45d350574151017e1d`, and `synthesis-manifest.yaml` is also covered by the pin.
5. `malformed_csv_factory` (tests/adversarial/conftest.py): the `bytes` branch (`write_bytes`) is now unexercised, since the bytes-input CSV_ATTACK_VECTORS were deleted; PATH_ATTACK_VECTORS and CSV_ATTACK_VECTORS themselves have been removed (no consumers).
6. Extra covering guards added by the fold-fixes:
   - `tests/coordination/test_commit_router_fail_loud.py::test_2739_genuine_no_op_unchanged_stays_exit0` now asserts `reason == "no_op_no_changes"` (row 4; commit_router.py:446).
   - `tests/unit/test_symbol_key.py::test_body_hash_stable_under_intra_class_comment_insertion`, `::test_body_hash_stable_under_intra_line_whitespace_reformat`, `::test_body_hash_control_real_edit_alters_key_despite_noise` (ported ClassDef stability from deleted spike 598abdfc).
   - `tests/specify_cli/missions/test_read_path_resolver_validation.py::test_delegator_propagates_status_read_path_not_found` now pins the "Status read path not found for" + slug message frame (_read_path_resolver.py:91).
