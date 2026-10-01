# IC-01 — Doctrine probe unmask + fragment-intent product fix (WP01)

Materialized at closeout from WP01's reported evidence (scratchpad `wp01-evidence.md`) and
the reviewer's full approval note (`status.events.jsonl`, `to_lane: approved` event,
`review_ref: auto-approval:WP01:20260930` — far more itemized than the one-line
`tasks/WP01-.../review-cycle-1.md`). Issue filed: #5494. Red commit
`d4250e9266a9420dabff413f708e5f914556f499`; fix commit `6775faea9d8301f4aa445a1d5bd106fbacd6b4ee`.

## MG-01 (masked-greens rows 1 + 3) — doctrine-probe unmask (disposition RUN)

```yaml
id: EV-IC01-01
item: MG-01
kind: RUN   # not in the FIX|RETIRE|RE-POINT|KEEP|RESOLVED|NO-OP enum (data-model §4);
            # mapped here as the closest fit to FIX (a masking-removal proof with red/green
            # evidence, no product defect). See evidence/README.md "Kind vocabulary".
planted_break:
  target: "src/specify_cli/doctrine/pack_validator.py::_load_built_in_ids_per_kind (plus two sibling branches of _intent_aware_collision_messages, the new precondition assert, and src/charter/offering/tactics/models.py::_RETIRED_RELATIONSHIP_FIELDS — 5 planted breaks total, see notes)"
  description: >
    5 planted breaks, each reverted independently: (1) _load_built_in_ids_per_kind
    returns {} early; (2) the "overrides target unknown" errors.append(...) call removed;
    (3) the "enhances target unknown" errors.append(...) call removed; (4) the new
    precondition assert's fixture path pointed at a nonexistent tactic id; (5)
    _RETIRED_RELATIONSHIP_FIELDS set to () (disarms the FR-028 hard-cutover rejection).
  reverted: true
command: "uv run --frozen pytest tests/specify_cli/doctrine/test_pack_validator.py tests/integration/test_quickstart_end_to_end.py -n0 -q -rs"
results:
  old_form_under_break: "SKIP (all items; baseline masking probe never executed the assertion)"
  new_form_under_break: fail   # FAIL x2 / FAIL / FAIL x2 / 11 ERRORS / FAIL, per planted break (see notes for exact messages)
  clean_tree: pass
counts:
  test_pack_validator.py: {executed_before: 37, executed_after: 46}
  test_quickstart_end_to_end.py: {executed_before: 7, executed_after: 11}
  combined_before: 44
  combined_after: 57   # >= 44 + 9 = 53 (amended NFR-001 satisfied)
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP01:20260930 — "Reviewer re-run breaks (all
  reverted, tree clean)"): break C ("drop enhances unknown_target append => RED") and break D
  ("_load_built_in_ids_per_kind->return {} => reworded_wording + step4a + positive-control
  [None-False] FAIL (control proves non-vacuity)") reproduce this record's planted breaks
  (3) and (1) respectively. The reviewer also ran an additional plant not in the WP's own
  report: break B, "_collect_fragment_yaml_edges->return None => 4 FAIL, graph case stays
  green (fragment branch isolated)" — confirming the *.graph.yaml path is independent of the
  fragment.yaml path this record's breaks touch; recorded here since it extends this same
  MG-01/MG-02 isolation claim, not as a separate WP-reported inventory item.
  Baseline command (before any WP01 edit): `uv run --frozen pytest
  tests/specify_cli/doctrine/test_pack_validator.py tests/integration/test_quickstart_end_to_end.py
  -n0 -q -rs` -> 44 passed, 9 skipped. Per-break detail (path::function::mutation / under-break
  result / after-revert result), verbatim from WP01's report:
  (1) target _load_built_in_ids_per_kind returns {}: under break, FAIL x2 ("Same-ID collision
  without declared intent MUST produce an advisory. Saw advisories: []" / "... MUST emit an
  advisory. Saw: []"); after revert, PASS x2.
  (2) target _intent_aware_collision_messages, "overrides target unknown" branch, errors.append
  removed: under break, FAIL ("Unknown `overrides` target MUST emit `unknown_target`. Errors:
  [...schema_invalid via FR-028 retired-field rejection...]"); after revert, PASS.
  (3) target _intent_aware_collision_messages, "enhances target unknown" branch, errors.append
  removed: under break, FAIL x2; after revert, PASS x2.
  (4) target test_pack_validator.py::_assert_built_in_fixture_tactic_present (the new
  precondition assert), fixture path pointed at "totally-bogus-nonexistent-tactic-id.tactic.yaml":
  under break, 11 ERRORS (whole TestIntentAwareCollision class, autouse fixture) -
  "AssertionError: fixture tactic ...adversarial-qa-handoff... missing from shipped
  built-ins at .../totally-bogus-nonexistent-tactic-id.tactic.yaml" (loud, not vacuous);
  after revert, 11 passed.
  (5) target _RETIRED_RELATIONSHIP_FIELDS = (): under break, FAIL (the reworded "Retired
  relationship field(s) ...enhances..." message is gone; only the generic pydantic
  "Extra inputs are not permitted" schema_invalid fires, rejected by the test's substring
  assertion); after revert, PASS.
```

## MG-02 (masked-greens row 2) — drg/fragment.yaml intent + FR-005 product fix (disposition RUN+FIX)

```yaml
id: EV-IC01-02
item: MG-02
kind: FIX
planted_break:
  target: "src/specify_cli/doctrine/pack_validator.py::_collect_fragment_edge_intent"
  description: "return {} as the function's first statement (before the real body)"
  reverted: true
command: >
  uv run --frozen pytest
  "tests/specify_cli/doctrine/test_pack_validator.py::TestIntentAwareCollision::test_enhances_suppresses_collision_advisory"
  "tests/specify_cli/doctrine/test_pack_validator.py::TestIntentAwareCollision::test_overrides_suppresses_collision_advisory"
  "tests/specify_cli/doctrine/test_pack_validator.py::TestIntentAwareCollision::test_fragment_yaml_augmentation_intent_suppresses_same_id_collision"
  "tests/specify_cli/doctrine/test_pack_validator.py::TestIntentAwareCollision::test_graph_yaml_augmentation_intent_still_covered"
  -n0 -q -rs
results:
  old_form_under_break: "n/a — before WP01 these 2 tests were SKIPPED, never executed against the real product"
  red_commit_state: "4 failed on commit d4250e9266 (before the T004 fix): both original tests + the 2 positive parametrize arms; the positive-control arm and the graph-yaml case passed (the latter needs the T004 fix target to exist)"
  new_form_under_break: "5 FAILED / 1 passed — re-planting the same break AFTER the T004 fix reproduces the identical same_id_collision failure on all 5 fragment/graph-yaml-dependent tests; only the positive control [None-False] stays green"
  clean_tree: "PASS x6 (2 original + 3 parametrize cases + 1 graph-yaml-covered case)"
covering_guard:
  node_id: null
  under_break: null
counts:
  executed_before: 0   # both tests SKIPPED pre-WP01
  executed_after: 6    # 2 original + 4 new
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): break A, "_collect_fragment_edge_intent->return {} => 5
  FAIL (2 suppress + 2 regression arms + graph case)" — exactly this record's planted break,
  re-applied against the fix commit and reverted clean. Fallback checked per research.md D-3 /
  masked-greens.md note 2: the original drg/*.graph.yaml fixture still suppresses the advisory
  after the fix (test_graph_yaml_augmentation_intent_still_covered, PASS) — the
  _DRG_GRAPH_GLOB path is unchanged, only additive.
```

## FR-005 product fix (issue #5494)

```yaml
id: EV-IC01-03
item: F-5494
kind: FIX
planted_break:
  target: "src/specify_cli/doctrine/pack_validator.py::_collect_fragment_edge_intent"
  description: "same as MG-02's planted break: return {} before the real body"
  reverted: true
command: "uv run --frozen pytest tests/specify_cli/doctrine/test_pack_validator.py tests/integration/test_quickstart_end_to_end.py tests/doctrine/drg/test_org_fragment_validation.py -n0 -q -rs"
results:
  old_form_under_break: "n/a (FR-005 is a new fix, not a masked pre-existing test)"
  new_form_under_break: fail   # same_id_collision, both edge-authored suppression tests
  clean_tree: pass   # 89 passed across all 3 named files, 0 failed, 0 skipped
covering_guard:
  node_id: null
  under_break: null
counts:
  executed_before: null
  executed_after: null
reviewer_rerun: true
notes: >
  Red commit d4250e9266a9420dabff413f708e5f914556f499; fix commit
  6775faea9d8301f4aa445a1d5bd106fbacd6b4ee, `git show --stat` confirms exactly 1 file touched
  (src/specify_cli/doctrine/pack_validator.py). Issue #5494 filed during implementation,
  open at the time of this note. This is quickstart.md's Break #3/#1 (FR-001/FR-005 section),
  one of the SC-005 suggested reviewer picks. Reviewer re-run (approval note): break A,
  "_collect_fragment_edge_intent->return {} => 5 FAIL" — the same planted break recorded
  here, re-applied against the fix commit (re-red on same_id_collision, both edge-authored
  suppression tests) and reverted clean; "Fix 6775faea9d touches only
  src/specify_cli/doctrine/pack_validator.py -> GREEN at HEAD" confirms the clean-tree claim
  independently. #5494 confirmed OPEN; issue-matrix row confirmed present by the reviewer.
```

## Counts summary (NFR-001, amended)

| File | executed before | executed after |
|---|---|---|
| tests/specify_cli/doctrine/test_pack_validator.py | 37 | 46 |
| tests/integration/test_quickstart_end_to_end.py | 7 | 11 |
| **combined** | **44** | **57** (>= 44+9=53 required) |

Final named-file run (all 3 files): `89 passed, 1 warning in 127.41s` (0 skipped, 0 failed).
`make test-fast`: `2169 passed, 5 skipped, 4 warnings in 266.11s` — the 5 skips are
pre-existing/unrelated, exit code 0.

## Skip hygiene (NFR-004)

`rg -n "pytest\.(skip|xfail)|mark\.(skip|skipif|xfail)|importorskip" tests/specify_cli/doctrine/test_pack_validator.py tests/integration/test_quickstart_end_to_end.py` -> 0 hits.

## Quality gates (NFR-005)

- `ruff check` on the 3 owned files -> All checks passed! (0 new noqa)
- `mypy` on `pack_validator.py` -> Success: no issues found in 1 source file (0 new type: ignore)
- `tests/architectural/test_no_dead_symbols.py` -> 35 passed (F-04: no symbol revived/newly dead)

## Issue matrix

`spec-kitty agent issue-verdict --mission test-suite-remediation-01M3SSDW --issue "#5494" --verdict fixed --actor claude-sonnet-5 --wp WP01 --evidence-ref "6775faea9d8301f4aa445a1d5bd106fbacd6b4ee"` -> OK #5494 -> fixed
