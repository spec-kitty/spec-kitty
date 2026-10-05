---
work_package_id: WP07
title: Behaviour-neutral seam cleanups
dependencies:
- WP06
requirement_refs:
- FR-009
- NFR-001
- NFR-003
- C-001
planning_base_branch: issue-5634-mission-creation-degod
merge_target_branch: issue-5634-mission-creation-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5634-mission-creation-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5634-mission-creation-degod unless the human explicitly redirects the landing branch.
subtasks:
- T033
- T034
- T035
- T036
- T037
phase: Phase 2 - Decision cores and the split
history:
- at: '2026-10-04T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- src/specify_cli/core/mission_creation_decisions.py
- src/specify_cli/core/mission_creation_protected_mint.py
- src/specify_cli/core/mission_creation_meta.py
- src/specify_cli/core/mission_creation_rollback.py
- src/specify_cli/core/mission_creation_commit.py
- src/specify_cli/core/mission_creation_scaffold.py
- src/specify_cli/core/mission_creation_events.py
- tests/core/test_mission_creation_family.py
- tests/core/test_mission_creation_decisions.py
- docs/api/mission-creation-internals.md
- tests/core/test_mission_creation_probe_order.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/core/mission_creation.py
- src/specify_cli/core/mission_creation_decisions.py
- src/specify_cli/core/mission_creation_protected_mint.py
- src/specify_cli/core/mission_creation_meta.py
- src/specify_cli/core/mission_creation_rollback.py
- src/specify_cli/core/mission_creation_commit.py
- src/specify_cli/core/mission_creation_scaffold.py
- src/specify_cli/core/mission_creation_events.py
- tests/core/test_mission_creation_family.py
- tests/core/test_mission_creation_decisions.py
- tests/core/test_mission_creation_probe_order.py
- docs/api/mission-creation-internals.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Behaviour-neutral seam cleanups

## ⚡ Do This First: Load Agent Profile

Run `spec-kitty agent profile show python-pedro` (skill `spk-doctrine-profile-load` / `/ad-hoc-profile-load`) and `spec-kitty charter context --action implement --json`, then apply them.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log and the Activity Log for returned feedback.

---

## Objectives & Success Criteria

After the WP06 split, make the seams match the responsibilities without changing behaviour or **when errors are raised** (spec FR-009, C-001). Four cleanups, each a separate commit so a reviewer can bisect:

1. **Protection resolved at most once per create, memoised at its first-use point (T033).** Today `_target_is_protected` runs in the recreate guard (only when `meta.json` exists, inside `_scaffold_mission_dir`) and again inside the mint (after the scaffold write).
   - Introduce a per-create memo, a small `_ProtectionProbe` object created by the orchestrator and passed down. It resolves `ProtectionPolicy.resolve(write_root)` and `resolve_primary_branch(write_root, bias=False)` **lazily, on first call**, and returns the cached answer after that.
   - Exceptions are not cached: if the first call raises, the exception propagates from that same point, exactly as today.
   - **Never resolve earlier than today.** Do not gather protection facts before the scaffold write (post-specify squad finding; #5704-shaped residue change).
2. **The protected mint is invoked from the orchestrator, not from inside `_build_create_meta` (T034)**, in the same position relative to the other effects: after the coordination-branch mint and before `write_meta`.
   - `_build_create_meta` currently writes meta after the mint mutates `meta["mission_branch"]`. Split it into "build meta dict" → mint (orchestrator) → "write meta", with the same file bytes and key order.
   - `_MetaBuild.minted_mission_branch` keeps its meaning.
3. **A typed rollback journal replaces the `list` holder (T035).** `_coord_rollback_holder: list[_CoordCreateRollbackContext]` becomes a `CreateRollbackJournal` with `record_coord(ctx)` and `coord: _CoordCreateRollbackContext | None`.
   - The private keyword parameter name `_coord_rollback_holder` is part of `_create_mission_core_impl`'s signature. Grep the tests for it. If tests pass it, keep accepting the list form too, through a small adapter, rather than editing tests.
4. **Fan-out is split from the pure file sets in `_build_create_result` (T036).** The hosted fan-out stays an effect, and `created_file_sets` (WP05) is the pure part. Keep the order: compute sets, then fan out.

Done means:

- The golden matrix (WP01/WP02), including the **malformed-protection-config** and **refused-mint orphan + retry** cells, passes with **0 edits** to the golden files.
- The WP03 tests and the covering set pass.
- The structural checks (T037) pass, and each has a planted control.
- `mypy` and `ruff` are clean, and complexity is ≤ 15 (`_build_create_meta` was 11; splitting it should lower it).

## Context & Constraints

- **Do not unify the two `commit_to_target` sources** (spec edge case; the recreate guard reads the parameter, and the mint reads `read_commit_to_target(meta)`). If you are tempted, do not do it: it is out of scope.
- `research/code-grounding.md` Appendix A §4 has the call chain and line refs (pre-split). The split moved these functions to `mission_creation_protected_mint.py`, `mission_creation_meta.py` and `mission_creation_scaffold.py`; follow the routing rule (C-004) for any new cross-module call.
- The WP06 routing check (`tests/core/test_mission_creation_family.py`) must stay green. A new cross-family call from a leaf goes through `_mc.`.
- Update the module map in `docs/api/mission-creation-internals.md` if a responsibility moved (the mint call site).

## Branch Strategy

- **Strategy**: populated by finalize-tasks · **Planning base**: `issue-5634-mission-creation-degod` · **Merge target**: `issue-5634-mission-creation-degod`

## Subtasks & Detailed Guidance

### Subtask T033 – Lazy, memoised protection probe

- Define `_ProtectionProbe(write_root)` with `is_protected(target_branch) -> bool`. It lazily caches `(policy, primary_for_protection)` and delegates to the WP05 core `target_is_protected`.
- The orchestrator creates one probe per create and passes it to `_scaffold_mission_dir` (the recreate guard) and the mint. Keep the old `_target_is_protected(write_root, target_branch)` function as a façade-compatible wrapper if tests call it (grep first).
- Add a unit test: a fake resolver counts calls, two `is_protected` calls give one resolution, and a raising resolver raises on each call (not cached).
- Golden proof: the malformed-config cell is unchanged.

### Subtask T034 – Mint invoked from the orchestrator

- In `_create_mission_core_impl`, right after `_build_create_meta` and before anything that reads `meta_build.minted_mission_branch`, call the mint. Today that happens inside the builder, so the meta write that follows it must move too. Read `_build_create_meta` end to end before cutting.
- Pin the order with a structural check in T037. Re-derive `create_time_target` from `minted_mission_branch` as today (~:2265-2276 pre-split).

### Subtask T035 – Typed rollback journal

- `@dataclass class CreateRollbackJournal: coord: _CoordCreateRollbackContext | None = None; def record_coord(...)`. `create_mission_core` passes a journal; the impl records into it, and the except-path reads `journal.coord`.
- If any test passes `_coord_rollback_holder=[...]`, accept both forms.

### Subtask T036 – Fan-out split

- `_build_create_result` computes file sets via the pure core, then calls the fan-out effect. If the fan-out is already a separate call, this subtask is a no-op. Record that and skip it.

### Subtask T037 – Structural checks

Add to `tests/core/test_mission_creation_family.py`:

- the coordination-routed predicate is defined exactly once across the family (AST `FunctionDef` name search), and no leaf re-implements it (no inline `topology in (MissionTopology.COORD, MissionTopology.LANES_WITH_COORD)` pattern; grep for both enum members appearing together in one comparison);
- the meta builder function body contains no call to the mint function;
- one planted control per check (in-memory source mutation).

## Test Strategy

```bash
.venv/bin/python -m pytest tests/core/test_mission_creation_family.py tests/core/test_mission_creation_decisions.py tests/core/test_mission_creation_purity.py tests/_support/test_mission_creation_source.py -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/core/test_mission_creation_golden_*.py tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py tests/specify_cli/cli/commands/agent/test_mission_create_topology_fallback.py tests/core/test_mission_creation_branch_coverage.py tests/core/test_mission_creation_invariants.py -n 4 --dist loadfile -q
PWHEADLESS=1 .venv/bin/python -m pytest $(grep '^tests/' <(sed -n '/^## Appendix — covering test set/,/^```$/p' kitty-specs/mission-creation-degod-01M44467/research/test-remediation.md)) -n 4 --dist loadfile -q
.venv/bin/python -m pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_single_mission_surface_resolver.py tests/core/test_adapters.py -q
git diff <lane-base> -- tests/core/golden tests/core/test_mission_creation_golden_* tests/core/_mission_create_golden.py tests/specify_cli/cli/commands/agent/golden   # must be empty
for f in src/specify_cli/core/mission_creation*.py; do .venv/bin/mypy "$f" || exit 1; done
uv run --frozen ruff check src/specify_cli/core/ tests/core && uv run --frozen ruff check --select C901 src/specify_cli/core/mission_creation*.py
make test-fast
```

## Risks & Mitigations

- **Earlier protection resolution** changes residue: lazy plus memoised, and the golden malformed-config cell catches it.
- **Meta byte drift** when splitting build and write: the golden `meta_key_order` dimension catches it.
- **Over-reach**: four cleanups only. Anything else is a follow-up note in `traces/approach.md`.

## Review Guidance

- Read each of the 4 commits separately; each must keep the golden matrix green.
- Plant one early protection resolution (move the probe call before the scaffold write) and see the malformed-config cell go red.

## Post-tasks squad folds (binding)

1. **Proof of "resolved at most once".** Reuse WP05's `GIT_TRACE` approach (`tests/core/test_mission_creation_probe_order.py`, sequentially owned here). The path that resolves protection twice today is an **idempotent re-create of a `SINGLE_BRANCH` mission on an UNPROTECTED target with `meta.json` present**. The recreate guard resolves protection, gets False and does not refuse, and the mint resolves it again. (On a protected target the guard refuses first, so there is no second resolution.) For that path, assert the git subcommands `resolve_primary_branch` issues now run once, captured before and after T033, and that none runs before the scaffold write.
2. The malformed-config golden cell WP07 relies on is the **wrong-shape `protection:` block** (`ProtectionConfigError`), WP01 fold 4(b).
3. Record planted breaks as `git diff` patch blocks in the Activity Log.

## Activity Log

- 2026-10-04T20:00:00Z – system – Prompt created
