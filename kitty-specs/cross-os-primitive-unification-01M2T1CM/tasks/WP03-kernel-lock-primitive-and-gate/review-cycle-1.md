---
affected_files: []
cycle_number: 1
mission_slug: cross-os-primitive-unification-01M2T1CM
reproduction_command:
reviewed_at: '2026-09-18T14:04:45Z'
reviewer_agent: user
wp_id: WP03
---

# WP03 Review Feedback — REJECT (one surgical blocking fix)

reviewer-renata (opus). The design, gate teeth, structural parity proof, async preservation, and quality are all strong and VERIFIED (144 passed). Both adjudication points resolved: G1 auto-derive omission ACCEPTED (G2 is the load-bearing #4703 property and is proven); mypy-narrowing exemption LEGIT and narrowly scoped.

## BLOCKING (the only required change)
`src/kernel/locks.py`'s module docstring asserts G1: "Callers pass the resource path; the lock sidecar path (`resource.parent/f'.{resource.name}.lock'`) is derived internally. A caller cannot point the lock at the payload." **The code does not do this** — `_LockCore.open_fd` opens the caller-supplied path verbatim and `_atomic_write_under_lock` truncates it and writes the JSON record into it. A caller who trusts the docstring and passes a *payload* path would have it truncated/corrupted AND re-create #4703 on Windows. A false safety guarantee on the canonical single-door primitive will mislead WP04/WP05.

### Required fix (doc + rename only; NO re-architecture — the direct-lock behaviour is correct and accepted)
1. Rename the `resource` parameter → `lock_path` across `MachineFileLock`, `SyncMachineFileLock`, `machine_file_lock`, `read_lock_record`, `force_release`, and the internal `_LockCore.resource` field. Update the 4 consumer call sites if they pass by keyword (positional needs no change).
2. Correct the G1 docstring bullet to the truth: "Caller passes a **dedicated lock-only path**; this path is opened, locked, and **truncated** directly — never pass a payload path. The #4703 property is G2: the API yields only a `LockRecord`, never a handle to any file, so a held lock cannot be read as a payload."
3. Align `kitty-specs/.../contracts/lock-primitive.md` param naming to `lock_path` and the same clarification.

## Re-review scope (per reviewer): targeted only — `test_locks.py` + `test_lock_parity.py` + `ruff` + `mypy --strict` on `kernel/locks.py`. No full suite for a doc/rename-only change.

## Carry to WP04/WP05 (advisory, not WP03's job)
- asset_preparation has ZERO live raw-lock calls (locks via `bootstrap._lock_exclusive`); do NOT add an asset_preparation exemption line — migrating bootstrap's raw calls (seeded lock-ban-wp04 lines 70-80) covers it.
- bootstrap flocks a *directory* on POSIX / a *sentinel file* on Windows — reconcile toward the sentinel-file shape (the canonical primitive opens O_RDWR|O_CREAT + truncates; a directory-fd won't map cleanly).
- Always pass the dedicated `.lock` path when migrating (safe-by-construction once the rename lands).
- Apply the WP02 S_ISLNK safe-delete guard at any migrated site that deletes/truncates a lock artifact.
