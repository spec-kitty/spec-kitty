"""Planted-violation tests for ``contracts/tools/no_pytest_scan.py`` (FR-017, no-pytest half).

The clean control is committed under ``contracts/tools/fixtures/no_pytest_scan/clean``. Planted scripts
are written into a temporary root at run time, so no committed file under ``contracts/tools`` reaches
the test runner (a planted import would also fail the repository's own lint). Each plant is asserted
by its stable code next to the clean control on the same root, and the scanner is shown to scan
itself and every sibling script.
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
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "no_pytest_scan"
SCRIPT = TOOLS_DIR / "no_pytest_scan.py"

# The name is assembled so that this test module does not itself contain the bare token.
RUNNER = "pyt" + "est"
HEAD, TAIL = RUNNER[:3], RUNNER[3:]

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


# fragment plant name -> source text; the sink call builds the runner name from fragments, and each must give one PYTEST_REFERENCE
FRAGMENT_PLANTS = {
    "import_module_concat": f'import importlib\n\nMODULE = importlib.import_module("{HEAD}" + "{TAIL}")\n',
    "import_module_submodule": f'from importlib import import_module\n\nMODULE = import_module("{HEAD}" + "{TAIL}.config")\n',
    "dunder_import_concat": f'MODULE = __import__("{HEAD}" + "{TAIL}")\n',
    "private_dunder_import": f'MODULE = __import__("_" + "{HEAD}" + "{TAIL}")\n',
    "import_module_fstring": f'import importlib\n\nPART = "{HEAD}"\nMODULE = importlib.import_module(f"{{PART}}{TAIL}")\n',
    "import_module_join": f'import importlib\n\nMODULE = importlib.import_module("".join(["{HEAD}", "{TAIL}"]))\n',
    "import_module_via_name": f'import importlib\n\nNAME = "{HEAD}" + "{TAIL}"\nMODULE = importlib.import_module(NAME)\n',
    "subprocess_list_concat": f'import subprocess\n\nsubprocess.run(["uv", "run", "{HEAD}" + "{TAIL}", "-q"], check=False)\n',
    "subprocess_string_concat": f'import subprocess\n\nsubprocess.check_call("python -m " + "{HEAD}" + "{TAIL}", shell=True)\n',
    "subprocess_popen_name": f'import subprocess\n\nRUN = "{HEAD}" + "{TAIL}"\nsubprocess.Popen(["python", "-m", RUN])\n',
    "os_system_concat": f'import os\n\nos.system("cd tests && " + "{HEAD}" + "{TAIL}")\n',
}


@pytest.fixture(scope="module")
def scan() -> Iterator[Any]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, SCRIPT, "no_pytest_scan_under_test", syspath=TOOLS_DIR)


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


# -- scripts in sub-directories and fragment-built runner names ---------------------------------------


@pytest.mark.parametrize("plant", sorted(FRAGMENT_PLANTS))
def test_a_runner_name_built_from_fragments_at_a_sink_is_a_reference(scan: Any, tmp_path: Path, plant: str) -> None:
    root = _planted_root(tmp_path, None)
    (root / "tools" / "plant_fragments.py").write_text(FRAGMENT_PLANTS[plant], encoding="utf-8")
    report = scan.check(root)
    assert [f.code for f in report.findings] == ["PYTEST_REFERENCE"], [f.render() for f in report.findings]
    assert "plant_fragments.py" in report.findings[0].subject
    assert report.exit_code == 1


def test_a_fragment_plant_is_one_finding_per_line_even_when_a_literal_names_the_runner(scan: Any, tmp_path: Path) -> None:
    root = _planted_root(tmp_path, None)
    (root / "tools" / "plant_literal.py").write_text(f'import importlib\n\nMODULE = importlib.import_module("{RUNNER}")\n', encoding="utf-8")
    assert [f.subject.rsplit(":", 1)[-1] for f in scan.check(root).findings] == ["3"]


def test_fragments_that_do_not_spell_the_runner_or_sit_outside_a_sink_are_not_references(scan: Any, tmp_path: Path) -> None:
    root = _planted_root(tmp_path, None)
    (root / "tools" / "harmless.py").write_text(
        'import importlib\nimport subprocess\n\nMODULE = importlib.import_module("json" + ".tool")\n'
        'subprocess.run(["py" + "thon", "-V"], check=False)\n'
        f'NAME = "{HEAD}" + "{TAIL}"\nWORDS = [NAME, "{HEAD}"]\n',
        encoding="utf-8",
    )
    assert scan.check(root).findings == []


@pytest.mark.parametrize("directory", ["helpers", "helpers/deeper"])
def test_a_script_in_a_sub_directory_of_tools_is_scanned(scan: Any, tmp_path: Path, directory: str) -> None:
    root = _planted_root(tmp_path, None)
    nested = root / "tools" / directory
    nested.mkdir(parents=True)
    (nested / "plant_nested.py").write_text(PLANTS["import"][1], encoding="utf-8")
    (nested / "run.sh").write_text(PLANTS["shell_script"][1], encoding="utf-8")
    report = scan.check(root)
    assert sorted(f.subject.split(":")[0] for f in report.findings) == [f"tools/{directory}/plant_nested.py", f"tools/{directory}/run.sh"]
    assert report.counts["scripts_scanned"] == 4
    result = _run("--root", str(root))
    assert result.returncode == 1
    assert f"tools/{directory}/plant_nested.py:1" in result.stdout


def test_fixtures_and_bytecode_caches_are_not_scanned(scan: Any, tmp_path: Path) -> None:
    root = _planted_root(tmp_path, None)
    for excluded in ("fixtures/case/tools", "__pycache__", "fixtures"):
        directory = root / "tools" / excluded
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "plant_excluded.py").write_text(PLANTS["import"][1], encoding="utf-8")
    report = scan.check(root)
    assert report.findings == []
    assert report.counts == {"scripts_scanned": 2}


def test_an_unparseable_script_in_a_sub_directory_exits_two(scan: Any, tmp_path: Path) -> None:
    root = _planted_root(tmp_path, None)
    (root / "tools" / "helpers").mkdir()
    (root / "tools" / "helpers" / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    report = scan.check(root)
    assert [(f.code, f.subject) for f in report.blocked] == [("UNREADABLE_SCRIPT", "tools/helpers/broken.py")]
    assert report.exit_code == 2


def test_the_scanner_builds_the_runner_name_from_fragments_yet_is_clean_without_an_exemption(scan: Any) -> None:
    # it assembles the name for its own search, but never passes it to an import, subprocess or shell sink
    assert scan.scan_python("tools/no_pytest_scan.py", SCRIPT.read_text(encoding="utf-8")) == []
    assert scan.check(REPO_ROOT / "contracts").findings == []
