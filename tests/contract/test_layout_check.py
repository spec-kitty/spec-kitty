"""Planted-violation tests for ``contracts/tools/layout_check.py`` (FR-001, FR-021, FR-025).

One committed fixture root, ``contracts/tools/fixtures/layout_check/``, holds a
clean control module (``clean``, whose path item ``/items/{itemId}`` lives in the
brace-free file ``items_itemId.yaml``), the clean ``_shared`` pieces, and one module
per planted violation. Every rule is asserted on its own module and the control
stays clean in the same run. Path-file names in test code come from the resolver's
``path_file_name`` or ``chr`` calls, never from brace literals (Rule BRACE-1).
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
import yaml

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
    "v_brace_in_ref": ["BAD_REF_FORM"],
    "v_path_file_collision": ["PATH_FILE_COLLISION"],
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


def test_the_committed_control_names_its_brace_path_item_by_the_resolver_mapping(layout: Any, resolver: ModuleType, tmp_path: Path) -> None:
    root = _copy_modules(tmp_path, "clean", "_shared")
    key = "/items/" + OPEN_BRACE + "itemId" + CLOSE_BRACE
    assert (root / "clean" / "paths" / resolver.path_file_name(key)).is_file()
    assert layout.check(root).findings == []


def test_a_brace_named_path_file_is_refused_even_when_the_ref_is_plain(layout: Any, tmp_path: Path) -> None:
    root = _copy_modules(tmp_path, "clean", "_shared")
    braced = "items_" + OPEN_BRACE + "itemId" + CLOSE_BRACE + ".yaml"
    (root / "clean" / "paths" / "items_itemId.yaml").rename(root / "clean" / "paths" / braced)
    (root / "clean" / "openapi.yaml").write_text(
        (root / "clean" / "openapi.yaml").read_text(encoding="utf-8").replace("items_itemId.yaml", braced), encoding="utf-8"
    )

    codes = sorted({f.code for f in layout.check(root).findings})

    assert codes == ["BAD_REF_FORM", "PATH_FILE_NAME"]


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


def test_the_layout_check_keeps_no_second_copy_of_the_name_rule(layout: Any) -> None:
    assert not hasattr(layout, "derived_path_file_name")


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


# -- the real shared pieces (FR-002) pass the layout check ---------------------

SHARED_DIR = Path(__file__).resolve().parents[2] / "contracts" / "_shared"


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _all_properties(node: Any) -> list[tuple[str, Any]]:
    """Every (name, schema) pair under any ``properties`` mapping of a loaded document."""
    found: list[tuple[str, Any]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                found.extend(value.items())
            found.extend(_all_properties(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_all_properties(item))
    return found


def test_real_shared_pieces_pass_the_layout_check_beside_a_one_file_module(layout: Any, tmp_path: Path) -> None:
    shutil.copytree(SHARED_DIR, tmp_path / "_shared")
    _copy_modules(tmp_path, "clean")

    report = layout.check(tmp_path)

    assert report.findings == [] and report.blocked == []
    assert report.counts == {"modules": 1, "path_files": 2, "index_files": 4}


@pytest.mark.parametrize(
    ("directory", "listed"),
    [
        ("schemas", {"PageCursor.yaml", "PageInfo.yaml", "Problem.yaml"}),
        ("parameters", {"PageCursor.yaml", "PageSize.yaml"}),
        ("responses", {"Problem.yaml"}),
    ],
)
def test_shared_indexes_list_exactly_the_pieces_present(directory: str, listed: set[str]) -> None:
    index = _load_yaml(SHARED_DIR / directory / "_index.yaml")

    assert set(index["files"]) == listed
    assert {p.name for p in (SHARED_DIR / directory).iterdir() if p.name != "_index.yaml"} == listed


def test_shared_problem_response_uses_the_problem_media_type() -> None:
    response = _load_yaml(SHARED_DIR / "responses" / "Problem.yaml")

    assert list(response["content"]) == ["application/problem+json"]
    assert response["content"]["application/problem+json"]["schema"] == {"$ref": "../schemas/Problem.yaml"}


def test_every_shared_property_is_described_and_no_field_is_the_bare_word_cursor() -> None:
    properties: list[tuple[str, Any]] = []
    for schema_file in (SHARED_DIR / "schemas").glob("*.yaml"):
        if schema_file.name != "_index.yaml":
            properties.extend(_all_properties(_load_yaml(schema_file)))

    assert len(properties) >= 6, "the floor: the shared schemas define their properties"
    assert [name for name, schema in properties if not (isinstance(schema, dict) and schema.get("description"))] == []
    assert "cursor" not in {name.lower() for name, _ in properties}


def test_page_cursor_is_an_opaque_string_with_no_link_to_the_stream_cursor() -> None:
    cursor = _load_yaml(SHARED_DIR / "schemas" / "PageCursor.yaml")

    assert cursor["type"] == "string" and "properties" not in cursor
    assert "opaque" in cursor["description"].lower()
    page_info_fields = {name for name, _ in _all_properties(_load_yaml(SHARED_DIR / "schemas" / "PageInfo.yaml"))}
    assert not {"offset", "invariant"} & page_info_fields


@pytest.mark.parametrize("schema_name", ["Problem", "PageInfo"])
def test_shared_object_schemas_are_closed(schema_name: str) -> None:
    assert _load_yaml(SHARED_DIR / "schemas" / f"{schema_name}.yaml")["additionalProperties"] is False
