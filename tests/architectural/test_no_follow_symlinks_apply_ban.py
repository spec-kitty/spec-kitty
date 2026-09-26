"""No-follow-symlinks apply ban gate (#4923, T004): close the crash class by construction.

Modelled on ``tests/architectural/test_os_detection_ban.py`` +
``_os_detection_scan.py`` + its exemption-file pattern, adapted for a
single-owner, single exemption file (``_exemptions/no_follow_symlinks_apply.txt``)
rather than a per-owner glob: this gate has one owning WP and one violation
shape, so a plural ``*-ban-*.txt`` convention would add indirection with no
benefit. See ``tests.architectural._no_follow_symlinks_apply_scan`` for the
full detector rationale and scan-scope divergence from the OS-detection gate.

The single sanctioned door is ``kernel.no_follow`` (``chmod_no_follow`` /
``utime_no_follow``), which lives outside the two scanned packages
(``src/specify_cli/skills/``, ``src/specify_cli/tool_surface/``) entirely --
no door/exemption dance is needed the way the OS-detection gate needs one
for ``kernel/paths.py``.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

import pytest

from tests.architectural import _no_follow_symlinks_apply_scan as scan

pytestmark = [pytest.mark.architectural]

Violation = tuple[str, int]

_EXEMPTIONS_FILE = Path(__file__).resolve().parent / "_exemptions" / "no_follow_symlinks_apply.txt"


def _load_exemptions() -> frozenset[Violation]:
    exemptions: set[Violation] = set()
    for raw_line in _EXEMPTIONS_FILE.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        path_part, _, lineno_part = stripped.rpartition(":")
        if not path_part:
            continue
        exemptions.add((path_part, int(lineno_part)))
    return frozenset(exemptions)


def _violations_for_file(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return scan.find_no_follow_symlinks_apply_violations(tree)


def collect_violations(paths: Iterable[Path]) -> list[Violation]:
    """``(repo-relative path, line)`` for every banned ``follow_symlinks=False`` call across ``paths``."""
    violations: list[Violation] = []
    for path in paths:
        relpath = scan.relpath(path)
        violations.extend((relpath, lineno) for lineno in _violations_for_file(path))
    return sorted(violations)


def test_scanned_file_floor_is_met() -> None:
    """NOTE-3: a detector silently scanning zero files must go red, not green."""
    scanned = scan.iter_python_files()

    assert len(scanned) > scan.MIN_SCANNED_FILES, (
        f"only {len(scanned)} files scanned under {[str(r) for r in scan.SCAN_ROOTS]} -- the no-follow-symlinks apply ban gate would otherwise pass vacuously."
    )


def test_no_unguarded_follow_symlinks_false_in_apply_surface() -> None:
    """FR-002/NFR-003: no unguarded ``chmod``/``utime`` ``follow_symlinks=False`` call remains.

    Non-vacuity (C-009): ``test_self_mutation_reds_the_gate`` below proves
    this assertion is load-bearing by planting a synthetic offender and
    observing the same collection-and-filter logic go red.
    """
    scanned = scan.iter_python_files()
    exemptions = _load_exemptions()

    violations = [(relpath, lineno) for relpath, lineno in collect_violations(scanned) if (relpath, lineno) not in exemptions]

    assert violations == [], (
        "A chmod/utime call with an explicit `follow_symlinks=False` keyword "
        "is banned in the managed-skill apply surface (#4923/FR-002): it "
        "raises NotImplementedError on a host lacking follow_symlinks "
        "support. Route through `kernel.no_follow.chmod_no_follow` / "
        "`utime_no_follow` instead, or add `<path>:<line>` to "
        "tests/architectural/_exemptions/no_follow_symlinks_apply.txt if "
        "this is a currently-tracked, not-yet-remediated site.\nViolations:\n" + "\n".join(f"  {relpath}:{lineno}" for relpath, lineno in violations)
    )


def test_every_exemption_entry_is_a_real_violation() -> None:
    """Anti-staleness: every exemption entry must correspond to an actual violation today."""
    scanned = scan.iter_python_files()
    live_sites = set(collect_violations(scanned))
    exemptions = _load_exemptions()

    stale = exemptions - live_sites
    assert not stale, (
        "The following tests/architectural/_exemptions/no_follow_symlinks_apply.txt "
        "entries no longer correspond to a real violation -- delete them "
        "(the site is already clean):\n" + "\n".join(f"  {path}:{line}" for path, line in sorted(stale))
    )


def test_exemption_file_is_empty_shrink_only_floor() -> None:
    """T002 already routed every pre-existing offender; the floor is empty (comment-only)."""
    assert _load_exemptions() == frozenset(), "the no-follow-symlinks apply ban exemption file must stay empty -- T002 closed every known offender."


def test_self_mutation_reds_the_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-009 non-vacuity: planting an unguarded call-site makes the gate red.

    Plants a synthetic ``path.chmod(0o755, follow_symlinks=False)`` in an
    unexempted ``tmp_path`` file and runs it through the REAL detector,
    proving the gate is load-bearing rather than vacuously green.
    """
    module = tmp_path / "offender.py"
    module.write_text("path.chmod(0o755, follow_symlinks=False)\n", encoding="utf-8")
    monkeypatch.setattr(scan, "REPO_ROOT", tmp_path.resolve())

    violations = collect_violations([module])

    assert violations == [("offender.py", 1)], "the planted violation must be detected by the real detector"
    exemptions = _load_exemptions()
    assert ("offender.py", 1) not in exemptions, "the planted site must not accidentally match a real exemption entry"


def test_planted_chmod_follow_symlinks_false_fires(tmp_path: Path) -> None:
    """A planted ``x.chmod(mode, follow_symlinks=False)`` is caught."""
    module = tmp_path / "offender.py"
    module.write_text("x.chmod(0o600, follow_symlinks=False)\n", encoding="utf-8")

    assert _violations_for_file(module) == [1]


def test_planted_os_utime_follow_symlinks_false_fires(tmp_path: Path) -> None:
    """A planted ``os.utime(path, ns=ns, follow_symlinks=False)`` is caught."""
    module = tmp_path / "offender.py"
    module.write_text("import os\n\nos.utime(path, ns=(1, 1), follow_symlinks=False)\n", encoding="utf-8")

    assert _violations_for_file(module) == [3]


def test_in_function_call_is_caught(tmp_path: Path) -> None:
    """Full-AST walk (not module-level-only): an in-function call is still caught."""
    module = tmp_path / "offender.py"
    module.write_text(
        "def helper(path):\n    path.chmod(0o644, follow_symlinks=False)\n",
        encoding="utf-8",
    )

    assert _violations_for_file(module) == [2]


def test_safe_stat_follow_symlinks_does_not_fire(tmp_path: Path) -> None:
    """Negative (over-fire boundary): ``stat``/``is_file``/``lstat`` are different functions -- never matched."""
    module = tmp_path / "offender.py"
    module.write_text(
        "path.stat(follow_symlinks=False)\npath.is_file(follow_symlinks=False)\nos.lstat(path)\n",
        encoding="utf-8",
    )

    assert _violations_for_file(module) == []


def test_default_follow_utime_does_not_fire(tmp_path: Path) -> None:
    """Negative: the legitimate default-follow ``os.utime(dest, ns=...)`` (no flag) is never flagged.

    Mirrors the real ``asset_preservation/backup.py:38`` call, which must
    stay untouched by this gate.
    """
    module = tmp_path / "offender.py"
    module.write_text("import os\n\nos.utime(dest, ns=(mtime_ns, mtime_ns))\n", encoding="utf-8")

    assert _violations_for_file(module) == []


def test_follow_symlinks_true_does_not_fire(tmp_path: Path) -> None:
    """Negative (over-fire boundary): an explicit ``follow_symlinks=True`` is not banned."""
    module = tmp_path / "offender.py"
    module.write_text("path.chmod(0o644, follow_symlinks=True)\n", encoding="utf-8")

    assert _violations_for_file(module) == []


def test_unrelated_call_with_similar_kwarg_name_does_not_fire(tmp_path: Path) -> None:
    """Negative (over-fire boundary): a differently-named call is never matched, even with the same keyword."""
    module = tmp_path / "offender.py"
    module.write_text("some_other_call(mode, follow_symlinks=False)\n", encoding="utf-8")

    assert _violations_for_file(module) == []
