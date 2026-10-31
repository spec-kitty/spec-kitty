# Data Model: decisions lock log anchor

The mission introduces no new persisted entity. It re-keys one runtime identity and pins
the invariants around it.

## Entities

### Log anchor

- **What**: the resolved `status.events.jsonl` path a decision row is appended to —
  `decisions.service._write_events_path(repo_root, mission_slug, owned=...)`.
- **Fields**: a filesystem path (absolute after resolution).
- **Relationships**: one per (Mission, checkout-resolution); every decision write of that
  Mission resolves exactly one before it takes any lock.
- **Invariant A-1**: two writers that append to the same anchor file must take the same
  lock file.

### Anchor lock

- **What**: `<git-common-dir>/spec-kitty-locks/event-logs/<32-hex digest>.lock`, where the
  digest is the first 32 hex characters of `sha256(os.path.normcase(resolved anchor))`.
- **Owner**: `kernel.event_log_append.event_log_lock_path` (the single anchor→lock
  authority; #6606, contract rule 1).
- **Fallbacks**: outside a git repository, `<anchor>.event-log.lock` beside the log; when
  git cannot be invoked, `EventLogLockUnavailableError` (never an unlocked write).
- **Invariant A-2**: the anchor lock lives outside every working tree, so it needs no
  ignore rule and never appears in `git status` (NFR-004).
- **Invariant A-3**: distinct anchors ⇒ distinct lock files (no global lock, FR-003).

### Ledger-dir sidecar lock (unchanged)

- **What**: `kitty-specs/<mission>/decisions/index.json.lock`
  (`_decisions_lock_path(ledger_dir)`, `_LOCK_FILENAME`).
- **Holders today, unchanged**: forward writes (`open_decision`, `_terminal_command`), the
  reconciler `cli/commands/_decisions_doctor._decisions_lock_path`, `repair-runtime-lock`,
  and `next`'s owned-commit guard (`machine_file_lock(runtime_lock)` — it guards the
  gitignore provisioning, not a decision write).
- **Invariant S-1**: a repair and a forward write in one ledger directory never overlap
  (#4848; pinned by the pre-existing suites).

### Decision index (unchanged)

- **What**: `kitty-specs/<mission>/decisions/index.json`, the dedup source consulted inside
  the critical section by logical key (`origin_flow`, `step_id`, `slot_key`, `input_key`).
- **Invariant D-1**: the index append, the `DM-<id>.md` artifact write and the
  `DecisionPointOpened` append all happen inside one hold of the lock pair, so a crash or a
  concurrent open cannot leave an opening with no artifact or vice versa (the #4848
  property this mission must not regress).

## Acquisition order (single global order — C-004)

```
anchor lock (event log)          <- new, cross-checkout
  ledger-dir sidecar lock        <- unchanged, intra-ledger (reconciler/repair)
    Mission status lock          <- unchanged, taken by emit inside the critical section
```

Rules:

1. No code path may take the sidecar before the anchor.
2. `dry_run` takes nothing.
3. `open_decision` waits unbounded on both (NFR-001); the terminal verbs keep their
   existing bounded sidecar wait and use the same bound for the anchor.

## State transitions

None. The decision lifecycle (`open` → `resolved|deferred|canceled`) and its fold are
unchanged; only the mutual-exclusion identity in front of the writes changes.

## Validation rules

| Rule | Where enforced | Failure |
|---|---|---|
| Anchor resolved before any lock | `open_decision` / `_terminal_command` pre-resolve `events_path` (already the case, #5113) | placement refusal before any write |
| Both locks released on any exception | context managers (`ExitStack` in `_decisions_lock`) | nothing written; the error propagates unchanged |
| Anchor path derived only from the anchor file | `event_log_lock_path` | n/a — pure digest of the resolved path |
| No new error type | both takes go through `_decisions_lock` | `DecisionError(LOCK_TIMEOUT)`, the existing single shape |
