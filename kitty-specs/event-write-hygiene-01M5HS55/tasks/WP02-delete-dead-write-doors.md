---
work_package_id: WP02
title: Delete the dead write doors (#6614)
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-005
- NFR-004
- SC-001
- C-005
planning_base_branch: feat/event-write-hygiene
merge_target_branch: feat/event-write-hygiene
branch_strategy: Planning artifacts for this mission were generated on feat/event-write-hygiene. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/event-write-hygiene unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T009
phase: 'Phase 2 - #6614'
history:
- at: '2026-10-22T13:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/store.py
- src/specify_cli/status/_unsafe.py
- src/specify_cli/status/design.py
- src/specify_cli/coordination/status_service.py
- src/specify_cli/cli/commands/invocations_cmd.py
- tests/architectural/dead_symbol_allowlist.yaml
- tests/architectural/_baselines.yaml
- tests/agent/test_orchestrator_lane_allocation.py
- tests/agent/test_orchestrator_lane_context_refresh.py
- tests/architectural/test_status_events_writes_gate.py
- tests/architectural/test_status_unsafe_allowlist.py
- tests/contract/test_mission_status_drift.py
- tests/contract/test_mission_status_ops.py
- tests/specify_cli/cli/commands/agent/test_emit_review_result.py
- tests/specify_cli/coordination/test_1622_dead_symbol_retirement.py
- tests/specify_cli/coordination/test_owned_status_read_contract.py
- tests/specify_cli/coordination/test_phantom_fanout.py
- tests/specify_cli/coordination/test_plain_door_semantics.py
- tests/specify_cli/coordination/test_status_surface_owned.py
- tests/specify_cli/coordination/test_status_transition.py
- tests/specify_cli/coordination/test_wp05_status_emit_seam_feature_dir.py
- tests/specify_cli/invocation/cli/test_invocations.py
- tests/specify_cli/lanes/test_for_review_gate_parity.py
- tests/specify_cli/test_workspace_context_tombstone.py
- tests/status/test_execution_projection.py
- tests/status/test_lane_head.py
- tests/status/test_store.py
- tests/specify_cli/status/test_store_sanitized.py
- src/kernel/atomic.py
- tests/kernel/test_atomic.py
- src/specify_cli/cli/commands/agent/mission_finalize_commit.py
- tests/specify_cli/test_locked_frontmatter_writers.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Delete the dead write doors (#6614)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter. Follow its guidance before reading the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status --mission event-write-hygiene-01M5HS55` for a `review_ref`. Address every item, and record each change with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

Delete five functions that no production code calls:

| Function | Location |
|---|---|
| `append_event` (plain `open("a")`, not atomic) | `src/specify_cli/status/store.py:303` |
| `append_event_verified` | `store.py:347` |
| `append_primary_checkout_event_verified` | `store.py:360` |
| `append_event_log` | `src/specify_cli/coordination/status_service.py:304` |
| `append_to_index` | `src/specify_cli/cli/commands/invocations_cmd.py:150` |

Done means:

- Every **existing** gate that should keep these doors from coming back is re-pinned, and each change is committed **red first** (C-005).
- A single-writer check pins `kitty-ops/ops-index.jsonl` to `specify_cli.invocation.writer`.
- Behaviour does not change. Every surviving writer writes the same bytes, and contract-validation coverage moves to `append_event_stream_log` rather than disappearing.

Requirements: FR-001, FR-002, FR-003, FR-005, NFR-004, SC-001.

## Context & Constraints

- **Mission documents** (all under `kitty-specs/event-write-hygiene-01M5HS55/`):
  - `plan.md`: IC-02, IC-03 and the Engineering Alignment gate list.
  - `research.md`: the squad dispositions.
  - `research-census.md`: sections 3 and 6, plus the riskiest-findings list.
- **WP01 has landed.** Tests no longer import the door; they seed through `tests._support.status_seed`. The only remaining users are the door's own tests in `tests/status/test_store.py` and `tests/specify_cli/status/test_store_sanitized.py`, which this WP owns.
- **Charter gate discipline.** Extend the owning gates; do not write a parallel scanner. Every gate keeps a non-vacuity floor and a planted-fault self-test. Add **no** allowlist entries.
- **`ALLOWED_CALLERS` and `BASELINE` in `_unsafe` do NOT shrink.** `coordination.status_service` still imports `append_event_stream_atomic_verified` and `append_annotations_atomic_verified`.
  - `append_event_log` currently imports `append_annotations_atomic_verified`. After the deletion, check that some other function in `status_service.py` still imports it. If none does, the stale-entry rule in `test_status_unsafe_allowlist.py` will say so; follow it.
- **Ownership-map leeway.** Two files WP01 owns also use `append_event_log`: `tests/lanes/test_claim_base.py` and `tests/status/test_dependency_guard.py`. Retarget them here as small recorded out-of-map edits, with a one-line history note.

## Branch Strategy

- **Strategy**: `single_branch`, in the repository root checkout on `feat/event-write-hygiene`.
- **Planning base branch**: `feat/event-write-hygiene`.
- **Merge target branch**: `feat/event-write-hygiene`.
- Implement with: `spec-kitty agent action implement WP02 --agent claude --mission event-write-hygiene-01M5HS55`.

## Subtasks & Detailed Guidance

### Subtask T005 – Red-first: re-pin the door gates

- **Purpose:** make the gates describe the target state before the code reaches it, and commit them failing.
- **Steps:**
  1. In `tests/architectural/test_status_unsafe_allowlist.py`:
     - Remove `append_event`, `append_event_verified` and `append_primary_checkout_event_verified` from `STORE_APPEND_PRIMITIVES` (:72-84).
     - Remove `append_event_log` from `COORD_WRAPPER_DOORS` (:93).
     - The sample-door fixtures at :278, :314 and :316 use `from specify_cli.status._unsafe import append_event`. They still count as doors after the change (`_doors_from_import_from`, :165), so switching them to `append_raw_rows_atomic` is optional. The file has 316 lines and no rationale map.
     - Keep the module docstring's door-shape list accurate (:37 names `append_event_log`).
  2. In `tests/architectural/test_status_events_writes_gate.py::test_store_writes_are_found` (:687-694), re-pin the expected store write set to `{("os.replace", "replace")}`. Update the comment: the store's only write to the event log is now the atomic rename.
  3. **Make FR-002/FR-003 red first through the dead-symbol gate.**
     - Remove the `append_to_index` (:1277) and `append_event_log` (:1287) entries from `tests/architectural/dead_symbol_allowlist.yaml` in this red commit. While those symbols still exist with no `src/` caller, `test_no_dead_symbols` fails on them.
     - Add `assert not hasattr(status_service, "append_event_log")` to `tests/specify_cli/coordination/test_1622_dead_symbol_retirement.py`, in the style of its existing `append_event_log_batch` ban (:54).
  4. **Invocation-index single writer.** Add a test to the same writes-gate file, reusing its `src_source_tree` fixture and its `_classify_call` / `_classify_method_call` write classifiers. Do not write a second classifier.
     - **What to flag:** a top-level function or method in `src/` that (a) refers to the index through a **non-docstring** string constant exactly equal to `"ops-index.jsonl"` or `"kitty-ops/ops-index.jsonl"`, or through a `Name` / `Attribute` reference to `INDEX_PATH` (or a module constant holding that exact value), and (b) contains a write-mode file operation, or calls a same-module function or `staticmethod` that contains one. Never match substrings and never inspect docstrings: `write_started`'s docstring (writer.py:240) names the index and that method opens a file with `"x"`.
     - **Expected set:** exactly `{("specify_cli.invocation.writer", "InvocationWriter._append_to_index")}`.
     - **Why a function census:** the plain path resolver cannot follow `INDEX_PATH` across modules, and the writer's shared `_append_line_no_follow` staticmethod is called with different paths. Document this in the test docstring.
     - **Non-vacuity:**
       - a planted source like `invocations_cmd.append_to_index` must be reported;
       - a planted read-only use of `INDEX_PATH` must not be reported. Model it on `invocations_cmd._iter_records` (:346), which uses both `INDEX_PATH` and the literal and only reads.
       - a planted docstring-only mention plus an unrelated `"x"` open must not be reported;
       - a floor: the live scan finds the writer's own function.
  5. Run the gates. They must fail on the current tree, and each reported failure must be one of the following:
     - the store doors still exist (`STORE_APPEND_PRIMITIVES`);
     - the store still has the `Path.open "a"` site;
     - `append_event_log` / `append_to_index` are dead symbols missing from the allowlist;
     - the `hasattr` ban fails;
     - the index census reports `invocations_cmd.append_to_index`. Commit only the gate changes, with message `test(arch): re-pin door gates for #6614 dead write doors (red)`. Record the red output (test ids and the failing assertions) in history.

### Subtask T006 – Delete the store doors and shrink `_unsafe`

- **Steps:**
  1. In `store.py`, delete `append_event` (:303-314), `append_event_verified` (:347-357) and `append_primary_checkout_event_verified` (:360-366).
     - Keep `verify_event_readback` and `_event_matches_expected`; the surviving verified primitives use them. Confirm with `rg`.
     - Fix the `append_events_atomic` docstring (:461-466), which says the single-event append "remains the compatibility path". That is no longer true.
     - `kernel.atomic.notify_file_written` loses its only `src/` caller (store.py:314) and would turn `test_no_dead_symbols` red. Delete it from `src/kernel/atomic.py` (:72-80) and from its `__all__` (:40).
     - Delete its test in `tests/kernel/test_atomic.py` (:452-, and drop the name from the :22 import). Keep `notify_written` and its tests.
     - Fix the docstring at `src/specify_cli/cli/commands/agent/mission_finalize_commit.py:1057`, which names it: appends are now recorded by `notify_written` after the atomic replace.
     - `tests/specify_cli/test_locked_frontmatter_writers.py:524` tests the door's in-place notify behaviour. Delete that test. If the file's intent covers status-log writes generally, retarget it to assert that `append_events_atomic` notifies through `notify_written`. Record which you did.
  2. In `status/_unsafe.py`, drop the three names from the import and from `__all__`. Fix the docstring at :18, which uses `append_event` as its ImportError example (pick a surviving primitive), and the Family 3 comment at :83.
  3. In `status/__init__.py:75-77`, fix the comment that lists the retired primitives. This is a one-line recorded leeway edit; WP03 owns the file.
  4. In `status/design.py:79`, fix the claim that every writer "appends through the same inode". The atomic path replaces the file.
  5. Door tests in `tests/status/test_store.py` and `tests/specify_cli/status/test_store_sanitized.py`:
     - Delete tests whose only subject is the deleted door (plain append, `append_event_verified` error wrapping).
     - Retarget tests that cover row serialization or sanitization through the door onto `append_events_atomic` or `append_events_atomic_verified`, keeping their assertions. This includes the monkeypatches at `test_store.py:83` and `:114` if they test readback verification, which `append_events_atomic_verified` still performs.
     - Record each delete-vs-retarget decision in history.
- **Validation:** `.venv/bin/python -m pytest tests/status/test_store.py tests/specify_cli/status/test_store_sanitized.py -q`

### Subtask T007 – Delete `append_event_log`; retarget its tests

- **Steps:**
  1. In `coordination/status_service.py`, delete `append_event_log` (:304-321). Keep `append_event_stream_log` and `_validate_write_contract`.
  2. Retarget every test call `append_event_log(contract, event)` to `append_event_stream_log(contract, [event])`.
     - The census found 28 calls in 16 files, all passing one `StatusEvent`. The files are in this WP's `owned_files`, plus the two leeway files.
     - Tests that assert contract-validation errors (`requires EventLogWriteContract`, the coordination-path refusals) keep their meaning, because both doors share `_validate_write_contract`. Update an expected message only where it names the function (`append_event_log requires ...`).
  3. `tests/specify_cli/coordination/test_1622_dead_symbol_retirement.py` may pin this symbol's dead status. Read it and update it to state the symbol is now deleted, or drop the pin if a deleted symbol makes it vacuous.
- **Validation:** run all 18 files.

### Subtask T008 – Delete `append_to_index`; retarget the invocation tests

- **Steps:**
  1. In `cli/commands/invocations_cmd.py`, delete `append_to_index` (:150-173), including its false docstring. Keep `INDEX_PATH` reads. Drop imports that are now unused.
  2. In `tests/specify_cli/invocation/cli/test_invocations.py`, retarget the four call sites:
     - Where the test builds a real invocation, use `InvocationWriter(...).write_started(...)`. Look at how other tests in that file construct the writer.
     - The census found one seed that writes an index entry with **no** matching op file. It tests that `invocations list` tolerates a dangling index row. The public writer cannot produce that state, so write the fixture line directly in the test with a small local helper (`(repo_root / INDEX_PATH).write_text(json.dumps({...}) + "\n")`). Name the intent in a comment. Do not call the writer's private `_append_to_index`.
  3. `tests/contract/test_mission_status_ops.py:1817` and `tests/contract/test_mission_status_drift.py:1927` keep `append_to_index` in their forbidden or writing name sets as reintroduction bans. Leave them unless they fail; if they do, read why first.
- **Validation:** `.venv/bin/python -m pytest tests/specify_cli/invocation tests/contract/test_mission_status_ops.py tests/contract/test_mission_status_drift.py -q`

### Subtask T009 – Dead-symbol allowlist, baselines and the blast radius

- **Steps:**
  1. In `tests/architectural/dead_symbol_allowlist.yaml`, remove the `append_to_index` (:1277) and `append_event_log` (:1287) entries.
  2. In `tests/architectural/_baselines.yaml`, lower the counts that track that allowlist. The allowlist entries were already removed in the red commit (T005). Both sit in `widened_grandfathered_470`, so expect 85→83 there. `allowlist_entries` 229→228 is probably wrong. Verify the real keys and numbers by running `tests/architectural/test_no_dead_symbols.py` and the baseline ratchet test that reads `_baselines.yaml`. Shrinkage only warns, but keep the ledger truthful.
  3. Run the gate files on their own:
     ```bash
     PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_status_unsafe_allowlist.py tests/architectural/test_status_events_writes_gate.py tests/architectural/test_no_dead_symbols.py -q
     ```
     Also run `tests/architectural/test_ruff_format_exclude_ratchet.py` (test_store.py and test_store_sanitized.py are on the formatter-debt ratchet, pyproject :2183/:2059; keep them unformatted), `tests/kernel/test_atomic.py`, `tests/specify_cli/test_locked_frontmatter_writers.py`, the baselines ratchet file, then `tests/status`, `tests/specify_cli/coordination`, `tests/specify_cli/invocation`, the 18 retargeted files and `make test-fast`.
  4. Run `mypy` on `store.py`, `_unsafe.py`, `status_service.py` and `invocations_cmd.py`. Then run `ruff check` and `ruff format --check --force-exclude` on every changed file.

## Test Strategy

- Gate changes are red first (T005), then green. Record both runs.
- Never run a bare `tests/architectural` sweep or `make test-full`.

## Risks & Mitigations

- **Contract validation silently dropped.** Every `append_event_log` contract test must still assert its error, now through `append_event_stream_log`.
- **Stale `_unsafe` import.** If `append_annotations_atomic_verified` has no remaining importer in `status_service`, the allowlist test's stale-entry rule fires. Read it before "fixing" anything.
- **Index census over-matching read-only users.** The planted read-only control in T005 guards against it.

## Review Guidance

- Confirm the red commit precedes the deletions, and its failure output is in history.
- Confirm the door's own tests were retargeted or deleted with a recorded reason, and no assertion was weakened.
- Confirm the index single-writer test has both the positive and negative planted controls and a live floor.
- Confirm mypy and ruff are clean and no suppression was added.

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP02 --note "..."` and `spec-kitty agent tasks mark-status T005 ... --status done`. When finished, run `spec-kitty agent tasks move-task WP02 --to for_review`.
