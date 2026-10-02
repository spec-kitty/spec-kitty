---
affected_files: []
cycle_number: 2
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-02T04:31:38Z'
reviewer_agent: claude
wp_id: WP09
---

# WP09 review — cycle 2 (reviewer-renata) — CHANGES REQUESTED

Cycle-1 folds verified: B2, B3 (WP17 allocation accepted by the coordinator), B4, N1 and N2.
One blocker remains: the **second half of the B1 ruling is not met**.

## B1-residual (BLOCKING): a coordination-routed topology with no declared branch still degrades to PRIMARY

The coordinator's B1 ruling has two halves:

1. Fall back to the repository-root `meta.json` when the owned copy lacks `coordination_branch`. **Met** by `0e64a3b66e`.
2. If a coordination-routed topology STILL has no declared branch after that fallback, **REFUSE — never degrade to PRIMARY**. **Not met.**

### Reproduction

I wrote a temporary probe test and deleted it afterwards.

Setup:

- fixture: `make_prefix_coord_mission(tmp_path, topology, worktree="empty")`;
- strip `coordination_branch` from every `meta.json` copy, keeping `topology` (`coord` / `lanes_with_coord`) intact;
- for the owned arm, add a real worktree as the owned checkout and use `mint_test_fact(..., topology=topology)`;
- call `establish_coord_write_location(repo_root, slug, STATUS_STATE, owned=...)`.

| arm | topology | result |
|---|---|---|
| owned | coord | **no refusal → `surface == "primary"`** |
| owned | lanes_with_coord | **no refusal → `surface == "primary"`** |
| non-owned | coord | **no refusal → `surface == "primary"`** |
| non-owned | lanes_with_coord | **no refusal → `surface == "primary"`** |

### Root cause

In `src/specify_cli/coordination/coord_seed.py`, `establish_coord_write_location` does:

```python
raw_branch = meta.get("coordination_branch")
coordination_branch = str(raw_branch) if raw_branch else None
if coordination_branch is None:
    return _primary_write_location(repo_root, mission_slug, kind, owned)
```

- The branch is the only gate. The stored topology (`meta["topology"]`, and on the owned arm `owned.topology`) is never consulted.
- `read_primary_meta`'s second return value is discarded (`_declares_coordination`), and it only means "a branch string is present", so it is not a topology gate either.
- The non-owned half of this shape predates WP09 (identical at `7afabf4eff`). The owned arm, which `a6b4165638` and `0e64a3b66e` routed onto this accessor, now inherits the same fail-open.

### The same shape on the WP09-touched consumer

In `src/runtime/next/runtime_bridge.py::_wrap_with_decision_git_log`, the non-owned arm takes `location = write_dir(DECISION_LOG)` whenever `coord_routing_topology` is True (stored topology). It then uses `location.path` without checking `location.surface`.

A coord-topology Mission whose meta lacks the branch therefore gets a `DecisionGitLog` on the PRIMARY dir. That is exactly the "quiet PRIMARY write" which the B1 fallback comment itself says the accessor contract forbids.

### Required

- Topology-gate the degrade in `establish_coord_write_location`.
- **Decision required — the coordinator chooses the remedy.** The open question is how the gate behaves when the stored topology routes through coordination (canonical predicate `routes_through_coordination` over `read_topology(meta)`; on the owned arm also `owned.topology`) and no branch is declared after the fallback. Two options:
  - (a) raise a typed refusal; the CLI needs a renderer and `.code`. This is what the B1 ruling asks for.
  - (b) derive the deterministic branch name (`lanes.branch_naming`) and materialize.
- **Why (b) is on the table — the O8 tension.** The cycle-1 comment in `runtime_bridge.py` (≈L364-381) states that the exercised O8 owned shape (`tests/integration/test_owned_next_runtime.py`) mints its coordination branch through `CoordinationWorkspace`'s deterministic naming WITHOUT recording it in `meta.json`.
  - With (a), any owned `write_dir` caller in that shape refuses, so its blast radius must be measured.
  - The `runtime_bridge` owned arm is unaffected, because it stays on the historical ladder.
- **Precedent for the topology gate:** `_mission_routes_through_coordination` / `routes_through_coordination` already classify from the stored topology.
- **Keep:** legacy or topology-less meta (no `topology`, `read_topology` classifies it as coord-less) still returns PRIMARY. Only a coordination-routed stored topology refuses.
- **Defence in depth in `_wrap_with_decision_git_log`:** when `coord_routing_topology` holds and `location.surface != "coordination"`, raise `DecisionGitLogUnavailable` with the chained code. Never build a `DecisionGitLog` on the primary dir for a coord-routed Mission.
- **Red-first tests:** both arms × {coord, lanes_with_coord} with the branch stripped expect the refusal (or the derived-branch materialization, under (b)). Add a positive control: a topology-less legacy meta still gives PRIMARY.

## Verified (no action)

- **B1 first half:** `test_owned_arm_translates_workspace_failure` is green (`tests/coordination/test_coord_seed.py -k owned`, 3/3). The O8 suite results are in the handback counts.
- **B2:** `-> NoReturn` on both handlers, and all 8 `# pragma: no cover` returns are deleted. The WP09 diff vs `7afabf4eff` contains no `pragma: no cover` directive; the only hit is a docstring sentence. `mypy --strict` on `decision.py` is clean.
- **B3:** the three-way agreement test is present. The legacy bare-dir stream fold is allocated to WP17 (coordinator accepted).
- **B4:** the `emit._mission_dir` `write_dir` → `read_dir` mutant is now **killed**: `test_emit_decision_opened_seeds_pre_fix_empty_mission_directly[COORD]` and `[LANES_WITH_COORD]` both fail under the mutant.
- **N1:** the owned arm composes through `coord_mission_dir_name(mission_slug, mid8=_mid8)`.
- **N2:** the typed `code` / `error_code` is chained into the `DecisionGitLogUnavailable` message.

## Non-blocking, out of WP09 scope (for the coordinator to file or allocate)

- The B3 test docstring discloses a pre-existing defect. `_mission_routes_through_coordination` reads `meta.json` via `placement_seam(...).read_dir(PRIMARY_METADATA)` without canonicalizing a **bare** (non-mid8-embedding) handle.
  - As a result, it classifies a genuinely coord-routed bare-slug Mission as coord-less.
  - `_wrap_with_decision_git_log` then takes the coord-less arm: decisions go to the primary checkout, with only a log warning on failure.
  - It is the same fail-open family as B1-residual, reached through a different door.
  - It is not in the WP09 diff, but it should be tracked. WP17's fork detection should expect bare-slug Missions to have written decisions on the PRIMARY surface too.

## Evidence (cycle 2, all at -n 3 --dist loadfile)
- decisions/runtime/next/events/regression/guard/coord_read_seam + decision CLI files: 2204 passed, 2 skipped.
- tests/coordination + tests/specify_cli/coordination: 912 passed, 10 skipped.
- tests/specify_cli/cli/commands: 5142 passed, 3 failed (known base-red test_doctrine_asset x3, red at 7afabf4eff).
- integration list (43) + test_owned_next_runtime.py (O8): 456 passed, 7 failed (known base-red runtime-walk x7).
- Named gates: all green except the known OD-DEAD COORD_SEED_TRAILER (test_no_dead_symbols, test_dead_symbol_allowlist_contract).
- Diff coverage vs 7afabf4eff: 69/69 (coord_seed 1043-1045 covered by tests/coordination -k owned). No pragma directives.
