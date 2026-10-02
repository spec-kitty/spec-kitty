"""Golden-tree and refusal tests for ``contracts/tools/contract_resolver.py``.

The resolver is the single resolution authority (plan D-P1, D-P2): every
contract check, the resolver-parity script and the reality check read the
contract through it. It is a bare script directory (``contracts/`` is not a
package), so it is loaded by file path.

Golden trees under ``contracts/tools/fixtures/contract_resolver/`` are
hand-written expected results, one per supported construct, an oracle that
does not run the resolver. Refusals assert the stable error code, not just
that something raised.

Rule BRACE-1 (single source of the brace ``$ref`` spelling) is enforced
here by an executable scan, and the scan is shown to be able to fail.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "contracts" / "tools"
FIXTURES = TOOLS_DIR / "fixtures" / "contract_resolver"
RESOLVER_PATH = TOOLS_DIR / "contract_resolver.py"
GOLDEN_CASES = ("file_ref", "pointer_ref", "sibling_keywords", "composition")

# Directories scanned by the single-source rule: contract tooling and the whole test tree.
SCAN_ROOTS = (TOOLS_DIR, REPO_ROOT / "tests")


def _load_resolver() -> ModuleType:
    spec = importlib.util.spec_from_file_location("contract_resolver_under_test", RESOLVER_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {RESOLVER_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def resolver() -> ModuleType:
    return _load_resolver()


def _write(root: Path, relative: str, text: str) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def _module_with_path_file(root: Path, path_file_text: str, *, extra: dict[str, str] | None = None) -> Path:
    """A one-path module whose single path file holds ``path_file_text``."""
    _write(
        root,
        "openapi.yaml",
        "openapi: 3.1.0\ninfo:\n  title: t\n  version: 1.0.0\npaths:\n  /x:\n    $ref: paths/x.yaml\n",
    )
    _write(root, "paths/x.yaml", path_file_text)
    for relative, text in (extra or {}).items():
        _write(root, relative, text)
    return root


# ---------------------------------------------------------------------------
# Golden trees: one case per supported construct
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", GOLDEN_CASES)
def test_golden_tree_matches_the_hand_written_expectation(resolver: ModuleType, case: str) -> None:
    expected = json.loads((FIXTURES / case / "expected.json").read_text(encoding="utf-8"))

    result = resolver.resolve(FIXTURES / case)

    assert result.tree == expected["tree"]
    assert result.counts == expected["counts"]


def test_golden_cases_are_all_present_on_disk() -> None:
    """Floor: a parametrised test over an empty or shrunken case list must not pass silently."""
    present = sorted(p.name for p in FIXTURES.iterdir() if (p / "expected.json").is_file())
    assert present == sorted(GOLDEN_CASES)


def test_sibling_keywords_override_the_referenced_schema(resolver: ModuleType) -> None:
    schema = resolver.resolve(FIXTURES / "sibling_keywords").tree["paths"]["/gadgets"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["description"] == "A gadget as listed, narrower than the shared text."
    assert schema["nullable"] is True
    assert schema["type"] == "object", "keywords of the referenced schema are kept"


def test_brace_named_path_file_resolves_through_the_spelling_constant(resolver: ModuleType, tmp_path: Path) -> None:
    """The brace-named file is built from the constant at run time, so no spelling is hard-coded here."""
    open_brace, close_brace = chr(123), chr(125)
    file_name = "items_" + open_brace + "itemId" + close_brace + ".yaml"
    ref = resolver.encode_brace_ref("paths/" + file_name)
    _write(
        tmp_path,
        "openapi.yaml",
        f"openapi: 3.1.0\ninfo:\n  title: t\n  version: 1.0.0\npaths:\n  /items/{open_brace}itemId{close_brace}:\n    $ref: {ref}\n",
    )
    _write(tmp_path, "paths/" + file_name, "get:\n  operationId: getItem\n  responses:\n    '200':\n      description: ok\n")

    result = resolver.resolve(tmp_path)

    assert result.tree["paths"]["/items/" + open_brace + "itemId" + close_brace]["get"]["operationId"] == "getItem"
    assert result.counts["path_items"] == 1


def test_encode_brace_ref_uses_exactly_the_constant(resolver: ModuleType) -> None:
    open_piece, close_piece = resolver.BRACE_REF_SPELLING
    encoded = resolver.encode_brace_ref("a" + chr(123) + "b" + chr(125))

    assert encoded == "a" + open_piece + "b" + close_piece
    assert chr(123) not in encoded and chr(125) not in encoded


# ---------------------------------------------------------------------------
# Refusals: one stable code each
# ---------------------------------------------------------------------------


def _resolve_error(resolver: ModuleType, module_dir: Path) -> Any:
    with pytest.raises(resolver.ResolveError) as raised:
        resolver.resolve(module_dir)
    return raised.value


def test_unresolved_file_ref_is_refused(resolver: ModuleType, tmp_path: Path) -> None:
    module = _module_with_path_file(tmp_path, "get:\n  schema:\n    $ref: ../schemas/Missing.yaml\n")

    error = _resolve_error(resolver, module)

    assert error.code == "UNRESOLVED_REF"
    assert "Missing.yaml" in error.detail


def test_unresolved_pointer_is_refused(resolver: ModuleType, tmp_path: Path) -> None:
    module = _module_with_path_file(
        tmp_path,
        "get:\n  schema:\n    $ref: ../schemas/Thing.yaml#/properties/nope\n",
        extra={"schemas/Thing.yaml": "type: object\nproperties:\n  id:\n    type: string\n"},
    )

    assert _resolve_error(resolver, module).code == "UNRESOLVED_REF"


def test_url_ref_is_refused(resolver: ModuleType, tmp_path: Path) -> None:
    module = _module_with_path_file(tmp_path, "get:\n  schema:\n    $ref: https://example.invalid/schemas/Thing.yaml\n")

    assert _resolve_error(resolver, module).code == "URL_REF"


@pytest.mark.parametrize("ref", ["/schemas/Thing.yaml", "~/schemas/Thing.yaml", "C:/schemas/Thing.yaml"])
def test_absolute_ref_is_refused(resolver: ModuleType, tmp_path: Path, ref: str) -> None:
    module = _module_with_path_file(tmp_path, f"get:\n  schema:\n    $ref: '{ref}'\n")

    assert _resolve_error(resolver, module).code == "ABSOLUTE_REF"


def test_tilde_pointer_is_refused(resolver: ModuleType, tmp_path: Path) -> None:
    module = _module_with_path_file(
        tmp_path,
        "get:\n  schema:\n    $ref: '../schemas/Thing.yaml#/properties/a~1b'\n",
        extra={"schemas/Thing.yaml": "type: object\nproperties:\n  id:\n    type: string\n"},
    )

    assert _resolve_error(resolver, module).code == "TILDE_POINTER"


def test_cycle_is_refused(resolver: ModuleType, tmp_path: Path) -> None:
    module = _module_with_path_file(
        tmp_path,
        "get:\n  schema:\n    $ref: ../schemas/A.yaml\n",
        extra={
            "schemas/A.yaml": "type: object\nproperties:\n  b:\n    $ref: B.yaml\n",
            "schemas/B.yaml": "type: object\nproperties:\n  a:\n    $ref: A.yaml\n",
        },
    )

    assert _resolve_error(resolver, module).code == "CYCLE"


def test_self_reference_is_a_cycle(resolver: ModuleType, tmp_path: Path) -> None:
    module = _module_with_path_file(
        tmp_path,
        "get:\n  schema:\n    $ref: ../schemas/Tree.yaml\n",
        extra={"schemas/Tree.yaml": "type: object\nproperties:\n  child:\n    $ref: '#'\n"},
    )

    assert _resolve_error(resolver, module).code == "CYCLE"


def test_referenced_file_that_is_not_a_mapping_is_refused(resolver: ModuleType, tmp_path: Path) -> None:
    module = _module_with_path_file(
        tmp_path,
        "get:\n  schema:\n    $ref: ../schemas/Listy.yaml\n",
        extra={"schemas/Listy.yaml": "- one\n- two\n"},
    )

    assert _resolve_error(resolver, module).code == "NOT_A_MAPPING"


def test_root_document_that_is_not_a_mapping_is_refused(resolver: ModuleType, tmp_path: Path) -> None:
    _write(tmp_path, "openapi.yaml", "- not\n- a mapping\n")

    assert _resolve_error(resolver, tmp_path).code == "NOT_A_MAPPING"


def test_sibling_keywords_on_a_non_mapping_target_are_refused(resolver: ModuleType, tmp_path: Path) -> None:
    module = _module_with_path_file(
        tmp_path,
        "get:\n  schema:\n    $ref: ../schemas/Thing.yaml#/properties/id/type\n    description: cannot merge into a string\n",
        extra={"schemas/Thing.yaml": "type: object\nproperties:\n  id:\n    type: string\n"},
    )

    assert _resolve_error(resolver, module).code == "NOT_A_MAPPING"


@pytest.mark.parametrize("keyword", ["$defs", "$anchor", "discriminator"])
def test_construct_outside_the_supported_list_is_refused(resolver: ModuleType, tmp_path: Path, keyword: str) -> None:
    """D-P2 change control: an unlisted form is refused loudly, never read silently."""
    module = _module_with_path_file(tmp_path, f"get:\n  schema:\n    {keyword}: whatever\n")

    assert _resolve_error(resolver, module).code == "UNSUPPORTED_CONSTRUCT"


def test_missing_root_document_is_refused(resolver: ModuleType, tmp_path: Path) -> None:
    assert _resolve_error(resolver, tmp_path).code == "UNRESOLVED_REF"


def test_error_text_is_code_then_detail(resolver: ModuleType) -> None:
    assert str(resolver.ResolveError("CYCLE", "a.yaml -> a.yaml")) == "CYCLE: a.yaml -> a.yaml"


def test_supported_constructs_are_one_constant_and_disjoint_from_the_refused_ones(resolver: ModuleType) -> None:
    supported = set(resolver.SUPPORTED_CONSTRUCTS)

    assert {"file-ref", "pointer-ref", "sibling-keywords", "allOf", "oneOf", "anyOf"} <= supported
    assert not supported & set(resolver.UNSUPPORTED_KEYWORDS)
    assert {"$defs", "$anchor", "discriminator"} <= set(resolver.UNSUPPORTED_KEYWORDS)


def test_resolver_codes_are_the_stable_set(resolver: ModuleType) -> None:
    assert set(resolver.ERROR_CODES) >= {"UNRESOLVED_REF", "URL_REF", "ABSOLUTE_REF", "TILDE_POINTER", "CYCLE", "NOT_A_MAPPING"}


def test_resolver_imports_no_test_or_pytest_machinery() -> None:
    """The module is a bare-script library: no pytest, no tests/, no scripts. import."""
    tree = ast.parse(RESOLVER_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert not imported & {"pytest", "tests", "scripts"}


# ---------------------------------------------------------------------------
# Rule BRACE-1: the brace ref spelling has one source
# ---------------------------------------------------------------------------


def _forbidden_fragments(pieces: tuple[str, ...]) -> tuple[str, ...]:
    """The two spelling pieces and the raw-brace path-file stem, all built without a literal."""
    stem = "missions_" + chr(123)
    return (*pieces, stem)


def _string_literals(source: str) -> list[str]:
    tree = ast.parse(source)
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _spelling_offenders(files: list[Path], fragments: tuple[str, ...]) -> list[Path]:
    """Files holding any fragment as a string literal; a file is parsed only if its text could hold one."""
    lowered = tuple(f.lower() for f in fragments)
    offenders: list[Path] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        if not any(fragment in text.lower() for fragment in lowered):
            continue
        try:
            literals = _string_literals(text)
        except SyntaxError:
            continue
        if any(fragment in literal.lower() for literal in literals for fragment in lowered):
            offenders.append(path)
    return offenders


def _scan_files(roots: tuple[Path, ...]) -> list[Path]:
    files = sorted(p for root in roots for p in root.rglob("*.py") if "fixtures" not in p.relative_to(root).parts)
    assert files, "the single-source scan visited zero files, which proves nothing"
    return files


def test_scan_covers_a_meaningful_number_of_files() -> None:
    """Non-vacuity floor: a scan that visits nothing proves nothing."""
    assert len(_scan_files(SCAN_ROOTS)) > 500


def test_brace_spelling_constant_is_assigned_in_the_resolver_only(resolver: ModuleType) -> None:
    assignments: list[Path] = []
    for path in _scan_files(SCAN_ROOTS):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "BRACE_REF_SPELLING" not in text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            if any(isinstance(t, ast.Name) and t.id == "BRACE_REF_SPELLING" for t in targets):
                assignments.append(path)

    assert assignments == [RESOLVER_PATH]
    spelling = resolver.BRACE_REF_SPELLING
    assert isinstance(spelling, tuple) and len(spelling) == 2
    assert all(isinstance(piece, str) and piece for piece in spelling)


def test_no_scanned_file_other_than_the_resolver_holds_a_spelling_literal(resolver: ModuleType) -> None:
    fragments = _forbidden_fragments(tuple(resolver.BRACE_REF_SPELLING))
    files = [p for p in _scan_files(SCAN_ROOTS) if p != RESOLVER_PATH]

    assert len(files) > 500, "the scan must visit the real tree"
    assert _spelling_offenders(files, fragments) == []


def test_the_scan_detects_a_planted_offender(resolver: ModuleType, tmp_path: Path) -> None:
    open_piece = resolver.BRACE_REF_SPELLING[0]
    planted = _write(tmp_path, "offender.py", f'PATH = "paths/items_{open_piece}itemId.yaml"\n')
    clean = _write(tmp_path, "clean.py", 'PATH = "paths/items.yaml"\n')

    found = _spelling_offenders([planted, clean], _forbidden_fragments(tuple(resolver.BRACE_REF_SPELLING)))

    assert found == [planted]


def test_the_scan_detects_a_planted_raw_brace_stem(resolver: ModuleType, tmp_path: Path) -> None:
    stem = "missions_" + chr(123)
    planted = _write(tmp_path, "offender.py", "NAME = '" + stem + "missionId}.yaml'\n")

    assert _spelling_offenders([planted], _forbidden_fragments(tuple(resolver.BRACE_REF_SPELLING))) == [planted]


def test_a_scan_over_zero_files_is_not_a_pass(tmp_path: Path) -> None:
    empty_root = tmp_path / "nothing"
    empty_root.mkdir()

    with pytest.raises(AssertionError, match="zero files"):
        _scan_files((empty_root,))


def test_layout_check_imports_the_spelling_constant() -> None:
    source = (TOOLS_DIR / "layout_check.py").read_text(encoding="utf-8")
    imported_names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module == "contract_resolver":
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Attribute) and node.attr == "BRACE_REF_SPELLING":
            imported_names.add("BRACE_REF_SPELLING")

    assert "BRACE_REF_SPELLING" in imported_names
