---
work_package_id: WP03
title: Fix the pack-1-only readers
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-005
- NFR-001
planning_base_branch: kitty/org-pack-chain-authority-stack
merge_target_branch: kitty/org-pack-chain-authority-stack
branch_strategy: Planning artifacts for this mission were generated on kitty/org-pack-chain-authority-stack. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/org-pack-chain-authority-stack unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-pack-chain-authority-01M4JXF5
base_commit: 449c6976a33161831152b8f52aa167327d4d23c1
created_at: '2026-10-10T14:29:13.874471+00:00'
subtasks:
- T014
- T015
- T016
- T017
- T018
- T019
phase: Phase 2 - Migration
history:
- at: '2026-10-10T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/list_cmd.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/charter/list_cmd.py
- src/charter/activation/invocation_context.py
- src/charter/activation/action_governance_bundle.py
- tests/specify_cli/cli/commands/charter/test_org_cascade_chain.py
- tests/charter/test_invocation_context.py
- tests/charter/test_action_governance_bundle_org_fragment.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Fix the pack-1-only readers

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the profile in the frontmatter first.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Fix the three surfaces that still read pack #1 only.

Done when:
- `charter list --all` lists org missions, templates, and artifacts from **every** configured existing pack (not just pack 1).
- The write-only `ProjectContext.org_root` single-root field is removed.
- `action_governance_bundle`'s legacy single-root `org_root` param is dropped (its chain resolution stays lenient; the full chain was already threaded and used downstream — no behaviour change).
- `TestListAllLayersBackCompat` is updated: the pack-2-hidden assertion is SUPERSEDED (pack 2 is now shown); the single-Path and no-crash assertions are KEPT.
- `resolve_layer_roots`'s `dict[str, Path]` contract is untouched (NFR-001).
- ruff/mypy clean; complexity ≤15.

## Context & Constraints

Spec: FR-003, FR-005, NFR-001. Depends on **WP01** (authority) and coordinates with **WP02** (uses the same migration pattern). Depends on **WP04** only if you choose to thread `org_root_chain` into `list_available_detailed` (see T015) — if WP04 has not landed, fall back to the chain-aware per-root scan pattern (below), which does not need the widened signature.

Verified file:line:
- `list_cmd.py`:
  - `:88` `org_root = layer_roots.get("org")` builds the ORG template `TierRoot` (`org_root / "missions"`) — pack 1 only.
  - `:197` `layer_roots = resolve_layer_roots(repo_root)` → `:245` `list_available_detailed(..., layer_roots=layer_roots)` → `pack_manager._scan_layer_dirs` reads `roots.get("org")` (pack 1).
  - **Fix pattern**: mirror `effective_set._scanned_ids` — iterate `resolve_pack_chain(repo_root, strict=False)` and build one ORG `TierRoot` per chain root (templates, T014); for availability (T015), either pass `org_root_chain=resolve_pack_chain(...)` into `list_available_detailed` (if WP04 landed) or union a per-root scan here.
- `invocation_context.py`: `ProjectContext.org_root` field (:82) + `org_root = org_roots[0] if org_roots else None` (:106). No `src/` reader; only `tests/charter/test_invocation_context.py:69` asserts it is `None`. **Remove the field and the `[0]` computation.**
- `action_governance_bundle.py`: `effective_org_root = effective_org_roots[0]` (:215) is a fallback-only value; the full `org_roots` chain is already threaded and used at `:298`. **Drop the `org_root` param** through `_load_action_governance_bundle` so the `[0]` disappears; verify the chain path is unaffected.

Constraints:
- Do NOT widen `resolve_layer_roots` (NFR-001).
- `action_governance_bundle` resolution stays **lenient** (a governance bundle degrades on a missing pack, not refuses — research.md Decision 4).

## Subtasks

### T014 — `list_cmd` templates read the full chain
Replace the single `layer_roots.get("org")` ORG template tier with one ORG `TierRoot` per `resolve_pack_chain(repo_root, strict=False)` root (`<root>/missions`). Last-declared-wins falls out of the scan order.

### T015 — `list_cmd` availability reads the full chain
Make `list_available_detailed`'s org scan cover the chain: pass `org_root_chain=resolve_pack_chain(...)` if WP04's widened signature is available; otherwise union a per-root `_scan_layer_dirs` call here. Pack-2 artifacts must appear in `--all`.

### T016 — Remove dead `ProjectContext.org_root`
Delete the field (:82) and the `org_roots[0]` computation (:106). Update `ProjectContext.from_repo` so nothing writes the removed field.

### T017 — Drop `action_governance_bundle` legacy param + migrate its chain call
Remove `effective_org_root`/`org_root` from `_resolve_action_bundle` → `_load_action_governance_bundle`; keep the full-chain path. **Also** migrate the `:209` `effective_org_roots = resolve_existing_org_roots(repo_root)` to `resolve_pack_chain(repo_root, strict=False)` (lenient — a governance bundle degrades on a missing pack, it does not refuse; research.md Decision 4). This clears `action_governance_bundle.py` for the WP06 census. No behaviour change.

### T018 — Update pinned tests
In `test_org_cascade_chain.py::TestListAllLayersBackCompat`: KEEP `test_resolve_layer_roots_org_key_stays_single_path_over_a_chain` and `test_list_all_does_not_crash_over_a_two_pack_chain`; SUPERSEDE `test_list_all_shows_pack_one_but_not_pack_two_unchanged` → rename/rewrite so it asserts `c-directive` (pack 2) **IS** shown (`assert "c-directive" in squashed`). In `test_invocation_context.py`: remove/replace the `ctx.org_root is None` assertion (the attribute no longer exists).

### T019 — Reader regression repros + gates
Issue-pinned `@pytest.mark.regression` through the `charter list` CLI: a pack-2-only `c-directive` is listed under `--all` (red before, green after); same-fixture positive control (pack-1 `a-directive` still listed). ruff/mypy clean.

## Test strategy
```bash
.venv/bin/python -m pytest tests/specify_cli/cli/commands/charter/test_org_cascade_chain.py tests/charter/test_invocation_context.py tests/charter/test_action_governance_bundle_org_fragment.py -q
```

## Branch strategy
Planning base / merge target `kitty/org-pack-chain-authority-stack`; worktree per lane from `lanes.json`. Depends on **WP01** (+ optionally WP04 for the widened signature in T015).

## Definition of Done
- `charter list --all` shows pack-2 artifacts/templates; `ProjectContext.org_root` gone; `action_governance_bundle` param dropped with no behaviour change; `TestListAllLayersBackCompat` disposition applied exactly; NFR-001 intact; ruff/mypy clean.

## Risks & reviewer guidance
- **Deleting the wrong `TestListAllLayersBackCompat` assertion** — reviewer confirms: single-Path KEPT, no-crash KEPT, pack-2-hidden SUPERSEDED. This is the stacking hazard (editing #6005's test file).
- **Accidentally widening `resolve_layer_roots`** — reject (NFR-001).
- **Making `action_governance_bundle` strict** — regression; keep lenient.
