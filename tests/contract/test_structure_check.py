"""Planted-violation tests for ``contracts/tools/structure_check.py`` (FR-001 structure, FR-024).

One committed fixture root, ``contracts/tools/fixtures/structure_check/``, holds a clean control
(``clean``: a README with every required heading and a module whose CHANGELOG has the four section
headings and a heading for the module's current ``info.version``) and one root per planted
violation. Each rule is asserted by its stable code on its own root while the control stays clean.
The README planted-removal test removes each required heading in turn from a copy of the control.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "contracts" / "tools"
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "structure_check"
SCRIPT = TOOLS_DIR / "structure_check.py"

# fixture root -> exactly the codes it must produce, sorted
PLANTED = {
    "v_readme_heading_missing": ["README_HEADING_MISSING"],
    "v_changelog_no_changed": ["CHANGELOG_HEADING_MISSING"],
    "v_changelog_no_provisional": ["CHANGELOG_HEADING_MISSING"],
    "v_changelog_version_missing": ["CHANGELOG_VERSION_HEADING_MISSING"],
    "v_changelog_file_missing": ["CHANGELOG_HEADING_MISSING"] * 4 + ["CHANGELOG_VERSION_HEADING_MISSING"],
}
EXIT2 = ["zero_readme_headings", "zero_changelog_headings", "no_module"]

# WP01's T007 hand-off list, entry for entry and in order
WP01_README_HEADINGS = [
    "Layout",
    "Path file naming",
    "Relative $ref rules",
    "_shared admission",
    "Module version and the /api/v1 prefix",
    "x-source, x-derived and x-provisional",
    "Lane terminology",
    "Workflow phase and glossary phase",
    "Topology enum",
    "The bundle is a build product",
    "Validate and bundle locally",
    "Markdown lint is advisory",
    "Not the CLI contract registry",
    "Board columns are a consumer convention",
    "Versioning rule",
    "Residual risk: handle-shaped strings",
    "Reader-author warning",
    "Preview tags",
]


@pytest.fixture(scope="module")
def structure() -> Any:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("structure_check_under_test", SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(TOOLS_DIR))
    return module


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, check=False, cwd=REPO_ROOT)


def _counts(stdout: str) -> dict[str, int]:
    return {key: int(value) for key, value in (pair.split("=") for pair in stdout.splitlines()[-1].removeprefix("counts: ").split())}


@pytest.mark.parametrize(("case", "codes"), sorted(PLANTED.items()))
def test_each_planted_violation_gives_its_stable_code(structure: Any, case: str, codes: list[str]) -> None:
    report = structure.check(FIXTURE_ROOT / case)
    assert sorted(f.code for f in report.findings) == codes
    assert report.blocked == []
    assert report.exit_code == 1


def test_the_clean_control_has_no_finding_and_the_floor_is_met(structure: Any) -> None:
    report = structure.check(FIXTURE_ROOT / "clean")
    assert report.findings == []
    assert report.blocked == []
    assert report.exit_code == 0
    assert report.counts["readme_headings"] >= len(WP01_README_HEADINGS)
    assert report.counts["changelog_headings"] >= 5


def test_the_readme_heading_constant_equals_the_wp01_hand_off_list(structure: Any) -> None:
    assert list(structure.README_HEADINGS) == WP01_README_HEADINGS


@pytest.mark.parametrize("heading", WP01_README_HEADINGS)
def test_removing_each_readme_heading_in_turn_is_reported(structure: Any, tmp_path: Path, heading: str) -> None:
    root = tmp_path / "root"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    readme = root / "README.md"
    lines = [line for line in readme.read_text(encoding="utf-8").splitlines() if line.removeprefix("## ") != heading]
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = structure.check(root)
    assert [(f.code, f.subject) for f in report.findings] == [("README_HEADING_MISSING", heading)]


def test_a_heading_inside_a_code_fence_does_not_count(structure: Any, tmp_path: Path) -> None:
    root = tmp_path / "root"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    readme = root / "README.md"
    lines = readme.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if line != "## Preview tags"]
    readme.write_text("\n".join([*kept, "```", "## Preview tags", "```"]) + "\n", encoding="utf-8")
    assert [f.code for f in structure.check(root).findings] == ["README_HEADING_MISSING"]


def test_the_version_heading_may_carry_a_date_but_not_a_longer_version(structure: Any, tmp_path: Path) -> None:
    root = tmp_path / "root"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    changelog = root / "mod" / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    changelog.write_text(text.replace("## 1.0.0", "## 1.0.0 - 2026-10-02"), encoding="utf-8")
    assert structure.check(root).findings == []
    changelog.write_text(text.replace("## 1.0.0", "## 1.0.01"), encoding="utf-8")
    assert [f.code for f in structure.check(root).findings] == ["CHANGELOG_VERSION_HEADING_MISSING"]


@pytest.mark.parametrize("case", EXIT2)
def test_a_check_that_cannot_do_its_job_exits_two_with_zero_headings(structure: Any, case: str) -> None:
    root = FIXTURE_ROOT / "exit2" / case
    report = structure.check(root)
    assert [f.code for f in report.blocked][:1] == ["ZERO_HEADINGS"]
    assert report.exit_code == 2
    result = _run("--root", str(root))
    assert result.returncode == 2
    assert "CONTRACT-CHECK structure_check: ZERO_HEADINGS" in result.stdout
    assert result.stdout.rstrip().splitlines()[-1].startswith("counts: readme_headings=")


def test_command_line_output_grammar_and_exit_status() -> None:
    result = _run("--root", str(FIXTURE_ROOT / "v_changelog_no_changed"))
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert lines[-1].startswith("counts: readme_headings=")
    assert any(line.startswith("CONTRACT-CHECK structure_check: CHANGELOG_HEADING_MISSING: ") for line in lines)
    clean = _run("--root", str(FIXTURE_ROOT / "clean"))
    assert clean.returncode == 0, clean.stdout
    assert clean.stdout.splitlines()[-1].startswith("counts: readme_headings=")


def test_the_real_contracts_tree_passes_with_a_floor() -> None:
    result = _run("--root", str(REPO_ROOT / "contracts"))
    assert result.returncode == 0, result.stdout
    counts = _counts(result.stdout)
    assert counts["readme_headings"] >= len(WP01_README_HEADINGS)
    assert counts["changelog_headings"] >= 5


def test_no_node_tooling_is_referenced() -> None:
    text = SCRIPT.read_text(encoding="utf-8").lower()
    assert "markdownlint" not in text.replace("markdown lint", "")
    assert "npm" not in text.split()
