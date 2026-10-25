# Research: EventBridge port, event-log writes gate and locked appends

## R-1: Which lock contract?

- **Decision:** a per-log exclusive `kernel.locks.machine_file_lock` on
  `<git-common-dir>/spec-kitty-locks/event-ledgers/<digest>.lock`, where `<digest>` is the first 32 hex characters of the SHA-256 of the log's resolved, `os.path.normcase`d absolute path (UTF-8). Outside a git repository the lock is the sibling `<log>.lock`.
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

## R-3: Port location and shape

- **Decision:** `runtime/next/event_bridge.py` defines `WorkPackageTransitionPort`, `EventBridgePort(RuntimeEventEmitter, WorkPackageTransitionPort)` and `WorkPackageTransition`.
  - `WorkPackageTransition` carries the unit's rows, the resolved write location, and an opaque CLI write contract (ADR 2026-10-22-1 D-3: during the strangler, the CLI sends the resolved location).
  - Binding is reject-on-conflict, like `register_runtime_emitter_factory`.
- **Rationale:** ADR 2026-10-14-1 D-2 and open question 1's default. It grows the existing seam rather than duplicating it. `_internal_runtime` is not for external importers, so the port is public in `runtime.next`.

## R-4: Byte stability

- **Finding:** every writer serialises its own line (`json.dumps` with its own options), so the primitive takes pre-serialised text lines and encodes them as UTF-8. The rows are unchanged.
- **Residual:** Windows text-mode CRLF becomes LF. Every reader uses `splitlines()` or `json.loads` per line, so this is compatible.

## R-5: Gate technique

- **Decision:** reuse `scan_write_sites` from `test_status_events_writes_gate.py`, which does static path resolution. Two censuses are added:
  - door callers (`append_ledger_lines`, `ledger_lock`, `persistence.append_event`) by `(module, path expression)`;
  - raw writes whose path resolves to a named event log, or to any `.jsonl`, outside the sanctioned modules.
- **Rationale:** the resolver is already proven with non-vacuity floors. Keying on `.jsonl` catches the Op-record f-string path that a name match cannot.
