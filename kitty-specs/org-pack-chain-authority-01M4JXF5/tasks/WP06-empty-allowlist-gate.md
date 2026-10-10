---
work_package_id: WP06
title: Empty-allowlist architectural gate (charter-surface scope)
dependencies:
- WP02
- WP03
- WP04
- WP05
- WP07
- WP08
requirement_refs:
- FR-006
- NFR-002
planning_base_branch: kitty/org-pack-chain-authority-stack
merge_target_branch: kitty/org-pack-chain-authority-stack
branch_strategy: Planning artifacts for this mission were generated on kitty/org-pack-chain-authority-stack. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/org-pack-chain-authority-stack unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-pack-chain-authority-01M4JXF5
base_commit: a86cdb995f9bf9ffb92d9d3401b8a9d1c40e23a6
created_at: '2026-10-10T15:12:45.363909+00:00'
subtasks:
- T032
- T033
- T034
- T035
phase: Phase 3 - Enforcement
history:
- at: '2026-10-10T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/test_org_pack_chain_single_authority.py
create_intent:
- tests/architectural/test_org_pack_chain_single_authority.py
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_org_pack_chain_single_authority.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Empty-allowlist architectural gate (charter-surface scope)

## ⚡ Do This First: Load Agent Profile

Use `/spk-charter-profile-load` to load the frontmatter profile first.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Lock the single-authority invariant with an architectural AST-census gate that ships with an **empty allowlist** (Standing Order #5 / ADR 2026-09-30-1). This WP lands **last** — it goes red until every in-scope migration (WP02, WP03, WP04, WP05, WP07, WP08) is done.

**Scope (operator ruling — path-scoped + follow-up):** the census covers **`src/charter/activation/**` and `src/specify_cli/cli/commands/charter/**`** only. The non-charter callers (runtime/tool_surface/review/skills/…) are a named follow-up; do NOT census them here. The allowlist is literally empty — the *scope*, not an allowlist entry, is what bounds this mission (NFR-002: no ratchet).

**Why the `charter.offering` tier is OUT of census scope (important):** the authority `resolve_pack_chain` lives in `charter.activation.layer_roots`, and `charter.offering` modules MUST NOT import `charter.activation` (enforced by `tests/architectural/test_charter_offering_does_not_import_activation.py`). The offering tier therefore cannot use `resolve_pack_chain`; its chain authority IS its own tier primitives in `org_pack_config.py`. So offering-tier callers (e.g. `charter/offering/resolver.py` calling `resolve_org_roots`) are legitimately NOT governed by this gate and are NOT a violation. Censusing the offering tier would wrongly red-flag them with no valid fix. The gate governs exactly the tiers that CAN and SHOULD route through the authority: `charter.activation` and the charter CLI.

Done when:
- `tests/architectural/test_org_pack_chain_single_authority.py` exists and, over the **in-scope** paths, forbids — outside the authority module (`src/charter/activation/layer_roots.py`) and the primitives' own module (`src/charter/offering/drg/org_pack_config.py`) — any call to a chain primitive (`resolve_org_roots`, `resolve_existing_org_roots`, `require_declared_org_roots`, `resolve_org_root_chain`) or any iteration of `load_pack_registry().packs` to assemble roots.
- The allowlist is a literal empty collection with no shrink-only ratchet.
- Non-vacuity controls: a scanned-file-count floor, a planted-violation positive control, an owner-bypass control proving the census sees the authority module.
- The gate is green over the in-scope tree (all in-scope migrations complete).

## Context & Constraints

Spec: FR-006, NFR-002. Depends on **WP02, WP03, WP04, WP05, WP07, WP08**. Mirror `tests/architectural/test_remote_contact_owner.py` / `test_evidence_gates_check_origin.py` (AST-census + non-vacuity-control shape).

Discriminator (module-ownership, research.md Decision 5): the forbidden symbols are legitimate ONLY inside `layer_roots.py` (authority) and `org_pack_config.py` (primitives' own module). `resolve_layer_roots`'s single-root `resolve_org_roots` call lives in `layer_roots.py`, so module-ownership exempts it automatically — do not special-case it.

Census CALL-based, not import-based: a re-export module (e.g. `charter/drg.py`) that only imports/`__all__`-lists the primitives is NOT a violation (WP07 migrates its re-export separately for hygiene, but the gate keys on `Call` nodes). Docstring mentions are not violations.

Known residuals that the gate must tolerate (all inside owner modules → exempt): the transitional `resolve_org_root_chain` delegate in `layer_roots.py` (WP01; dead-code removal is an integration sweep, not a WP). Do NOT edit `layer_roots.py` here.

## Subtasks

### T032 — Census gate (path-scoped)
New `tests/architectural/test_org_pack_chain_single_authority.py`. Walk `src/charter/activation/**/*.py` and `src/specify_cli/cli/commands/charter/**/*.py` with `ast` (do NOT walk `src/charter/offering/**` — see scope note above); for each in-scope module that is not the authority module (`src/charter/activation/layer_roots.py`), flag a `Call` to any of the four primitive names and any `.packs` access on a `load_pack_registry(...)` result used to build a list of roots. (The primitives' own module `org_pack_config.py` is in the excluded offering tier, so it needs no explicit owner exemption; `layer_roots.py` is the one in-scope exempt owner.) Empty allowlist constant (`_ALLOWED: frozenset[str] = frozenset()`), asserted empty by the test.

### T033 — Non-vacuity controls
- **File-count floor**: assert the census scanned ≥ N in-scope modules.
- **Planted-violation positive control**: feed a synthetic in-scope module source calling `resolve_existing_org_roots` outside the owner set and assert it is flagged.
- **Owner-bypass control**: feed the authority module's shape and assert it is NOT flagged.

### T034 — Confirm the invariant over the charter scope
Run the census over the real in-scope tree and assert zero violations. If a surface still calls a primitive directly, the gate names it — the fix belongs in that surface's WP (report it), not here.

### T035 — Quality gates
ruff/mypy clean on the new test module; complexity ≤15.

## Test strategy
```bash
.venv/bin/python -m pytest tests/architectural/test_org_pack_chain_single_authority.py -q
```
Per `NO_FULL_HEAVY_SUITES_IN_MISSION`, run only this gate file, not the whole `tests/architectural/` directory.

## Branch strategy
Planning base / merge target `kitty/org-pack-chain-authority-stack`; worktree per lane from `lanes.json`. Depends on **WP02, WP03, WP04, WP05, WP07, WP08** (lands last).

## Definition of Done
Gate exists, path-scoped, empty allowlist, all three non-vacuity controls; green over the in-scope tree; planted violation proves non-vacuity; owner-bypass proves the census sees the authority. ruff/mypy clean.

## Risks & reviewer guidance
- **Vacuous gate**: without the planted-violation control a green gate proves nothing — reviewer confirms the control turns it red.
- **Scope drift**: censusing the whole tree here would go red on the ~12 follow-up files — reviewer confirms the census is path-scoped to the charter surfaces.
- **Import-based false positives**: the census is call-based; a re-export module must not be flagged for an import alone.
- **Ratchet smell**: the allowlist must be literally empty — reject any seeded entry (NFR-002).
