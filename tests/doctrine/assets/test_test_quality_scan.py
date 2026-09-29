"""Behaviour of the internal ``test-quality-scan`` asset (the static triage pass).

The scanner is a maintainer asset in ``packs/internal/assets/``; these tests
drive it through its CLI entry point (``main``) over a planted test corpus and
read back the files it writes, the way a maintainer or a review squad does.
Each weak-oracle pattern is planted beside a clean control so a detector that
fires on everything, or on nothing, goes red.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit]

_ASSET = Path(__file__).resolve().parents[3] / "packs" / "internal" / "assets" / "test-quality-scan.py"
_MODULE_NAME = "test_quality_scan_asset"

_CLEAN_TEST = """
def test_total_adds_line_items():
    assert total([2, 3]) == 5
"""

#: One planted test per detector: (flag code, test source).
_PLANTED: list[tuple[str, str]] = [
    ("no-assertion", "def test_runs():\n    build_report()\n"),
    ("weak-only-assert", "def test_report_exists():\n    report = build_report()\n    assert report is not None\n"),
    ("type-only-assert", "def test_report_type():\n    assert isinstance(build_report(), dict)\n"),
    ("broad-raises", "def test_rejects():\n    with pytest.raises(Exception):\n        parse('x')\n"),
    (
        "over-mocking",
        "@patch('a.b')\n@patch('a.c')\ndef test_flow(m1, m2):\n    x = MagicMock()\n    y = Mock()\n    assert run(x, y) == 1\n",
    ),
    ("interaction-assert", "def test_calls(m):\n    run(m)\n    m.save.assert_called_once_with(1)\n"),
    (
        "literal-source-scan",
        "def test_guard_present():\n    text = Path('src/specify_cli/x.py').read_text()\n    assert 'guard(' in text\n",
    ),
    ("line-number-pin", "def test_points_at_line():\n    assert error_location() == 'emit.py:42'\n"),
    ("fake-short-ulid", "def test_mission():\n    meta = {'mission_id': 'ABC123'}\n    assert load(meta).ok\n"),
    ("fake-short-ulid", "def test_short_folded():\n    meta = {'mission_id': '01M' + '0' * 5}\n    assert load(meta).ok\n"),
    ("sleep", "def test_waits():\n    time.sleep(0.5)\n    assert done()\n"),
    ("wallclock", "def test_stamp():\n    assert stamp() <= time.time()\n"),
    ("skip-or-xfail", "@pytest.mark.xfail(reason='later')\ndef test_future():\n    assert future() == 1\n"),
    ("vague-name", "def test_basic():\n    assert total([1]) == 1\n"),
    ("provenance-tokens", 'def test_wp03_gate():\n    """T012: pins FR-004."""\n    assert gate() == 1\n'),
]

#: Look-alikes a detector must leave alone: (flag code, test source).
_NOT_FLAGGED: list[tuple[str, str]] = [
    ("fake-short-ulid", "def test_real():\n    meta = {'mission_id': '01M' + '0' * 23}\n    assert load(meta).ok\n"),
    ("fake-short-ulid", "def test_real2():\n    assert load(mission_id='01K3N7ZQ8X1V2B3C4D5E6F7G8H').ok\n"),
]


def _planted_name(source: str) -> str:
    return next(line.split("(")[0].removeprefix("def ") for line in source.splitlines() if line.startswith("def "))


@pytest.fixture(scope="module")
def scan() -> Iterator[ModuleType]:
    """Load the asset as a module; dataclasses need it registered while executing."""
    with pytest.MonkeyPatch.context() as mp:
        spec = importlib.util.spec_from_file_location(_MODULE_NAME, _ASSET)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        mp.setitem(sys.modules, _MODULE_NAME, module)
        spec.loader.exec_module(module)
        yield module


def _write(root: Path, rel: str, source: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _run(scan: ModuleType, repo: Path, *extra: str) -> Path:
    out = repo / "out"
    exit_code = scan.main(["--repo", str(repo), "--out", str(out), *extra])
    assert exit_code == 0
    return out


def _flags_by_test(out: Path) -> dict[str, list[str]]:
    rows = json.loads((out / "tests.json").read_text(encoding="utf-8"))
    return {row["test"]: row["flags"] for row in rows}


@pytest.mark.parametrize(("code", "source"), _PLANTED, ids=[code for code, _ in _PLANTED])
def test_planted_weak_test_is_flagged_and_clean_control_is_not(scan: ModuleType, tmp_path: Path, code: str, source: str) -> None:
    _write(tmp_path, "tests/billing/test_planted.py", _CLEAN_TEST + "\n\n" + source)

    flags = _flags_by_test(_run(scan, tmp_path, "--no-git"))

    assert code in flags[_planted_name(source)]
    assert "test_total_adds_line_items" not in flags


@pytest.mark.parametrize(("code", "source"), _NOT_FLAGGED, ids=[_planted_name(source) for _, source in _NOT_FLAGGED])
def test_look_alike_is_not_flagged(scan: ModuleType, tmp_path: Path, code: str, source: str) -> None:
    _write(tmp_path, "tests/billing/test_planted.py", source)

    flags = _flags_by_test(_run(scan, tmp_path, "--no-git"))

    assert code not in flags.get(_planted_name(source), [])


def test_files_are_ranked_by_score_within_their_domain(scan: ModuleType, tmp_path: Path) -> None:
    _write(tmp_path, "tests/billing/test_clean.py", _CLEAN_TEST)
    _write(tmp_path, "tests/billing/test_weak.py", "def test_runs():\n    build_report()\n")
    _write(tmp_path, "tests/specify_cli/status/test_weak.py", "def test_runs():\n    build_report()\n")

    out = _run(scan, tmp_path, "--no-git")

    files = json.loads((out / "files.json").read_text(encoding="utf-8"))
    assert [(f["file"], f["domain"], f["score"]) for f in files] == [
        ("tests/billing/test_weak.py", "billing", 5),
        ("tests/specify_cli/status/test_weak.py", "specify_cli/status", 5),
        ("tests/billing/test_clean.py", "billing", 0),
    ]
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert "| billing | 2 | 2 | 1 | 5 | no-assertion 1 |" in summary


def test_rerun_keeps_a_ledger_a_squad_already_filled_in(scan: ModuleType, tmp_path: Path) -> None:
    _write(tmp_path, "tests/billing/test_weak.py", "def test_runs():\n    build_report()\n")
    ledger = _run(scan, tmp_path, "--no-git") / "ledger" / "billing.md"
    assert "- [ ] `tests/billing/test_weak.py` score 5" in ledger.read_text(encoding="utf-8")
    ledger.write_text("- [x] `tests/billing/test_weak.py` Verdict: RETIRE\n", encoding="utf-8")

    _run(scan, tmp_path, "--no-git")

    assert ledger.read_text(encoding="utf-8") == "- [x] `tests/billing/test_weak.py` Verdict: RETIRE\n"


@pytest.mark.git_repo
def test_since_scores_only_tests_changed_after_the_revision(scan: ModuleType, tmp_path: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    _write(tmp_path, "tests/billing/test_old.py", "def test_old():\n    build_report()\n\ndef test_edited():\n    build_report()\n")
    git("add", ".")
    git("commit", "-qm", "base")
    _write(tmp_path, "tests/billing/test_old.py", "def test_old():\n    build_report()\n\ndef test_edited():\n    rebuild()\n")
    _write(tmp_path, "tests/billing/test_new.py", "def test_new():\n    build_report()\n")
    git("add", ".")
    git("commit", "-qm", "WP02 add billing tests")

    out = _run(scan, tmp_path, "--since", "HEAD~1")

    assert set(_flags_by_test(out)) == {"test_edited", "test_new"}
    files = {f["file"]: f for f in json.loads((out / "files.json").read_text(encoding="utf-8"))}
    assert files["tests/billing/test_new.py"]["added_by"].endswith("WP02 add billing tests")
