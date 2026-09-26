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
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import NamedTuple

import pytest

from tests.architectural import _lock_gate_scan as scan
from tests.architectural._content_identity import partition_findings, render_descriptor_line, resolve_allowlist
from tests.architectural._lock_ban_exemptions import load_lock_ban_exemptions
from tests.architectural._ratchet_keys import CompositeKey, ContentDescriptor, composite_key

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


class _LockFinding(NamedTuple):
    """One raw-lock finding: its content identity plus its current line."""

    key: CompositeKey
    lineno: int


#: The door's repo-relative path, fixed at import (before any test monkeypatches ``scan.REPO_ROOT``).
_DOOR_RELPATH = scan.relpath(scan.DOOR_FILE)


def _scanned_sources() -> dict[str, str]:
    """``{repo-relative path: source}`` for every scanned file."""
    return {scan.relpath(path): path.read_text(encoding="utf-8") for path in scan.iter_python_files()}


def _source_under_repo(relpath: str) -> str:
    return (scan.REPO_ROOT / relpath).read_text(encoding="utf-8")


def _lock_findings(sources: Mapping[str, str]) -> list[_LockFinding]:
    """Every raw-lock finding outside the door, keyed by ``(relpath, qualname, token_line)``."""
    findings: list[_LockFinding] = []
    for relpath, source in sorted(sources.items()):
        if relpath == _DOOR_RELPATH:
            continue
        for lineno in scan.find_lock_ban_violations(ast.parse(source)):
            findings.append(_LockFinding((relpath, *composite_key(source, lineno)), lineno))
    return findings


def _split_lock_findings(sources: Mapping[str, str], allowed: Counter[CompositeKey]) -> tuple[list[_LockFinding], Counter[CompositeKey]]:
    """Split the findings in *sources* into ``(unexpected, unused)`` via :func:`partition_findings` (multiset)."""
    return partition_findings(((finding.key, finding) for finding in _lock_findings(sources)), allowed)


def _content_line_for(finding: _LockFinding) -> str:
    """The exemption line that would suppress *finding* (its full normalized token line as the substring)."""
    relpath, qualname, token_line = finding.key
    return render_descriptor_line(ContentDescriptor(relpath, qualname, token_line, None, ""))


def test_no_banned_raw_lock_usage_outside_the_door() -> None:
    """FR-010: no raw msvcrt/fcntl/filelock import or call outside kernel/locks.py.

    Findings are matched against the exemption descriptors by content identity
    ``(relpath, qualname, token_line)`` through
    :func:`tests.architectural._content_identity.partition_findings`.

    Non-vacuity (C-009): ``test_stale_exemption_removal_reds_the_gate`` below
    proves this assertion is load-bearing by removing a planted exemption
    entry and observing the same collection-and-filter logic go red on the
    now-unexempted call site.
    """
    allowed, _errors = resolve_allowlist(load_lock_ban_exemptions(), _source_under_repo)
    unexpected, _unused = _split_lock_findings(_scanned_sources(), allowed)

    assert unexpected == [], (
        "Raw lock primitives (`import msvcrt`/`fcntl`/`filelock`, "
        "`msvcrt.locking(...)`, `fcntl.flock/lockf(...)`, `FileLock(...)`) "
        f"are banned outside {_DOOR_RELPATH} (the single door, FR-010). Route through "
        "kernel.locks (MachineFileLock / SyncMachineFileLock / "
        "machine_file_lock), or, if this is a currently-tracked, "
        "not-yet-remediated site, add the content line shown "
        "(`<path>::<qualname>::<token_substring>`) to the owning WP's "
        "tests/architectural/_exemptions/lock-ban-<owner>.txt."
        "\nViolations:\n" + "\n".join(f"  {finding.key[0]}:{finding.lineno}  ->  {_content_line_for(finding)}" for finding in unexpected)
    )


def test_every_exemption_entry_is_a_real_violation() -> None:
    """Anti-staleness (FR-007): every exemption descriptor must suppress a live violation today."""
    exemptions = load_lock_ban_exemptions()
    allowed, errors = resolve_allowlist(exemptions, _source_under_repo)
    _unexpected, unused = _split_lock_findings(_scanned_sources(), allowed)
    checked = len(errors) + sum(allowed.values())

    stale = [f"  {render_descriptor_line(descriptor)} ({descriptor.rationale}): {reason}" for descriptor, reason in errors]
    stale += [f"  {key[0]} [{key[1]}] {key[2]!r} suppresses no live violation" for key in sorted(unused)]
    assert not stale, (
        "The following tests/architectural/_exemptions/lock-ban-*.txt "
        "entries no longer correspond to a real violation -- delete them "
        "(the site is already clean):\n" + "\n".join(stale)
    )
    assert checked == len(exemptions)


def test_stale_exemption_removal_reds_the_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-009 non-vacuity: removing a live exemption line makes the gate red, naming the call site.

    Plants a SYNTHETIC ``import fcntl`` in an unexempted ``tmp_path`` file,
    runs it through the REAL detector (``collect_violations``), then proves
    the exemption mechanism is load-bearing: a content-form exemption line,
    parsed by the real loader and resolved against the planted source,
    suppresses the finding; emptying the exemption file reds it again.
    ``scan.REPO_ROOT`` is monkeypatched to ``tmp_path`` so the planted file --
    which must physically live under ``tmp_path``, never the real scanned tree
    -- still resolves through the SAME ``relpath`` function the real gate
    uses. No write ever touches the real repo tree or a committed exemption
    file.
    """
    module = tmp_path / "offender.py"
    module.write_text("import fcntl\n", encoding="utf-8")
    monkeypatch.setattr(scan, "REPO_ROOT", tmp_path.resolve())

    all_violations = collect_violations([module])
    assert all_violations == [("offender.py", 1)], "the planted violation must be detected by the real detector"
    sources = {"offender.py": module.read_text(encoding="utf-8")}

    isolated_dir = tmp_path / "_exemptions"
    isolated_dir.mkdir()
    (isolated_dir / "lock-ban-isolated.txt").write_text("offender.py::<module>::import fcntl\n", encoding="utf-8")

    def _fake_iter_exemption_entries() -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for path in sorted(isolated_dir.glob("lock-ban-*.txt")):
            entries.extend((path.name, line.strip()) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        return entries

    import tests.architectural._lock_ban_exemptions as exemptions_module

    monkeypatch.setattr(exemptions_module, "_iter_exemption_entries", _fake_iter_exemption_entries)

    def _unexpected_with_current_exemptions() -> list[_LockFinding]:
        allowed, errors = resolve_allowlist(exemptions_module.load_lock_ban_exemptions(), _source_under_repo)
        assert errors == []
        return _split_lock_findings(sources, allowed)[0]

    assert _unexpected_with_current_exemptions() == [], "the content-form exemption must suppress the planted finding"

    isolated_dir.joinpath("lock-ban-isolated.txt").write_text("", encoding="utf-8")
    without_exemption = _unexpected_with_current_exemptions()

    assert [(finding.key[0], finding.lineno) for finding in without_exemption] == [("offender.py", 1)]


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
    assert not any(descriptor.rel_path == door_relpath for descriptor in exemptions)


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


def test_lock_ban_loader_rejects_line_pinned_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-OP-6: a ``path:line`` exemption line is refused with a ``ValueError`` naming it."""
    import tests.architectural._lock_ban_exemptions as exemptions_module

    monkeypatch.setattr(exemptions_module, "_iter_exemption_entries", lambda: [("lock-ban-x.txt", "src/x.py:12")])

    with pytest.raises(ValueError, match=re.escape("src/x.py:12")):
        exemptions_module.load_lock_ban_exemptions()
