# Quickstart — reproduce the raw `LockAcquireTimeout` (#6763)

These are the three operator-visible paths the mission fixes. Each one, on the pre-fix
tree, prints a Python traceback instead of a refusal, and `--json` callers get no document.

## The shared precondition

Every path waits on the SAME sidecar lock, `decisions/index.json.lock`, under
`<mission>/decisions/`. Hold it from a second process (or a helper thread) for longer than
the bounded wait:

```python
# hold_decisions_lock.py — run in a second shell, 30 s
import sys, time
from pathlib import Path
from kernel.locks import machine_file_lock
from specify_cli.decisions.service import _decisions_lock_path

mission_dir = Path(sys.argv[1])
with machine_file_lock(_decisions_lock_path(mission_dir), blocking=True, timeout_s=5):
    time.sleep(30)
```

## 1. `doctor decisions --repair`

```bash
spec-kitty doctor decisions --mission <m> --repair --json
```

- **Before:** uncaught `kernel.locks.LockAcquireTimeout`; stdout empty.
- **After:** `{"ok": false, "error": {"code": "DECISION_LOCK_TIMEOUT", "message": "Timed out
  after 10s waiting for the decisions lock '…/decisions/index.json.lock'; another decision
  command is holding it. Nothing was written; retry the command."}}` and exit 1.

The coordination-only ledger copy (`--repair` on a Mission whose ledger exists only on the
coordination branch) takes the same lock and refuses the same way.

## 2. Owned `next`

```bash
spec-kitty next --agent python-pedro --mission <m> --owned-checkout <path> --result success --json
```

- **Before:** uncaught `LockAcquireTimeout` from `_commit_owned_next_mutations`.
- **After:** `{"result": "error", "error_code": "DECISION_LOCK_TIMEOUT", "error": "…",
  "lock_path": "…", "timeout_seconds": 10.0, "next_step": "Retry the command (no lock was
  taken, so the advancement is safe to retry)."}` and exit 1.

## 3. `agent decision repair-runtime-lock`

```bash
spec-kitty agent decision repair-runtime-lock --mission <m> --owned-checkout <path>
```

- **Before:** uncaught `LockAcquireTimeout`.
- **After:** `{"status": "error", "code": "DECISION_LOCK_TIMEOUT", "message": "…"}` on
  stdout and exit 1, with the checkout unchanged.

## Why retry is always safe

The seam translates only the ACQUIRE. A timed-out acquire never enters the critical
section, so nothing was written; the holder finishes its own write and the retry sees a
consistent ledger.
