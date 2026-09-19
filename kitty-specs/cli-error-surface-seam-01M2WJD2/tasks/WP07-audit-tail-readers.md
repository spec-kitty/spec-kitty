---
work_package_id: WP07
title: Harden audit-tail readers + replace runtime_bridge mask (#4746)
dependencies:
- WP01
requirement_refs:
- FR-012
planning_base_branch: fix/cli-error-surface-seam
merge_target_branch: fix/cli-error-surface-seam
branch_strategy: Planning artifacts for this mission were generated on fix/cli-error-surface-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cli-error-surface-seam unless the human explicitly redirects the landing branch.
subtasks:
- T024
- T025
- T026
- T027
phase: Phase 2 - Adoption
history:
- at: '2026-09-19T10:45:02Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/
create_intent:
- tests/specify_cli/test_audit_tail_readers.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/decisions/service.py
- src/specify_cli/merge/state.py
- src/specify_cli/review/baseline.py
- src/specify_cli/review/lock.py
- src/specify_cli/review/artifacts.py
- src/specify_cli/status/validate.py
- src/specify_cli/core/wps_manifest.py
- src/runtime/next/runtime_bridge.py
- tests/specify_cli/test_audit_tail_readers.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Harden audit-tail readers + replace runtime_bridge mask (#4746)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## 🔴 BINDING SQUAD AMENDMENTS (post-tasks fold — read before implementing)

1. **T026 — the `runtime_bridge` try-block guards a 5th operation** the census omits: `_log_requirement_extraction_warnings_safely` (`runtime_bridge.py:1022`), alongside `spec_md.read_text` (:1016), `parse_requirement_ids_from_spec_md` (:1017), `load_wps_manifest` (:1023), `read_all_wp_requirement_refs` (:1024). Enclosing fn is `_check_requirement_mapping_ready` (def :982, try opens ~:1010). The broad catch at **:1034 returns `[f"Requirement mapping preflight failed: {exc}"]`** (not `[]`) — preserve that return contract for the non-manifest failures; only narrow so `WpsManifestReadError` (and other typed reads) surface via the seam. `_log_requirement_extraction_warnings_safely` self-swallows via its own `except` at :974, so it will not raise into the narrowed block — name it in the companion assertion anyway.
2. **Depends on WP01** — do not re-parent `DecisionIndexReadError` here (WP01 owns `decisions/store.py`); WP07 mints `WpsManifestReadError` in `core/wps_manifest.py` itself.
3. **D5 is load-bearing**: `merge/state.py::_load_state_file` (~:220) returns `None` on missing; `load_wps_manifest` (:69-86) returns `None` when `wps.yaml` is absent (caller `runtime_bridge` branches on it). Preserve absent→`None`; only corrupt→typed error.

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

FR-012 "audit-tail" adoption: route the 7 readers named in research.md's
census through `kernel.read_guarded` (WP01), and replace the masking
`except Exception` in `runtime_bridge.py` with the typed seam. Wave-1
(parallel with WP02–WP06); **WP08's gate depends on this WP being green**.

Success (spec.md US3 scenarios 2–4, SC-004):

- Each of the 7 readers, exercised **through its real command entry
  point** (never a bare call to the reader function), presents a typed
  `GuardedReadError` subclass via the hook on corrupt/non-UTF-8 input —
  zero traceback frames.
- **D5 preserved exactly**: every reader that returns `None`/empty/`False`
  on *absent* input keeps doing so; only decode/parse/schema failure on
  *present* input routes to the typed error.
- The `runtime_bridge.py` mask around `load_wps_manifest` is replaced by
  the typed seam, with a companion assertion that the other three
  operations sharing that block (`spec_md.read_text`,
  `parse_requirement_ids_from_spec_md`, `read_all_wp_requirement_refs`)
  are unaffected.
- ruff + mypy clean, no suppressions; complexity ≤ 15; ≥ 90% new-code
  coverage (C-007, NFR-004).

## Context & Constraints

- Depends on **WP01** — read `contracts/guarded-read-primitive.md` +
  `contracts/error-envelope.md` first; call the primitive, don't reinvent it.
- `research.md`'s except-site census + D5 are binding: never collapse a
  `None`-on-absent contract into an error.
- WP01 re-parents the *type hierarchy* on `core/wps_manifest.py` /
  `decisions/store.py`; this WP owns the *reader logic* only.
- The 7 readers, verified against the live tree 2026-09-19 (re-confirm
  before writing tests — the tree moves):
  | Reader | Guard gap | Reachable via | Preserve |
  |---|---|---|---|
  | `decisions/service.py::_opened_event_exists` (~188, ~200) | `read_text` only guards `OSError`; `json.loads` only `JSONDecodeError` | `open_decision()` → `spec-kitty decision open` | n/a (no absent branch) |
  | `merge/state.py::_load_state_file` (~225) | `open`+`json.load` guarded by `(JSONDecodeError, TypeError, KeyError)`, not `OSError`/`UnicodeDecodeError` | `spec-kitty merge`, coordination doctor | `None` on `not state_path.exists()` (~222) stays outside the guard |
  | `review/baseline.py::BaselineTestResult.load` (~131) | `JSONDecodeError` guarded, raw `OSError` not | `agent tasks move-task`, `workflow_executor.py` | `None` on `not path.exists()` |
  | `review/lock.py::ReviewLock.load` (~108) | fully unguarded for `OSError` | `ReviewLock.acquire()` ← `spec-kitty review` claim step | `None` on `not lock_path.exists()` |
  | `review/artifacts.py::ReviewCycleArtifact.from_file` (~288) | `read_text` catches `OSError` → re-raises bare `ValueError` | `review/cycle.py` → `spec-kitty review` | n/a |
  | `status/validate.py::validate_materialization_drift` (~249) | `read_text`+`json.loads` fully unguarded | `agent status validate` (`status.py` ~930) | n/a |
  | `core/wps_manifest.py::load_wps_manifest` (~86, ~90) | `yaml.load`+`model_validate` unguarded, raises `pydantic.ValidationError` | `finalize-tasks` + `runtime_bridge.py` (T026) | `None` when `wps.yaml` absent (~80) stays outside |
- `runtime_bridge.py` (~1010–1035, enclosing function — re-derive its name
  from the live file): the `try` wraps `load_wps_manifest` plus
  `spec_md.read_text`, `parse_requirement_ids_from_spec_md`,
  `read_all_wp_requirement_refs`, and the tasks.md prose fallback; the
  broad `except Exception as exc: return [f"...{exc}"]` masks all of them
  behind one generic string. T026 narrows this without changing the other
  three operations' fail-closed behavior.

## Branch Strategy

- **Strategy**: coord (coordination-branch topology; this WP's lane
  worktree branches off the mission coordination branch
  `kitty/mission-cli-error-surface-seam-01M2WJD2`).
- **Planning base branch**: `fix/cli-error-surface-seam`
- **Merge target branch**: `fix/cli-error-surface-seam`

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### T024 – Red-first: repro every reader's crash through its real command

- **Purpose**: ATDD red-first (charter C-003) — prove each of the 7 readers
  above currently either crashes with an untyped traceback or masks the
  failure, and prove it **through the command that reaches it**, not a
  bare call to the reader function. A reader-level unit test would pass
  today even for the unguarded readers if it just asserts an exception
  type; the command-level test is what proves the operator-visible defect.
- **Steps**:
  1. Create `tests/specify_cli/test_audit_tail_readers.py`. Mark every case
     `@pytest.mark.regression`.
  2. For each of the 7 readers, invoke the CLI command named in Context
     above (via `typer.testing.CliRunner` or the project's existing CLI
     test harness — grep `tests/specify_cli/` for the established pattern)
     against a fixture repo/mission where the reader's target file exists
     but is corrupt: non-UTF-8 bytes for the text readers, malformed JSON
     for the JSON readers, malformed YAML for `wps.yaml`.
  3. Assert the CURRENT (pre-fix) behavior for each: an unguarded reader
     raises an untyped exception (`pydantic.ValidationError`,
     `UnicodeDecodeError`, `yaml.YAMLError`) that surfaces as a traceback
     through the CLI; a masked reader (`runtime_bridge`) returns a vague
     string instead of a typed error. Do not assert exit codes yet if the
     hook (WP01) isn't wired into these commands — assert the untyped
     exception type is what currently propagates.
  4. Also add one case per reader for the **absent-input** path (file does
     not exist) and assert today's `None`/empty/`False` return — this is
     the D5 baseline you must not regress in T025/T027.
- **Files**: `tests/specify_cli/test_audit_tail_readers.py` (new).
- **Parallel?**: No — T025/T026/T027 build on these fixtures.
- **Notes**: If a command already routes through the WP01 hook by the time
  you write this (WP01 lands first), the "current" red state may already
  be a clean typed error for some readers and genuinely red (untyped) for
  others — that's expected; record which is which so T027's green
  assertions are precise per reader.

### T025 – Route each reader through `read_guarded`, preserving D5

- **Purpose**: Replace each reader's ad hoc partial guard (or lack of one)
  with a call to `kernel.read_guarded`, per
  `contracts/guarded-read-primitive.md`'s signature
  (`read_guarded(path, parse, *, errors=(...), error_cls=..., mode=...)`),
  choosing the domain `error_cls` appropriate to each reader.
- **Steps**:
  1. For `decisions/service.py::_opened_event_exists`: wrap the
     `path.read_text(...).splitlines()` + per-line `json.loads` in
     `read_guarded`, raising `DecisionIndexReadError` (already a
     `GuardedReadError` subclass per WP01) — or a new sibling if the
     existing type doesn't fit the decision-event-log domain; check
     `decisions/store.py` first (WP01 territory) before minting a new type.
  2. For `merge/state.py::_load_state_file`: guard the `open()` +
     `json.load()` with `read_guarded`, `errors=(json.JSONDecodeError,
     TypeError, KeyError)`, raising a `MergeStateReadError` (new, subclass
     of `GuardedReadError`) — keep the `not state_path.exists()` → `None`
     branch untouched, outside the guard.
  3. For `review/baseline.py::BaselineTestResult.load`: guard
     `path.read_text` + `json.loads` together; the current `raise
     ValueError(...)` becomes `raise ReviewBaselineReadError(...)` (new
     subclass) via `error_cls`; keep `not path.exists()` → `None` outside.
  4. For `review/lock.py::ReviewLock.load`: guard `read_text` +
     `json.loads` + `.from_dict`; today it silently returns `None` on
     `(json.JSONDecodeError, KeyError, TypeError)` — decide with the
     existing call site (`acquire`, which treats `None` as "no lock") that
     a genuinely corrupt lock file should now raise a typed error to
     `acquire`'s caller rather than being silently treated as "no lock"
     (a corrupt lock silently ignored is a stale-lock safety gap, not just
     a presentation bug) — confirm this is in scope for FR-012 before
     changing the return contract; if the plan's D5 language is read
     strictly as "presentation only," keep the `None` return but note the
     trade-off in the Activity Log for the reviewer.
  5. For `review/artifacts.py::ReviewCycleArtifact.from_file`: route the
     `read_text` + yaml-frontmatter-parse chain through `read_guarded`,
     raising a `ReviewArtifactReadError` (new subclass) instead of the
     current bare `ValueError`.
  6. For `status/validate.py::validate_materialization_drift`: guard the
     `status_path.read_text()` + `json.loads()` pair, raising a
     `StatusValidationReadError` (new subclass).
  7. For `core/wps_manifest.py::load_wps_manifest`: guard the `yaml.load` +
     `WpsManifest.model_validate` pair, `errors=(pydantic.ValidationError,
     yaml.YAMLError)`, raising a `WpsManifestReadError` (new subclass) —
     keep the `not wps_path.exists()` → `None` branch untouched.
- **Files**: the 7 reader files listed in `owned_files` (not
  `runtime_bridge.py` — that's T026).
- **Parallel?**: Can be split across readers internally, but land as one
  coherent commit set given the shared `tests/specify_cli/test_audit_tail_readers.py`.
- **Notes**: mint the smallest number of new `GuardedReadError` subclasses
  that make sense (one per domain, not one per call site); declare each in
  its module's `__all__` per charter C-004/C-007.

### T026 – Replace the `runtime_bridge.py` masking `except Exception`

- **Purpose**: FR-012's second half — the broad `except Exception as exc:
  return [f"Requirement mapping preflight failed: {exc}"]` around the
  `load_wps_manifest` call (and its three neighboring operations) hides
  the now-typed `WpsManifestReadError` from T025 behind a generic string,
  and (per D5's rationale) risks silently swallowing a genuine bug from
  the other three operations in the same `try` block.
- **Steps**:
  1. Re-read the current `try`/`except` block in `runtime_bridge.py`
     (function containing the `load_wps_manifest` call — re-derive the
     enclosing function name from the live file; do not hardcode a stale
     name here). It wraps: the `load_wps_manifest` call, `spec_md.read_text`,
     `parse_requirement_ids_from_spec_md`, `read_all_wp_requirement_refs`,
     and the `tasks_md.read_text` prose-fallback branch.
  2. Split the block: catch `WpsManifestReadError` (from T025) narrowly
     around the `load_wps_manifest` call and translate it into the
     function's existing return contract (`list[str]` of findings) with a
     specific, typed message — do NOT let it propagate as a raw
     traceback from this internal preflight function (it is not itself a
     CLI command boundary; it's a gather-only fact source consumed
     upstream), but stop presenting it as an indistinguishable generic
     string.
  3. For the remaining three operations in the block, keep their existing
     fail-closed behavior (the module's own docstring calls this out as
     intentional) — do not broaden or narrow what they catch; only the
     `load_wps_manifest` call's exception surface changes.
  4. Add the **companion assertion** the spec (D5, US3 scenario 3) demands:
     a test proving that when `spec_md.read_text` or
     `parse_requirement_ids_from_spec_md` raises something unrelated to
     `WpsManifestReadError`, the function's behavior is byte-for-byte
     unchanged from before this WP (same findings list shape, same
     fail-closed posture).
- **Files**: `src/runtime/next/runtime_bridge.py`.
- **Parallel?**: Depends on T025 (needs `WpsManifestReadError` to exist).
- **Notes**: keep this function's cyclomatic complexity ≤ 15 — extract a
  small `_load_wps_manifest_findings(feature_dir) -> list[str] | None`
  helper if narrowing the except clause pushes the enclosing function over
  the ceiling.

### T027 – Green: command-level + contract-preservation tests

- **Purpose**: Prove every red case from T024 is now green, and prove D5
  (missing-vs-corrupt) is preserved for every reader.
- **Steps**:
  1. Update the fixtures in `tests/specify_cli/test_audit_tail_readers.py`
     so the corrupt-input cases now assert: the command exits 1, a typed
     `GuardedReadError` subclass name appears in the JSON envelope (for
     `--json` commands) or the clean text line (non-JSON commands), and
     zero traceback frames appear on stdout/stderr.
  2. Add/confirm the absent-input cases still assert the pre-existing
     `None`/empty/`False` contract per reader (no regression).
  3. Add the `runtime_bridge` companion assertion from T026 into the same
     test module (or a sibling `tests/runtime/next/test_runtime_bridge_*`
     file if that's where existing `runtime_bridge` tests live — check
     first, follow the existing test-tree mirror).
  4. Assert the `--json` cases emit exactly one JSON error object on
     stdout per INV-1 (`contracts/error-envelope.md`) with no non-JSON
     prose mixed in.
  5. Run `ruff check`, `ruff format --check`, and mypy over every touched
     file; run the targeted test file plus `tests/status/`, `tests/cli/`
     (blast radius per CLAUDE.md's test policy) before marking this WP
     done.
- **Files**: `tests/specify_cli/test_audit_tail_readers.py` and any
  sibling runtime test file the companion assertion belongs in.
- **Parallel?**: No — final gate for this WP.
- **Notes**: this WP is a **dependency of WP08** — WP08's construction
  gate assumes this WP's readers are clean. Leave nothing red here.

## Test Strategy

- Every case in `tests/specify_cli/test_audit_tail_readers.py` runs
  through the real CLI command (T024/T027), never a bare function call —
  per spec.md US3's explicit requirement.
- Baseline: `make test-fast` plus the module tests you touch
  (`tests/specify_cli/`, `tests/status/`, `tests/cli/`) plus
  `tests/runtime/` (owning subsystem for `runtime_bridge.py`).
- mypy: `uv run --frozen mypy -p specify_cli -p runtime` (or the project's
  configured invocation) must be clean on every touched file — a passing
  pytest run does not substitute for this.
- Do not run the full `tests/architectural/` suite locally (memory:
  full-suite runs are heavy); WP08 owns that gate.

## Risks & Mitigations

- **Risk**: mistaking an absent-input branch for a corrupt-input branch
  and routing both through `read_guarded`, silently turning a `None`
  return into an error. **Mitigation**: T024's absent-input fixtures are
  the regression net; keep the `exists()` check *outside* `read_guarded`
  for every reader, exactly as it is today.
- **Risk**: widening `runtime_bridge`'s narrowed except clause changes the
  behavior of the sibling operations in the same block. **Mitigation**:
  T026's companion assertion is mandatory, not optional.
- **Risk**: minting 7 new `GuardedReadError` subclasses balloons the type
  surface. **Mitigation**: reuse an existing WP01 subclass when the domain
  genuinely matches (e.g. `DecisionIndexReadError` for the decisions
  reader) instead of minting a new type per file.
- **Risk**: `review/lock.py`'s corrupt-vs-absent semantics are genuinely
  ambiguous (see T025 step 4) — resolve it explicitly in code + Activity
  Log rather than leaving it implicit; flag for the reviewer if uncertain.

## Review Guidance

- Confirm every one of the 7 readers is tested through its real command
  entry point (spec.md US3 explicit requirement) — a bare unit test on the
  reader function is not sufficient evidence.
- Confirm the D5 missing-vs-corrupt contract is unchanged for all 7
  readers (diff the `exists()`/`None` branches against `main`).
- Confirm the `runtime_bridge.py` companion assertion actually exercises
  the three untouched operations, not just the `load_wps_manifest` path.
- Confirm no new kernel-layer import was introduced (this WP stays at the
  `specify_cli`/`runtime` layer, consuming WP01's kernel primitive — it
  must not add new symbols to `src/kernel/`).
- Confirm ruff/mypy are clean with no new suppressions, and complexity
  stayed ≤ 15 on every touched function.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Example (correct chronological order)**:

```
- 2026-01-12T10:00:00Z – system – Prompt created
- 2026-01-12T10:30:00Z – claude – Started implementation
- 2026-01-12T11:00:00Z – codex – Implementation complete, ready for review
- 2026-01-12T11:30:00Z – claude – Review passed, all tests passing  ← LATEST (at bottom)
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-09-19T10:45:02Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

### Optional Phase Subdirectories

For large features, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
