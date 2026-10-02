"""Planted-violation tests for ``contracts/tools/no_pytest_scan.py`` (FR-017, no-pytest half).

The clean control is committed under ``contracts/tools/fixtures/no_pytest_scan/clean``. Planted scripts
are written into a temporary root at run time, so no committed file under ``contracts/tools`` reaches
the test runner (a planted import would also fail the repository's own lint). Each plant is asserted
by its stable code next to the clean control on the same root, and the scanner is shown to scan
itself and every sibling script.
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
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "no_pytest_scan"
SCRIPT = TOOLS_DIR / "no_pytest_scan.py"

# The name is assembled so that this test module does not itself contain the bare token.
RUNNER = "pyt" + "est"

# plant name -> (file name, file text); each must produce exactly one PYTEST_REFERENCE
PLANTS = {
    "import": ("plant_import.py", f"import {RUNNER}\n\nNAME = {RUNNER}.__name__\n"),
    "from_import": ("plant_from.py", f"from {RUNNER} import raises\n\nUSED = raises\n"),
    "private_import": ("plant_private.py", f"import _{RUNNER}\n\nNAME = _{RUNNER}.__name__\n"),
    "dynamic_import": ("plant_dynamic.py", f'import importlib\n\nMODULE = importlib.import_module("{RUNNER}")\n'),
    "python_dash_m": ("plant_dash_m.py", f'COMMAND = "python -m {RUNNER} tests"\n'),
    "subprocess_list": ("plant_list.py", f'import subprocess\n\nsubprocess.run(["uv", "run", "{RUNNER}", "-q"], check=False)\n'),
    "shell_string": ("plant_shell.py", f'import os\n\nos.system("cd tests && {RUNNER} -q")\n'),
    "make_target": ("Makefile", f"test:\n\t{RUNNER} -q\n"),
    "shell_script": ("plant_run.sh", f"#!/bin/sh\nset -e\n{RUNNER} -q\n"),
}


@pytest.fixture(scope="module")
def scan() -> Any:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("no_pytest_scan_under_test", SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(TOOLS_DIR))
    return module


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, check=False, cwd=REPO_ROOT)


def _planted_root(tmp_path: Path, plant: str | None) -> Path:
    root = tmp_path / "contracts"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    if plant is not None:
        name, text = PLANTS[plant]
        (root / "tools" / name).write_text(text, encoding="utf-8")
    return root


@pytest.mark.parametrize("plant", sorted(PLANTS))
def test_each_planted_reference_gives_its_stable_code(scan: Any, tmp_path: Path, plant: str) -> None:
    root = _planted_root(tmp_path, plant)
    report = scan.check(root)
    assert [f.code for f in report.findings] == ["PYTEST_REFERENCE"]
    assert PLANTS[plant][0] in report.findings[0].subject
    assert report.exit_code == 1
    result = _run("--root", str(root))
    assert result.returncode == 1
    assert "CONTRACT-CHECK no_pytest_scan: PYTEST_REFERENCE" in result.stdout


def test_the_clean_control_has_no_finding_and_the_floor_is_met(scan: Any, tmp_path: Path) -> None:
    report = scan.check(_planted_root(tmp_path, None))
    assert report.findings == []
    assert report.blocked == []
    assert report.exit_code == 0
    assert report.counts == {"scripts_scanned": 2}


def test_prose_a_cache_directory_and_a_hyphenated_word_are_not_references(scan: Any) -> None:
    assert not scan.mentions_runner(f"never imports it; see .{RUNNER}_cache and {RUNNER}-free notes")
    assert scan.mentions_runner(f"{RUNNER} -q")
    assert scan.mentions_runner(f"/venv/bin/{RUNNER} -q")
    assert not scan.mentions_runner(f"my_{RUNNER}_helper and .{RUNNER}_cache and {RUNNER}-free")


def test_a_docstring_may_name_the_runner_but_a_message_string_may_not(scan: Any, tmp_path: Path) -> None:
    root = _planted_root(tmp_path, None)
    (root / "tools" / "doc_only.py").write_text(
        f'"""Never imports {RUNNER}."""\n\n\ndef f() -> None:\n    """Does not call {RUNNER} either."""\n', encoding="utf-8"
    )
    assert scan.check(root).findings == []
    (root / "tools" / "message.py").write_text(f'MESSAGE = "needs {RUNNER} installed"\n', encoding="utf-8")
    assert [f.code for f in scan.check(root).findings] == ["PYTEST_REFERENCE"]


def test_a_comment_is_not_a_reference(scan: Any, tmp_path: Path) -> None:
    root = _planted_root(tmp_path, None)
    (root / "tools" / "commented.py").write_text(f"# run {RUNNER} somewhere else\nVALUE = 1\n", encoding="utf-8")
    assert scan.check(root).findings == []


def test_zero_scripts_exits_two(scan: Any) -> None:
    root = FIXTURE_ROOT / "exit2" / "zero_scripts"
    report = scan.check(root)
    assert [f.code for f in report.blocked] == ["ZERO_SCRIPTS"]
    assert report.exit_code == 2
    result = _run("--root", str(root))
    assert result.returncode == 2
    assert "CONTRACT-CHECK no_pytest_scan: ZERO_SCRIPTS" in result.stdout
    assert result.stdout.rstrip().splitlines()[-1] == "counts: scripts_scanned=0"


def test_a_script_that_cannot_be_parsed_exits_two_instead_of_passing(scan: Any, tmp_path: Path) -> None:
    root = _planted_root(tmp_path, None)
    (root / "tools" / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    report = scan.check(root)
    assert [f.code for f in report.blocked] == ["UNREADABLE_SCRIPT"]
    assert report.exit_code == 2


def test_the_scanner_scans_itself_and_every_sibling(scan: Any) -> None:
    report = scan.check(REPO_ROOT / "contracts")
    expected = sorted(p.name for p in TOOLS_DIR.glob("*.py"))
    assert "no_pytest_scan.py" in expected
    assert sorted(Path(name).name for name in report.scanned) == expected
    assert report.counts["scripts_scanned"] == len(expected)


def test_the_scanner_passes_on_its_own_source_in_isolation(scan: Any, tmp_path: Path) -> None:
    root = tmp_path / "contracts"
    (root / "tools").mkdir(parents=True)
    shutil.copy(SCRIPT, root / "tools" / SCRIPT.name)
    report = scan.check(root)
    assert report.findings == []
    assert report.counts["scripts_scanned"] == 1


def test_the_real_tools_directory_passes_and_the_count_is_the_number_of_scripts() -> None:
    result = _run("--root", str(REPO_ROOT / "contracts"))
    assert result.returncode == 0, result.stdout
    count = int(result.stdout.splitlines()[-1].removeprefix("counts: scripts_scanned="))
    assert count == len(list(TOOLS_DIR.glob("*.py")))
    assert count >= 18
