"""Planted-violation tests for ``contracts/tools/resolver_parity.py`` (FR-019, plan D-P2).

Parity compares the Java generator's bundle with the Python resolver's tree. No
JVM runs here, so the bundles are committed fixtures under
``contracts/tools/fixtures/resolver_parity/bundles/``: a clean one that equals the
resolver's tree and planted copies that drop one ``$ref`` target or alter one
schema. The independent dereference check is exercised on three modules: a clean
one, one with planted invalid examples both readings reject (no disagreement), and
one where the resolver's sibling-keyword reading and the library's differ.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

TOOLS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "tools"
FIXTURES = TOOLS_DIR / "fixtures" / "resolver_parity"
BUNDLES = FIXTURES / "bundles"
SCRIPT = TOOLS_DIR / "resolver_parity.py"
THING_SCHEMA = "/paths/~1p0/get/responses/200/content/application~1json/schema"


@pytest.fixture(scope="module")
def parity() -> ModuleType:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("resolver_parity_under_test", SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(TOOLS_DIR))
    return module


def _stage(tmp_path: Path, bundle: str | None) -> Path:
    """A bundle directory laid out as bundle.py stages it: ``<dir>/bundle/alpha/openapi.yaml``."""
    staged = tmp_path / "staged"
    if bundle is not None:
        target = staged / "bundle" / "alpha" / "openapi.yaml"
        target.parent.mkdir(parents=True)
        shutil.copy(BUNDLES / f"{bundle}.yaml", target)
    else:
        staged.mkdir()
    return staged


def _run(parity: ModuleType, root: str, staged: Path, *extra: str, **keywords: Any) -> tuple[int, str]:
    lines: list[str] = []
    code = parity.run(["--root", str(FIXTURES / root), "--bundles", str(staged), *extra], out=lines.append, **keywords)
    return code, "\n".join(lines)


def _counts(output: str) -> dict[str, int]:
    last = output.splitlines()[-1]
    assert last.startswith("counts: "), last
    return {key: int(value) for key, value in (pair.split("=") for pair in last.removeprefix("counts: ").split())}


# -- the tree comparison -------------------------------------------------------


def test_clean_bundle_equals_the_resolver_tree_and_prints_every_count(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, "ok"))

    assert code == 0, output
    assert _counts(output) == {"path_items": 5, "schemas": 1, "refs_resolved": 10, "normalisations": 0, "examples_cross_checked": 2}


def test_a_dropped_ref_target_names_the_first_differing_pointer(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, "drops_ref"))

    assert code == 1
    assert f"CONTRACT-CHECK resolver_parity: TREE_DIFFERS: alpha: {THING_SCHEMA}" in output
    assert "/p2/" not in output.split("TREE_DIFFERS")[1].split("/p2")[0], "the first difference is reported, not a later one"


def test_an_altered_schema_names_the_pointer_of_the_altered_mapping(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, "alters_schema"))

    assert code == 1
    assert f"TREE_DIFFERS: alpha: {THING_SCHEMA}/properties" in output


def test_report_all_lists_every_differing_pointer_for_the_spike(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, "alters_schema"), "--report-all")

    assert code == 1
    assert output.count("TREE_DIFFERS") == 5, "the same alteration is reached through all five path items"


def test_key_order_never_matters(parity: ModuleType) -> None:
    assert parity.first_difference({"a": 1, "b": {"c": 2, "d": 3}}, {"b": {"d": 3, "c": 2}, "a": 1}) is None
    assert parity.first_difference({"a": [1, 2]}, {"a": [2, 1]}) == "/a/0"
    assert parity.first_difference({"a/b": {"x": 1}}, {"a/b": {"x": 2}}) == "/a~1b/x"


def test_a_bundle_below_the_floor_cannot_do_its_job(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, "four_paths"))

    assert code == 2
    assert "BELOW_FLOOR" in output and "4 path items" in output


@pytest.mark.parametrize("bundle", ["empty", None])
def test_an_empty_or_absent_bundle_cannot_do_its_job(parity: ModuleType, tmp_path: Path, bundle: str | None) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, bundle))

    assert code == 2
    assert "BUNDLE_MISSING_OR_EMPTY" in output


def test_an_unimportable_resolver_cannot_do_its_job(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, "ok"), resolver_module="no_such_resolver_module")

    assert code == 2
    assert "RESOLVER_IMPORT_FAILED" in output


# -- named normalisations ---------------------------------------------------------


def _without_examples(tmp_path: Path) -> Path:
    staged = _stage(tmp_path, "ok")
    target = staged / "bundle" / "alpha" / "openapi.yaml"
    document = yaml.safe_load(target.read_text(encoding="utf-8"))
    del document["components"]["schemas"]["Thing"]["examples"]
    target.write_text(yaml.safe_dump(document), encoding="utf-8")
    return staged


def _strip_examples(parity: ModuleType, **overrides: str) -> Any:
    def strip(node: Any) -> Any:
        if isinstance(node, dict):
            return {key: strip(value) for key, value in node.items() if key != "examples"}
        if isinstance(node, list):
            return [strip(item) for item in node]
        return node

    fields = {
        "name": "strip-examples",
        "construct": "schema `examples` keyword",
        "behaviour": "the generator does not carry schema examples into the bundle",
        "planted_test": "test_a_named_normalisation_closes_a_known_generator_rewrite",
    }
    fields.update(overrides)
    return parity.Normalisation(apply=strip, **fields)


def test_a_generator_rewrite_is_a_difference_until_it_is_named(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "clean", _without_examples(tmp_path))

    assert code == 1
    assert "TREE_DIFFERS" in output


def test_a_named_normalisation_closes_a_known_generator_rewrite(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "clean", _without_examples(tmp_path), normalisations=(_strip_examples(parity),))

    assert code == 0, output
    assert _counts(output)["normalisations"] == 1


def test_a_normalisation_without_its_documentation_is_refused(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "clean", _stage(tmp_path, "ok"), normalisations=(_strip_examples(parity, behaviour=""),))

    assert code == 1
    assert "UNDOCUMENTED_NORMALISATION: strip-examples" in output


def test_more_than_eight_normalisations_are_refused(parity: ModuleType, tmp_path: Path) -> None:
    assert parity.MAX_NORMALISATIONS == 8
    nine = tuple(_strip_examples(parity, name=f"strip-{index}") for index in range(9))

    code, output = _run(parity, "clean", _stage(tmp_path, "ok"), normalisations=nine)

    assert code == 1
    assert "NORMALISATION_CAP_EXCEEDED" in output and "9" in output


def test_no_normalisation_ships_until_the_spike_observes_one(parity: ModuleType) -> None:
    assert parity.NORMALISATIONS == ()


# -- the independent dereference check ------------------------------------------------


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
    code, output = _run(parity, "invalid_example", _stage(tmp_path, "ok"))

    assert code == 0, output
    assert _counts(output)["examples_cross_checked"] == 3


def test_a_resolver_defect_the_tree_comparison_cannot_see_is_found_by_the_library_reading(parity: ModuleType) -> None:
    assert _verdicts(parity, "shared_defect") == [("schemas/Child.yaml", 0, True, False)]


def test_the_examples_only_run_fails_with_the_disagreement_named(parity: ModuleType, tmp_path: Path) -> None:
    code, output = _run(parity, "shared_defect", _stage(tmp_path, None), "--examples-only")

    assert code == 1
    assert "CONTRACT-CHECK resolver_parity: INDEPENDENT_DEREF_DISAGREES: alpha: schemas/Child.yaml example 0" in output
    assert _counts(output)["examples_cross_checked"] == 1


def test_the_library_reading_uses_no_resolver_code() -> None:
    source = (TOOLS_DIR / "resolver_parity.py").read_text(encoding="utf-8")
    library_part = source.split("def cross_check_examples", 1)[1].split("\ndef ", 1)[0]

    assert "resolve(" not in library_part.split("def _library_validator", 1)[-1].split("\ndef ", 1)[0]


def test_script_exits_2_with_a_counts_line_when_the_root_has_no_module(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--bundles", str(tmp_path)], capture_output=True, text=True, timeout=60, check=False
    )

    assert result.returncode == 2
    assert result.stdout.splitlines()[-1].startswith("counts: path_items=0 ")
