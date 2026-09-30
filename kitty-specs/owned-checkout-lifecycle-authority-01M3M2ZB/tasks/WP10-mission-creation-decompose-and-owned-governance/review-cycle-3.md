---
affected_files: []
cycle_number: 3
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T06:56:24Z'
reviewer_agent: claude
wp_id: WP10
---

# WP10 review, cycle 3: CHANGES REQUESTED (small)

## Verified and accepted
- **Cycle-2 fix 1 (fail-open): closed, red-first verified.**
  - At cdcd835e1 both spy parametrisations fail for the right reason: `_switch_to_start_branch` was called on R and on the foreign repository.
  - At 4732c2a96 all 3 tests pass.
  - `_mint_owned_create_root` runs right after `locate_project_root()` and before every git operation. `_rollback_start_branch_on_failure`, `_resolve_start_branch_phase`, `get_current_branch` and `_resolve_default_topology_phase` now all receive `owned_create_root.checkout`.
  - Refusals go through the same `_emit_create_core_error_and_exit` funnel, so the envelopes are unchanged: `OWNED_CHECKOUT_IS_REPOSITORY_ROOT`, `OWNERSHIP_FOREIGN`, and the no-root `MissionCreationError`.
- **Cycle-2 fix 2 (assert): closed.** No `assert` remains in the WP's `src/` diff.
- **Cycle-2 fix 3 (R snapshot): closed.** The canonical `RSnapshotter` is used with `tolerate_status_mutex_for=result.feature_dir.name`. The local helper and its `# noqa: TID251` are deleted.
- **The lane-e merge (d9f3fb23d) is clean.** It brought 8 `src/`/`tests/` files, each blob-identical to the lane-e tip 2afe6d1d3. Its only conflicts were in status bookkeeping (`status.events.jsonl`, `status.json`).

## Required fixes
1. **[MEDIUM] A new G5 offender in `src/specify_cli/cli/commands/agent/mission_create.py:542`.** `_mint_owned_create_root(repo_root, owned_checkout: Path | None, ...)` carries the claim as a bare `Path`.
   - WP01's scanner (`tests/architectural/_owned_checkout_scan.py::bare_owned_root_paths`) reports: `G5 mission_create.py:542 param owned_checkout: Path`. It was clean at 22bebeb91.
   - This breaks WP10 objective 5 and the T055 checklist grep (`owned_checkout: *Path` must return nothing), and WP18's G5 gate will go red on it.
   - Fix: annotate the parameter `owned_checkout: OwnedCheckoutOption`, the exemption under `CLI_CLAIM_INPUT_RULE` for the raw claim. Do not rename it; that would be gate evasion. Then re-run the scanner on both files and require `bare_owned_root_paths == []`.
2. **[LOW] G4: `effective_root` remains in `src/specify_cli/core/mission_creation.py`** at lines 791, 797, 805, 811, 1535, 1538, 1562, 1593 and 1602 (`effective_root_identifiers`). This WP rewrote those lines, and step 4b anticipates the rename ("T055 renames the root").
   - Rename them to `write_root`, which the extracted helpers already use.
   - The re-pinned join token (`feature_dir = write_root / ...`) is unaffected. Re-run `test_single_mission_surface_resolver.py`.
3. **[NIT; remove in the same commit]** The `# noqa: BLE001` on `_mint_owned_create_root`'s `except Exception` suppresses nothing: BLE is not selected, and `ruff check --extend-select RUF100` reports it as unused. The funnel's own `except Exception` carries none. Delete it.

After the fix, run the same targeted set (491 passed at the current head), ruff/format, and mypy `--strict` on the 5 files.
