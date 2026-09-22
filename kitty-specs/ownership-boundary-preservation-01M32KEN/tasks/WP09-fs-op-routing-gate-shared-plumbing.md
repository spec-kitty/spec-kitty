---
work_package_id: WP09
title: Non-vacuous FS-op routing gate + shared plumbing + CHANGELOG
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
- WP06
- WP07
- WP08
requirement_refs:
- FR-010
- NFR-002
- NFR-004
- NFR-006
planning_base_branch: fix/ownership-boundary-preservation
merge_target_branch: fix/ownership-boundary-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/ownership-boundary-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ownership-boundary-preservation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ownership-boundary-preservation-01M32KEN
base_commit: 047b0b69d9683fff3c309c7a1918d84c13bef39a
created_at: '2026-09-22T07:58:55.552286+00:00'
subtasks:
- T024
- T025
- T026
phase: Phase 3 - Non-vacuous gate + closeout
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_mutation_ownership_routing.py
- tests/architectural/_destructive_op_census.py
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_mutation_ownership_routing.py
- tests/architectural/_destructive_op_census.py
- tests/architectural/test_destructive_op_routing.py
- tests/architectural/_baselines.yaml
- CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – Non-vacuous FS-op routing gate + shared plumbing + CHANGELOG

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ Binding post-tasks corrections (supersede any conflicting text below)

- **Routed sites are LITERAL-FREE** (the guard performs the delete), so the census buckets are
  {inside `asset_preservation`'s guard implementation — the chokepoint} ∪ {frozen allowlist (safe
  ops + the `rmdir` empty-only category)}. A NEW raw destructive literal at any migration/init site
  is neither ⇒ it FAILS the gate by construction (contract C3.3).
- **Positive-routing module set is PINNED + completeness-checked** to the WP02–WP08
  `authoritative_surface` set: `cli/commands/init.py` + `m_3_2_0rc45`, `m_3_1_1`, `m_0_10_0`,
  `m_0_10_2`, `m_2_0_11`, `m_2_1_2`, `m_2_2_0`, `m_3_2_0rc43`, `m_0_6_7` (+ `m_unify` iff B4 routed).
  Dropping a module from the set FAILS the gate. Each routed module must carry a call into
  `asset_preservation` AND no raw destructive literal (contract C3.4).
- **Reject, don't absorb.** The gate MUST reject an un-rationalized user-content op (e.g. a leftover
  `m_0_10_0:229`) rather than silently absorbing a still-raw site into the allowlist. The guard's own
  internal `rmtree`/`unlink` is the allowlisted chokepoint.

## Objectives & Success Criteria

Prove the charter class closed **by construction** with a non-vacuous architectural gate, on shared
plumbing (single authority — DIRECTIVE_044), and record the closeout. This WP lands LAST — its
census + positive-routing assertions go green only once every routing WP (WP02–WP08) is final.

- `tests/architectural/_destructive_op_census.py` holds the shared AST census / allowlist-diff /
  self-mutation plumbing; BOTH `test_destructive_op_routing.py` (existing git gate) and the new
  FS-op gate consume it.
- `tests/architectural/test_mutation_ownership_routing.py` performs a LIVE AST census over
  `cli/commands/init.py` + `upgrade/migrations/*.py`; every op is inside the guard, routed via the
  guard chokepoint (no raw literal), or a frozen rationalized allowlist member; a NEW un-routed op
  FAILS; dropping one allowlist entry FAILS (self-mutation both directions); a per-routed-module
  positive-routing assertion holds.
- A shrink-only baseline is registered in `_baselines.yaml`.
- `CHANGELOG.md` records the data-loss class closure as a bug-fix — **no `__init__.py` / version
  bump** (C-004).
- **Success**: `pytest tests/architectural -q` green (new gate + existing git gate + layer rules).

## Context & Constraints

- **Requirement refs**: NFR-002, NFR-004, NFR-006, SC-003, SC-005, FR-010.
- **Reuse anchors** (verified on base, `test_destructive_op_routing.py`): `_iter_py_files:72`,
  `_parse:76`, `_module_string_constants:83`, `_resolve_token:111`, `_diff_against_allowlist:222`,
  `_ALLOWLIST:238`, `test_removing_an_allowlist_entry_reproduces_a_gate_failure:498`,
  `test_scanner_detects_a_planted_unrouted_worktree_remove_force:450`,
  `test_live_worktree_removal_sites_route_through_the_guard:358`. The existing gate scans git argv
  literals; the new one scans Python FS `ast.Call`s — complementary, shared machinery.
- **Op vocabulary** (from [data-model.md](../data-model.md)): `shutil.rmtree`, `Path.unlink`,
  `shutil.move`, `Path.rmdir`, `os.unlink`/`os.remove`, plus the `_safe_rmtree`/`_safe_unlink`
  wrappers. `rmdir`/`os.rmdir` are an empty-only category (raise on non-empty ⇒ cannot silently
  lose content) — a rationalized allowlist class (the ~10 sites enumerated in data-model.md).
- **The allowlist is computed against the LIVE census** — the line numbers in data-model.md are
  illustrative and self-correct; enumerate the real ephemeral-scratch/worktree-teardown/
  broken-symlink/relocation/already-guarded/non-user-surface/wrapper categories with a one-line
  rationale each (NFR-006).
- **Design**: [contracts/ownership-guard-contract.md](../contracts/ownership-guard-contract.md) C3
  (all five gate invariants); [research.md](../research.md) Decision 4; [spec.md](../spec.md)
  NFR-002 / SC-003 / SC-005.
- **Caveat to document**: positive routing is MODULE-COARSE — per-path preservation (e.g.
  `command-templates` preserved while `templates` deleted at the single `init.py:1568` literal) is
  proven by the behavioural WP03 tests, NOT the gate; state this in the gate so a reader does not
  over-trust it (contract C3.4).

## Branch Strategy

- **Strategy**: shared-lane
- **Planning base branch**: fix/ownership-boundary-preservation
- **Merge target branch**: fix/ownership-boundary-preservation

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T024 – Extract shared census plumbing (single authority)

- **Purpose**: DIRECTIVE_044 — one authoritative AST-census/self-mutation harness, not a copy.
- **Steps**:
  1. Create `tests/architectural/_destructive_op_census.py` and MOVE the reusable helpers out of
     `test_destructive_op_routing.py`: `_iter_py_files`, `_parse`, `_module_string_constants`,
     `_resolve_token`, `_diff_against_allowlist`, and the planted-op + drop-one-entry self-mutation
     harness. Keep them generic (parametrized by the op/argv classifier and the module set).
  2. Refactor `test_destructive_op_routing.py` to import them from `_destructive_op_census.py` — its
     git-argv classifier and `_ALLOWLIST` stay in that file; only the shared machinery moves.
  3. Confirm the existing git gate stays GREEN after the refactor (no behavior change).
- **Files**: `tests/architectural/_destructive_op_census.py`,
  `tests/architectural/test_destructive_op_routing.py`.
- **Notes**: a leading-underscore module name keeps pytest from collecting it as a test file.

### Subtask T025 – Build the FS-op routing gate

- **Purpose**: The non-vacuous class-closure proof.
- **Steps**:
  1. `test_mutation_ownership_routing.py`: LIVE AST census over `cli/commands/init.py` +
     `upgrade/migrations/*.py` for the op vocabulary above (resolving module-level string-constant
     path indirections via the shared `_module_string_constants`/`_resolve_token`).
  2. Classify each op ∈ {inside `asset_preservation` guard impl} ∪ {routed via the guard chokepoint
     — no raw destructive literal at the site} ∪ {frozen, individually-rationalized, shrink-only
     `_ALLOWLIST`}. A NEW un-routed op FAILS.
  3. **Op-vocabulary EXHAUSTIVENESS self-test**: assert the scanned attribute set covers every
     `shutil`/`os`/`pathlib` destructive method appearing in the module set, so a future
     `os.remove`/`rmdir` cannot silently evade the census (contract C3.2).
  4. **POSITIVE-routing assertion per routed module**: each routed fix-site module contains a call
     into `asset_preservation` (module-coarse, mirroring
     `test_live_worktree_removal_sites_route_through_the_guard`). Document that per-path guarantees
     ride on the behavioural tests, not the gate (C3.4).
  5. **`rmdir` empty-only category**: allowlist the enumerated `rmdir` sites with a one-line
     rationale (raises on non-empty ⇒ cannot lose content).
  6. **Self-mutation BOTH directions**: a planted un-routed op ⇒ detected/FAIL; dropping one real
     `_ALLOWLIST` entry ⇒ reproduces the gate failure. Shrink-only (a vanished site warns; growth
     FAILS — charter Burn-down Policy).
  7. Register the shrink-only baseline in `tests/architectural/_baselines.yaml`.
  8. Fold in the B4 allowlist entry if WP08 resolved B4 as compiled-only.
- **Files**: `tests/architectural/test_mutation_ownership_routing.py`,
  `tests/architectural/_baselines.yaml`.
- **Edge cases**: `_safe_rmtree`/`_safe_unlink` wrappers count as ops (decision at their call site);
  the guard's OWN implementation lives in `src/`, not the scanned test-side module set — the census
  scans the `specify_cli` module set, so guard-internal ops are the `asset_preservation` package
  (not in `init.py`/`migrations/`).

### Subtask T026 – CHANGELOG entry (closeout)

- **Purpose**: Record the class closure honestly.
- **Steps**:
  1. Add a `CHANGELOG.md` entry: the data-loss class is closed — `init` and the upgrade migrations
     now preserve unprovable user assets (commands, skills, command-templates, governance, scripts)
     instead of deleting by name; genuinely package-owned targets are still removed.
  2. Note it is a **bug-fix**: no `src/specify_cli/__init__.py` change ⇒ no version bump required
     (C-004). Reference #4859, #4861, #4862, epic #4792 (closed via #4861), epic #3347 (advanced).
- **Files**: `CHANGELOG.md`.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/architectural/test_mutation_ownership_routing.py \
  tests/architectural/test_destructive_op_routing.py -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural -q   # new module + gate ⇒ cross-cutting
uv run --frozen mypy --strict tests/architectural/_destructive_op_census.py \
  tests/architectural/test_mutation_ownership_routing.py
```

- This is a cross-cutting change (new arch module + gate) — run the FULL `tests/architectural/`
  suite and record counts in the PR.

## Risks & Mitigations

- **Refactor breaks the existing git gate** — extract without behavior change; re-run
  `test_destructive_op_routing.py` and its self-mutation tests.
- **Vacuous gate** — the positive-routing assertions + the drop-one-entry self-mutation prevent a
  gate that passes by allowlisting a target op (SC-003).
- **Over-trusted gate** — document the module-coarse caveat (per-path is behavioural).
- **Baseline drift** — shrink-only; growth must FAIL CI.

## Review Guidance

- Confirm the shared plumbing is a single authority consumed by both gates and the git gate stays
  green.
- Confirm all five C3 invariants: census, exhaustiveness self-test, routed-or-allowlisted,
  positive-routing per module, self-mutation both directions.
- Confirm every allowlist entry carries a one-line rationale and the baseline is shrink-only.
- Confirm the CHANGELOG entry states bug-fix / no version bump and that
  `src/specify_cli/__init__.py` was NOT touched.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

- {{TIMESTAMP}} – system – Prompt created.
