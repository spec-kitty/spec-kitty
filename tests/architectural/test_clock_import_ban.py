"""Import-ban gate (FR-012(a) / SC-001 / C-008): repo-wide raw ``datetime`` import ban.

Modelled on ``tests/architectural/test_kernel_no_charter_offering_import.py``: walks
the FULL AST (``ast.walk``) over every ``.py`` file under ``src/``, ``tests/``,
and ``scripts/`` (C-008's scope), so an in-function or in-``try`` stdlib
``datetime`` import is caught, not merely a module-level ``import``
statement. The one sanctioned holder is ``src/kernel/clock.py`` (the door,
landed in WP01a) -- every other occurrence is either fixed or named in a
per-owner exemption file under ``tests/architectural/_exemptions/`` (unioned
by ``tests.architectural._exemptions.load_import_exemptions``).

This is the (a) leg of FR-012's dual gate; the (b) leg (banned CALLS, e.g.
``datetime.now()``) is the sibling ``test_clock_call_ban.py``, which reuses a
different -- whole-module -- entry point of the same shared alias engine
(``tests/_support/wall_clock_assertions.py``). ``import time`` alone is never
banned here (only ``datetime`` imports); the call-ban separately bans the
``time.time()`` CALL (NFR-006 leaves ``time.monotonic``/``perf_counter``
untouched).

Ratchet contract (NFR-004 / plan Sec 1.3): the allow-list is seeded
FAIL-CLOSED with every currently-violating path, split one ``.txt`` file per
package owner (``tests/architectural/_exemptions/<owner>.txt``) so each
remediation WP shrinks only its own file. Terminal acceptance (WP15, SC-003)
is the union going empty.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

import pytest

from tests.architectural import _clock_gate_scan as scan
from tests.architectural._exemptions import load_call_exemptions, load_import_exemptions

pytestmark = [pytest.mark.architectural]


def _datetime_import_linenos(path: Path) -> list[int]:
    """Line numbers of every raw stdlib ``datetime`` import in ``path``, full-AST."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    linenos: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".", 1)[0] == "datetime" for alias in node.names):
                linenos.append(node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".", 1)[0] == "datetime":
            linenos.append(node.lineno)
    return linenos


def collect_import_ban_violations(paths: Iterable[Path]) -> list[tuple[Path, int]]:
    """``(path, lineno)`` for every raw ``datetime`` import outside the door, across ``paths``."""
    door = scan.DOOR_FILE.resolve()
    violations: list[tuple[Path, int]] = []
    for path in paths:
        if path.resolve() == door:
            continue
        violations.extend((path, lineno) for lineno in _datetime_import_linenos(path))
    return sorted(violations, key=lambda item: (str(item[0]), item[1]))


def test_scanned_file_floor_is_met() -> None:
    """NOTE-3: a detector silently scanning zero files must go red, not green."""
    scanned = scan.iter_python_files()

    assert len(scanned) > scan.MIN_SCANNED_FILES, (
        f"only {len(scanned)} files scanned under {[str(r) for r in scan.SCAN_ROOTS]} -- "
        "the import-ban gate would otherwise pass vacuously."
    )


def test_no_raw_datetime_import_outside_the_door() -> None:
    """FR-012(a)/SC-001: no ``import datetime``/``from datetime import ...`` outside kernel.clock.

    Non-vacuity (C-009): ``test_stale_exemption_removal_reds_the_gate`` below
    proves this assertion is load-bearing by removing one live exemption
    entry and observing this same collection go red on the now-unexempted
    path, then restoring it.
    """
    scanned = scan.iter_python_files()
    exemptions = load_import_exemptions()

    violations = [
        (path, lineno) for path, lineno in collect_import_ban_violations(scanned) if scan.relpath(path) not in exemptions
    ]

    assert violations == [], (
        "Raw stdlib `datetime` imports are banned outside src/kernel/clock.py "
        "(the single door, FR-012(a)). Import from kernel.clock instead, or add "
        "the (repo-relative path, IMPORT:) to your package's "
        "tests/architectural/_exemptions/<owner>.txt if this is a currently-"
        "tracked, not-yet-remediated site.\nViolations:\n"
        + "\n".join(f"  {scan.relpath(p)}:{lineno}" for p, lineno in violations)
    )


def test_every_import_exemption_entry_is_a_real_violation() -> None:
    """Anti-staleness (mirrors test_kernel_no_charter_offering_import's exemption self-check).

    Every entry in every ``_exemptions/*.txt`` IMPORT line must correspond to
    an actual violation this detector finds today; a WP that fixes its site
    must delete the line, not leave a vacuous stale entry sitting in its file.
    """
    scanned = scan.iter_python_files()
    live_violation_paths = {scan.relpath(path) for path, _ in collect_import_ban_violations(scanned)}
    exemptions = load_import_exemptions()

    stale = exemptions - live_violation_paths
    assert not stale, (
        "The following tests/architectural/_exemptions/*.txt IMPORT entries no "
        "longer correspond to a real violation -- delete them (the site is "
        "already clean):\n" + "\n".join(f"  IMPORT:{path}" for path in sorted(stale))
    )


def test_stale_exemption_removal_reds_the_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-009 non-vacuity: removing a live exemption line makes the gate red, naming the path.

    TREE-INDEPENDENT (WP15 terminal remediation): the real tree's exemption
    union is now empty (SC-003) -- WP05-WP14 shrank every ``_exemptions/*.txt``
    to nothing, so there is no live in-tree violation left to harvest via
    ``collect_import_ban_violations(scan.iter_python_files())`` the way the
    pre-terminal version of this test did. Instead plants a SYNTHETIC
    ``import datetime`` in an unexempted ``tmp_path`` file, runs it through
    the REAL detector (``collect_import_ban_violations``), then proves the
    exemption mechanism is load-bearing via the exact same
    collection-and-filter logic ``test_no_raw_datetime_import_outside_the_door``
    runs -- an ISOLATED one-owner exemption directory (never the real
    committed ``_exemptions/*.txt`` files) containing exactly one entry for
    the planted violation, then WITHOUT that entry the same filter is
    non-empty and names the now-unexempted path. ``scan.REPO_ROOT`` is
    monkeypatched to ``tmp_path`` for the duration of the ``scan.relpath``
    call below, so the planted file -- which must physically live under
    ``tmp_path``, never the real scanned tree -- still resolves through the
    SAME ``relpath`` function the real gate uses. No write ever touches the
    real repo tree or a committed ``_exemptions/*.txt`` file.
    """
    module = tmp_path / "offender.py"
    module.write_text("import datetime\n\ndatetime.timedelta(seconds=1)\n", encoding="utf-8")
    monkeypatch.setattr(scan, "REPO_ROOT", tmp_path.resolve())

    all_violations = collect_import_ban_violations([module])
    assert all_violations == [(module, 1)], "the planted import-ban violation must be detected by the real detector"
    sample_path, sample_lineno = all_violations[0]
    sample_relpath = scan.relpath(sample_path)
    assert sample_relpath == "offender.py"

    isolated_dir = tmp_path / "_exemptions"
    isolated_dir.mkdir()
    (isolated_dir / "isolated_owner.txt").write_text(f"IMPORT:{sample_relpath}\n", encoding="utf-8")

    def _fake_iter_exemption_lines() -> list[str]:
        lines: list[str] = []
        for path in sorted(isolated_dir.glob("*.txt")):
            lines.extend(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        return lines

    import tests.architectural._exemptions as exemptions_module

    monkeypatch.setattr(exemptions_module, "_iter_exemption_lines", _fake_iter_exemption_lines)
    exempted_here = exemptions_module.load_import_exemptions()
    assert sample_relpath in exempted_here
    with_exemption = [(p, ln) for p, ln in all_violations if scan.relpath(p) not in exempted_here]
    assert (sample_path, sample_lineno) not in with_exemption

    isolated_dir.joinpath("isolated_owner.txt").write_text("", encoding="utf-8")
    without_exemption = [
        (p, ln) for p, ln in all_violations if scan.relpath(p) not in exemptions_module.load_import_exemptions()
    ]

    assert (sample_path, sample_lineno) in without_exemption


def test_planted_import_violation_fires(tmp_path: Path) -> None:
    """C-009 non-vacuity: a planted ``import datetime`` in an unexempted file IS caught."""
    module = tmp_path / "offender.py"
    module.write_text("import datetime\n\ndatetime.timedelta(seconds=1)\n", encoding="utf-8")

    violations = collect_import_ban_violations([module])

    assert violations == [(module, 1)]


def test_planted_from_import_violation_fires(tmp_path: Path) -> None:
    """A ``from datetime import datetime`` (not a bare ``import datetime``) is also caught."""
    module = tmp_path / "offender.py"
    module.write_text("from datetime import datetime\n", encoding="utf-8")

    violations = collect_import_ban_violations([module])

    assert violations == [(module, 1)]


def test_in_function_import_is_caught(tmp_path: Path) -> None:
    """Full-AST walk (not module-level-only): an in-function import is still caught."""
    module = tmp_path / "offender.py"
    module.write_text(
        "def helper():\n    import datetime\n    return datetime.timedelta(seconds=1)\n",
        encoding="utf-8",
    )

    violations = collect_import_ban_violations([module])

    assert violations == [(module, 2)]


def test_door_file_itself_is_exempt() -> None:
    """The one sanctioned holder never counts as a violation of its own gate."""
    violations = collect_import_ban_violations([scan.DOOR_FILE])

    assert violations == []


def test_import_time_alone_is_not_banned_here(tmp_path: Path) -> None:
    """NFR-006: a bare ``import time`` (no ``datetime`` import) is never flagged by THIS gate."""
    module = tmp_path / "offender.py"
    module.write_text("import time\n\ntime.monotonic()\n", encoding="utf-8")

    violations = collect_import_ban_violations([module])

    assert violations == []


def test_exemption_union_is_empty() -> None:
    """SC-003 terminal proof (WP15): the union of every owner's IMPORT+CALL entries is zero.

    Every per-package remediation WP (WP05-WP14) shrank its own
    ``tests/architectural/_exemptions/<owner>.txt`` to empty; this is the
    ratchet's terminal floor -- the whole tree (``src/`` + ``tests/`` +
    ``scripts/``) is now on the door. Non-vacuity (C-009): this is a live
    read of real repository state, not a scaffold -- reintroducing a single
    ``IMPORT:``/``CALL:`` line into any committed ``_exemptions/<owner>.txt``
    (verified manually during review; never committed) reds this assertion
    immediately, and it would equally have been red at any point before
    WP14 finished (when the union was still non-empty).
    """
    import_exemptions = load_import_exemptions()
    call_exemptions = load_call_exemptions()

    assert import_exemptions == frozenset(), (
        "SC-003 not met: the IMPORT exemption union is not empty. Remaining "
        f"entries: {sorted(import_exemptions)}"
    )
    assert call_exemptions == frozenset(), (
        "SC-003 not met: the CALL exemption union is not empty. Remaining "
        f"entries: {sorted(call_exemptions)}"
    )
