"""The shape of the split ``consolidation/reconciliation*.py`` family (Mission consolidation-window-provenance-01M6Y84D, WP15).

NFR-003 as durable gates: the facade defines nothing, every module is within the size limit, no split module
imports the facade (the split is acyclic), every split module imports alone in a fresh interpreter, no body
exists twice, every seeded-mutation row targets a symbol that has exactly one home, and every family import
points down the rank table (:data:`_RANKS`, the facade docstring's order).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.consolidation import reconciliation
from tests.consolidation.test_reconciliation_seeded_mutations import MUTATIONS

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONSOLIDATION = _REPO_ROOT / "src" / "specify_cli" / "consolidation"
_FACADE = _CONSOLIDATION / "reconciliation.py"
_MODULES = sorted(_CONSOLIDATION.glob("reconciliation*.py"))
_SPLIT_MODULES = [path for path in _MODULES if path != _FACADE]
_FACADE_MODULE = "specify_cli.consolidation.reconciliation"
_ORIGINAL_LINE_COUNT = 4096
_MAX_MODULE_LINES = 1200
_FACADE_ALL = (
    "ApprovedWpCommitSet",
    "MergeOutcomeVerifier",
    "TERMINUS_ENTRY_POINTS",
    "UnroutedTerminusPathError",
    "VerifyResult",
    "build_approved_wp_set",
    "claim_integrity_refusal",
    "detect_legacy_in_flight_state",
    "route_terminus",
    "write_post_fix_marker",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _top_level_definitions(path: Path) -> list[str]:
    return [node.name for node in _tree(path).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]


def _imports_the_facade(path: Path) -> list[str]:
    """Every import in *path*, function-local ones included, that reaches the facade."""
    hits: list[str] = []
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module == _FACADE_MODULE:
            hits.append(f"line {node.lineno}: from {node.module} import ...")
        elif node.module == "specify_cli.consolidation" and any(alias.name == "reconciliation" for alias in node.names):
            hits.append(f"line {node.lineno}: from specify_cli.consolidation import reconciliation")
    return hits


def test_facade_defines_nothing() -> None:
    allowed_other = []
    for index, node in enumerate(_tree(_FACADE).body):
        if isinstance(node, ast.Expr) and index == 0:
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Assign) and [getattr(target, "id", None) for target in node.targets] == ["__all__"]:
            continue
        allowed_other.append(f"{type(node).__name__} at line {node.lineno}")
    assert not allowed_other, f"the facade may hold only its docstring, imports and __all__: {allowed_other}"


def test_facade_all_is_the_original_ten_names() -> None:
    assert sorted(reconciliation.__all__) == sorted(_FACADE_ALL)


@pytest.mark.parametrize("path", _MODULES, ids=lambda path: path.name)
def test_every_reconciliation_module_is_at_most_1200_lines(path: Path) -> None:
    length = _line_count(path)
    assert length <= _MAX_MODULE_LINES, f"{path.name} is {length} lines (limit {_MAX_MODULE_LINES})"


def test_largest_reconciliation_module_is_at_most_30_percent_of_the_original() -> None:
    longest = max(_MODULES, key=_line_count)
    limit = int(0.30 * _ORIGINAL_LINE_COUNT)
    assert _line_count(longest) <= limit, f"{longest.name} is {_line_count(longest)} lines (limit {limit})"


def test_split_modules_never_import_the_facade() -> None:
    offenders = {path.name: hits for path in _SPLIT_MODULES if (hits := _imports_the_facade(path))}
    assert not offenders, f"a split module imports the facade (a cycle waiting to happen): {offenders}"


def test_facade_import_scan_catches_a_facade_import(tmp_path: Path) -> None:
    """Control: the scan the gate above relies on can fail, function-local imports included."""
    sample = tmp_path / "sample.py"
    sample.write_text(
        "def f():\n    from specify_cli.consolidation.reconciliation import x\n    return x\nfrom specify_cli.consolidation import reconciliation\n",
        encoding="utf-8",
    )
    assert len(_imports_the_facade(sample)) == 2


#: Import-direction ranks of the split family (pre-PR fold L7): a module may import, at module level or
#: function-locally, only family modules of a strictly LOWER rank. The facade docstring lists them in this order.
_RANKS: dict[str, int] = {
    "reconciliation_kernel": 0,
    "reconciliation_claim_types": 0,
    "reconciliation_rendering": 1,
    "reconciliation_canceled": 2,
    "reconciliation_authorship": 3,
    "reconciliation_bound": 3,
    "reconciliation_closed_world": 4,
    "reconciliation_verifier": 4,
    "reconciliation_claim": 5,
}


def _family_imports(path: Path) -> set[str]:
    """Every split-family module *path* imports, module-level and function-local (absolute or relative)."""
    found: set[str] = set()
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        leaf = node.module.rsplit(".", 1)[-1]
        in_package = node.level == 1 or node.module.startswith("specify_cli.consolidation.")
        if in_package and leaf in _RANKS:
            found.add(leaf)
    return found


def _rank_violations(paths: list[Path]) -> dict[str, list[str]]:
    return {
        path.stem: sorted(target for target in _family_imports(path) if _RANKS[target] >= _RANKS[path.stem])
        for path in paths
        if any(_RANKS[target] >= _RANKS[path.stem] for target in _family_imports(path))
    }


def test_rank_table_names_every_split_module() -> None:
    assert sorted(path.stem for path in _SPLIT_MODULES) == sorted(_RANKS)


def test_family_imports_point_down_the_rank_table() -> None:
    offenders = _rank_violations(_SPLIT_MODULES)
    assert not offenders, f"a split module imports a module of its own or a higher rank: {offenders}"


def test_facade_docstring_lists_the_modules_in_rank_order() -> None:
    doc = ast.get_docstring(_tree(_FACADE)) or ""
    listed = [line.split("``")[1] for line in doc.splitlines() if line.startswith("* ``reconciliation_")]
    assert sorted(listed) == sorted(_RANKS)
    ranks = [_RANKS[name] for name in listed]
    assert ranks == sorted(ranks), f"the facade docstring must list the modules in import order: {listed}"


def test_rank_scan_catches_an_upward_import(tmp_path: Path) -> None:
    """Control: a function-local relative import of a higher-rank module is a violation."""
    sample = tmp_path / "reconciliation_kernel.py"
    sample.write_text("def f():\n    from .reconciliation_claim import x\n    return x\n", encoding="utf-8")
    assert _rank_violations([sample]) == {"reconciliation_kernel": ["reconciliation_claim"]}


def test_no_top_level_name_is_defined_in_two_split_modules() -> None:
    owners: dict[str, list[str]] = {}
    for path in _SPLIT_MODULES:
        for name in _top_level_definitions(path):
            owners.setdefault(name, []).append(path.name)
    duplicates = {name: homes for name, homes in owners.items() if len(homes) > 1}
    assert not duplicates, f"a body exists in two split modules: {duplicates}"


@pytest.mark.parametrize("path", _SPLIT_MODULES, ids=lambda path: path.name)
def test_every_split_module_imports_alone_in_a_fresh_interpreter(path: Path) -> None:
    subprocess.run(
        [sys.executable, "-I", "-c", f"import specify_cli.consolidation.{path.stem}"],
        check=True,
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )


def test_every_mutation_target_is_defined_in_exactly_one_split_module() -> None:
    homes: dict[str, list[str]] = {}
    for path in _SPLIT_MODULES:
        for name in _top_level_definitions(path):
            homes.setdefault(name, []).append(path.stem)
    bad = {}
    for row in MUTATIONS:
        symbol = row.target.split(".")[0]
        if len(homes.get(symbol, [])) != 1:
            bad[row.target] = homes.get(symbol, [])
    assert not bad, f"a seeded-mutation target is not defined in exactly one split module: {bad}"
