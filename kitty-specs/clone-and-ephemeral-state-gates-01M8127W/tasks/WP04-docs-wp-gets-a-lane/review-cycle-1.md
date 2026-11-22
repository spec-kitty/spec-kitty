---
affected_files: []
cycle_number: 1
mission_slug: clone-and-ephemeral-state-gates-01M8127W
reproduction_command:
reviewed_at: '2026-11-22T09:02:07Z'
reviewer_agent: reviewer-renata
wp_id: WP04
---

# WP04 review, cycle 1: changes requested

Reviewer: `claude::reviewer-renata`. Review range `7fbbee86..057d16dc` (recorded).

The design is sound and close to approval. The pure rule, the settlement count, the persistence and the split remedy match the three operator rulings. The red run is real: at `b654f875`, 6 of 6 acceptance tests fail. One finding blocks approval. A second must be fixed in the same fold because it is a one-line guard and it contradicts the "single_branch is untouched" claim in the ADR amendment and the changelog.

## Blocking

### B1. The facade re-export gate is red, and it runs only in the nightly

`tests/specify_cli/cli/commands/agent/test_mission_finalize_phase_modules.py::test_mission_finalize_reexports_every_phase_definition[mission_finalize_bootstrap]` fails on the lane and passes on the base (`b654f875`: 26 passed; `057d16dc`: 1 failed, 25 passed):

```
AssertionError: mission_finalize does not re-export mission_finalize_bootstrap:
['_KIND_NORMALISED_NOTICE', '_MIXED_WP_SPLIT_REMEDY', '_WP_FILE_ID_PATTERN']
```

This directory is out-of-matrix, so a per-PR CI run stays green and the nightly goes red. Fix: add the three names to the `mission_finalize_bootstrap` re-export block in `mission_finalize.py` (`X as X`, like the others). Do not narrow the gate.

## Must fix in this fold

### F1. single_branch re-finalize now reads the status surface, and can refuse

`_kind_normalisation_for` (`mission_finalize_lanes.py`) runs before the topology is known. Whenever some WP would be rewritten and `lanes.json` exists, it calls `_started_wp_ids_for_normalisation` → `_read_started_wp_ids`. That reader fails closed with `status_unreadable` when the surface cannot be resolved or the log is unreadable.

The frozen preflight never does this for single_branch: `_preflight_frozen_lane_membership` returns `FrozenLaneMembership.empty()` for `SINGLE_BRANCH` before it reads status. So a settled single_branch Mission that has a docs WP and a damaged or unresolvable status surface now refuses re-finalize where it did not before. Its normalisation result is discarded anyway (`_is_lane_topology_this_run` is False). The ADR amendment and changelog say single_branch "keeps every authored kind and writes nothing new". A new refusal path contradicts "untouched". I found this by reading the code; no test proves it.

Fix: do not read the started set when the stored topology is a settled single_branch. For example, short-circuit in `_kind_normalisation_for` when `topology_from_meta` is `SINGLE_BRANCH` and `topology_settled` is true, using the same predicate the frozen preflight uses. Add a test.

## Non-blocking (record them; no change needed for approval)

- **N1. Started-WP exception has no CLI-level test.** `test_started_wp_is_never_rewritten` covers only the pure rule. The wiring (re-finalize of a lane Mission whose docs WP is history-started keeps `planning_artifact` and passes the frozen preflight) is untested end to end. Add one if it is cheap. Detection itself is sound: it reuses `_read_started_wp_ids`, the frozen preflight's whole-history, fail-closed reader, and has the same first-finalize shortcut (no `lanes.json` means nothing started).
- **N2 (implementer question 1). The `ownership/validation.py` warning.** "code_change WP does not own any files under src/ or tests/" is a warning (`warnings.append`) and gates nothing. It fires on the first finalize as well as later ones, for every normalised docs WP, because the normalised manifests feed validation. Ruling: a fold after consolidation is acceptable. Record it now as a tracked follow-up (an issue, or an issue-matrix row), not a plan in prose, and say so in the PR. If you take it inside this fold under ownership-map leeway, that is also fine. It does not block.
- **N3 (implementer question 2). The out-of-matrix test edits are legitimate.**
  - `test_five_wp_one_code_lane_settles_single_branch` still pins its original intent: planning-only WPs do not count as code lanes, so the rule is `code_lanes_le_1`. Moving its planning WPs from `docs/` to `kitty-specs/<mission>/` is required by the "Count it" ruling. The new behaviour is pinned positively in `test_docs_wp_counts_toward_settlement`.
  - The same holds for the `test_canceled_wps_not_counted_planning_wps_counted` edit.
  - The orchestration harness line fakes the new seam in the same way as its neighbours.
  - No assertion was weakened. This is a re-pin, not green-washing. Disclose both files as nightly-only in the PR, and add `test_mission_finalize_phase_modules.py` once B1 touches it, if you touch it.

## Settlement impact on existing Missions (checked)

Settlement runs once, at the first finalize (`topology_settled: false`). Settled Missions are unaffected by "Count it". Only a provisional Mission that has not been finalized yet changes its verdict: one code WP plus a docs WP plus a third WP now settles `lanes_with_coord` instead of `single_branch`. That is the ruling, and the ADR amendment states it. A mixed kitty-specs/ + docs/ WP in a lane Mission already in flight is refused on re-finalize only while it is unstarted. A started mixed WP is not rewritten, so it is not refused. That matches the frozen-membership exception.

## Anti-pattern checklist

1. Dead code: PASS
2. Synthetic fixtures: PASS (the CLI tests drive real create and finalize)
3. Silent empty return: PASS (`_persist_kind_rewrites` skips a missing WP file; the ids come from the same file set)
4. FR coverage: PASS
5. Frozen surface: PASS
6. Locked decision: FAIL. "single_branch untouched" is violated on the status-read path (F1).
7. Shared files: PASS
8. Fragility: PASS

## Gates I ran on 057d16dc

- ruff check and ruff format --check --force-exclude on the 8 touched files: clean.
- mypy on the 4 source files: clean.
- C901: clean.
- changelog style: no finding for 7809.

## Tests I ran on 057d16dc (source on PYTHONPATH)

- **Red at b654f875:** `pytest tests/lanes/test_docs_wp_gets_a_lane_7809.py`: 6 failed. The `two_wp` control test fails only on the new `kind_normalised` key, which is legitimate.
- **WP tests and the two edited out-of-matrix files:**
  - `tests/lanes/test_docs_wp_gets_a_lane_7809.py`
  - `tests/lanes/test_kind_normalisation_7809.py`
  - `.../agent/test_finalize_topology_settlement.py`
  - `.../agent/test_finalize_tasks_orchestration.py`

  49 passed.
- **Finalize tests in `tests/specify_cli/cli/commands/agent/`** (`-k finaliz`): 1 failed (B1), 696 passed, 1 skipped, 2 xfailed.
- **Remaining blast radius**, 2069 passed, 1 skipped:
  - `tests/tasks/`, `tests/lanes/`, `tests/specify_cli/ownership/`
  - `tests/consolidation/test_wp_evidence.py`
  - architectural gates: `test_layer_rules.py`, `test_no_dead_symbols.py`, `test_json_contract_enumeration.py`, `test_finalize_refresh_pin_authority.py`, `test_no_legacy_terminology.py`
- **`make test-fast`:** 3170 passed, 7 skipped.
