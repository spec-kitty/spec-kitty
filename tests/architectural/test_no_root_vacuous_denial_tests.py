"""Root-vacuous denial-test gate (#5691): no new test that skips, or passes vacuously, as root.

Root ignores mode bits, so a test that denies access with ``chmod`` gives no
coverage when it runs as uid 0, which is how CI containers and cloud sessions
run. New denial tests inject ``PermissionError`` at the seam with
``tests/_support/eacces.py`` instead. Modelled on
``test_no_follow_symlinks_apply_ban.py``; the detector lives in
``tests.architectural._root_vacuous_denial_scan``.
"""

from __future__ import annotations

import ast
import functools
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

import pytest

from tests.architectural import _root_vacuous_denial_scan as scan

pytestmark = [pytest.mark.architectural]

Site = tuple[str, str]

_EXEMPTIONS_FILE = Path(__file__).resolve().parent / "_exemptions" / "root_vacuous_denial.txt"
_CATEGORIES = frozenset({"kernel-check", "uid-independent", "deferred-6595"})

#: Shrink-only ceiling: the entry count at landing (#5691). Lower it when an
#: entry is removed; never raise it.
_MAX_EXEMPTIONS = 17


class Exemption(NamedTuple):
    kinds: frozenset[str]
    category: str
    reason: str


def _load_exemptions() -> dict[Site, Exemption]:
    """``{(path, qualname): Exemption}`` from the exemption file."""
    entries: dict[Site, Exemption] = {}
    for raw_line in _EXEMPTIONS_FILE.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        site, _, note = stripped.partition("#")
        key, _, kinds = site.strip().partition(" [")
        path, _, qualname = key.partition("::")
        category, _, reason = note.strip().partition(":")
        entries[(path, qualname)] = Exemption(frozenset(kinds.rstrip("]").split(",")) - {""}, category.strip(), reason.strip())
    return entries


def _findings_for_file(path: Path, display: str) -> list[scan.Finding]:
    return scan.find_findings(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)), display)


def collect_sites(paths: Iterable[Path]) -> dict[Site, set[str]]:
    """``{(path, qualname): {kind, ...}}`` for every flagged function across *paths*."""
    sites: dict[Site, set[str]] = {}
    for path in paths:
        for relpath, qualname, kind in _findings_for_file(path, scan.relpath(path)):
            sites.setdefault((relpath, qualname), set()).add(kind)
    return sites


def unexempted_sites(live: dict[Site, frozenset[str]], exemptions: dict[Site, Exemption]) -> dict[Site, frozenset[str]]:
    """Flagged functions with no entry, or with a kind their entry does not list."""
    return {site: kinds for site, kinds in live.items() if site not in exemptions or not kinds <= exemptions[site].kinds}


@functools.cache
def _live_sites() -> dict[Site, frozenset[str]]:
    """The scan of ``tests/``, done once per session: it parses several thousand files."""
    return {site: frozenset(kinds) for site, kinds in collect_sites(scan.iter_python_files()).items()}


def _findings_in(tmp_path: Path, source: str) -> list[tuple[str, str]]:
    module = tmp_path / "test_planted.py"
    module.write_text(source, encoding="utf-8")
    return [(qualname, kind) for _path, qualname, kind in _findings_for_file(module, "test_planted.py")]


def test_scanned_file_floor_is_met() -> None:
    """A detector that silently scans zero files must go red, not green."""
    scanned = scan.iter_python_files()

    assert len(scanned) > scan.MIN_SCANNED_FILES, f"only {len(scanned)} files scanned under {scan.SCAN_ROOT}; the gate would pass vacuously."


def test_no_new_root_vacuous_denial_test() -> None:
    """Every flagged function is an exempted one.

    Non-vacuity: ``test_self_mutation_reds_the_gate`` plants an offender and
    sees the same collection go red.
    """
    unexempted = unexempted_sites(_live_sites(), _load_exemptions())

    assert unexempted == {}, (
        "A test denies access with chmod, or skips as root (#5691). Root ignores mode bits, so as "
        "uid 0 (CI containers, cloud sessions) the test either skips or passes without reaching "
        "the denied branch. Inject PermissionError at the seam with tests/_support/eacces.py "
        "(deny_open_in, deny_path_method, deny_removal_from) instead; see "
        "docs/development/testing/permission-denied-tests.md. Only a test that must exercise the "
        "real kernel check belongs in tests/architectural/_exemptions/root_vacuous_denial.txt "
        "(an exempted function that gained a new kind is listed too).\n"
        + "\n".join(f"  {path}::{qualname}  [{', '.join(sorted(kinds))}]" for (path, qualname), kinds in sorted(unexempted.items()))
    )


def test_every_exemption_entry_is_a_live_site() -> None:
    """Anti-staleness: an entry whose test was converted or removed, or lost a kind, must be updated."""
    live = _live_sites()

    stale = sorted(site for site, entry in _load_exemptions().items() if live.get(site) != entry.kinds)
    assert stale == [], "These root_vacuous_denial.txt entries no longer match a flagged function and its kinds; delete or narrow them:\n" + "\n".join(
        f"  {p}::{q} (live: {sorted(live.get((p, q), ()))})" for p, q in stale
    )


def test_every_exemption_has_a_category_and_a_reason() -> None:
    bad = {site: entry for site, entry in _load_exemptions().items() if entry.category not in _CATEGORIES or not entry.reason or not entry.kinds}

    assert bad == {}, f"each entry needs one of {sorted(_CATEGORIES)} and a reason: {bad}"


def test_exemptions_only_shrink() -> None:
    count = len(_load_exemptions())

    assert count <= _MAX_EXEMPTIONS, f"{count} exemptions exceed the shrink-only ceiling of {_MAX_EXEMPTIONS}; inject at the seam instead of adding an entry."


def test_self_mutation_reds_the_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Planting a root-skipped chmod test makes the real collection report it, unexempted."""
    module = tmp_path / "tests" / "test_offender.py"
    module.parent.mkdir()
    module.write_text(
        "import os\nimport pytest\n\n@pytest.mark.skipif(os.geteuid() == 0, reason=\"root\")\ndef test_denied(tmp_path):\n    (tmp_path / 'x').chmod(0o000)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(scan, "REPO_ROOT", tmp_path.resolve())

    sites = collect_sites([module])

    assert sites == {("tests/test_offender.py", "test_denied"): {"uid-skip", "chmod-denial"}}
    assert not set(sites) & set(_load_exemptions())


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            '@pytest.mark.skipif(os.getuid() == 0, reason="r")\ndef test_a():\n    pass\n',
            [("test_a", "uid-skip")],
            id="uid-skip-decorator",
        ),
        pytest.param(
            "_skip = pytest.mark.skipif(hasattr(os, 'geteuid') and os.geteuid() == 0, reason='r')\n",
            [("<module>", "uid-skip")],
            id="uid-skip-module-marker",
        ),
        pytest.param(
            "def test_a(p):\n    if not mode_bits_enforced(p):\n        pytest.skip('r')\n",
            [("test_a", "mode-bits-skip")],
            id="mode-bits-skip",
        ),
        pytest.param(
            "def test_a(p):\n    if os.access(p, os.R_OK):\n        pytest.skip('r')\n",
            [("test_a", "access-skip")],
            id="access-skip",
        ),
        pytest.param("def test_a(p):\n    os.chmod(p, 0o555)\n", [("test_a", "chmod-denial")], id="os-chmod-locked-dir"),
        pytest.param("def test_a(p):\n    p.chmod(0o200)\n", [("test_a", "chmod-denial")], id="path-chmod-write-only"),
        pytest.param(
            "def test_a(p):\n    p.chmod(stat.S_IRUSR | stat.S_IXUSR)\n",
            [("test_a", "chmod-denial")],
            id="stat-constants",
        ),
        pytest.param(
            "class TestX:\n    def test_a(self, p):\n        def inner():\n            p.chmod(0)\n",
            [("TestX.test_a.inner", "chmod-denial")],
            id="nested-qualname",
        ),
        pytest.param("def test_a():\n    if not os.geteuid():\n        pytest.skip('r')\n", [("test_a", "uid-skip")], id="not-geteuid"),
        pytest.param("def test_a():\n    assert getpass.getuser() != 'root'\n", [("test_a", "uid-skip")], id="getuser-root"),
        pytest.param(
            "@pytest.mark.skipif(os.access('/x', os.R_OK), reason='r')\ndef test_a():\n    pass\n",
            [("test_a", "access-skip")],
            id="access-in-skipif",
        ),
        pytest.param("def test_a(p):\n    if os.access(p, os.R_OK):\n        return\n", [("test_a", "access-skip")], id="access-return"),
        pytest.param("def test_a(p):\n    chmod(p, 0o000)\n", [("test_a", "chmod-denial")], id="bare-chmod-import"),
        pytest.param("def test_a(p):\n    Path.chmod(p, 0)\n", [("test_a", "chmod-denial")], id="unbound-path-chmod"),
        pytest.param("def test_a(fd):\n    os.fchmod(fd, 0o500)\n", [("test_a", "chmod-denial")], id="fchmod"),
        pytest.param(
            "def test_a(p, monkeypatch):\n    p.chmod(0)\n    deny_list(p)\n    def inner():\n        deny_path_method(monkeypatch, 'stat', p)\n",
            [("test_a", "chmod-denial")],
            id="not-a-seam",
        ),
    ],
)
def test_detector_flags(tmp_path: Path, source: str, expected: list[tuple[str, str]]) -> None:
    assert _findings_in(tmp_path, source) == expected


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("def test_a(p):\n    p.chmod(0o444)\n", id="managed-read-only-file"),
        pytest.param("def test_a(p):\n    p.chmod(stat.S_IREAD)\n", id="s-iread"),
        pytest.param("def test_a(p):\n    os.chmod(p, 0o755)\n", id="restore-mode"),
        pytest.param("def test_a(p, mode):\n    p.chmod(mode)\n", id="unevaluable-mode"),
        pytest.param(
            "def test_a(p, monkeypatch):\n    p.chmod(0o555)\n    deny_removal_from(monkeypatch, p)\n",
            id="seam-in-same-function",
        ),
        pytest.param("def test_a():\n    assert os.getuid() > 1000\n", id="uid-compare-not-zero"),
        pytest.param("def test_a(p):\n    assert os.access(p, os.X_OK)\n", id="access-without-skip"),
    ],
)
def test_detector_does_not_flag(tmp_path: Path, source: str) -> None:
    assert _findings_in(tmp_path, source) == []


def test_denies_owner_truth_table() -> None:
    denied = [0o000, 0o100, 0o200, 0o300, 0o500, 0o555, 0o511]
    allowed = [0o400, 0o444, 0o600, 0o644, 0o700, 0o755]

    assert [scan.denies_owner(m) for m in denied] == [True] * len(denied)
    assert [scan.denies_owner(m) for m in allowed] == [False] * len(allowed)


def test_an_exempted_function_that_gains_a_kind_reds_the_gate() -> None:
    """An entry covers only the kinds it lists: a root skip added to a uid-independent test is caught."""
    exemptions = _load_exemptions()
    site, entry = next((site, entry) for site, entry in exemptions.items() if entry.category == "uid-independent")
    live = {site: entry.kinds | {"uid-skip"}}

    assert unexempted_sites(live, exemptions) == {site: entry.kinds | {"uid-skip"}}
    assert unexempted_sites({site: entry.kinds}, exemptions) == {}
