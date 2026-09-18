"""Lock-primitive ban gate (FR-010 / DIRECTIVE_043): repo-wide banned raw locking.

Modelled on ``tests/architectural/test_clock_import_ban.py`` +
``test_clock_call_ban.py`` (the ``kernel.clock`` dual gate) and
``tests/architectural/test_os_detection_ban.py`` (the sibling OS-detection
single-idiom-family gate this one most closely mirrors structurally). See
``tests.architectural._lock_gate_scan`` for the full rationale behind this
gate's scan-scope divergence from the clock template.

**Scope**: bans raw ``msvcrt``/``fcntl``/``filelock`` import AND call outside
``src/kernel/locks.py`` (the sole sanctioned door, T010), scanning ``src/``
ONLY -- ``tests/``/``scripts/`` legitimately exercise raw locking (the
parity harness in ``tests/kernel/test_lock_parity.py`` simulates it
directly) and are out of scope by design (post-tasks squad MF-1).

**C-004 (predicate honours the holder)**: the door is excluded from the ban
entirely (mirrors the OS-detection gate's ``relpath != door`` guard below),
so the door's own raw ``msvcrt.locking``/``fcntl.flock`` calls and its
legitimate sidecar-record reads (``read_lock_record``/
``_read_lock_record_from_fd``, neither of which this gate's banned-shape
list even names) never trip the predicate. The invariant enforced is
narrowly "no raw locking outside the sanctioned holder" -- never a blunt "no
read under lock" that would misfire on the door's own diagnostics.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

import pytest

from tests.architectural import _lock_gate_scan as scan
from tests.architectural._lock_ban_exemptions import load_lock_ban_exemptions

pytestmark = [pytest.mark.architectural]

Violation = tuple[str, int]


def _violations_for_file(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return scan.find_lock_ban_violations(tree)


def collect_violations(paths: Iterable[Path]) -> list[Violation]:
    """``(repo-relative path, line)`` for every banned raw-lock shape across ``paths``."""
    violations: list[Violation] = []
    for path in paths:
        relpath = scan.relpath(path)
        violations.extend((relpath, lineno) for lineno in _violations_for_file(path))
    return sorted(violations)


def test_scanned_file_floor_is_met() -> None:
    """NOTE-3: a detector silently scanning zero files must go red, not green."""
    scanned = scan.iter_python_files()

    assert len(scanned) > scan.MIN_SCANNED_FILES, (
        f"only {len(scanned)} files scanned under {[str(r) for r in scan.SCAN_ROOTS]} -- the lock-primitive ban gate would otherwise pass vacuously."
    )


def test_door_contains_the_concrete_floor() -> None:
    """Concrete floor (FR-010): the canonical door must actually CONTAIN both raw primitives.

    Non-vacuity: deleting ``kernel/locks.py``'s own ``msvcrt.locking``/
    ``fcntl.flock`` bodies (e.g. hollowing ``_os_lock`` out to a no-op) must
    fail this assertion, not silently pass -- a gate whose door can be
    emptied out while the gate stays green is not a floor at all.
    """
    violations = _violations_for_file(scan.DOOR_FILE)

    assert violations, f"{scan.relpath(scan.DOOR_FILE)} no longer contains a recognizable raw msvcrt/fcntl call -- the door's own body has been hollowed out."

    door_source = scan.DOOR_FILE.read_text(encoding="utf-8")
    assert "msvcrt.locking(" in door_source, "the door must retain its Windows-side msvcrt.locking() call"
    assert "fcntl.flock(" in door_source, "the door must retain its POSIX-side fcntl.flock() call"


def test_no_banned_raw_lock_usage_outside_the_door() -> None:
    """FR-010: no raw msvcrt/fcntl/filelock import or call outside kernel/locks.py.

    Non-vacuity (C-009): ``test_stale_exemption_removal_reds_the_gate`` below
    proves this assertion is load-bearing by removing a planted exemption
    entry and observing the same collection-and-filter logic go red on the
    now-unexempted call site.
    """
    scanned = scan.iter_python_files()
    exemptions = load_lock_ban_exemptions()
    door = scan.relpath(scan.DOOR_FILE)

    violations = [(relpath, lineno) for relpath, lineno in collect_violations(scanned) if relpath != door and (relpath, lineno) not in exemptions]

    assert violations == [], (
        "Raw lock primitives (`import msvcrt`/`fcntl`/`filelock`, "
        "`msvcrt.locking(...)`, `fcntl.flock/lockf(...)`, `FileLock(...)`) "
        f"are banned outside {door} (the single door, FR-010). Route through "
        "kernel.locks (MachineFileLock / SyncMachineFileLock / "
        "machine_file_lock), or add `<path>:<line>` to the owning WP's "
        "tests/architectural/_exemptions/lock-ban-<owner>.txt if this is a "
        "currently-tracked, not-yet-remediated site.\nViolations:\n" + "\n".join(f"  {relpath}:{lineno}" for relpath, lineno in violations)
    )


def test_every_exemption_entry_is_a_real_violation() -> None:
    """Anti-staleness: every exemption entry must correspond to an actual violation today."""
    scanned = scan.iter_python_files()
    live_sites = set(collect_violations(scanned))
    exemptions = load_lock_ban_exemptions()

    stale = exemptions - live_sites
    assert not stale, (
        "The following tests/architectural/_exemptions/lock-ban-*.txt "
        "entries no longer correspond to a real violation -- delete them "
        "(the site is already clean):\n" + "\n".join(f"  {path}:{line}" for path, line in sorted(stale))
    )


def test_stale_exemption_removal_reds_the_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-009 non-vacuity: removing a live exemption line makes the gate red, naming the call site.

    Plants a SYNTHETIC ``import fcntl`` in an unexempted ``tmp_path`` file,
    runs it through the REAL detector (``collect_violations``), then proves
    the exemption mechanism is load-bearing via the exact same
    collection-and-filter logic ``test_no_banned_raw_lock_usage_outside_the_door``
    runs. ``scan.REPO_ROOT`` is monkeypatched to ``tmp_path`` for the
    duration of the ``scan.relpath`` call, so the planted file -- which must
    physically live under ``tmp_path``, never the real scanned tree -- still
    resolves through the SAME ``relpath`` function the real gate uses. No
    write ever touches the real repo tree or a committed exemption file.
    """
    module = tmp_path / "offender.py"
    module.write_text("import fcntl\n", encoding="utf-8")
    monkeypatch.setattr(scan, "REPO_ROOT", tmp_path.resolve())

    all_violations = collect_violations([module])
    assert all_violations == [("offender.py", 1)], "the planted violation must be detected by the real detector"
    sample_relpath, sample_lineno = all_violations[0]

    isolated_dir = tmp_path / "_exemptions"
    isolated_dir.mkdir()
    (isolated_dir / "lock-ban-isolated.txt").write_text(f"{sample_relpath}:{sample_lineno}\n", encoding="utf-8")

    def _fake_iter_exemption_lines() -> list[str]:
        lines: list[str] = []
        for path in sorted(isolated_dir.glob("lock-ban-*.txt")):
            lines.extend(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        return lines

    import tests.architectural._lock_ban_exemptions as exemptions_module

    monkeypatch.setattr(exemptions_module, "_iter_exemption_lines", _fake_iter_exemption_lines)
    exempted_here = exemptions_module.load_lock_ban_exemptions()
    assert (sample_relpath, sample_lineno) in exempted_here
    with_exemption = [v for v in all_violations if v not in exempted_here]
    assert (sample_relpath, sample_lineno) not in with_exemption

    isolated_dir.joinpath("lock-ban-isolated.txt").write_text("", encoding="utf-8")
    without_exemption = [v for v in all_violations if v not in exemptions_module.load_lock_ban_exemptions()]

    assert (sample_relpath, sample_lineno) in without_exemption


def test_planted_import_msvcrt_fires(tmp_path: Path) -> None:
    """C-009 non-vacuity: a planted ``import msvcrt`` in an unexempted file IS caught."""
    module = tmp_path / "offender.py"
    module.write_text("import msvcrt\n", encoding="utf-8")

    assert _violations_for_file(module) == [1]


def test_planted_import_fcntl_fires(tmp_path: Path) -> None:
    module = tmp_path / "offender.py"
    module.write_text("import fcntl\n", encoding="utf-8")

    assert _violations_for_file(module) == [1]


def test_planted_from_filelock_import_fires(tmp_path: Path) -> None:
    module = tmp_path / "offender.py"
    module.write_text("from filelock import FileLock\n", encoding="utf-8")

    assert _violations_for_file(module) == [1]


def test_planted_msvcrt_locking_call_fires(tmp_path: Path) -> None:
    module = tmp_path / "offender.py"
    module.write_text("import msvcrt\n\nmsvcrt.locking(3, 0, 1)\n", encoding="utf-8")

    assert _violations_for_file(module) == [1, 3]


def test_planted_fcntl_flock_call_fires(tmp_path: Path) -> None:
    module = tmp_path / "offender.py"
    module.write_text("import fcntl\n\nfcntl.flock(3, fcntl.LOCK_EX)\n", encoding="utf-8")

    assert _violations_for_file(module) == [1, 3]


def test_planted_fcntl_lockf_call_fires(tmp_path: Path) -> None:
    module = tmp_path / "offender.py"
    module.write_text("import fcntl\n\nfcntl.lockf(3, fcntl.LOCK_EX)\n", encoding="utf-8")

    assert _violations_for_file(module) == [1, 3]


def test_planted_filelock_constructor_call_fires(tmp_path: Path) -> None:
    module = tmp_path / "offender.py"
    module.write_text("from filelock import FileLock\n\nlock = FileLock('x')\n", encoding="utf-8")

    assert _violations_for_file(module) == [1, 3]


def test_planted_filelock_module_attribute_call_fires(tmp_path: Path) -> None:
    module = tmp_path / "offender.py"
    module.write_text("import filelock\n\nlock = filelock.FileLock('x')\n", encoding="utf-8")

    assert _violations_for_file(module) == [1, 3]


def test_in_function_usage_is_caught(tmp_path: Path) -> None:
    """Full-AST walk (not module-level-only): an in-function import/call is still caught."""
    module = tmp_path / "offender.py"
    module.write_text(
        "def helper():\n    import fcntl\n    fcntl.flock(3, fcntl.LOCK_EX)\n",
        encoding="utf-8",
    )

    assert _violations_for_file(module) == [2, 3]


def test_door_file_itself_is_exempt_by_construction() -> None:
    """The door is scanned but excluded from the ban assertion by its own relpath, not a text exemption."""
    door_relpath = scan.relpath(scan.DOOR_FILE)
    exemptions = load_lock_ban_exemptions()

    # The door earns its exemption by BEING the door, never by an entry in an
    # exemption file -- confirm no such entry exists, so a future edit cannot
    # silently swap the mechanism for a weaker one.
    assert not any(path == door_relpath for path, _ in exemptions)


def test_door_sidecar_record_read_is_never_a_banned_shape() -> None:
    """C-004: the door's own sidecar-record read is not even a shape this gate recognises.

    ``read_lock_record``/``_read_lock_record_from_fd`` call ``path.read_bytes()``
    / ``os.read(fd, ...)`` -- neither matches any of the banned import/call
    shapes (msvcrt.locking / fcntl.flock / fcntl.lockf / FileLock(...)), so
    the predicate structurally cannot flag the holder's own legitimate
    metadata read as a violation, independent of the `relpath != door` guard.
    """
    door_source = scan.DOOR_FILE.read_text(encoding="utf-8")
    tree = ast.parse(door_source)
    read_functions = {"read_lock_record", "_read_lock_record_from_fd"}
    read_function_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name in read_functions]
    assert len(read_function_nodes) == len(read_functions), "expected both sidecar-record readers to be present in the door"

    for node in read_function_nodes:
        assert scan.find_lock_ban_violations(node) == [], f"{node.name} must not itself look like a banned raw-lock shape"


def test_unrelated_locking_named_function_does_not_fire(tmp_path: Path) -> None:
    """Negative (over-fire boundary): an unrelated ``.locking(...)``/``.flock(...)`` on a non-msvcrt/fcntl receiver never fires."""
    module = tmp_path / "offender.py"
    source = (
        "class Scheduler:\n"
        "    def locking(self, *a):\n"
        "        pass\n\n\n"
        "class Herd:\n"
        "    def flock(self, *a):\n"
        "        pass\n\n\n"
        "Scheduler().locking(1)\n"
        "Herd().flock(2)\n"
    )
    module.write_text(source, encoding="utf-8")

    assert _violations_for_file(module) == []


def test_unrelated_filelock_named_callable_is_a_disclosed_over_fire(tmp_path: Path) -> None:
    """Disclosed limitation (not a negative): a bare ``FileLock(...)`` call fires by name alone.

    The detector matches the call SHAPE (a name-only call to ``FileLock``),
    not a verified import binding -- mirroring the clock gate's own
    disclosed residuals (``test_clock_call_ban.py``'s "HONEST LIMITS"
    section). In this repo no production code defines its own callable named
    ``FileLock``, so this over-fire never actually costs anything; recording
    it here (rather than silently assuming precision) keeps the gate honest
    about its detection boundary.
    """
    module = tmp_path / "offender.py"
    module.write_text("def FileLock(*a):\n    return None\n\n\nFileLock('x')\n", encoding="utf-8")

    assert _violations_for_file(module) == [5]
