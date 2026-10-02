"""Planted-violation tests for ``contracts/tools/resolver_parity.py`` (FR-019, plan D-P2; E-1 ruling of 2026-10-02).

The released bundle is written by the Python resolver, so parity no longer compares trees (the Java
generator's re-emission drops 3.1 constructs, which is exactly why it is not the artefact). It proves
that the Java parser ACCEPTS the bundle and sees the same *inventory*: path keys, operations
(method plus operationId), parameters (name and location), response codes with media types, and
schema names. The Java parser's view is the ``javaview`` re-emission; no JVM runs here, so the views
are committed fixtures under ``contracts/tools/fixtures/resolver_parity/java_views/``: a clean one with
the generator's typical synthesised keys, and planted copies that drop an operation, rename a schema,
drop a response code, and so on. The independent dereference check is exercised on three modules.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

TOOLS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "tools"
FIXTURES = TOOLS_DIR / "fixtures" / "resolver_parity"
VIEWS = FIXTURES / "java_views"
SCRIPT = TOOLS_DIR / "resolver_parity.py"


@pytest.fixture(scope="module")
def parity() -> Iterator[ModuleType]:
    # The tools directory stays on sys.path for the module's lifetime: the script imports its sibling
    # modules by name, including lazily (the resolver), exactly as it does when run as a bare script.
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("resolver_parity_under_test", SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path.remove(str(TOOLS_DIR))


def _stage(tmp_path: Path, root: str, view: str | None, *, write_bundle: bool = True) -> Path:
    """Stage ``<dir>/bundle/alpha/openapi.yaml`` (as bundle.py writes it) and ``<dir>/javaview/alpha/openapi.yaml``."""
    staged = tmp_path / "staged"
    staged.mkdir()
    if write_bundle:
        sys.modules["bundle"].write_bundle(FIXTURES / root / "alpha", staged)
    if view is not None:
        target = staged / "javaview" / "alpha" / "openapi.yaml"
        target.parent.mkdir(parents=True)
        shutil.copy(VIEWS / f"{view}.yaml", target)
    return staged


@pytest.fixture(autouse=True)
def _bundle_module(parity: ModuleType) -> None:
    assert "bundle" in sys.modules, "resolver_parity imports bundle by name"


def _run(parity: ModuleType, root: str, staged: Path, *extra: str, **keywords: Any) -> tuple[int, str]:
    lines: list[str] = []
    code = parity.run(["--root", str(FIXTURES / root), "--bundles", str(staged), *extra], out=lines.append, **keywords)
    return code, "\n".join(lines)


def _counts(output: str) -> dict[str, int]:
    last = output.splitlines()[-1]
    assert last.startswith("counts: "), last
    return {key: int(value) for key, value in (pair.split("=") for pair in last.removeprefix("counts: ").split())}


def _codes(output: str) -> list[str]:
    return sorted({line.split(": ")[1] for line in output.splitlines() if line.startswith("CONTRACT-CHECK")})


# -- the inventory comparison -------------------------------------------------------------------------


def test_clean_view_has_the_same_inventory_and_prints_every_count(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, "clean", "ok"))

    assert code == 0, output
    assert _counts(output) == {
        "path_items": 5,
        "schemas": 1,
        "refs_resolved": 10,
        "operations": 5,
        "parameters": 1,
        "responses": 5,
        "schema_names": 1,
        "examples_cross_checked": 2,
    }


def test_the_comparison_tolerates_what_the_java_emitter_adds_and_rewrites(parity: ModuleType, tmp_path: Path) -> None:
    view = yaml.safe_load((VIEWS / "ok.yaml").read_text(encoding="utf-8"))
    thing = view["components"]["schemas"]["Thing"]

    assert "example" in thing and thing["additionalProperties"] == {}, "the clean view carries synthesised keys the bundle never had"
    assert _run(parity, "clean", _stage(tmp_path, "clean", "ok"))[0] == 0


@pytest.mark.parametrize(
    ("view", "expected"),
    [
        ("missing_operation", ["OPERATIONS_DIFFER", "RESPONSES_DIFFER"]),
        ("renamed_schema", ["SCHEMA_NAMES_DIFFER"]),
        ("dropped_response_code", ["RESPONSES_DIFFER"]),
        ("renamed_parameter", ["PARAMETERS_DIFFER"]),
        ("missing_path", ["OPERATIONS_DIFFER", "PATHS_DIFFER", "RESPONSES_DIFFER"]),
        ("changed_media_type", ["RESPONSES_DIFFER"]),
    ],
)
def test_each_planted_difference_fails_with_its_stable_code(parity: ModuleType, tmp_path: Path, view: str, expected: list[str]) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, "clean", view))

    assert code == 1, output
    assert _codes(output) == expected


def test_a_difference_names_the_item_and_the_side_it_is_missing_from(parity: ModuleType, tmp_path: Path) -> None:
    _, output = _run(parity, "clean", _stage(tmp_path, "clean", "dropped_response_code"))

    assert "CONTRACT-CHECK resolver_parity: RESPONSES_DIFFER: alpha: only in the bundle: /p2 GET 200 application/json" in output
    assert "only in the Java view: /p2 GET 201 application/json" in output


def test_the_inventory_follows_internal_references_in_the_java_view(parity: ModuleType) -> None:
    view = yaml.safe_load((VIEWS / "ok.yaml").read_text(encoding="utf-8"))

    inventory = parity.inventory(view)

    assert inventory.schema_names == {"Thing"}
    assert ("/p2", "GET", "200", "application/json") in inventory.responses
    assert ("/p1", "GET", "limit", "query") in inventory.parameters


def test_the_stale_bundle_is_refused(parity: ModuleType, tmp_path: Path) -> None:
    staged = _stage(tmp_path, "clean", "ok")
    bundle = staged / "bundle" / "alpha" / "openapi.yaml"
    bundle.write_text(bundle.read_text(encoding="utf-8").replace("op0", "opZero"), encoding="utf-8")

    code, output = _run(parity, "clean", staged)

    assert code == 1 and "BUNDLE_STALE: alpha" in output


# -- cannot do the job ---------------------------------------------------------------------------------


@pytest.mark.parametrize("view", ["empty", None])
def test_an_empty_or_absent_java_view_cannot_do_its_job(parity: ModuleType, tmp_path: Path, view: str | None) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, "clean", view))

    assert code == 2
    assert "BUNDLE_MISSING_OR_EMPTY: alpha" in output and "javaview" in output


def test_an_absent_python_bundle_cannot_do_its_job(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, "clean", "ok", write_bundle=False))

    assert code == 2
    assert "BUNDLE_MISSING_OR_EMPTY: alpha" in output and "bundle/alpha" in output


def test_a_bundle_below_the_floor_cannot_do_its_job(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, "clean", "ok"), "--min-paths", "6")

    assert code == 2
    assert "BELOW_FLOOR" in output and "5 path items" in output


def test_an_unimportable_resolver_cannot_do_its_job(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, "clean", "ok"), resolver_module="no_such_resolver_module")

    assert code == 2
    assert "RESOLVER_IMPORT_FAILED" in output


def test_the_tree_equality_machinery_is_gone(parity: ModuleType) -> None:
    for name in ("NORMALISATIONS", "Normalisation", "MAX_NORMALISATIONS", "first_difference", "all_differences", "deref_bundle_tree"):
        assert not hasattr(parity, name), name


# -- the independent dereference check ------------------------------------------------------------------


def _verdicts(parity: ModuleType, root: str) -> list[tuple[str, int, bool, bool]]:
    result = parity.cross_check_examples(FIXTURES / root, FIXTURES / root / "alpha")
    return [(v.schema, v.index, v.resolver_valid, v.library_valid) for v in result]


def test_clean_examples_are_valid_under_both_readings(parity: ModuleType) -> None:
    assert _verdicts(parity, "clean") == [("schemas/Thing.yaml", 0, True, True), ("schemas/Thing.yaml", 1, True, True)]


def test_planted_invalid_examples_are_rejected_by_both_readings_including_the_timestamp_format(parity: ModuleType) -> None:
    assert _verdicts(parity, "invalid_example") == [
        ("schemas/Thing.yaml", 0, True, True),
        ("schemas/Thing.yaml", 1, False, False),
        ("schemas/Thing.yaml", 2, False, False),
    ]


def test_agreeing_invalid_examples_are_not_a_parity_failure(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "invalid_example", _stage(tmp_path, "invalid_example", None), "--examples-only")

    assert code == 0, output
    assert _counts(output)["examples_cross_checked"] == 3


def test_a_resolver_defect_the_inventory_cannot_see_is_found_by_the_library_reading(parity: ModuleType) -> None:
    assert _verdicts(parity, "shared_defect") == [("schemas/Child.yaml", 0, True, False)]


def test_the_examples_only_run_fails_with_the_disagreement_named(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "shared_defect", _stage(tmp_path, "shared_defect", None, write_bundle=False), "--examples-only")

    assert code == 1
    assert "CONTRACT-CHECK resolver_parity: INDEPENDENT_DEREF_DISAGREES: alpha: schemas/Child.yaml example 0" in output
    assert _counts(output)["examples_cross_checked"] == 1


def test_the_library_reading_uses_no_resolver_code() -> None:
    source = (TOOLS_DIR / "resolver_parity.py").read_text(encoding="utf-8")
    start = source.index("# -- the library reading")
    end = source.index("# -- the resolver reading")

    assert "contract_resolver" not in source[start:end] and "resolver." not in source[start:end]


def test_script_exits_2_with_a_counts_line_when_the_root_has_no_module(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--bundles", str(tmp_path)], capture_output=True, text=True, timeout=60, check=False
    )

    assert result.returncode == 2
    assert result.stdout.splitlines()[-1].startswith("counts: path_items=0 ")
