"""Planted-violation tests for ``contracts/tools/layout_check.py`` (FR-001, FR-021, FR-025).

One committed fixture root, ``contracts/tools/fixtures/layout_check/``, holds a
clean control module (``clean``, with a brace-named path file referenced in the
canonical spelling), the clean ``_shared`` pieces, and one module per planted
violation. Every rule is asserted on its own module and the control stays
clean in the same run. Brace spellings in test code come from the resolver's
constant and ``chr`` calls, never from literals (Rule BRACE-1).
"""

from __future__ import annotations

import ast
import importlib.util
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

TOOLS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "tools"
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "layout_check"
SCRIPT = TOOLS_DIR / "layout_check.py"

OPEN_BRACE, CLOSE_BRACE = chr(123), chr(125)

# module directory in the fixture root -> exactly the codes it must produce, in report order
PLANTED = {
    "v_path_file_name": ["PATH_FILE_NAME"],
    "v_mapped_file_missing": ["MAPPED_FILE_MISSING"],
    "v_orphan_path_file": ["ORPHAN_PATH_FILE"],
    "v_schema_name_mismatch": ["SCHEMA_NAME_MISMATCH"],
    "v_index_missing_file": ["INDEX_MISSING_FILE"],
    "v_index_omits_file": ["INDEX_OMITS_FILE"],
    "v_bad_ref_form": ["BAD_REF_FORM", "BAD_REF_FORM", "BAD_REF_FORM"],
    "v_brace_ref_spelling": ["BRACE_REF_SPELLING"],
    "v_shared_misuse": ["SHARED_MISUSE"],
    "v_tracked_bundle": ["TRACKED_BUNDLE"],
}
CLEAN_MODULES = ("clean", "_shared")


@pytest.fixture(scope="module")
def layout() -> Any:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("layout_check_under_test", SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(TOOLS_DIR))
    return module


@pytest.fixture(scope="module")
def resolver(layout: ModuleType) -> ModuleType:
    return sys.modules["contract_resolver"]


@pytest.fixture(scope="module")
def planted_report(layout: Any) -> Any:
    return layout.check(FIXTURE_ROOT)


def _by_module(report: Any) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for finding in report.findings:
        grouped[finding.path.split("/")[0]].append(finding)
    return grouped


def _copy_modules(destination: Path, *names: str) -> Path:
    for name in names:
        shutil.copytree(FIXTURE_ROOT / name, destination / name)
    return destination


def _run_script(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], capture_output=True, text=True, timeout=120, check=False)


# -- one planted violation per rule, with the control clean in the same run ---


@pytest.mark.parametrize(("module", "codes"), sorted(PLANTED.items()))
def test_each_planted_violation_yields_exactly_its_code(planted_report: Any, module: str, codes: list[str]) -> None:
    findings = _by_module(planted_report)[module]

    assert [f.code for f in findings] == codes
    assert all(f.path.startswith(module + "/") for f in findings), "every finding names the offending path"


@pytest.mark.parametrize("module", CLEAN_MODULES)
def test_the_clean_control_has_no_finding_in_the_same_run(planted_report: Any, module: str) -> None:
    assert planted_report.findings, "the run found the planted violations"
    assert _by_module(planted_report).get(module, []) == []


def test_every_planted_module_exists_on_disk_so_the_table_is_not_stale() -> None:
    on_disk = {p.name for p in FIXTURE_ROOT.iterdir() if (p / "openapi.yaml").is_file()}

    assert on_disk == {"clean", *PLANTED}


def test_the_whole_planted_root_fails_with_the_counts_it_inspected(planted_report: Any) -> None:
    assert planted_report.exit_code == 1
    assert planted_report.counts == {"modules": 11, "path_files": 12, "index_files": 5}
    assert planted_report.counts_line() == "counts: modules=11 path_files=12 index_files=5"


def test_bad_ref_forms_are_named_url_absolute_and_tilde(planted_report: Any) -> None:
    details = " ".join(f.detail for f in _by_module(planted_report)["v_bad_ref_form"])

    assert "URL_REF" in details and "ABSOLUTE_REF" in details and "TILDE_POINTER" in details


# -- the clean control passes ---------------------------------------------------


def test_clean_control_and_shared_pass_on_their_own(layout: Any, tmp_path: Path) -> None:
    root = _copy_modules(tmp_path, "clean", "_shared")

    report = layout.check(root)

    assert report.findings == [] and report.blocked == []
    assert report.exit_code == 0
    assert report.counts == {"modules": 1, "path_files": 2, "index_files": 2}


def test_script_prints_codes_and_a_final_counts_line(tmp_path: Path) -> None:
    failing = _run_script(FIXTURE_ROOT)
    clean = _run_script(_copy_modules(tmp_path, "clean", "_shared"))

    assert failing.returncode == 1
    lines = failing.stdout.splitlines()
    assert lines[-1] == "counts: modules=11 path_files=12 index_files=5"
    assert all(line.startswith("CONTRACT-CHECK layout_check: ") for line in lines[:-1])
    assert any(": PATH_FILE_NAME: " in line for line in lines)
    assert clean.returncode == 0
    assert clean.stdout.splitlines()[-1] == "counts: modules=1 path_files=2 index_files=2"


# -- cannot-do-its-job: exit 2, never a vacuous pass (FR-025) -------------------


@pytest.mark.parametrize(
    ("case", "code"),
    [("no_module", "NO_MODULE"), ("zero_path_files", "ZERO_PATH_FILES"), ("zero_index", "ZERO_INDEX")],
)
def test_a_check_that_cannot_do_its_job_exits_two_with_its_code(layout: Any, case: str, code: str) -> None:
    root = FIXTURE_ROOT / "exit2" / case

    report = layout.check(root)
    completed = _run_script(root)

    assert [f.code for f in report.blocked] == [code]
    assert report.exit_code == 2
    assert completed.returncode == 2
    assert f": {code}: " in completed.stdout
    assert completed.stdout.splitlines()[-1].startswith("counts: ")


def test_an_empty_directory_is_no_module_not_a_pass(layout: Any, tmp_path: Path) -> None:
    report = layout.check(tmp_path)

    assert [f.code for f in report.blocked] == ["NO_MODULE"] and report.exit_code == 2


def test_a_missing_root_is_no_module(layout: Any, tmp_path: Path) -> None:
    assert layout.check(tmp_path / "absent").exit_code == 2


def test_tool_directories_are_never_modules(layout: Any, tmp_path: Path) -> None:
    for name in ("_shared", "fixtures", "gradle", "tools"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "openapi.yaml").write_text("openapi: 3.1.0\npaths: {}\n", encoding="utf-8")

    assert [f.code for f in layout.check(tmp_path).blocked] == ["NO_MODULE"]


# -- rules that need a variant of the fixtures ---------------------------------


def test_brace_spelling_rule_follows_the_resolver_constant(layout: Any, resolver: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The canonical spelling is whatever the constant says; the committed control is checked against the live value."""
    root = _copy_modules(tmp_path, "clean", "_shared")
    assert layout.check(root).findings == []

    monkeypatch.setattr(resolver, "BRACE_REF_SPELLING", ("<<", ">>"))
    findings = layout.check(root).findings

    assert [f.code for f in findings] == ["BRACE_REF_SPELLING"]
    assert findings[0].path.startswith("clean/")


def test_canonical_spelling_derived_from_the_constant_passes(layout: Any, resolver: ModuleType, tmp_path: Path) -> None:
    root = _copy_modules(tmp_path, "clean", "_shared")
    openapi = root / "clean" / "openapi.yaml"
    name = "paths/items_" + OPEN_BRACE + "itemId" + CLOSE_BRACE + ".yaml"
    openapi_text = openapi.read_text(encoding="utf-8")
    assert resolver.encode_brace_ref(name) in openapi_text, "the committed control uses the live canonical spelling"

    assert layout.check(root).findings == []


def test_shared_piece_depending_on_a_module_piece_is_misuse(layout: Any, tmp_path: Path) -> None:
    root = _copy_modules(tmp_path, "clean", "_shared")
    (root / "_shared" / "schemas" / "Problem.yaml").write_text(
        "title: Problem\ntype: object\nproperties:\n  detail:\n    $ref: ../../clean/schemas/Pong.yaml\n", encoding="utf-8"
    )

    findings = layout.check(root).findings

    assert [f.code for f in findings] == ["SHARED_MISUSE"]
    assert findings[0].path == "_shared/schemas/Problem.yaml"


def test_root_document_carrying_components_is_a_bundle(layout: Any, tmp_path: Path) -> None:
    root = _copy_modules(tmp_path, "clean", "_shared")
    with (root / "clean" / "openapi.yaml").open("a", encoding="utf-8") as handle:
        handle.write("components:\n  schemas:\n    Pong:\n      type: object\n")

    assert [f.code for f in layout.check(root).findings] == ["TRACKED_BUNDLE"]


def test_a_build_output_directory_is_not_scanned_for_bundles(layout: Any, tmp_path: Path) -> None:
    root = _copy_modules(tmp_path, "clean", "_shared")
    build = root / "clean" / "build"
    build.mkdir()
    (build / "openapi.yaml").write_text("openapi: 3.1.0\ninfo:\n  title: t\n  version: 1.0.0\npaths: {}\ncomponents:\n  schemas: {}\n", encoding="utf-8")

    assert layout.check(root).findings == []


def test_malformed_index_is_reported_not_skipped(layout: Any, tmp_path: Path) -> None:
    root = _copy_modules(tmp_path, "clean", "_shared")
    (root / "clean" / "schemas" / "_index.yaml").write_text("- Pong.yaml\n", encoding="utf-8")

    assert [f.code for f in layout.check(root).findings] == ["INDEX_MALFORMED"]


def test_path_item_names_follow_the_slash_to_underscore_rule(layout: Any) -> None:
    assert layout.derived_path_file_name("/ping") == "ping.yaml"
    assert layout.derived_path_file_name("/missions/" + OPEN_BRACE + "missionId" + CLOSE_BRACE) == "missions_" + OPEN_BRACE + "missionId" + CLOSE_BRACE + ".yaml"
    assert layout.derived_path_file_name("/a/b-c") == "a_b-c.yaml"
    assert layout.derived_path_file_name("/") is None
    assert layout.derived_path_file_name("ping") is None


def test_layout_check_never_imports_test_machinery() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}

    assert not imported & {"pytest", "tests", "scripts"}


def test_findings_name_paths_relative_to_the_root_never_absolute(tmp_path: Path) -> None:
    """Regression: a relative --root once printed the absolute host path of a mapped file."""
    shutil.copytree(FIXTURE_ROOT, tmp_path / "layout_check")

    completed = subprocess.run([sys.executable, str(SCRIPT), "--root", "layout_check"], capture_output=True, text=True, timeout=120, check=False, cwd=tmp_path)

    assert completed.returncode == 1
    assert str(tmp_path) not in completed.stdout
    assert "PATH_FILE_NAME: v_path_file_name/paths/pingy.yaml:" in completed.stdout
