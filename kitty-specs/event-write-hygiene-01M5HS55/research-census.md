# Scout report: event-write-hygiene-01M5HS55 mechanical census

Scout: python-pedro (brownfield, read-only). Tree: /home/user/spec-kitty as checked out on 2026-10-22.
Method: an AST census over every `tests/**/*.py` file that resolves imports per module, so other `append_event` names
(`glossary.append_event`, `spec_kitty_events.persistence.append_event`, `BookkeepingTransaction.append_event`,
runtime `engine._append_event`) are excluded. Scripts and raw JSON are in /tmp/claude-0/-home-user/1d938983-4d3b-55c7-ada3-9e0565e3967a/scratchpad/.

## 1. Test usage of `specify_cli.status.store.append_event` (and its two wrappers)

**Totals:** 189 test files import and call a door, with 382 call sites. 380 calls go to `append_event` and 2 to `append_event_verified` (tests/status/test_store.py).
Every importing file also calls a door, and every calling file imports one. Two more files reference a door without importing it by name:
`tests/integration/refinalize_frozen_lanes_support.py` (a spy) and `tests/status/test_store.py` (a monkeypatch target, already counted).
That gives **190 files to touch for FR-004**, plus the gate and allowlist files in section 1e. The spec says "about 195".

### 1a. Import shapes

| Shape | Files | Occurrences |
|---|---|---|
| `from specify_cli.status.store import append_event` (alone, module level) | 109 | 109 |
| `from specify_cli.status.store import append_event` (alone, **function-local**) | 29 | 40 |
| `from specify_cli.status.store import append_event, <others>` (single line, module level) | 38 | 38 |
| same, parenthesised multi-line, module level | 5 | 5 |
| same, parenthesised multi-line, function-local | 1 | 1 |
| same, single-line multi-name, function-local | 1 | 1 |
| `from specify_cli.status.store import (..., append_event_verified, ...)` multi-line | 1 (tests/status/test_store.py) | 1 |
| `from specify_cli.status._unsafe import append_event` (module level) | 6 | 6 |
| `from specify_cli.status._unsafe import append_event` (function-local) | 2 | 3 |
| `import ... as X` alias of a door name | **0** | 0 |
| `append_primary_checkout_event_verified` in any test | **0** (named only in a gate constant) | 0 |

The lists of files per shape are in Appendix A. Function-local imports are the main thing an AST codemod has to handle beyond a plain line rewrite: 33 files, 45 sites.

Shared fixture hubs: one edit here covers many tests.
- `tests/utils.py:54,80`
- `tests/_factories/coord_mission.py:92,617` (it already imports `append_raw_rows_atomic`)
- `tests/status/conftest.py`
- `tests/reliability/fixtures/mission.py`
- `tests/runtime/_next_mission_scaffold.py`
- `tests/specify_cli/cli/commands/_review_fixtures.py`
- `tests/specify_cli/cli/commands/agent/_rework_loop_harness.py`

### 1b. Module-attribute and monkeypatch shapes

| Shape | Site | Notes |
|---|---|---|
| `status_store.append_event` passed as a value | tests/integration/refinalize_frozen_lanes_support.py:311 | `wrap_everywhere(monkeypatch, status_store.append_event, ...)` is a spy over every module dict entry that `is` the door. **Must be deleted, not retargeted.** If the seeding helper imports `append_raw_rows_atomic` by name, the spy at :312 also wraps it, so any seed written after `spy_writers()` would be recorded (used by test_refinalize_keeps_started_lanes.py:89,116 and test_refinalize_frozen_lane_refusals.py:81). |
| `monkeypatch.setattr(status_store, "append_event", ...)` (string attribute) | tests/status/test_store.py:83, :114 | These are self-tests of the `append_event_verified` wrapper. Delete them. |
| `patch("specify_cli.status.store.append_event")` style | **0** | |
| `store.append_event(...)` call through a module alias | **0** | The 9+1+3+2 files that import `store` / `_unsafe` as a module use other attributes (`os`, `_fsync_directory`, `ALLOWED_CALLERS`, ...). |
| `monkeypatch.setattr(glossary_cmd, "append_event", ...)` | tests/agent/cli/commands/test_glossary.py:1702 | **Not the door.** This is the glossary's own append. The codemod must exclude it. |
| String-embedded source (parsed as an AST fixture, never executed) | tests/architectural/test_no_absolute_event_timestamp_mixture.py:465,495,668,686-687 | The rule does not key on the name. An AST codemod skips these. A sed codemod would rewrite them harmlessly. |
| Docstring mention | tests/runtime/next/test_coord_topology_fixture.py:118 | Prose. |

### 1c. Call signatures

All 382 calls are positional with two arguments and no keywords. The second argument resolves to a `StatusEvent` in every case:
- 192 inline `StatusEvent(...)` constructions;
- 92 calls to helpers annotated `-> StatusEvent`;
- 55 variables assigned from `StatusEvent(...)`, 28 from `_make_event`, 2 from `StatusEvent.from_dict`, 1 from `build_status_event`;
- 5 loop variables over event lists;
- 3 parameters annotated `StatusEvent`;
- 3 calls to unannotated helpers (`build_status_event`, a `dataclasses.replace(StatusEvent)`), plus `_b_event -> Any` at tests/migration/test_mission_state_repair.py:1743, which builds a `StatusEvent`.

**No call passes an `InnerStateChanged`, a dict, or a keyword argument.** The first argument is always a directory. The most common names are `feature_dir` (288) and `tmp_path` (34). No call passes an events-file path or a `str`.
So a helper `seed_status_events(feature_dir: Path, *events: StatusEvent)` (or a single-event form) covers every site mechanically.

### 1d. Door self-tests: delete, do not retarget

tests/status/test_store.py:
- :67 `test_append_and_read_round_trip`
- :77 `test_append_event_verified_fails_when_readback_misses_event`
- :102 `test_append_event_verified_wraps_append_failures_in_diagnostic`
- :127 `test_multiple_appends_preserve_order`
- :373 `test_file_created_on_first_event`
- :382 `test_directory_created_on_first_event`
- :459 `test_deterministic_key_ordering`

These either test the door itself or seed through it. :185, :197, :268 and :436 only seed through it, so retarget those.

tests/specify_cli/status/test_store_sanitized.py:
- :104 `test_pii_absent_from_status_events_jsonl`
- :133 `test_non_pii_fields_preserved...`
- :333 `test_sanitizer_is_called_in_append_event`

These are titled after the door, but the sanitizer lives in `serialize_event_line`, which the atomic path shares. Retargeting them onto `append_events_atomic` keeps the coverage. The test at :389 already covers `append_raw_rows_atomic`.

### 1e. Gates and baselines that name the doors (each needs a coordinated edit)

| File:line | What breaks |
|---|---|
| tests/architectural/test_status_unsafe_allowlist.py:72-84 | `STORE_APPEND_PRIMITIVES` pins every `def append_*` in store.py, including the three doors. It must shrink in the same commit. |
| tests/architectural/test_status_unsafe_allowlist.py:93 | `COORD_WRAPPER_DOORS` contains `append_event_log`. |
| tests/architectural/test_status_unsafe_allowlist.py:263-270, 278, 314, 316 | Non-vacuity fixtures use `append_event` as the synthetic door. Retarget them to a surviving primitive, or they go red once `append_event` is no longer a recognised door. |
| **tests/architectural/test_status_events_writes_gate.py:691** | `test_store_writes_are_found` asserts that the store's write kinds are exactly `{("Path.open","a"), ("os.replace","replace")}`. The `Path.open "a"` entry is `append_event`, so deleting the door turns this red. It must become `{("os.replace","replace")}`. **High-risk hidden coupling.** |
| tests/architectural/dead_symbol_allowlist.yaml:1121-1123 | `specify_cli.status._unsafe: append_event`. |
| tests/architectural/dead_symbol_allowlist.yaml:1286-1287 | `coordination.status_service: append_event_log`. |
| tests/architectural/dead_symbol_allowlist.yaml:1276-1277 | `invocations_cmd: append_to_index`. Whether stale entries fail the gate depends on how it handles them. |
| src/specify_cli/status/_unsafe.py:47-66, :83 comment | Re-exports and `__all__`. `ALLOWED_CALLERS` needs **no** entry removed: `coordination.status_service` still imports the annotation and stream doors, and no other src module imports a deleted door. |
| src/specify_cli/status/__init__.py:75-77 | Comment only. |
| src/specify_cli/status/design.py:79-89 | The docstring says every writer of `status.events.jsonl` mutates the same inode via `append_event`'s `"a"` mode. That is **already false**, because `append_raw_rows_atomic` uses `os.replace`. It becomes more false after the change. Fix it in the same change. |
| tests/release/coverage_breadth_baseline.json:4047 | `store.py` is recorded as [252, 291] statements. This is a historical measurement; check whether any gate recomputes it (only `files`/totals provenance is asserted, per test_coverage_breadth.py:272-299). |

## 2. Does any test rely on plain-door semantics?

Differences between `append_event` (an `open("a")` that keeps the inode) and `append_raw_rows_atomic` (read existing text with O_NOFOLLOW, add a `\n` if missing, write mkstemp, fsync, os.replace, fsync the directory):

| Hazard | Finding |
|---|---|
| `st_ino` / inode identity / `samefile` / `os.link` | **0 hits** in the 189 door files. |
| Pre-existing file without a trailing newline, or invalid JSON, then a door append | **0.** AST scan of every function that calls the door: tests/consolidation/test_canceled_dependency_lane.py:285 and tests/integration/test_two_partition_preview.py:84 write `''` first (equivalent). tests/specify_cli/test_acceptance_regressions.py:309 writes malformed content only in a branch that excludes the door call (:327). tests/runtime/test_artifact_presence_placement.py:123 writes a different file. tests/consolidation/test_done_bookkeeping_seam.py:831 and tests/retrospective/test_reducer_integration.py:61 do raw `open("a")` writes, newline-terminated, so they are equivalent. |
| Symlinked events log (the atomic path refuses with `StoreError`) | **0** door seeds into a symlink. Symlink tests in test_store.py:295-324 target `append_events_atomic` directly. Others (test_merge_done_recording.py:925, test_merge.py:857/976, test_explicit_checkout_commands.py:618/894) do not seed through a link. |
| CRLF logs (atomic reads in text mode, translating `\r\n` to `\n` on rewrite) | Only tests/migration/test_mission_state_repair.py:582, and that test does not call the door after reshaping. **Latent risk** if a future seed lands on a CRLF log. Worth a line in the helper's docstring. |
| File mode (mkstemp gives 0600; `open("a")` creates with umask, typically 0644) | **Byte-identical, but the mode differs.** No test in the set asserts `st_mode`. The chmod hits are hooks. Note it for NFR-001: the bytes are identical, the permission bits are not. |
| `notify_file_written` vs `notify_written` | Same observer contract (kernel/atomic.py:72-87). No door test installs an observer. Equivalent. |
| Concurrent unlocked appends | None. The threaded door calls (tests/status/test_dependency_guard.py:625 `holder`, tests/migration/test_mission_state_repair.py:1830 `_ConcurrentWriter`) both append **under `feature_status_lock`**. The repair race tests (:1873-2010) give the same verdict for in-place and replace appends: the erase or keep outcome is decided by the lock, not by the inode. |
| Global `os.replace` / `_append_serialized_atomic` patched **before** seeding (a seed would silently no-op or raise) | None today. Every patch lands after seeding: test_store.py:275 (seed :268); test_diffcov_2684 :180/:194 (no seed in those functions); test_move_task_git_validation_unit.py:310 (seed in fixture :103); test_review_durability_matrix.py:1812 `_sc004_worker` (worker only; its `ordered_replace` blocks on the **first** `os.replace` of `status.events.jsonl` for 9 s, so any seed added inside that context would deadlock-timeout). Note that `monkeypatch.setattr(status_store.os, "replace", ...)` patches the **global** `os.replace`. |

**Verdict:** no test depends on the plain door's semantics beyond its own self-tests. The risks to manage are the writes-gate pin (section 1e), the refinalize spy, and the file-mode difference.

## 3. `append_event_log` (coordination/status_service.py:304) in tests

17 files reference it: 16 call it, and test_status_unsafe_allowlist.py names it in a constant. There are 28 call sites. Imports: 8 at module level and 7 function-local, all multi-name `from specify_cli.coordination.status_service import (...)`.
**No call passes an `InnerStateChanged`.** Every event argument is a `StatusEvent`, so the function's `InnerStateChanged` branch has no test caller.

| Contract | Calls |
|---|---|
| `EventLogWriteContract.coordination_transaction_append(dir)` | 15 (seeds in test_orchestrator_lane_allocation:131, _context_refresh:106, test_claim_base:350, test_emit_review_result:274, test_phantom_fanout:524, test_status_transition:147/426/803, test_wp05_...:89, test_for_review_gate_parity:121, test_workspace_context_tombstone:147, test_dependency_guard:743, test_execution_projection:386, test_lane_head:452, test_status_transition:469 [error]) |
| `EventLogWriteContract.primary_checkout_append(dir)` | 11 (test_plain_door_semantics:71, test_status_surface_owned:193/211/270, test_owned_status_read_contract:156, test_status_transition:410/421/463/893/1224, test_dependency_guard:751) |
| a variable `contract` (parametrised) | 1 (test_status_surface_owned.py:302 `_run(op, contract)`) |
| `EventLogReadContract` passed on purpose (type-error path) | 1 (test_status_transition.py:451) |

Tests that assert contract-validation errors (all of them must move to `append_event_stream_log(contract, [event])`):
- test_status_transition.py:451 `test_read_contract_cannot_be_used_as_write_contract`, `pytest.raises(StatusContractError)` with no match. The stream form raises "append_event_stream_log requires EventLogWriteContract", which is compatible.
- test_status_transition.py:463 / :469 `test_wrong_write_target_fails_loudly`, `match="primary_checkout_append"` / `"coordination_transaction_append"`. The message comes from the shared `_validate_write_contract`, so it is compatible.
- test_status_surface_owned.py:211, :270, and :302 via `_run`. Match `_OWNED_APPEND_REFUSED_MESSAGE = "primary_checkout_append must not target coordination worktree paths"` (:281), from the shared validator, so compatible.
- test_owned_status_read_contract.py:156, same message.

No test pins the wrapper's own name in an error string. Note one name collision: test_plain_door_semantics.py's "plain door" means the `emit_status_transition` fallback, not `store.append_event`. Its `append_event_log` use (:71) is fixture seeding only.
`append_event_stream_log` writes through `append_event_stream_atomic_verified`, which uses the same `serialize_event_line` and the same readback, so the bytes are the same.
Other references: tests/specify_cli/coordination/test_1622_dead_symbol_retirement.py:16 (prose that names `append_event_log` as a raiser of `StatusContractError`), dead_symbol_allowlist.yaml:1287, docs/architecture/event-ledger-writers-and-readers.md:97, and docs/reports/dead-code-review/.../domain-c-workflow-core.md:19 (historical).

## 4. Produce-seam "saas" names

Format: lines / files, measured with word-boundary grep (`grep -w`). `docs/archive` is excluded from the detail tables.

| Name | src | tests | docs | String-based references (risk) |
|---|---|---|---|---|
| `_saas_fanout_timeout_s` | 2/1 (adapters.py:41,86) | 1/1 (test_saas_fanout_timeout.py:109) | - | attribute access |
| `_DEFAULT_SAAS_FANOUT_TIMEOUT_S` | 4/1 (adapters.py:37,51,55,57) | 1/1 (:109) | - | |
| `_SAAS_FANOUT_TIMEOUT_ENV` | 2/1 (adapters.py:38,49) | 0 | - | |
| `SPEC_KITTY_SAAS_FANOUT_TIMEOUT` | 1/1 (adapters.py:38) | 7/1 (test_saas_fanout_timeout.py:36,60,81,93,108,117,146 `monkeypatch.setenv`) | 1 (event-ledger-writers-and-readers.md:206 G-11) | **env-string** |
| `SaasFanOutHandler` | 3/1 (adapters.py:120,128,150) | 0 | - | |
| `LifecycleSaasFanOutHandler` | 3/1 (:122,129,165) | 0 | - | |
| `_saas_handlers` | 7/1 (:128,158,160,162,198,248,250) | 0 | - | |
| `_lifecycle_saas_handlers` | 6/1 (:129,168,170,172,199,333) | 0 | - | |
| `register_saas_fanout_handler` | 4/2 (adapters.py:150,178 docstring; status/__init__.py:216,656) | 26/6 (test_emit.py x7, test_emit_fanout_after_adapter.py x6, test_saas_fanout_timeout.py x6, test_emit_backward_transition.py x3, test_sync_lane_mapping.py x2, test_saas_resolved_binding_fanout.py x2) | 1 (ADR 2026-10-13-2:165) | attribute calls |
| `register_lifecycle_saas_fanout_handler` | 3/2 (adapters.py:165; __init__.py:214,654) | 8/3 (test_lifecycle_events.py x5, test_saas_fanout_timeout.py:152, test_mission_creation_fire_once.py:17 docstring + :124) | 1 (ADR 2026-10-13-2:165) | |
| `fire_saas_fanout` | 17/4 (adapters.py:217,282; __init__.py:213,677; emit.py:84,1382,1522,1550,1553; coordination/outbound.py:14,15,27,92,96,100,103) | 34/8 | 8/7 (incl. ADRs, CHANGELOG, plans) | **`mock.patch` / `monkeypatch.setattr` string targets**: test_plain_door_semantics.py:46-48; test_phantom_fanout.py:53-55; conftest_saas_sink.py:89,93,104 (plus :102 `hasattr` guard) |
| `fire_lifecycle_saas_fanout` | 9/4 (adapters.py:321; __init__.py:211,675; lifecycle_events.py:485,488; decisions/emit.py:14,170,179,190) | 13/5 | 3/3 | **string targets**: test_agent/test_create_feature_branch_unit.py:65 `patch("specify_cli.status.adapters.fire_lifecycle_saas_fanout")`; decisions/test_emit.py:315,337,365,394,421 `monkeypatch.setattr("specify_cli.status.fire_lifecycle_saas_fanout", ...)`; core/test_mission_creation_fanout_commit_boundary.py:62,94,132,156,191 |
| log text `"fire_saas_fanout:"` | adapters.py:243 | **caplog**: test_emit_fanout_after_adapter.py:102 asserts the full string `"fire_saas_fanout: wp_id=WP01 from=planned to=claimed force=False handlers=0"` | - | **caplog-text** |
| log text "SaaS fan-out" (any) | 22/5: adapters.py:29-30 comments, :151,166,218,252 label,255,262,270,322,335 label,338,342,346; emit.py:911,928,930,1367,1449,1538; lifecycle_events.py:390,827; models.py:151; init.py:1236 | 27/16, mostly prose. **caplog**: test_emit.py:1862 `"Skipping SaaS fan-out for genesis transition"` (emit.py:1538, **not** adapters.py, so outside SC-003). test_saas_fanout_timeout.py:51 / :137 match only `"timed out"` / `"still in flight"`, which survive the rename. | 4/4 | The `label="SaaS fan-out"` value at adapters.py:252/335 also names the worker thread (`f"{label}-handler"`, :105). No test asserts thread names. |

SC-003 baseline: adapters.py has **44 lines containing "saas" (any case)**. The only ones not covered by the 12 names are the comments at :29-30.

Adjacent "saas" residue that is **not** among the 12 names but sits in the same blast radius:
- `emit._saas_fan_out` (emit.py private caller). 107 references in total: 11 in src, about 96 in 45 test files (`monkeypatch.setattr(emit, "_saas_fan_out", ...)`, test_emit.py alone has 27). Renaming it would double the test churn. Recommend recording it as follow-up per the Assumptions section, unless the plan explicitly scopes it in.
- The test fixture `mock_saas_sink` and the file `tests/conftest_saas_sink.py`, loaded via `pytest_plugins = ("tests.conftest_saas_sink",)` at test_status_transition.py:48.
- Test file names `tests/status/test_saas_fanout_timeout.py` and `tests/specify_cli/status/test_saas_resolved_binding_fanout.py`.
- **Release-gate coupling:** tests/release/coverage_breadth_baseline.json:36-37 (and coverage_breadth_evidence.md:225-226) pin the node IDs `tests/status/test_saas_fanout_timeout.py::test_hanging_lifecycle_handler_does_not_block` and `::test_hanging_saas_handler_returns_within_three_seconds`. They are checked by `tests/architectural/test_coverage_breadth.py::test_marker_mismatch_exception_set_is_reproducible` (:302). **Renaming that file or those functions turns the gate red** unless the baseline is updated too.

**Silent-vacuity hazard:** tests/conftest_saas_sink.py:102 patches `emit.fire_saas_fanout` only `if hasattr(emit, "fire_saas_fanout")`.
- If emit's import is renamed and this guard is not updated, the emit boundary is silently left unpatched.
- `mock_saas_sink.call_count == 0` assertions (test_status_transition.py:527, 560, 580) would then pass vacuously.
- The two `monkeypatch.setattr("...adapters.fire_saas_fanout")` string targets raise on a missing attribute, so they fail loudly. Only the `hasattr` path is silent.

## 5. Lifecycle builder and related names

| Name | src | tests | docs |
|---|---|---|---|
| `build_saas_lifecycle_queue_event` | lifecycle_events.py:408 (def), :1288 (`__all__`); status/__init__.py:289, 563 | test_lifecycle_events.py:1054-1059, :1062-1070 (2 tests to delete); tests/architectural/test_status_module_boundary.py:132 (prose) | ADR 2026-10-14-1:56, :89; docs/reports/test-sanitation/.../raw/{base,head}-census.json (historical node IDs) |
| `_canonical_lifecycle_payload_for_saas` | lifecycle_events.py:381 (def), :438 (only caller is the builder) | 0 | 0 |
| `_validate_lifecycle_payload` | lifecycle_events.py:342 (def), :439 (only caller is the builder). Holds core's **only** private import: `:368 from spec_kitty_events.conformance.validators import _EVENT_TYPE_TO_MODEL` | test_lifecycle_events.py: 6 tests at :926, :950, :975, :997, :1005, :1023, all delete. :1013 is a private test reach-in that goes away with them. | CHANGELOG.md:6805, :6841 (history) |
| `repo_root_for_lifecycle_log` (public alias) | lifecycle_events.py:398, :1287; status/__init__.py:305, 580; adapters.py:329 (docstring) | test_characterization_root_walks.py:42,106,160; test_simple_case_flat_topology.py:72,330 | - |
| `_repo_root_for_lifecycle_log` (private, live) | lifecycle_events.py:327, 475, 556, 587; migrate_lifecycle_envelope.py:76, 238 | test_lifecycle_events.py:885-923; test_owned_lifecycle_acceptance_finalize.py:776, 798 (**frame-name string** check `"_repo_root_for_lifecycle_log" in frames`); test_mission_setup_plan_phases.py:1093 and test_hermetic_ambient_git.py:5 (prose) | - |
| `fanout_lifecycle_event_hosted` (live) | lifecycle_events.py:462 (def), 633, 913, 933, 1274; status/__init__.py:292, 566; core/mission_creation_commit.py:282, 285, 287 | test_lifecycle_events.py:53, 820 | - |

Notes:
- After the builder is deleted, `_generate_event_id` (:207, still used at :315) and `now_utc_iso` (still used at :320 and others) stay live, so there is no dead-import fallout.
- The builder's other dependencies are local to the builder.
- `repo_root_for_lifecycle_log`'s docstring justifies it by "the sync fan-out handler", which is gone. Its remaining users are 2 test files. It is outside FR-006; record it as follow-up.
- `fanout_lifecycle_event_hosted` is live and production-called. The spec's Assumptions say to rename it only where it names seam identifiers, so it stays (follow-up).

Private-import census (AST, FR-007):
- src: **1** import, lifecycle_events.py:368.
- src/specify_cli/status/validate.py:192 and reducer.py:160 mention `spec_kitty_events.diary._...` in **docstrings or comments only**. A regex-based gate would false-positive on them, so the gate must be AST-based.
- tests: 6 files.
  - tests/architectural/test_verdict_vocab_single_source.py:74 `_apply_annotation_delta`
  - tests/architectural/test_2093_authority_invariant.py:68 `_RUNTIME_SLOTS`
  - tests/status/test_lifecycle_events.py:1013 `_EVENT_TYPE_TO_MODEL` (deleted with FR-006)
  - tests/status/test_release_runtime_claim_marker.py:32 `_apply_annotation_delta`
  - tests/status/test_2960_blanked_runtime_slot.py:119 `_apply_annotation_delta` (function-local)
  - tests/specify_cli/status/test_resolved_binding_reducer.py:40 `_REPLACE_SLOTS, _RUNTIME_SLOTS, _apply_annotation_delta, _wp_state_from_event`
- That leaves a shrink-only test allowlist of **5 files**.
- The existing gate to extend is tests/architectural/test_events_tracker_public_imports.py. It currently matches only `<pkg>._internal`, so it misses `_`-prefixed names.

## 6. `append_to_index`

| Where | Lines |
|---|---|
| src/specify_cli/cli/commands/invocations_cmd.py:150 (def; the docstring wrongly claims `InvocationWriter.write_started` calls it; plain `open("a")` at :171) | 1 |
| tests/specify_cli/invocation/cli/test_invocations.py: import :33; calls :138 (inside a `_write_started`-style helper, `if write_index:`), :325, :342, :346 | 4 calls |
| tests/contract/test_mission_status_ops.py:1817 `WRITING_NAMES` and tests/contract/test_mission_status_drift.py:1927 `FORBIDDEN_NAMES` | string members of forbidden-name sets. They stay valid as deny-list entries after deletion, since they are not asserted to exist. test_mission_status_ops.py:1165 checks `_append_to_index` (the writer's private method), which is unaffected. |
| tests/architectural/dead_symbol_allowlist.yaml:1277 | allowlist entry, remove |
| docs: docs/reports/dead-code-review/2026-09-30/test-only-deep-dive/domain-b-cli-surface.md:24, 187-196, 262; first-pass/domain-b-cli-surface.md:92, 129; docs/development/docs-retrieval-index.yaml:15158 (generated index heading); docs/architecture/event-ledger-writers-and-readers.md:211 (G-16) | 11 lines / 4 files |

Retargeting notes:
- The writer (`InvocationWriter._append_to_index`, writer.py:207) writes the same JSON shape to the same path. `INDEX_PATH = "kitty-ops/ops-index.jsonl"`, and `self._dir = repo_root / EVENTS_DIR` (:129). Both use `json.dumps` with insertion-ordered keys, so the bytes are identical.
- It differs in mode: O_NOFOLLOW and 0600.
- Its public entry is `write_started(OpStartedEvent)`, which also creates the per-op file. test_invocations.py:346 seeds a **dangling** index entry (no op file), and :138/:325/:342 pass dict records that already have their op file written.
- Retargeting therefore needs either `OpStartedEvent` construction plus deleting the op file afterwards, or a test-only call of the private `_append_to_index`. This is a design decision for the plan, not a mechanical one.
- No other src module writes `ops-index.jsonl`. doctor/ops.py:18 and m_3_3_0_op_record_schema_v2.py only list it.
## Appendix A: per-shape file:line lists (door imports)

### from specify_cli.status.store import append_event [alone] (109 occurrences)

- tests/agent/test_context_resolve_unit.py:12
- tests/agent/test_status_state_phantom_degrade.py:24
- tests/agent/test_workflow_feedback_pointer_2x_unit.py:16
- tests/agent/test_workflow_review_cycle_pointer.py:14
- tests/agent/test_workflow_review_lane_gate.py:24
- tests/architectural/test_2093_authority_invariant.py:69
- tests/charter_offering/test_spk_show_me_skill.py:17
- tests/cli/test_agent_retrospect_missing_record.py:14
- tests/cli/test_charter_activate_warning.py:41
- tests/cli/test_move_task_planned_guard.py:38
- tests/consolidation/test_2959_skip_review_artifact_check.py:27
- tests/consolidation/test_canceled_dependency_lane.py:48
- tests/consolidation/test_coord_teardown_order_3926.py:44
- tests/consolidation/test_issue_2709_projection_union.py:43
- tests/contract/test_machine_facing_canonical_fields.py:25
- tests/coordination/test_status_transition_write_dir.py:39
- tests/core/test_mission_create_idempotency_guard.py:40
- tests/integration/migration/test_noop_upgrade_leaves_history_untouched.py:37
- tests/integration/migration/test_residue_dir_not_treated_as_mission.py:23
- tests/integration/review/test_approve_without_force.py:40
- tests/integration/test_2646_stale_verdict_closes_via_fr001.py:57
- tests/integration/test_dossier_snapshot_no_self_block.py:40
- tests/integration/test_explicit_checkout_commands.py:22
- tests/integration/test_implement_review_retrospect_smoke.py:19
- tests/integration/test_mission_archiving.py:39
- tests/integration/test_prompt_builder_owned_arms.py:23
- tests/integration/test_rejection_cycle.py:25
- tests/integration/test_review_cycle_rejection_only.py:34
- tests/integration/test_review_handoff.py:20
- tests/integration/test_worktree_topology_claim_base.py:18
- tests/integration/test_wp_integrity_p0_repro.py:65
- tests/lanes/test_issue_4889_destroyed_lane_guard.py:51
- tests/lanes/test_recovery_post_merge.py:28
- tests/lanes/test_recovery_write_dir.py:23
- tests/mission_runtime/test_claim_commit.py:19
- tests/mission_runtime/test_resolution_target_branch.py:35
- tests/next/test_decision_unit.py:17
- tests/next/test_finalized_task_routing.py:11
- tests/next/test_next_claimable_payload.py:24
- tests/next/test_prompt_builder_review_base.py:19
- tests/orchestrator_api/test_issue_4889_caller_independence.py:41
- tests/perf/test_tasks_status_baseline.py:52
- tests/post_merge/test_2684_review_override_recognition.py:51
- tests/post_merge/test_review_artifact_consistency.py:20
- tests/reliability/fixtures/mission.py:13
- tests/review/test_arbiter.py:40
- tests/review/test_pre_review_gate_integration.py:94
- tests/review/test_verdict_save_performance.py:50
- tests/review/test_verdict_seam_reader_collapse.py:50
- tests/runtime/next/test_cli_guard_family.py:52
- tests/runtime/next/test_committed_authority.py:24
- tests/runtime/next/test_coord_topology_fixture.py:64
- tests/runtime/next/test_merged_mission_terminal.py:34
- tests/runtime/test_artifact_presence_placement.py:17
- tests/runtime/test_cli_guard_family.py:23
- tests/runtime/test_runtime_bridge_read_path_branches.py:47
- tests/runtime/test_workspace_context_unit.py:13
- tests/specify_cli/acceptance/test_accept_pre30_hard_reject.py:31
- tests/specify_cli/cli/commands/_review_fixtures.py:25
- tests/specify_cli/cli/commands/agent/_rework_loop_harness.py:31
- tests/specify_cli/cli/commands/agent/test_approval_after_forced_review_exit.py:23
- tests/specify_cli/cli/commands/agent/test_finalize_provenance_guard.py:49
- tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py:61
- tests/specify_cli/cli/commands/agent/test_issue_3311_finalize_rewrites_active_lanes.py:52
- tests/specify_cli/cli/commands/agent/test_issue_4141_refresh_planning_commit.py:58
- tests/specify_cli/cli/commands/agent/test_issue_4827_repin_orphaned_planning_commit.py:56
- tests/specify_cli/cli/commands/agent/test_issue_5328_finalize_refresh_dry_run.py:14
- tests/specify_cli/cli/commands/agent/test_issue_5328_refresh_fail_closed.py:19
- tests/specify_cli/cli/commands/agent/test_move_task_approval_body_collision.py:51
- tests/specify_cli/cli/commands/agent/test_move_task_approval_evidence.py:31
- tests/specify_cli/cli/commands/agent/test_move_task_done_exit.py:34
- tests/specify_cli/cli/commands/agent/test_move_task_orchestration.py:44
- tests/specify_cli/cli/commands/agent/test_move_task_reject_fix_approve_cycle.py:36
- tests/specify_cli/cli/commands/agent/test_tasks_canonical_cleanup.py:23
- tests/specify_cli/cli/commands/agent/test_tasks_cli_contract.py:53
- tests/specify_cli/cli/commands/agent/test_tasks_cli_contract_coord.py:77
- tests/specify_cli/cli/commands/agent/test_tasks_core_backed_orchestration.py:49
- tests/specify_cli/cli/commands/agent/test_tasks_dependency_readiness.py:31
- tests/specify_cli/cli/commands/agent/test_tasks_json_bytes.py:48
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py:40
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_identity_read.py:22
- tests/specify_cli/cli/commands/agent/test_tasks_planning_artifact_lifecycle.py:14
- tests/specify_cli/cli/commands/agent/test_tasks_status_progress.py:15
- tests/specify_cli/cli/commands/agent/test_wrapper_delegation.py:18
- tests/specify_cli/cli/commands/review/test_lane_gate_no_artifact_rendering.py:23
- tests/specify_cli/cli/commands/test_accept_clean_tree.py:38
- tests/specify_cli/cli/commands/test_accept_guidance_liveness.py:61
- tests/specify_cli/cli/commands/test_accept_merge_commit.py:45
- tests/specify_cli/cli/commands/test_accept_normalize_encoding.py:56
- tests/specify_cli/cli/commands/test_accept_readiness_no_write.py:32
- tests/specify_cli/cli/commands/test_materialize.py:13
- tests/specify_cli/cli/commands/test_merge.py:61
- tests/specify_cli/cli/commands/test_tasks_move_task_cwd.py:88
- tests/specify_cli/migration/test_normalize_mission_lifecycle.py:15
- tests/specify_cli/review/test_arbiter.py:26
- tests/specify_cli/status/test_lifecycle.py:17
- tests/specify_cli/status/test_progress.py:19
- tests/specify_cli/status/test_progress_integration.py:16
- tests/specify_cli/status/test_reconstruct_wp_view.py:38
- tests/specify_cli/test_accept_gate_convergence.py:32
- tests/specify_cli/test_accept_no_commit_readonly.py:37
- tests/specify_cli/test_acceptable_ending.py:36
- tests/specify_cli/test_acceptance.py:36
- tests/specify_cli/test_canonical_acceptance.py:22
- tests/status/conftest.py:21
- tests/status/test_cutover_eligibility.py:47
- tests/status/test_snapshot_schema_version.py:39
- tests/tasks/test_tasks_2x_unit.py:17
- tests/upgrade/migrations/test_m_3_2_0a4_normalize_mission_lifecycle.py:13

### from specify_cli.status.store import append_event [alone] [function-local] (40 occurrences)

- tests/consolidation/test_done_bookkeeping_seam.py:577
- tests/consolidation/test_merge_done_recording.py:729
- tests/consolidation/test_merge_done_recording.py:777
- tests/cross_branch/test_parity.py:142
- tests/integration/test_custom_mission_runtime_walk.py:371
- tests/integration/test_owned_next_runtime.py:813
- tests/integration/test_placement_partition_golden_path.py:680
- tests/integration/test_two_partition_preview.py:122
- tests/integration/test_two_partition_preview.py:82
- tests/integration/test_two_partition_preview.py:825
- tests/lanes/test_claim_base.py:723
- tests/migration/test_mission_state_repair.py:1817
- tests/next/test_next_command_integration.py:183
- tests/next/test_runtime_bridge_unit.py:80
- tests/retrospective/test_reducer_integration.py:729
- tests/retrospective/test_reducer_integration.py:858
- tests/retrospective/test_tracer_writer_write_dir.py:179
- tests/review/test_cycle_write_dir.py:383
- tests/runtime/_next_mission_scaffold.py:328
- tests/runtime/_next_mission_scaffold.py:77
- tests/runtime/test_next_board_authority.py:408
- tests/runtime/test_run_state_hardening.py:393
- tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py:304
- tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py:503
- tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py:617
- tests/specify_cli/cli/commands/agent/test_workflow.py:314
- tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py:366
- tests/specify_cli/consolidation/test_done_evidence_snapshot.py:264
- tests/specify_cli/core/test_dependency_graph_canceled.py:183
- tests/specify_cli/core/test_stale_sweep_snapshot.py:175
- tests/specify_cli/integration/test_migration_e2e.py:263
- tests/specify_cli/integration/test_migration_e2e.py:297
- tests/specify_cli/next/test_runtime_bridge_composition.py:1899
- tests/specify_cli/next/test_runtime_bridge_composition.py:979
- tests/specify_cli/test_locked_frontmatter_writers.py:527
- tests/status/test_emit.py:112
- tests/status/test_emit.py:121
- tests/status/test_emit.py:153
- tests/status/test_emit.py:173
- tests/tasks/test_pre_commit_wp_guard_unit.py:16

### from specify_cli.status.store import append_event [multi-name] (38 occurrences)

- tests/_factories/coord_mission.py:92
- tests/consolidation/test_conflict_resolution_integration.py:14
- tests/consolidation/test_event_count_union_4091.py:57
- tests/git_ops/test_atomic_status_commits_unit.py:51
- tests/integration/test_ac5_hash_guard.py:34
- tests/integration/test_review_durability_matrix.py:158
- tests/integration/test_wp_file_hash_stability.py:41
- tests/specify_cli/acceptance/test_accept_idempotency.py:42
- tests/specify_cli/cli/commands/agent/test_2684_force_provenance.py:50
- tests/specify_cli/cli/commands/agent/test_cancellation_provenance.py:37
- tests/specify_cli/cli/commands/agent/test_check_unchecked_subtasks_snapshot_source.py:32
- tests/specify_cli/cli/commands/agent/test_claim_ancestry_gate.py:46
- tests/specify_cli/cli/commands/agent/test_claim_event_source.py:77
- tests/specify_cli/cli/commands/agent/test_implement_runtime_frontmatter_claim.py:43
- tests/specify_cli/cli/commands/agent/test_move_task_agent_persistence_3029.py:51
- tests/specify_cli/cli/commands/agent/test_move_task_durability.py:78
- tests/specify_cli/cli/commands/agent/test_move_task_rollback_clears_claim.py:43
- tests/specify_cli/cli/commands/agent/test_status_baseline_wiring.py:26
- tests/specify_cli/cli/commands/agent/test_tasks.py:51
- tests/specify_cli/cli/commands/agent/test_tasks_backward_emit.py:48
- tests/specify_cli/cli/commands/agent/test_tasks_status_committed_authority.py:31
- tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py:67
- tests/specify_cli/cli/commands/agent/test_verdict_attribution_4670.py:31
- tests/specify_cli/cli/commands/agent/test_workflow_canonical_cleanup.py:26
- tests/specify_cli/cli/commands/test_implement_claim.py:22
- tests/specify_cli/status/test_lane_uninitialized.py:27
- tests/specify_cli/status/test_post_mission_lifecycle_events.py:39
- tests/specify_cli/status/test_store_sanitized.py:17
- tests/specify_cli/test_acceptance_regressions.py:36
- tests/specify_cli/test_runtime_hard_fail.py:23
- tests/specify_cli/test_terminal_state_gate_integrity.py:44
- tests/status/test_dependency_guard.py:41
- tests/status/test_derived_view_slug_traversal.py:34
- tests/status/test_emit.py:46
- tests/status/test_reducer.py:36
- tests/status/test_render_parity_golden.py:29
- tests/status/test_review_claim_role_aware.py:34
- tests/tasks/test_move_task_git_validation_unit.py:17

### import specify_cli.status.store as status_store (14 occurrences)

- tests/specify_cli/decisions/test_emit_locking.py:31
- tests/specify_cli/migration/test_backfill_writer_locking.py:24
- tests/specify_cli/retrospective/test_events_locking.py:20
- tests/specify_cli/retrospective/test_lifecycle_events_locking.py:21
- tests/status/test_agent_status_emit_cli.py:90
- tests/status/test_journal_lock_unification.py:41
- tests/status/test_store.py:109
- tests/status/test_store.py:174
- tests/status/test_store.py:211
- tests/status/test_store.py:242
- tests/status/test_store.py:273
- tests/status/test_store.py:81
- tests/status/test_writer_serialization.py:36
- tests/tasks/test_move_task_git_validation_unit.py:308

### from specify_cli.status._unsafe import append_event [alone] (6 occurrences)

- tests/characterization/test_trio_pure_cores.py:49
- tests/characterization/test_trio_transitions.py:37
- tests/review/test_artifacts.py:29
- tests/specify_cli/acceptance/test_populate_criteria_from_review_evidence.py:31
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_cli_4899.py:32
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py:55

### from specify_cli.status.store import append_event [multi-name] [parenthesised multiline] (5 occurrences)

- tests/integration/review/test_reject_from_in_review.py:21
- tests/specify_cli/cli/commands/agent/test_fixmode_ownership_4673.py:76
- tests/status/test_diffcov_2684_runtime_state_gaps.py:34
- tests/status/test_store.py:22
- tests/status/test_work_package_lifecycle.py:13

### import specify_cli.status.store as store_module (5 occurrences)

- tests/specify_cli/status/test_store_sanitized.py:110
- tests/specify_cli/status/test_store_sanitized.py:160
- tests/specify_cli/status/test_store_sanitized.py:338
- tests/specify_cli/status/test_store_sanitized.py:360
- tests/specify_cli/status/test_store_sanitized.py:393

### from specify_cli.status import store as status_store [function-local] (4 occurrences)

- tests/integration/review/test_verdict_save_topologies.py:823
- tests/integration/test_review_durability_matrix.py:1788
- tests/specify_cli/coordination/test_status_transition.py:176
- tests/specify_cli/coordination/test_status_transition.py:209

### from specify_cli.status._unsafe import append_event [alone] [function-local] (3 occurrences)

- tests/specify_cli/acceptance/test_accept_candidate_source_tree_4254.py:300
- tests/specify_cli/cli/commands/agent/test_tasks.py:435
- tests/specify_cli/cli/commands/agent/test_tasks.py:474

### from specify_cli.status import store as _store (2 occurrences)

- tests/specify_cli/coordination/test_transaction.py:41
- tests/status/test_diffcov_2684_runtime_state_gaps.py:26

### monkeypatch.setattr(<obj>, 'append_event', ...)  obj=status_store (2 occurrences)

- tests/status/test_store.py:114
- tests/status/test_store.py:83

### from specify_cli.status.store import append_event [multi-name] [function-local] (1 occurrences)

- tests/architectural/test_no_op_stable_writes.py:222

### from specify_cli.status import _unsafe (1 occurrences)

- tests/architectural/test_status_unsafe_allowlist.py:54

### from specify_cli.status import store as status_store (1 occurrences)

- tests/integration/refinalize_frozen_lanes_support.py:33

### from specify_cli.status.store import append_event_verified [multi-name] [parenthesised multiline] (1 occurrences)

- tests/status/test_store.py:22

### from specify_cli.status.store import append_event [multi-name] [parenthesised multiline] [function-local] (1 occurrences)

- tests/utils.py:52

## Appendix B: per-file door call counts

| File | Calls |
|---|---|
| tests/_factories/coord_mission.py | 1 |
| tests/agent/test_context_resolve_unit.py | 1 |
| tests/agent/test_status_state_phantom_degrade.py | 1 |
| tests/agent/test_workflow_feedback_pointer_2x_unit.py | 1 |
| tests/agent/test_workflow_review_cycle_pointer.py | 9 |
| tests/agent/test_workflow_review_lane_gate.py | 2 |
| tests/architectural/test_2093_authority_invariant.py | 2 |
| tests/architectural/test_no_op_stable_writes.py | 1 |
| tests/characterization/test_trio_pure_cores.py | 1 |
| tests/characterization/test_trio_transitions.py | 3 |
| tests/charter_offering/test_spk_show_me_skill.py | 1 |
| tests/cli/test_agent_retrospect_missing_record.py | 1 |
| tests/cli/test_charter_activate_warning.py | 1 |
| tests/cli/test_move_task_planned_guard.py | 2 |
| tests/consolidation/test_2959_skip_review_artifact_check.py | 1 |
| tests/consolidation/test_canceled_dependency_lane.py | 1 |
| tests/consolidation/test_conflict_resolution_integration.py | 2 |
| tests/consolidation/test_coord_teardown_order_3926.py | 1 |
| tests/consolidation/test_done_bookkeeping_seam.py | 1 |
| tests/consolidation/test_event_count_union_4091.py | 1 |
| tests/consolidation/test_issue_2709_projection_union.py | 1 |
| tests/consolidation/test_merge_done_recording.py | 2 |
| tests/contract/test_machine_facing_canonical_fields.py | 2 |
| tests/coordination/test_status_transition_write_dir.py | 2 |
| tests/core/test_mission_create_idempotency_guard.py | 1 |
| tests/cross_branch/test_parity.py | 1 |
| tests/git_ops/test_atomic_status_commits_unit.py | 1 |
| tests/integration/migration/test_noop_upgrade_leaves_history_untouched.py | 1 |
| tests/integration/migration/test_residue_dir_not_treated_as_mission.py | 1 |
| tests/integration/review/test_approve_without_force.py | 1 |
| tests/integration/review/test_reject_from_in_review.py | 1 |
| tests/integration/test_2646_stale_verdict_closes_via_fr001.py | 1 |
| tests/integration/test_ac5_hash_guard.py | 1 |
| tests/integration/test_custom_mission_runtime_walk.py | 1 |
| tests/integration/test_dossier_snapshot_no_self_block.py | 1 |
| tests/integration/test_explicit_checkout_commands.py | 1 |
| tests/integration/test_implement_review_retrospect_smoke.py | 4 |
| tests/integration/test_mission_archiving.py | 1 |
| tests/integration/test_owned_next_runtime.py | 1 |
| tests/integration/test_placement_partition_golden_path.py | 1 |
| tests/integration/test_prompt_builder_owned_arms.py | 1 |
| tests/integration/test_rejection_cycle.py | 19 |
| tests/integration/test_review_cycle_rejection_only.py | 9 |
| tests/integration/test_review_durability_matrix.py | 7 |
| tests/integration/test_review_handoff.py | 1 |
| tests/integration/test_two_partition_preview.py | 3 |
| tests/integration/test_worktree_topology_claim_base.py | 1 |
| tests/integration/test_wp_file_hash_stability.py | 1 |
| tests/integration/test_wp_integrity_p0_repro.py | 1 |
| tests/lanes/test_claim_base.py | 1 |
| tests/lanes/test_issue_4889_destroyed_lane_guard.py | 1 |
| tests/lanes/test_recovery_post_merge.py | 1 |
| tests/lanes/test_recovery_write_dir.py | 1 |
| tests/migration/test_mission_state_repair.py | 1 |
| tests/mission_runtime/test_claim_commit.py | 1 |
| tests/mission_runtime/test_resolution_target_branch.py | 1 |
| tests/next/test_decision_unit.py | 1 |
| tests/next/test_finalized_task_routing.py | 1 |
| tests/next/test_next_claimable_payload.py | 2 |
| tests/next/test_next_command_integration.py | 1 |
| tests/next/test_prompt_builder_review_base.py | 1 |
| tests/next/test_runtime_bridge_unit.py | 1 |
| tests/orchestrator_api/test_issue_4889_caller_independence.py | 1 |
| tests/perf/test_tasks_status_baseline.py | 1 |
| tests/post_merge/test_2684_review_override_recognition.py | 1 |
| tests/post_merge/test_review_artifact_consistency.py | 1 |
| tests/reliability/fixtures/mission.py | 1 |
| tests/retrospective/test_reducer_integration.py | 2 |
| tests/retrospective/test_tracer_writer_write_dir.py | 1 |
| tests/review/test_arbiter.py | 1 |
| tests/review/test_artifacts.py | 1 |
| tests/review/test_cycle_write_dir.py | 1 |
| tests/review/test_pre_review_gate_integration.py | 1 |
| tests/review/test_verdict_save_performance.py | 1 |
| tests/review/test_verdict_seam_reader_collapse.py | 1 |
| tests/runtime/_next_mission_scaffold.py | 2 |
| tests/runtime/next/test_cli_guard_family.py | 1 |
| tests/runtime/next/test_committed_authority.py | 1 |
| tests/runtime/next/test_coord_topology_fixture.py | 1 |
| tests/runtime/next/test_merged_mission_terminal.py | 1 |
| tests/runtime/test_artifact_presence_placement.py | 1 |
| tests/runtime/test_cli_guard_family.py | 1 |
| tests/runtime/test_next_board_authority.py | 1 |
| tests/runtime/test_run_state_hardening.py | 1 |
| tests/runtime/test_runtime_bridge_read_path_branches.py | 1 |
| tests/runtime/test_workspace_context_unit.py | 1 |
| tests/specify_cli/acceptance/test_accept_candidate_source_tree_4254.py | 1 |
| tests/specify_cli/acceptance/test_accept_idempotency.py | 1 |
| tests/specify_cli/acceptance/test_accept_pre30_hard_reject.py | 1 |
| tests/specify_cli/acceptance/test_populate_criteria_from_review_evidence.py | 10 |
| tests/specify_cli/cli/commands/_review_fixtures.py | 1 |
| tests/specify_cli/cli/commands/agent/_rework_loop_harness.py | 1 |
| tests/specify_cli/cli/commands/agent/test_2684_force_provenance.py | 1 |
| tests/specify_cli/cli/commands/agent/test_approval_after_forced_review_exit.py | 1 |
| tests/specify_cli/cli/commands/agent/test_cancellation_provenance.py | 1 |
| tests/specify_cli/cli/commands/agent/test_check_unchecked_subtasks_snapshot_source.py | 1 |
| tests/specify_cli/cli/commands/agent/test_claim_ancestry_gate.py | 1 |
| tests/specify_cli/cli/commands/agent/test_claim_event_source.py | 2 |
| tests/specify_cli/cli/commands/agent/test_finalize_provenance_guard.py | 1 |
| tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py | 1 |
| tests/specify_cli/cli/commands/agent/test_fixmode_ownership_4673.py | 1 |
| tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py | 1 |
| tests/specify_cli/cli/commands/agent/test_implement_runtime_frontmatter_claim.py | 1 |
| tests/specify_cli/cli/commands/agent/test_issue_3311_finalize_rewrites_active_lanes.py | 1 |
| tests/specify_cli/cli/commands/agent/test_issue_4141_refresh_planning_commit.py | 1 |
| tests/specify_cli/cli/commands/agent/test_issue_4827_repin_orphaned_planning_commit.py | 1 |
| tests/specify_cli/cli/commands/agent/test_issue_5328_finalize_refresh_dry_run.py | 1 |
| tests/specify_cli/cli/commands/agent/test_issue_5328_refresh_fail_closed.py | 3 |
| tests/specify_cli/cli/commands/agent/test_move_task_agent_persistence_3029.py | 1 |
| tests/specify_cli/cli/commands/agent/test_move_task_approval_body_collision.py | 2 |
| tests/specify_cli/cli/commands/agent/test_move_task_approval_evidence.py | 1 |
| tests/specify_cli/cli/commands/agent/test_move_task_done_exit.py | 1 |
| tests/specify_cli/cli/commands/agent/test_move_task_durability.py | 2 |
| tests/specify_cli/cli/commands/agent/test_move_task_orchestration.py | 3 |
| tests/specify_cli/cli/commands/agent/test_move_task_reject_fix_approve_cycle.py | 1 |
| tests/specify_cli/cli/commands/agent/test_move_task_rollback_clears_claim.py | 1 |
| tests/specify_cli/cli/commands/agent/test_status_baseline_wiring.py | 1 |
| tests/specify_cli/cli/commands/agent/test_tasks.py | 7 |
| tests/specify_cli/cli/commands/agent/test_tasks_backward_emit.py | 2 |
| tests/specify_cli/cli/commands/agent/test_tasks_canonical_cleanup.py | 3 |
| tests/specify_cli/cli/commands/agent/test_tasks_cli_contract.py | 1 |
| tests/specify_cli/cli/commands/agent/test_tasks_cli_contract_coord.py | 1 |
| tests/specify_cli/cli/commands/agent/test_tasks_core_backed_orchestration.py | 1 |
| tests/specify_cli/cli/commands/agent/test_tasks_dependency_readiness.py | 1 |
| tests/specify_cli/cli/commands/agent/test_tasks_json_bytes.py | 1 |
| tests/specify_cli/cli/commands/agent/test_tasks_move_task_cli_4899.py | 3 |
| tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py | 4 |
| tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_identity_read.py | 1 |
| tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py | 1 |
| tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py | 5 |
| tests/specify_cli/cli/commands/agent/test_tasks_planning_artifact_lifecycle.py | 1 |
| tests/specify_cli/cli/commands/agent/test_tasks_status_committed_authority.py | 1 |
| tests/specify_cli/cli/commands/agent/test_tasks_status_progress.py | 1 |
| tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py | 3 |
| tests/specify_cli/cli/commands/agent/test_verdict_attribution_4670.py | 1 |
| tests/specify_cli/cli/commands/agent/test_workflow.py | 1 |
| tests/specify_cli/cli/commands/agent/test_workflow_canonical_cleanup.py | 1 |
| tests/specify_cli/cli/commands/agent/test_wrapper_delegation.py | 1 |
| tests/specify_cli/cli/commands/review/test_lane_gate_no_artifact_rendering.py | 1 |
| tests/specify_cli/cli/commands/test_accept_clean_tree.py | 2 |
| tests/specify_cli/cli/commands/test_accept_guidance_liveness.py | 2 |
| tests/specify_cli/cli/commands/test_accept_merge_commit.py | 2 |
| tests/specify_cli/cli/commands/test_accept_normalize_encoding.py | 3 |
| tests/specify_cli/cli/commands/test_accept_readiness_no_write.py | 1 |
| tests/specify_cli/cli/commands/test_implement_claim.py | 1 |
| tests/specify_cli/cli/commands/test_materialize.py | 2 |
| tests/specify_cli/cli/commands/test_merge.py | 4 |
| tests/specify_cli/cli/commands/test_tasks_move_task_cwd.py | 3 |
| tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py | 1 |
| tests/specify_cli/consolidation/test_done_evidence_snapshot.py | 1 |
| tests/specify_cli/core/test_dependency_graph_canceled.py | 3 |
| tests/specify_cli/core/test_stale_sweep_snapshot.py | 1 |
| tests/specify_cli/integration/test_migration_e2e.py | 2 |
| tests/specify_cli/migration/test_normalize_mission_lifecycle.py | 1 |
| tests/specify_cli/next/test_runtime_bridge_composition.py | 2 |
| tests/specify_cli/review/test_arbiter.py | 1 |
| tests/specify_cli/status/test_lane_uninitialized.py | 1 |
| tests/specify_cli/status/test_lifecycle.py | 1 |
| tests/specify_cli/status/test_post_mission_lifecycle_events.py | 1 |
| tests/specify_cli/status/test_progress.py | 1 |
| tests/specify_cli/status/test_progress_integration.py | 1 |
| tests/specify_cli/status/test_reconstruct_wp_view.py | 1 |
| tests/specify_cli/status/test_store_sanitized.py | 3 |
| tests/specify_cli/test_accept_gate_convergence.py | 1 |
| tests/specify_cli/test_accept_no_commit_readonly.py | 3 |
| tests/specify_cli/test_acceptable_ending.py | 1 |
| tests/specify_cli/test_acceptance.py | 1 |
| tests/specify_cli/test_acceptance_regressions.py | 1 |
| tests/specify_cli/test_canonical_acceptance.py | 4 |
| tests/specify_cli/test_locked_frontmatter_writers.py | 2 |
| tests/specify_cli/test_runtime_hard_fail.py | 3 |
| tests/specify_cli/test_terminal_state_gate_integrity.py | 2 |
| tests/status/conftest.py | 1 |
| tests/status/test_cutover_eligibility.py | 11 |
| tests/status/test_dependency_guard.py | 2 |
| tests/status/test_derived_view_slug_traversal.py | 2 |
| tests/status/test_diffcov_2684_runtime_state_gaps.py | 1 |
| tests/status/test_emit.py | 7 |
| tests/status/test_reducer.py | 14 |
| tests/status/test_render_parity_golden.py | 1 |
| tests/status/test_review_claim_role_aware.py | 3 |
| tests/status/test_snapshot_schema_version.py | 1 |
| tests/status/test_store.py | 13 |
| tests/status/test_work_package_lifecycle.py | 30 |
| tests/tasks/test_move_task_git_validation_unit.py | 1 |
| tests/tasks/test_pre_commit_wp_guard_unit.py | 1 |
| tests/tasks/test_tasks_2x_unit.py | 1 |
| tests/upgrade/migrations/test_m_3_2_0a4_normalize_mission_lifecycle.py | 1 |
| tests/utils.py | 1 |
