# Implementation Plan: Concurrency-safe cold startup asset assessment

**Branch**: `issue-3998-startup-assess-cold-concurrency` | **Date**: 2026-09-26 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/spec.md` (GitHub #3998)

## Summary

A torn read on an owner's **unlocked assessment** is currently terminal. `retry_torn_read` re-races the writer three times, then `incomplete()` collapses the error into a generic diagnostic, and `ensure_*` raises `RuntimeError`, which prints a traceback.

The fix turns that torn read into a **typed signal** (`TornReadError`) that escalates *once* to the owner's **serialization point**. That serialization point is the same lock set the existing locked recheck takes, extracted into one shared context manager. The owner then rebuilds under it.

Only a torn read that recurs under the serialization point, recurs re-entrantly, or is on a source-role path stays terminal. Terminal startup failures are raised as `StartupAssetError(GuardedReadError, RuntimeError)`, so the existing CLI error hook renders them at exit 1 without a traceback. The warm path is untouched: one unlocked attempt, no lock.

### Engineering alignment (settled by the post-spec squad; no open planning questions)

The pre-spec grounding squad and the post-spec squad (design-soundness + spec-quality lenses, opus) converged on one design, and the operator confirmed the Intent Summary. No planning question remains open, so no Decision Moment was needed at plan time.

## Technical Context

**Language/Version**: Python 3.11+ (mypy --strict, ruff, ruff format)
**Primary Dependencies**: stdlib only (`contextlib`, `contextvars`); in-repo `kernel.locks.machine_file_lock` (canonical lock primitive), `kernel.errors.GuardedReadError` (CLI error-presentation base). No new third-party dependency, so no supply-chain surface.
**Storage**: Files under the per-user Spec Kitty home (`~/.kittify` / `SPEC_KITTY_HOME`) and agent roots under `$HOME`; owner lock files `cache/*.lock`; cold-install sentinel `~/.spec-kitty-cold-install/<hash>.lock`.
**Testing**: pytest (fast tier), with deterministic leaf-level torn-read injection (`asset_preparation.node_state`) and a `machine_file_lock` spy/wrapper in the `asset_preparation` namespace (kernel.locks G6 seam). The fresh-home N-process reproducer is PR evidence only.
**Target Platform**: Linux, macOS, Windows 10+ (Windows mandatory-lock semantics, #4703)
**Project Type**: single (CLI package `src/specify_cli/runtime/`)
**Performance Goals**: Warm-home startup unchanged: exactly 1 assessment and 0 lock acquisitions per owner (NFR-002). Torn-read path: 1 serialization acquisition and ≤1 extra assessment per owner (≤2 if effects remain) (NFR-003).
**Constraints**: C-001..C-010 of the spec: source drift always refused, warm path lock-free, no batch replay, reassess gate untouched (#4885), no re-entrant deadlock, one serialization authority, Windows lock-read safety, reuse the CLI error seam. Complexity ≤ 15 per function.
**Scale/Scope**: 4 source files (`asset_preparation.py`, `bootstrap.py`, `agent_commands.py`, `agent_skills.py`) plus 1 test-support/new test module set; about 150 LOC of production change.

## Charter Check

*GATE: passes. Re-checked after design: still passes.*

| Charter rule | Status | Evidence |
|---|---|---|
| Single canonical authority | ✅ | The serialization point is *extracted* from `recheck_assets` into `_serialize_owner`, and both callers use it (C-008). The torn-read identity is one exception type, and `_TORN_READ_MESSAGE_PREFIX` string matching is retired. The error surface reuses `GuardedReadError` and `_run_app_with_error_hook` (C-010). |
| Architectural alignment | ✅ | The change stays inside `specify_cli.runtime` and consumes `kernel.locks` / `kernel.errors` (allowed direction `kernel <- specify_cli`). There is no new module. |
| DDD + tiered rigour | ✅ | Concurrency and correctness core: high rigour (primitive unit tests, lock-set identity test, red-first entry-point test). Log wording: low rigour. |
| ATDD-first / red-first (ADR 2026-07-17-1, C-011) | ✅ planned | WP01 lands the issue-pinned `@pytest.mark.regression` repro through each owner's `ensure_*`. It is red on main with `Asset changed during preparation` and is committed before the fix. After the fix it is converted to a focused functional test (not left `regression`). |
| Campsite cleaning (Standing Order 2) | ✅ planned | Tidy-first inside the touched file set only: extract `_serialize_owner` from `recheck_assets` as a behaviour-preserving step first (WP01's second commit), guarded by the existing `recheck_assets` tests. No file-set growth. |
| Architectural gate discipline | ✅ | The retired `retry_torn_read` / `_TORN_READ_RETRY_ATTEMPTS` symbols are removed, not left dead (dead-symbol gate). A lock-set identity test pins the single authority. |
| Terminology canon | ✅ | Mission, not feature. Overloaded "lock", "recheck" and "assess" are pinned in the spec's Domain Language. |
| No ADR needed | ✅ | The lock-free warm-path invariant and the lock order are unchanged (reused `recheck_assets` set). "An assessment may block after a torn read" is plan-level and is documented in module docstrings (R-4). |
| Model/agent discipline | ✅ | implement=sonnet, review=opus, profile-loaded (python-pedro / reviewer-renata). |

## Design

### Control flow (per owner `assess_*`)

```mermaid
flowchart TD
    A[assess_* : build_serialized(_build)] --> B{_build unlocked}
    B -- ok --> Z[return prepared, assessment<br/>(warm path: 0 locks, 1 pass)]
    B -- TornReadError --> C{role == source_read?}
    C -- yes --> T1[raise: source drift, terminal]
    C -- no --> D{lock_paths ⊆ _HELD_LOCKS?}
    D -- yes --> T2[raise: under-held torn read, terminal]
    D -- no --> E[INFO log: waiting for concurrent peer]
    E --> F[with _serialize_owner(lock_paths, anchor)]
    F --> G{_build again, under lock}
    G -- ok --> Z2[return stabilized result<br/>then _batch.include() once]
    G -- TornReadError --> T3[raise: under-lock torn read, terminal]
    T1 & T2 & T3 --> H[incomplete(): distinct diagnostic code]
    H --> I[ensure_*: raise StartupAssetError<br/>GuardedReadError+RuntimeError]
    I --> J[_run_app_with_error_hook: exit 1, no traceback]
```

### Components

1. **`TornReadError(ValueError)`** (`asset_preparation.py`). `AssetPreparation.observe()` raises it instead of a bare `ValueError`. It carries `path`, `role` (the *effective* role after the source-role stickiness rule), `lock_paths=(self.lock_path,)` and `anchor=self.root.path`. The last two are exactly the values `finish()` feeds into `PreparedAssets`, so the identity is not derived in parallel.
   - Subclassing `ValueError` keeps every existing `except (OSError, ValueError)` handler and the `str()` message unchanged. That means the `TORN_READ_SIGNAL` negative assertion (`tests/runtime/test_generic_asset_scope.py:60`) and the reproducer's text still match.
   - `_GlobalAssetPreparation`'s cross-family "observations disagree" `ValueError` stays a plain `ValueError`, so it is terminal and out of scope (C-006).
2. **`_serialize_owner(lock_paths, anchor)`** is a context manager extracted *verbatim* from `recheck_assets`. It takes the sentinel if any lock path is absent, locks each existing lock path, then sets the `_HELD_LOCKS` token. `recheck_assets` is refactored to use it first, as a behaviour-preserving tidy-first step. It is the single serialization authority (C-008).
3. **`build_serialized(build)`** replaces `retry_torn_read`. There is one unlocked attempt. On a destination-role `TornReadError` whose lock paths are not already held, it logs INFO and rebuilds once inside `_serialize_owner`. In every other case it propagates. `_TORN_READ_RETRY_ATTEMPTS` and `_TORN_READ_MESSAGE_PREFIX` are removed.
4. **`incomplete()`** maps a `TornReadError` to a distinct diagnostic code: `asset_torn_read` for destination-role (under lock or re-entrant) and `asset_source_drift` for source-role. It keeps `global_assets_unavailable` for everything else. The message text is unchanged.
5. **Owners** (`bootstrap.py:166`, `agent_commands.py:718`, `agent_skills.py:242`) swap `retry_torn_read(_build)` for `build_serialized(_build)`. `_batch.include()` stays after it, so it runs once on the stabilized result (C-003). The skills startup path is `assess_global_assets(runtime=False, commands=False)`, a single-family batch whose owner locks and anchor equal the owner's. It is covered by the same swap.
6. **`StartupAssetError(GuardedReadError, RuntimeError)`** is raised by `ensure_runtime`, `_apply_command_assessment` and `ensure_global_agent_skills`. It replaces the three pairs of bare `RuntimeError("; ".join(...))` raises (incomplete and failed-apply). `reason` is the joined message plus a next-step hint, and `path` is the first diagnostic path when known. Existing `except RuntimeError` callers keep matching (D3 multiple inheritance). `_run_app_with_error_hook` renders it: exit 1, one stderr line, or a JSON envelope under `--json`.
   - **Where it lives:** in `asset_preparation.py`, next to `incomplete()`. That is the lowest shared runtime module, which avoids a new module and keeps one home for the startup-asset error family.
7. **Operator signal (FR-008).** `build_serialized` takes an optional `logger` (the owner's module logger) and emits one INFO line when it escalates, for example `"<owner>: waiting for a concurrent spec-kitty install to finish, then re-checking assets"`. The line never contains the word "Error". Logging goes to stderr, never stdout.

### Known, recorded (not changed)

- **R-1.** The installer's create-then-lock window in `_apply_retained_assets` (lock file created, then locked) is benign: writes are atomic and canonical.
- **R-2.** A different-CLI-version peer still hits `apply_with_reassess`'s `precondition_changed` refusal (C-006).
- **R-3.** The skills installer's cross-family batch conflict stays terminal.
- **R-4.** Callers outside startup (`skills/installer.py:1103`, `tool_surface/providers/slash_commands.py:98,146`) now wait and reassess on a torn read. This is intended, documented in the `build_serialized` docstring, and has no flag.

## Test strategy (maps to FR/NFR/C)

| Test | Kind | Covers |
|---|---|---|
| `tests/runtime/test_startup_torn_read_escalation.py::test_ensure_converges_when_unlocked_assessment_tears[runtime,commands,skills]`: leaf injection on `asset_preparation.node_state` for the owner inventory while `peer["active"]`; wrapper around `asset_preparation.machine_file_lock` clears the flag inside the real acquisition; drives `ensure_runtime` / `ensure_global_agent_commands` / `ensure_global_agent_skills` | regression → functional | FR-001, FR-002, FR-006, C-007, SC-002 |
| same module `test_torn_read_under_serialization_is_terminal_without_traceback`: the peer never finishes; asserts `StartupAssetError`, `isinstance(…, RuntimeError)`, diagnostic code, and a CliRunner run rendering exit 1 with no `Traceback` in text and `--json` | functional | FR-004, FR-005, C-010, SC-004 |
| `tests/runtime/test_build_serialized.py`: clean pass (0 locks); destination tear → 1 serialized rebuild; tear under lock → terminal; re-entrant held → terminal and never calls lock; source-role → refused, 0 locks; non-torn `ValueError` / `OSError` → propagates, 1 call; INFO log emitted once and free of "Error" | unit | FR-003, FR-004, FR-007, FR-008, C-001, C-005, NFR-003 |
| `test_serialize_owner_matches_recheck_lock_set`: for the same `PreparedAssets`, `recheck_assets` and the escalation request the identical sentinel key and lock paths | unit | C-008 |
| `test_warm_startup_takes_no_lock_and_assesses_once`: warm home, spies on `machine_file_lock` and each `assess_*` | fast | NFR-002, C-002, SC-003 |
| `test_escalation_never_reads_held_lock_bytes`: reuse `_mandatory_lock_read_simulation` from `tests/runtime/test_windows_self_held_lock_read.py` | unit | C-009 |
| `test_ancestor_directory_not_torn_by_peer_children`: creating children under an observed ancestor does not raise (directory identity excludes mtime) | unit | spec Assumption, C-001 safety |
| Re-pin (DIRECTIVE_041): `tests/specify_cli/runtime/test_agent_commands.py:180,:890` and `tests/runtime/test_windows_self_held_lock_read.py:181` if they assert the exact `RuntimeError` type or message | remediation | — |
| Fresh-home reproducer (#3998 comment script), N=16 and N=32 ×5 including one CPU-pinned run | PR evidence | NFR-001, SC-001 |

Blast radius per the CLAUDE.md test policy: `make test-fast`, plus `tests/runtime/`, `tests/specify_cli/runtime/`, and every test file that greps `asset_preparation`, `ensure_runtime`, `ensure_global_agent_commands`, `ensure_global_agent_skills`, `assess_global_assets`. This is not cross-cutting, so there is no `tests/architectural/` full run, except `test_no_dead_symbols.py` / `test_layer_rules.py` as a spot check for the removed symbols.

## Project Structure

### Documentation (this mission)

```
kitty-specs/startup-assess-cold-concurrency-01M3EQ9S/
├── spec.md
├── plan.md                 # this file
├── research.md             # decisions + rejected alternatives
├── data-model.md           # TornReadError / serialization point / diagnostic codes
├── contracts/
│   └── startup-asset-escalation.md   # primitive + error contract
├── quickstart.md           # how to reproduce and verify
├── tracer-approach.md
├── tracer-design-decisions.md
├── tracer-tooling-friction.md
└── tasks.md                # /spec-kitty.tasks output
```

### Source Code (repository root)

```
src/specify_cli/runtime/
├── asset_preparation.py   # TornReadError, _serialize_owner, build_serialized, incomplete(), StartupAssetError, recheck_assets refactor
├── bootstrap.py           # assess_runtime swap; ensure_runtime raises StartupAssetError
├── agent_commands.py      # assess_global_agent_commands swap; _apply_command_assessment raises StartupAssetError
└── agent_skills.py        # assess_global_agent_skills swap; ensure_global_agent_skills raises StartupAssetError

tests/runtime/
├── test_startup_torn_read_escalation.py   # new: entry-point red-first + terminal/no-traceback
└── test_build_serialized.py               # new: primitive + lock-set identity + warm spy + Windows + ancestor
```

**Structure Decision**: single package. All production changes are inside `src/specify_cli/runtime/`, and the new tests live under `tests/runtime/`, next to the existing `test_ensure_runtime_concurrency.py` / `test_generic_asset_scope.py`.

## Parallel Work Analysis

The mission is small and all changes touch the same core module (`asset_preparation.py`), so it is **sequential**. Parallel lanes would conflict on one file.

- **WP01 (red-first + tidy-first):** land the failing entry-point regression test (committed red), then extract `_serialize_owner` from `recheck_assets` as a behaviour-preserving step.
- **WP02 (the fix):** `TornReadError`, `build_serialized`, `incomplete()` codes, owner swaps, `StartupAssetError`, INFO signal, primitive tests, warm spy, Windows/ancestor tests, re-pins. Convert the regression test to functional.
- **WP03 (closeout, small):** CHANGELOG `[Unreleased]` entry, fresh-home reproducer evidence, tracker comments (#3998/#4017/#4885 via PR body and comments). This could fold into WP02, but it is kept separate so the fix WP stays reviewable.

## Complexity Tracking

No charter violations, so there is nothing to justify.
