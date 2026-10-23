---
title: Write Permission-Denied Tests
description: Inject PermissionError at the filesystem seam so a denied-access test gives the same verdict as root and as a regular user.
doc_status: active
updated: '2026-10-22'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
---
# Write Permission-Denied Tests

A test that covers an `EACCES` branch must reach that branch for every uid.

Root ignores mode bits. CI containers and cloud sessions run as uid 0, so a test that denies access with `chmod` either skips there or passes without reaching the branch it names (#5654, #5691). Inject the denial at the filesystem seam instead, with the helpers in [`tests/_support/eacces.py`](../../../tests/_support/eacces.py).

## Pick the seam the code under test calls

| The code under test | Use |
|---|---|
| calls a `Path` method (`read_text`, `read_bytes`, `write_text`, `stat`, `exists`, `iterdir`, ...) | `deny_path_method(monkeypatch, "<method>", path)` |
| calls the builtin `open()` in one module | `deny_open_in(monkeypatch, module, path)` |
| removes an entry of a read-only directory (`Path.unlink`, `Path.rmdir`, `shutil.rmtree`) | `deny_removal_from(monkeypatch, directory)` |

Each helper denies one target and delegates every other call. `deny_path_method` and `deny_open_in` compare resolved paths, so a symlinked spelling of the target is denied too. `deny_removal_from` applies the POSIX rule that removing an entry needs a writable parent, and lifts it once the code restores the write bit, so a retry-after-chmod branch runs as it does for a regular user.

```python
from tests._support.eacces import deny_path_method


def test_unreadable_env_file_fails_loud(tmp_path, monkeypatch):
    env_path = write_env(tmp_path, "FOO=bar\n")
    deny_path_method(monkeypatch, "read_text", env_path)

    with pytest.raises(OperatorEnvFileUnreadableError):
        load_operator_env_file(start=tmp_path, environ={})
```

Notes:

- Deny the call the code actually makes. A test whose seam is missed goes red on its first run, because the read succeeds.
- Deny every method that reaches the file when there is more than one, for example both `read_text` and `read_bytes` for a guarded reader.
- `sqlite3.connect` opens in C, so no helper reaches it. Deny the parent `Path.mkdir` instead, as #5654 did.
- A stat through a locked directory is a `Path.stat` denial on the entry, for example the symlink a `#3194` test plants into the locked directory.

## Prove the test bites

Plant a break in the product's error handling, run the test as root, and watch it go red. Revert the break; never commit it. Then run the test as a regular user as well and confirm the same verdict.

## When the real kernel check is the point

Keep `chmod`, and skip honestly with `mode_bits_enforced` from the same module, only when the test must exercise the kernel permission check itself: for example `test_safe_stat_predicates.py`, which pins that a real `stat()` through a `0o000` directory raises, or a test that runs a child process no in-process seam reaches. Add such a test to `tests/architectural/_exemptions/root_vacuous_denial.txt` with the `kernel-check` category and a reason.

## The gate

`tests/architectural/test_no_root_vacuous_denial_tests.py` fails on a test function that:

- checks for root (`os.geteuid() == 0`, `not os.getuid()`, `getpass.getuser() == "root"`);
- calls `mode_bits_enforced`;
- skips or returns on `os.access(...)`, including inside `skipif(...)`;
- or `chmod`s a path to a mode that denies its owner (no read, or a locked directory such as `0o555`) without calling an `eacces` seam helper in its own body.

A managed read-only file (`0o444`, `0o400`) is not flagged: replacing it does not need write permission on it, so the verdict is the same for every uid. Each exemption lists the kinds the detector reports for its function, so an exempted test that gains a root skip goes red. The exemption file is shrink-only.

## See also

- [Testing index](index.md)
- [Test-flakiness handling policy](testing-flakiness.md)
