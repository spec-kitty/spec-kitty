# Research: EventBridge port, event-log writes gate and locked appends

## R-1: Which lock contract?

- **Decision:** a per-log exclusive `kernel.locks.machine_file_lock` on
  `<git-common-dir>/spec-kitty-locks/event-logs/<digest>.lock`, where `<digest>` is the first 32 hex characters of the SHA-256 of the lock anchor's resolved, `os.path.normcase`d absolute path (UTF-8).
  - The anchor is the log, or the family directory for one-file-per-record logs (`kitty-ops/<op>.jsonl`), so lock files do not grow per record.
  - Outside a git repository (`NotAGitRepositoryError`) the lock is the sibling `<anchor>.event-log.lock`. It never shares a name with glossary's repair lock `<log>.lock`, which would self-deadlock.
  - When git cannot be invoked (`GitTopologyUnavailableError`) the append refuses (`EVENT_LOG_LOCK_UNAVAILABLE`), rather than locking where other writers do not.
- **Rationale:**
  - ADR 2026-10-22-1 D-2 keys the write service where core keeps its write locks (`<git-common-dir>/spec-kitty-locks/`).
  - D-4 says the service takes the same OS lock files with `flock(2)` semantics. One rule for every log is the one contract #6193 interoperates with.
  - A per-log lock keeps unrelated logs from contending.
  - The status lock (`feature_status_lock`) is per Mission and is held across whole transactions. Reusing it for the run journal or the Op logs would serialise unrelated work and could deadlock with the background propagation thread.
- **Alternatives considered:**
  - A sibling `<log>.lock` everywhere, as glossary repair does today. Rejected: it adds a file beside committed logs (`decisions.events.jsonl` in `kitty-specs/`), which is the #6628 churn class.
  - The Mission status lock. Rejected for the reasons above.

## R-2: Validation

- **Decision:** framing only. Each unit is whole LF-terminated lines; no schema validation.
- **Rationale:** the operator ruled on 2026-10-25 that the service is authoritative for validation (decision `01M5T0VEWMHT2R9EC6WK6WXAHS`). Strict validation through `persistence.append_event` would refuse rows that land today, which is a behaviour change.
- **Alternatives considered:** `persistence.append_event` for families with a model. Kept only where it is already used (glossary).

## R-6: Post-tasks review dispositions (reviewer-renata lens, 2026-10-25)

| # | Finding | Disposition |
|---|---|---|
| 1 | `_internal_runtime` import cycle | Fixed: stdlib-only port leaf |
| 2 | Glossary self-deadlock outside git | Fixed: `.event-log.lock` fallback suffix |
| 3 | Missing parent minted by the lock | Fixed: `FileNotFoundError` before any lock |
| 4 | Fallback on any git error | Fixed: refuse on `GitTopologyUnavailableError` |
| 5 | Third door (`emit_status_transition_batch`) | Fixed: goes through the port |
| 6 | `ALLOWED_CALLERS` stale entry; doors depend on the adapter | Swap; the doors are CLI shells, so they import the accessor (AS3 reworded) |
| 7 | Duplicate registry | Kept as the port's second half; tripwire added |
| 8 | Tests that break | Owned by WP02/WP04 |
| 9 | Torn `lifecycle.jsonl` breaks `next --result` | Pairing warns on refusal |
| 10 | Lock files per Op | Family anchor |
| 11 | Name collisions | Renamed `kernel.event_log_append`, `EventLog*` |
| 12 | Hand-rolled no-follow | `open_no_follow`, mapped to an `OSError` |
| 13 | Gate structure | Scanner extracted; canonical-events exemption stated |
| 14 | Dead `append_audit_event`; unreachable propagation log | Routed (one line each); deletion left to the operator, PR question |
| 15 | Test placement | Tests in owning module directories |
| 16 | Two torn-tail policies (refuse vs glossary repair) | Kept; PR question (doctor/remedy surface) |


## R-3: Port location and shape

- **Decision:** the stdlib-only leaf `runtime/next/event_bridge.py` defines `WorkPackageTransitionPort`, `WorkPackageTransition` and the binding. `EventBridgePort(RuntimeEventEmitter, WorkPackageTransitionPort)` is defined in `_internal_runtime/events.py`, which grows the emitter in place.
  - Why the split: importing `_internal_runtime` loads `engine`, which loads `status.emit` (post-tasks review finding 1). The doors therefore import only the leaf.
  - `WorkPackageTransition` carries the unit's rows, the resolved write location, and an opaque CLI write contract (ADR 2026-10-22-1 D-3: during the strangler, the CLI sends the resolved location).
  - Binding is reject-on-conflict, like `register_runtime_emitter_factory`.
- **Rationale:** ADR 2026-10-14-1 D-2 and open question 1's default. It grows the existing seam rather than duplicating it. `_internal_runtime` is not for external importers, so the port is public in `runtime.next`.

## R-4: Byte stability

- **Finding:** every writer serialises its own line (`json.dumps` with its own options), so the primitive takes pre-serialised text lines and encodes them as UTF-8. The rows are unchanged.
- **Residual:** Windows text-mode CRLF becomes LF. Every reader uses `splitlines()` or `json.loads` per line, so this is compatible.

## R-5: Gate technique

- **Decision:** extract `scan_write_sites` from `test_status_events_writes_gate.py` into `tests/architectural/_write_site_scan.py` (repo helper convention); both gates import it. Two censuses are added:
  - door callers (`append_event_log_lines`, `event_log_lock`, `persistence.append_event`) by `(module, path expression)`;
  - raw writes whose path resolves to a named event log, or to any `.jsonl`, outside the sanctioned modules.
- **Rationale:** the resolver is already proven with non-vacuity floors. Keying on `.jsonl` catches the Op-record f-string path that a name match cannot.
