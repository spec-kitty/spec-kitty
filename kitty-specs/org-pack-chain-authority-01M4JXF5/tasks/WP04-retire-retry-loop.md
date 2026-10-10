---
work_package_id: WP04
title: Retire the retry loop (widen ActiveCharterManager)
dependencies:
- WP01
requirement_refs:
- FR-004
- NFR-001
- NFR-005
planning_base_branch: kitty/org-pack-chain-authority-stack
merge_target_branch: kitty/org-pack-chain-authority-stack
branch_strategy: Planning artifacts for this mission were generated on kitty/org-pack-chain-authority-stack. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/org-pack-chain-authority-stack unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-pack-chain-authority-01M4JXF5
base_commit: 704b1e4578694fe448da6f006f720059f43a021a
created_at: '2026-10-10T14:29:24.471525+00:00'
subtasks:
- T020
- T021
- T022
- T023
- T024
- T025
phase: Phase 2 - Migration
history:
- at: '2026-10-10T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/pack_manager.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/pack_manager.py
- src/specify_cli/cli/commands/charter/activate.py
- tests/charter/test_pack_manager.py
- tests/charter/test_pack_manager_catalog.py
- tests/specify_cli/cli/commands/charter/test_multi_org_pack_chain_5779.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Retire the retry loop (widen ActiveCharterManager)

## ⚡ Do This First: Load Agent Profile

Use `/spk-charter-profile-load` to load the frontmatter profile first.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Retire the `_activate_cascade_target` per-pack retry loop that PR #6005 relies on, by teaching `ActiveCharterManager` to validate availability against the **whole chain** in one scan.

Done when:
- `ActiveCharterManager.activate`/`list_available`/`list_available_detailed`/`_scan_layer_dirs` accept `org_root_chain: list[Path] | None = None`; when supplied, `_scan_layer_dirs` emits one ORG scan pair per chain root **last-declared-first**; when `None`, it falls back to the single `layer_roots["org"]` slot (back-compat).
- `_activate_cascade_target` is removed; the direct activation target calls `manager.activate(...)` once with `org_root_chain=resolve_pack_chain(repo_root, strict=True)`.
- `activate.py`'s own `resolve_org_root_chain` call sites migrate to `resolve_pack_chain`.
- A pack-2-only artifact activates through the single widened scan; the `_org_scan_dirs` flat-wins precedence (NFR-005) and `resolve_layer_roots` dict (NFR-001) are untouched.
- ruff/mypy clean; complexity ≤15.

## Context & Constraints

Spec: FR-004, NFR-001, NFR-005. Depends on **WP01** (`resolve_pack_chain`). This WP supersedes #6005's retry mechanism — #6005 lands first; here we remove it.

Verified file:line:
- `pack_manager.py`: `ActiveCharterManager` is **stateless** (:661, constructed `ActiveCharterManager()` everywhere) — the chain enters via method params, not a constructor. Call chain: `activate` (:685) → `list_available` (:1001) → `list_available_detailed` (:900) → `_scan_layer_dirs` (:869) → `_resolve_layer_candidate` (:288) → `_resolve_org_layer_dir` (:263).
- `activate.py`: `_activate_cascade_target` (:236-303) substitutes each chain root into `layer_roots["org"]` and retries `manager.activate` once per root (`reversed(org_roots)`, last-declared-first), returning on first success; call site at `:1038`. Chain calls at `:331/:465/:1044/:1066` use `resolve_org_root_chain`.
- Precedence to reproduce: `kind_vocabulary._org_scan_dirs` (:234) already walks a full `list[Path]` with flat-before-legacy, last-declared-first grouping — the new ORG loop in `_scan_layer_dirs` must produce the same union/precedence (pinned by `tests/charter/test_kind_vocabulary_scan_roots.py` — keep green, do not edit).

Constraints:
- Do NOT change `resolve_layer_roots` (NFR-001) or `kind_vocabulary.py` (NFR-005).
- The `org_root_chain=None` fallback must be byte-identical to today's single-slot scan (back-compat for callers that do not pass a chain).
- Verify no test calls `activate(layer_roots=...)` positionally in a way the new kw-param breaks.

## Subtasks

### T020 — Widen `_scan_layer_dirs`
Add `org_root_chain: list[Path] | None = None`. When set, emit one `(ORG, _resolve_org_layer_dir(root, kind))` pair per chain root, last-declared-first; when None, keep the single `roots.get("org")` behaviour.

### T021 — Thread `org_root_chain` through `list_available` / `list_available_detailed`
Add the param and pass it down to `_scan_layer_dirs`. Default `None` preserves every existing caller.

### T022 — `activate` passes the chain; migrate `activate.py` chain calls
`activate` accepts `org_root_chain` and forwards it. In `activate.py`, swap the `resolve_org_root_chain` call sites (:331/:465/:1044/:1066) to `resolve_pack_chain(...)` (strict for the activation availability decision, lenient where the current call was lenient — match today's posture).

### T023 — Remove `_activate_cascade_target`
Delete the helper (:236-303). Replace the call site (:1038) with a single `manager.activate(ctx_project, kind_token, config_id, cascade=False, layer_roots=layer_roots, org_root_chain=resolve_pack_chain(repo_root, strict=True))`. The strict posture gives the #4984 fail-closed behaviour for an unfetched pack.

### T024 — Retry-loop regression repro
Issue-pinned `@pytest.mark.regression`: a two-pack fixture where an artifact lives only in pack 2 — `manager.list_available_detailed(..., org_root_chain=[pack1, pack2])` includes it (positive control); with `org_root_chain=None` the single-slot fallback is byte-identical. Assert `_activate_cascade_target` is gone (`not hasattr(activate_module, "_activate_cascade_target")`). Prove non-vacuity: pack-1 artifact still resolves.

### T025 — Quality gates + pins
ruff/mypy clean. Confirm green (unchanged): `tests/charter/test_pack_manager.py`, `test_pack_manager_catalog.py`, `tests/charter/test_mission_type_path_layout_ssot.py`, `tests/charter/test_kind_vocabulary_scan_roots.py`.

## Test strategy
```bash
.venv/bin/python -m pytest tests/charter/test_pack_manager.py tests/charter/test_pack_manager_catalog.py tests/charter/test_mission_type_path_layout_ssot.py tests/charter/test_kind_vocabulary_scan_roots.py tests/specify_cli/cli/commands/charter/test_multi_org_pack_chain_5779.py -q
```

## Branch strategy
Planning base / merge target `kitty/org-pack-chain-authority-stack`; worktree per lane from `lanes.json`. Depends on **WP01**.

## Definition of Done
- `org_root_chain` threaded through the four methods; `_activate_cascade_target` removed; single-scan activation of a pack-2 artifact works; fallback byte-identical; NFR-001/NFR-005 intact; pins green; ruff/mypy clean.

## Risks & reviewer guidance
- **Precedence mismatch**: the new ORG loop must reproduce `_org_scan_dirs`'s last-declared-first/flat-wins union — reviewer checks `test_kind_vocabulary_scan_roots.py` stays green.
- **Fallback drift**: `org_root_chain=None` must be byte-identical to today — reviewer checks `test_pack_manager*` stay green unchanged.
- **Stacking**: this edits #6005's `_activate_cascade_target`; reviewer confirms the single-scan path covers every case the retry loop did (incl. the aggregated-failure diagnostic).
