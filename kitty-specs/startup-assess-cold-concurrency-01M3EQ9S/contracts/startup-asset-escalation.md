# Contract: startup asset torn-read escalation

## `build_serialized(build: Callable[[], T], *, logger: logging.Logger | None = None) -> T`

**Preconditions**
- `build` constructs a fresh `AssetPreparation` on every call. It does everything up to and including `finish()` and performs no shared, non-retriable side effect (no `_GlobalAssetPreparation.include()`).

**Postconditions**
- P1. If the first `build()` succeeds, it is returned. No lock is acquired, and `build` is called exactly once.
- P2. If the first `build()` raises `TornReadError` with a destination role while `_HELD_LOCKS` is empty (no serialization point held by this process; see P4), the following happens:
  - Exactly one INFO record is logged; it does not contain "Error".
  - `_serialize_owner(exc.lock_paths, exc.anchor)` is entered exactly once, and `build()` is called exactly once more inside it.
  - That result is returned, or its exception propagates.
- P3. If the first `build()` raises `TornReadError` with a source role, it propagates immediately. No lock is taken and `build` is not re-called.
- P4. If the first `build()` raises `TornReadError` while `_HELD_LOCKS` is **non-empty** (this process is already inside any serialization point), it propagates immediately. No lock is taken. This rules out nesting. Owners that share an anchor share one non-reentrant cold-install sentinel, so a nested escalation could self-deadlock on it. Nesting across differently-keyed locks would risk lock-order inversion. Owner anchors coincide in the default layout, but not when e.g. `XDG_CONFIG_HOME` lives outside `HOME`.
- P5. Any other exception from `build()` propagates immediately and unchanged.
- P6. After return or raise, `_HELD_LOCKS` equals its value on entry.

## `_serialize_owner(lock_paths: tuple[Path, ...], anchor: Path)` (context manager)

- It acquires exactly the lock set that `recheck_assets` acquires for a `PreparedAssets` with the same `lock_paths` and `anchor`.
- Lock files are never read (`read_content=False` discipline, #4703).

## Startup entry points (`ensure_runtime`, `ensure_global_agent_commands` via `_apply_command_assessment`, `ensure_global_agent_skills`)

- An incomplete assessment, or an apply outcome other than `applied`/`skipped`, raises `StartupAssetError`.
- `StartupAssetError` is a subclass of both `kernel.errors.GuardedReadError` and `RuntimeError`.
- Through the CLI, `_run_app_with_error_hook` renders it: exit code 1; without `--json`, exactly one `Error: …` line on stderr and no traceback; with `--json`, one JSON object on stdout.
