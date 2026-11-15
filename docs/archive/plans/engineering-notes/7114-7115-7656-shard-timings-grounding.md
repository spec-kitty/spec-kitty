---
title: 'Grounding — #7656, #7115, #7114 shard-timings recapture and strict check'
description: 'Read-only grounding, similar-surfaces and tracked-issues verdicts for splitting the consolidation capture, putting the battery roster back on its rule and cap, and ordering the strict shard-timings check after the recapture.'
doc_status: closeout
type: explanation
updated: '2026-11-15'
---
# Grounding — #7656, #7115, #7114 shard-timings recapture and strict check

Base: `origin/main` @ `cb2d8f04`. Predecessor: PR #7657 (merged 2026-11-15, closed #7641, #7654, #7655), whose handoff comment proposed these three as separate work.

## The three defects, as the code holds them

**#7656, consolidation capture timeout.** `recapture_shard_timings._capture_one` runs the canonical producer (`capture_shard_timings --module <m> --write`) once per module in one subprocess under `DEFAULT_CAPTURE_TIMEOUT_SECONDS = 35 * 60`. The producer runs the module's resolved test directories serially in one `pytest.main` and writes one record: `module_test_node_durations`, its projections (`module_test_durations`, `module_test_count`, `module_duration_seconds`) and `module_capture_provenance`. `consolidation` resolves to `tests/consolidation`, `tests/specify_cli/consolidation`, `tests/terminus`. The last good capture was 1518.7 s serial; #7656 measured about 440 s more since then, so a serial capture now reaches the timeout. Nothing hangs.

**#7115, battery roster.** `.github/ci-module-registry.yml` `special_tiers.architectural.fast_gate.roster` holds 39 rows with hand-written `budget_seconds`. Against the committed junit table (`battery_file_durations.architectural`, captured 2026-11-13 from three nightly runs), the strict run of `tests/ci/test_battery_roster_budgets.py` fails 3 tests (witnessed locally, 127 s): 18 rows are over or off the rule `max(10, ceil(1.5 x seed))` (19 rows differ from the rule), and the roster total is 371.2 worker-s against the 300 cap. The recapture's battery step (`recapture_battery_timings.py`, #6365) refreshes the table whenever its file set changes or it is older than 14 days, but it never touches `budget_seconds`, so the rule check drifts again after every refresh. #5555 (closed) proposed re-deriving the budgets; that half was not built.

**#7114, strict check.** `ci-shard-recapture.yml` runs `strict-shard-timings-check` independently of `recapture-shard-timings` (header: "DELIBERATELY INDEPENDENT"), so the strict check always tests the committed tables from before that day's recapture. The recapture job is gated on `refs/heads/main`; a topic-branch dispatch runs only the strict job. A capture change is therefore verified only after the PR lands on main.

## Invariants that must survive

- The producer is the one writer of the module record (C-010, the producer's module docstring); the recapture never writes the tables itself.
- `is_valid_capture` is the single authority for "this provenance is a trustworthy capture", shared with `tests/architectural/test_shard_capture_provenance.py`. `validate_module_tables` is the single authority for the record's internal agreement.
- The keyed table is in collection order of `pytest <test_dirs>`, which for non-nested directories is the concatenation of each directory's own order. No resolved directory set in the registry nests (checked for all 20 modules).
- The write PAT never reaches a capture subprocess (F1, #5271); the recapture job never runs off `main` (F4).
- Job time arithmetic: budget 70 min + one capture timeout 35 min + about 25 min overhead = 130 min.
- Battery timings never come from a local run (charter C-009); the roster's admission rule, the 90 s file cap and the 300 s total stay as they are (no loosened floors).

## Gates and ledgers that read these files

- `tests/ci/test_recapture_shard_timings.py`, `tests/ci/test_capture_shard_timings.py`, `tests/ci/test_recapture_battery_timings.py`, `tests/ci/test_battery_roster_budgets.py`.
- `tests/architectural/test_module_length_agreement.py`, `test_shard_capture_provenance.py`, `test_module_shard_registry.py`, `test_battery_partition_proof.py`, `test_battery_scan_scope_routing.py`, `test_gate_scan_scope_completeness.py`, `test_workflow_coherence.py`.
- `tests/release/pinning_rule_inventory.json` records line numbers in several of these test files; it is re-derived with `scripts/ci/derive_pinning_inventory.py` after edits.
- Workflow changes run through the router and gate-selection tests (`tests/ci/test_ci_router*.py`, `tests/architectural/test_gate_selection_authority.py`).

## Similar surfaces (pointfix sweep)

- Other modules that could outgrow the 35-minute capture: `charter` (1009 s, two directories), `upgrade` (751 s, one directory), `execution_context` (662 s, three directories). In scope now: the part-wise capture applies to every module, so each directory gets its own timeout. A single directory that alone outgrows 35 minutes is not solved by this; none is close today (largest, `tests/consolidation`, about 1050 s).
- `integration_next` battery suite: has no roster and no budgets, so no rule drift. No action.
- The pinning-inventory freshness gate in the same strict job: its drift is unrelated to the recapture output (line numbers in test files). No action; it stays as it is.

## Operator rulings (2026-11-15)

- The recapture's battery step re-derives every roster `budget_seconds` by the rule whenever it runs, in the same proposal PR (#7115's second fix, the unbuilt half of #5555). Moving rows when the roster no longer fits its caps stays a human decision.
- The strict check grades the recapture output, so it also says what main still lacks: a `proposal-check` step warns for every module, battery table or roster budget main's committed files are stale on, and fails when the open recapture proposal is older than 3 days.
- The pre-PR review found that `test_src_reachability_guard` reads `tests/**` and the foreign-coverage baseline outside its scan scope, so it stays always-on and `test_status_events_writes_gate` moved instead.

## Tracked issues

- Closes (when fully delivered): #7656, #7115, #7114.
- Refs: #5555 (closed; its budget re-derivation half), #4437 (parent epic), #5658 (producer-environment test failures during capture; not this defect), #7660 / #7659 (an open PR adding `tests/characterization` to `execution_context`; touches the registry's module rows, not the roster; no conflict expected).
- No open recapture proposal PR on `ci/recapture-shard-timings` at grounding time.
