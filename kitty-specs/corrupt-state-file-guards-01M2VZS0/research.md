# Research: Corrupt per-mission state file crashes (#4642)

Consolidated from a 3-lens research squad (structural root-cause, architecture-scout census, remediation design) run 2026-09-18/19 against `skupstream/main` @ `29507866f3`.

## Decision: mirror the `MissionMetaReadError` precedent, no new primitive
- **Rationale**: `meta.json` already has the correct shape — a typed `MissionMetaReadError(RuntimeError)` (`core/paths.py:544`) raised by `load_meta_fail_closed`, routing through the kernel decoder `kernel.meta_decode.decode_meta`. Mirroring it is the smallest safe fix for a release blocker.
- **Alternatives considered**: a generic `read_json_state()` kernel primitive + a single CLI-boundary exception hook. Rejected for the P0 (spans ~8 subsystems with divergent typed-error contracts; risks the graceful siblings). Deferred to a hardening mission that subsumes #4600 + #4642.

## Root cause: unenforced two-half convention
Fail-closed handling requires (A) the reader to wrap raw decode failures into a typed domain error AND (B) the command boundary to catch it. Nothing enforces either half. The two instances fail on **opposite halves**:
- **`next` (Half B)**: `MissionMetaReadError` is raised correctly but escapes because the parse happens downstream of `_resolve_mission_slug` (via `query_current_state`→`runtime_bridge`→`load_meta_fail_closed`), outside the `next_cmd.py:195-217` try. Adding it to that except-list does NOT catch the crash — verified on current main by three independent traces.
- **decisions (Half A)**: `decisions/store.py:load_index` never wraps `json.loads(read_text)` / `model_validate`; raw `JSONDecodeError`/`UnicodeDecodeError`/`ValidationError` escape. `ownership.py:531` already re-implements the guard locally — proof the source reader lacks it.

## Recurrence evidence (adversarial finding, accepted)
`core/agent_config.py:78` (the #4600 fix) comments *"same defect class as ledger SK-16, charter status --json's leaked-exception bug"* — this is at least the 4th occurrence of the class. Disposition: **accepted** → recorded as the driver for the deferred hardening mission (C-003), not folded into this P0.

## Scope finding: `wps_manifest.py` is OUT (adversarial contested → changed)
paula-patterns flagged `core/wps_manifest.py` as same-tier and argued for P0 inclusion. Independent trace: its `next`-reachable call site (`runtime_bridge.py:1019`) is already wrapped in a broad `except Exception`→warning, so it does NOT crash `next`. Real exposure is `finalize-tasks` (a command not named in #4642). **Disposition: changed** — excluded from P0, moved to the deferred mission (where the broad `except Exception` is itself a smell to replace with the typed seam).

## Partial-guard tail (deferred)
`decisions/service.py`, `merge/state.py`, `review/baseline.py` catch `JSONDecodeError` but not `UnicodeDecodeError` (still crash on non-UTF-8); `review/lock.py`, `review/artifacts.py`, `status/validate.py` fully unguarded. All deferred to the hardening mission.
