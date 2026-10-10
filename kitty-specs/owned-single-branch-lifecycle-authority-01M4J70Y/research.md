# Research & Provenance — Owned single-branch lifecycle authority

**Date**: 2026-10-10 · **Base**: `origin/main` (grounded at `fb8b46c9`, rebased onto `b9aa9911e`)

## The shared root (confirmed by a 6-lens grounding squad)

Every one of the seven issues is the same defect: an owned-checkout `single_branch` command folds the invocation root to `get_main_repo_root` / `locate_project_root` / `get_status_read_root` and operates on the repository-root checkout, ignoring the validated `OwnedCheckout`. The fix seam already exists and is honoured by the working surfaces (`review/cycle.py`, `accept.py`, `next_cmd.py`, `workspace/context.py`, `git/protection_policy.py`):

- Mint once: `resolve_owned_mission(repository_root, checkout, handle, *, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)` (sole minter, `core/owned_mission.py`); flagless adoption via `adopt_owned_checkout` / `resolve_owned_or_adopt`.
- Thread the immutable fact as `owned=`.
- Resolve paths via `placement_seam(repo_root, slug, owned=owned).read_dir/write_dir/write_target`; commit via `commit_for_mission(..., owned=)` → `ProtectionPolicy.resolve_for_owned`.
- The fact carries `write_branch` (the minted `mission_branch` the owned writes land on), distinct from `target_branch` (the protected landing destination).

**No fix touches `core/paths.py`** — all repairs route around that shared seam (operator decision D1).

## Per-issue repair-branch provenance (adopted vs rewrote)

| Issue | Pri | Repair branch / commit | Disposition | Notes |
|-------|-----|------------------------|-------------|-------|
| #5874 | P1 | `codex/5874-owned-decisions` `28e526d73` (+`a3ec03b59` test) | **adopt-with-rebase + EXTEND** | 1 import-line merge on `decision.py`; emit/service/test auto-merge. Branch omitted `orchestrator_api/decision_verbs.py` (in scope, still folds `_get_main_repo_root`) → **extend** (operator D2). |
| #5877 | P1 | `codex/5877-owned-prerequisites` `96252a666` (+`0c9768e57`) | **adopt-as-is** | base byte-identical to main; threads `owned.write_branch` as `expected_checkout_branch`. |
| #5878 | P1 | `codex/5878-owned-requirement-mapping` `885833015` (+`03c71230f`) | **adopt-as-is** | applies 3-way clean; **no `core/paths.py` edit**; adds owned guard to `status/emit.py`. Confirm `mission_write_lock` composition post-merge. |
| #5880 | P1 | `codex/5880-owned-task-finalization` `4c0f5130c` (+`2be94e6fd`) | **adopt-with-rebase** | anchors verbatim; base drifted in unrelated write-ledger regions → line-offset rebase. Touches `mission_finalize.py`/`_lanes.py`/`_planning_pin.py` (not `_branch_contract.py`). |
| #5892 | P2 | `28a262f00` (+`5f5db01fe`) on `codex/owned-analysis-recording` | **adopt-with-rebase** (near as-is) | 6-line fix: pass stored `topology`+`mission_branch` to preview `compute_lanes`. Disjoint from #5880; kept in the same WP (operator instruction). |
| #5893 | P1 | recording `2084975b9` (+`2bfa4c485`); authority `9dafc88d3` (+`627c01acc`) | **recording adopt-as-is + authority adopt-with-rebase** | Operator D3: include BOTH halves. Authority rebase: `DoctrineService`→`ActiveCharterService`, `CharterPackConfigError`→`ActiveCharterConfigError`, `_declared_paths(source=)`. Guard relaxation kept EXACTLY as reviewed (package-identical GLOBAL mirror only). |
| #5947 | P0 | none (new work) | **verify-green + defensive hardening** | Operator D4. The two named tests + full `test_owned_history_support.py` (24) pass on current `main`; red nightly ran on older `f1e4e69`. Add by-construction owned-resolver-not-consulted invariant + tidy `cycle.py` `resolve(main_repo_root)`→`resolve_for_owned`. No fabricated red, no test-expectation edits. |

## Operator decisions (2026-10-10, binding)

- **D1** One-resolver seam; thread existing `OwnedCheckout` via `owned=`; **no** `core/paths.py` edit.
- **D2** Extend WP01 to also fix `orchestrator_api/decision_verbs.py` (open/resolve/defer/cancel/verify/list).
- **D3** Record-analysis WP includes **both** halves (recording + material/charter authority).
- **D4** #5947 = verify-green + defensive owned hardening; no fabricated red.

## Verification facts captured during grounding

- `#5947`: `PWHEADLESS=1 uv run --frozen python -m pytest tests/specify_cli/test_owned_history_support.py -q` → 24 passed on `fb8b46c9`; the two named tests pass in isolation. Nightly run #37880273598 was against `head_sha f1e4e69c`.
- Nightly invocation (CI-owned, not run in-mission): `pytest tests/specify_cli -m "not stress and not timing" -n auto --dist loadfile`.
- Scope fence (C-002): #5882 (specify→plan composition-stall, runtime domain) and the broader external-authority classes #5253/#5380 are OUT; the only in-scope authority change is the reviewed package-identical GLOBAL-mirror relaxation for #5893.
