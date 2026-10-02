"""Planted-violation tests for ``contracts/tools/codeowners_check.py`` (FR-023).

One committed fixture root, ``contracts/tools/fixtures/codeowners_check/``, holds a clean control
(``clean``: a ``.github/CODEOWNERS`` whose ``/contracts/`` rule names both required handles) and one
root per planted violation. The ``NOT_TRACKED`` case needs a git checkout whose ignore rules cover
the file, so it is built at run time in a throw-away repository. A last test asserts the real file is
tracked and not ignored in this checkout.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "contracts" / "tools"
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "codeowners_check"
SCRIPT = TOOLS_DIR / "codeowners_check.py"
GIT = shutil.which("git")

# fixture root -> exactly the codes it must produce, sorted
PLANTED = {
    "v_rule_missing": ["RULE_MISSING"],
    "v_handle_missing_one": ["HANDLE_MISSING"],
    "v_handle_missing_none": ["HANDLE_MISSING", "HANDLE_MISSING"],
    "v_pattern_not_covering_tools_only": ["PATTERN_DOES_NOT_COVER_MODULE"],
    "v_pattern_not_covering_star": ["PATTERN_DOES_NOT_COVER_MODULE"],
    "v_later_rule_overrides": ["HANDLE_MISSING", "HANDLE_MISSING"],
}
EXIT2 = {"file_missing": "FILE_MISSING", "zero_rules": "ZERO_RULES"}


@pytest.fixture(scope="module")
def owners() -> Iterator[Any]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, SCRIPT, "codeowners_check_under_test", syspath=TOOLS_DIR)


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, check=False, cwd=REPO_ROOT)


def _git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    assert GIT is not None, "git is required"
    return subprocess.run([GIT, *arguments], capture_output=True, text=True, check=False, cwd=cwd)


@pytest.mark.parametrize(("case", "codes"), sorted(PLANTED.items()))
def test_each_planted_violation_gives_its_stable_code(owners: Any, case: str, codes: list[str]) -> None:
    report = owners.check(FIXTURE_ROOT / case)
    assert sorted(f.code for f in report.findings) == codes
    assert report.blocked == []
    assert report.exit_code == 1


def test_the_clean_control_has_no_finding_and_the_floor_is_met(owners: Any) -> None:
    report = owners.check(FIXTURE_ROOT / "clean")
    assert report.findings == []
    assert report.blocked == []
    assert report.exit_code == 0
    assert report.counts == {"rules": 2}


def test_a_handle_finding_names_the_handle(owners: Any) -> None:
    (finding,) = owners.check(FIXTURE_ROOT / "v_handle_missing_one").findings
    assert "@MOES-Media" in finding.detail


@pytest.mark.parametrize(
    ("pattern", "path", "covers"),
    [
        ("/contracts/", "contracts/mission-status/openapi.yaml", True),
        ("contracts/", "contracts/mission-status/openapi.yaml", True),
        ("/contracts", "contracts/mission-status/openapi.yaml", True),
        ("/contracts/**", "contracts/mission-status/openapi.yaml", True),
        ("/contracts/mission-status/", "contracts/mission-status/openapi.yaml", True),
        ("*", "contracts/mission-status/openapi.yaml", True),
        ("/contracts/*", "contracts/mission-status/openapi.yaml", False),
        ("/contracts/*", "contracts/README.md", True),
        ("/contracts/tools/", "contracts/mission-status/openapi.yaml", False),
        ("/docs/", "contracts/mission-status/openapi.yaml", False),
        ("/mission-status/", "contracts/mission-status/openapi.yaml", False),
        ("mission-status/", "contracts/mission-status/openapi.yaml", True),
        ("*.yaml", "contracts/mission-status/openapi.yaml", True),
        ("/contract/", "contracts/mission-status/openapi.yaml", False),
    ],
)
def test_the_pattern_matcher_follows_codeowners_semantics(owners: Any, pattern: str, path: str, covers: bool) -> None:
    assert owners.pattern_covers(pattern, path) is covers


@pytest.mark.parametrize(("case", "code"), sorted(EXIT2.items()))
def test_a_check_that_cannot_do_its_job_exits_two_with_its_code(owners: Any, case: str, code: str) -> None:
    root = FIXTURE_ROOT / "exit2" / case
    report = owners.check(root)
    assert [f.code for f in report.blocked][:1] == [code]
    assert report.exit_code == 2
    result = _run("--root", str(root))
    assert result.returncode == 2
    assert f"CONTRACT-CHECK codeowners_check: {code}" in result.stdout
    assert result.stdout.rstrip().splitlines()[-1] == "counts: rules=0"


@pytest.mark.skipif(GIT is None, reason="git is required")
def test_an_ignored_file_in_a_git_checkout_exits_two_not_tracked(owners: Any, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    assert _git(root, "init", "-q").returncode == 0
    (root / ".gitignore").write_text(".github/*\n", encoding="utf-8")
    report = owners.check(root)
    assert [f.code for f in report.blocked] == ["NOT_TRACKED"]
    assert "ignored" in report.blocked[0].detail
    assert report.exit_code == 2
    result = _run("--root", str(root))
    assert result.returncode == 2
    assert "CONTRACT-CHECK codeowners_check: NOT_TRACKED" in result.stdout


@pytest.mark.skipif(GIT is None, reason="git is required")
def test_an_untracked_file_in_a_git_checkout_exits_two_not_tracked(owners: Any, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    assert _git(root, "init", "-q").returncode == 0
    report = owners.check(root)
    assert [f.code for f in report.blocked] == ["NOT_TRACKED"]
    assert "untracked" in report.blocked[0].detail


@pytest.mark.skipif(GIT is None, reason="git is required")
def test_a_tracked_file_in_a_git_checkout_passes(owners: Any, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    assert _git(root, "init", "-q").returncode == 0
    assert _git(root, "add", ".github/CODEOWNERS").returncode == 0
    report = owners.check(root)
    assert report.blocked == []
    assert report.exit_code == 0


def test_command_line_output_grammar_and_exit_status() -> None:
    result = _run("--root", str(FIXTURE_ROOT / "v_rule_missing"))
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert lines[-1] == "counts: rules=1"
    assert any(line.startswith("CONTRACT-CHECK codeowners_check: RULE_MISSING: ") for line in lines)
    clean = _run("--root", str(FIXTURE_ROOT / "clean"))
    assert clean.returncode == 0, clean.stdout
    assert clean.stdout.splitlines()[-1] == "counts: rules=2"


@pytest.mark.skipif(GIT is None, reason="git is required")
def test_the_real_file_is_tracked_not_ignored_and_passes() -> None:
    listed = _git(REPO_ROOT, "ls-files", ".github/CODEOWNERS")
    assert listed.stdout.split() == [".github/CODEOWNERS"]
    ignored = _git(REPO_ROOT, "check-ignore", ".github/CODEOWNERS")
    assert ignored.returncode == 1 and ignored.stdout == ""
    result = _run("--root", str(REPO_ROOT))
    assert result.returncode == 0, result.stdout
    assert int(result.stdout.splitlines()[-1].removeprefix("counts: rules=")) >= 1
