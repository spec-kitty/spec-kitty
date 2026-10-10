---
work_package_id: WP01
title: Pack chain authority
dependencies: []
requirement_refs:
- FR-001
- FR-007
- NFR-004
planning_base_branch: kitty/org-pack-chain-authority-stack
merge_target_branch: kitty/org-pack-chain-authority-stack
branch_strategy: Planning artifacts for this mission were generated on kitty/org-pack-chain-authority-stack. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/org-pack-chain-authority-stack unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-pack-chain-authority-01M4JXF5
base_commit: aabcd7ab7a8f6a8e75f7e5712a503b77f058f97a
created_at: '2026-10-10T14:09:33.335409+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Foundation
history:
- at: '2026-10-10T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/layer_roots.py
create_intent:
- tests/charter/activation/test_resolve_pack_chain.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/layer_roots.py
- src/charter/offering/drg/org_pack_config.py
- tests/charter/activation/test_layer_roots.py
- tests/charter/activation/test_resolve_pack_chain.py
- tests/charter_offering/drg/test_org_pack_config_resolve_existing_org_roots.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Pack chain authority

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Introduce **one** authority for the org-pack chain and make the existing lenient/strict spellings delegate to it. This WP is the foundation every other WP depends on.

Done when:
- `resolve_pack_chain(repo_root, *, strict: bool) -> list[Path]` exists in `src/charter/activation/layer_roots.py` and is the single producer of the ordered, existing org-pack chain (last-declared-wins order).
- `strict=False` returns the existing-filtered chain (behaviourally identical to today's `resolve_existing_org_roots`).
- `strict=True` raises on a **declared-but-missing** pack, naming the unfetched pack and the `spec-kitty charter fetch` remedy (behaviourally identical to today's `require_declared_org_roots`).
- `resolve_org_root_chain` becomes a thin delegate to `resolve_pack_chain(strict=False)` (kept green for callers migrated in later WPs; removed at integration).
- `resolve_org_dirs` resolves its chain through `resolve_pack_chain(strict=False)` while preserving its per-dropped-root WARNING byte-for-byte (NFR-004).
- A red-first, issue-pinned regression test proves both postures through the authority.
- `ruff check`, `ruff format --check`, and `mypy` are clean on the two edited modules; no function exceeds complexity 15.

## Context & Constraints

Spec: `kitty-specs/org-pack-chain-authority-01M4JXF5/spec.md` (FR-001, FR-007, NFR-004).
Research/decisions: `research.md` Decision 1, 4. Data model: `data-model.md` (API: `resolve_pack_chain`).

Current landscape (verified file:line):
- `src/charter/offering/drg/org_pack_config.py`:
  - `resolve_org_roots` (:481) — unfiltered, declaration order.
  - `require_declared_org_roots` (:498) — **strict**: reads the registry `strict=True` and raises naming the unfetched pack; **reuse its message/logic** for the strict posture.
  - `resolve_existing_org_roots` (:522) — lenient, existing-filtered (silent drop at :540).
  - `resolve_org_dirs` (:543) — lenient + per-dropped-root WARNING (:567). Re-point onto the authority; keep the WARNING.
- `src/charter/activation/layer_roots.py`:
  - `resolve_org_root_chain` (:48) — today delegates to `resolve_existing_org_roots`. Make it delegate to `resolve_pack_chain(strict=False)`.
  - `resolve_layer_roots` (:20) — **DO NOT CHANGE**; its single-`Path` `roots["org"]` (the `break` at :40-43) is a load-bearing back-compat contract (NFR-001). It legitimately calls `resolve_org_roots` inside this module — that stays.

Constraints:
- Do not widen `resolve_layer_roots`'s `dict[str, Path]` (NFR-001).
- "Declared-but-missing" means declared-and-absent. **Zero declared packs → empty chain, never a raise**, in either posture (edge case).
- Layering: authority stays in the `charter` tier; returns `list[Path]` data (C-001).

## Subtasks

### T001 — Add `resolve_pack_chain(repo_root, *, strict)`
- In `layer_roots.py`. Lenient branch ≡ `resolve_existing_org_roots(repo_root)`. Strict branch ≡ `require_declared_org_roots(repo_root)` semantics (raise naming the first declared-but-absent pack).
- Keep it a thin composition over the `org_pack_config` primitives — it is the only module (besides `org_pack_config` itself) allowed to call them (WP06 gate).
- Docstring: state it is the single chain authority and that `strict` toggles fail-closed vs existing-filtered.

### T002 — Re-point `resolve_org_root_chain`
- Replace its body with `return resolve_pack_chain(repo_root, strict=False)`. Add a one-line note that it is a transitional delegate pending caller migration (WP02/WP04) and integration-time removal.

### T003 — Re-point `resolve_org_dirs` onto the authority
- Change its existing-chain source from `resolve_existing_org_roots(...)` to `resolve_pack_chain(repo_root, strict=False)`.
- **Preserve** the per-dropped-root WARNING exactly (it still compares the declared set `resolve_org_roots(...)` against the existing chain). The WARNING wording, level, and per-drop cardinality must not change (NFR-004).

### T004 — Strict error message
- The strict posture reuses `require_declared_org_roots`'s message: name the unfetched pack and point to `spec-kitty charter fetch`. Do not invent a new message shape.

### T005 — Red-first regression repro (ATDD)
- New `tests/charter/activation/test_resolve_pack_chain.py`, issue-pinned: `@pytest.mark.regression` with the issue reference per ADR 2026-07-17-1.
- Same-fixture positive+negative: a two-pack fixture (`pack1`, `pack2` both existing) → lenient returns `[pack1, pack2]` in declaration order; then drop `pack2` from disk → strict **raises** naming `pack2`, lenient returns `[pack1]`.
- Prove non-vacuity: assert the strict raise message contains the pack name AND the fetch remedy; assert zero-declared-packs returns `[]` with no raise in both postures.
- The test must call `resolve_pack_chain` directly (the production authority), not a helper.

### T006 — Quality gates
- `uv run --frozen ruff format <files>` then `make format-check-files FILES=...`; `ruff check`; `mypy` on the two modules. Complexity ≤15.

## Test strategy

Targeted only (CI owns full suites):
```bash
.venv/bin/python -m pytest tests/charter/activation/test_resolve_pack_chain.py tests/charter/activation/test_layer_roots.py tests/charter_offering/drg/test_org_pack_config_resolve_existing_org_roots.py -q
```
Red-first: write T005 first and watch it fail (resolve_pack_chain missing), then implement.

## Branch strategy

Planning base / merge target: `kitty/org-pack-chain-authority-stack` (stacked on PR #6005). Execution worktrees are allocated per lane from `lanes.json`; do not pick a base branch manually. This WP has no dependencies — it is the foundation.

## Definition of Done

- All six subtasks recorded done via `spec-kitty agent tasks mark-status`.
- `resolve_pack_chain` is the single authority; `resolve_org_root_chain` and `resolve_org_dirs` delegate to it; `resolve_layer_roots` unchanged.
- Red-first regression test green after implementation; targeted suites green.
- ruff/mypy clean; complexity ≤15.

## Risks & reviewer guidance

- **NFR-001 regression**: any change to `resolve_layer_roots`'s return type or the `roots["org"]` single-Path is a defect — reviewer must reject.
- **Silent strictness**: the strict posture must not fire when zero packs are declared — reviewer must see a test for it.
- **WARNING drift**: `resolve_org_dirs`'s per-drop WARNING must be byte-identical (NFR-004) — reviewer checks the existing org_pack_config tests stay green.
