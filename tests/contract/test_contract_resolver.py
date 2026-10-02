"""Golden-tree and refusal tests for ``contracts/tools/contract_resolver.py``.

The resolver is the single resolution authority (plan D-P1, D-P2): every
contract check, the resolver-parity script and the reality check read the
contract through it. It is a bare script directory (``contracts/`` is not a
package), so it is loaded by file path.

Golden trees under ``contracts/tools/fixtures/contract_resolver/`` are
hand-written expected results, one per supported construct, an oracle that
does not run the resolver. Refusals assert the stable error code, not just
that something raised.

Rule BRACE-1 (path files are named brace-free; ``path_file_name`` is the single
definition of the path-to-file-name mapping, and no ``$ref`` carries a brace) is
enforced here by an executable scan, and the scan is shown to be able to fail.
"""

from __future__ import annotations

import ast
import functools
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


def test_path_file_named_by_the_mapping_resolves_with_a_plain_ref(resolver: ModuleType, tmp_path: Path) -> None:
    """The path key keeps its template; the file is named by ``path_file_name`` and referenced plainly."""
    open_brace, close_brace = chr(123), chr(125)
    key = "/items/" + open_brace + "itemId" + close_brace
    file_name = resolver.path_file_name(key)
    assert file_name == "items_itemId.yaml"
    _write(
        tmp_path,
        "openapi.yaml",
        f"openapi: 3.1.0\ninfo:\n  title: t\n  version: 1.0.0\npaths:\n  {key}:\n    $ref: paths/{file_name}\n",
    )
    _write(tmp_path, "paths/" + file_name, "get:\n  operationId: getItem\n  responses:\n    '200':\n      description: ok\n")

    result = resolver.resolve(tmp_path)

    assert result.tree["paths"][key]["get"]["operationId"] == "getItem"
    assert result.counts["path_items"] == 1


@pytest.mark.parametrize(
    ("key", "name"),
    [
        ("/ping", "ping.yaml"),
        ("/missions", "missions.yaml"),
        ("/missions/{missionId}", "missions_missionId.yaml"),
        ("/missions/{missionId}/events", "missions_missionId_events.yaml"),
        ("/missions/{missionId}/work-packages/{wpId}", "missions_missionId_work-packages_wpId.yaml"),
        ("/a/b-c", "a_b-c.yaml"),
        ("/", None),
        ("ping", None),
        ("/a/{b", None),
        ("/a/b}", None),
        ("/a/{}", None),
    ],
)
def test_path_file_name_is_the_one_brace_free_mapping(resolver: ModuleType, key: str, name: str | None) -> None:
    assert resolver.path_file_name(key) == name


def test_path_keys_that_differ_only_by_braces_collide_on_one_file_name(resolver: ModuleType) -> None:
    open_brace, close_brace = chr(123), chr(125)

    assert resolver.path_file_name("/a/" + open_brace + "b" + close_brace) == resolver.path_file_name("/a/b")


def test_the_brace_spelling_machinery_is_gone(resolver: ModuleType) -> None:
    assert not hasattr(resolver, "BRACE_REF_SPELLING") and not hasattr(resolver, "encode_brace_ref")
    assert "BRACE_IN_REF" in resolver.ERROR_CODES


@pytest.mark.parametrize(
    "file_name",
    [
        "paths/a_" + chr(123) + "b" + chr(125) + ".yaml",
        "paths/a_%" + "7Bb%" + "7D.yaml",
        "paths/a_%" + "7bb%" + "7d.yaml",
        "paths/a_%25" + "7Bb%25" + "7D.yaml",
    ],
)
def test_a_ref_that_carries_a_brace_in_any_spelling_is_refused(resolver: ModuleType, tmp_path: Path, file_name: str) -> None:
    assert resolver.refusal_code_for_ref(file_name) == "BRACE_IN_REF"
    _write(tmp_path, "openapi.yaml", f"openapi: 3.1.0\ninfo:\n  title: t\n  version: 1.0.0\npaths:\n  /a:\n    $ref: '{file_name}'\n")

    with pytest.raises(resolver.ResolveError) as raised:
        resolver.resolve(tmp_path)

    assert raised.value.code == "BRACE_IN_REF"


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


def _forbidden_fragments() -> tuple[str, ...]:
    """A brace-named path-file stem and the percent-encoded brace pieces, all built without a literal."""
    return ("missions_" + chr(123), "%" + "7b", "%" + "7d")


def _string_literals(source: str) -> list[str]:
    tree = ast.parse(source)
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


@functools.cache
def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _spelling_offenders(files: list[Path], fragments: tuple[str, ...]) -> list[Path]:
    """Files holding any fragment as a string literal; a file is parsed only if its text could hold one."""
    lowered = tuple(f.lower() for f in fragments)
    offenders: list[Path] = []
    for path in files:
        text = _read(path)
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


def test_path_file_name_is_defined_in_the_resolver_only() -> None:
    definitions: list[Path] = []
    for path in _scan_files(SCAN_ROOTS):
        text = _read(path)
        if "path_file_name" not in text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        if any(isinstance(node, ast.FunctionDef) and node.name == "path_file_name" for node in ast.walk(tree)):
            definitions.append(path)

    assert definitions == [RESOLVER_PATH]


def test_no_scanned_file_other_than_the_resolver_holds_a_brace_spelling_literal() -> None:
    files = [p for p in _scan_files(SCAN_ROOTS) if p != RESOLVER_PATH]

    assert len(files) > 500, "the scan must visit the real tree"
    assert _spelling_offenders(files, _forbidden_fragments()) == []


def test_the_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    piece = "%" + "7B"
    planted = _write(tmp_path, "offender.py", f'PATH = "paths/items_{piece}itemId.yaml"\n')
    clean = _write(tmp_path, "clean.py", 'PATH = "paths/items.yaml"\n')

    found = _spelling_offenders([planted, clean], _forbidden_fragments())

    assert found == [planted]


def test_the_scan_detects_a_planted_raw_brace_stem(tmp_path: Path) -> None:
    stem = "missions_" + chr(123)
    planted = _write(tmp_path, "offender.py", "NAME = '" + stem + "missionId}.yaml'\n")

    assert _spelling_offenders([planted], _forbidden_fragments()) == [planted]


def test_a_scan_over_zero_files_is_not_a_pass(tmp_path: Path) -> None:
    empty_root = tmp_path / "nothing"
    empty_root.mkdir()

    with pytest.raises(AssertionError, match="zero files"):
        _scan_files((empty_root,))


def test_layout_check_takes_the_name_rule_from_the_resolver() -> None:
    source = (TOOLS_DIR / "layout_check.py").read_text(encoding="utf-8")
    names = {node.attr for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Attribute)}

    assert "path_file_name" in names, "layout_check calls contract_resolver.path_file_name, it does not restate the rule"
    assert "derived_path_file_name" not in source


@pytest.mark.parametrize(
    ("ref", "code"),
    [
        ("https://example.invalid/a.yaml", "URL_REF"),
        ("/a.yaml", "ABSOLUTE_REF"),
        ("~/a.yaml", "ABSOLUTE_REF"),
        ("C:/a.yaml", "ABSOLUTE_REF"),
        ("a.yaml#/x/a~1b", "TILDE_POINTER"),
        ("a.yaml", None),
        ("../schemas/A.yaml#/properties/x", None),
        ("#/properties/x", None),
    ],
)
def test_refusal_code_for_ref_is_the_one_definition_of_a_bad_ref_form(resolver: ModuleType, ref: str, code: str | None) -> None:
    assert resolver.refusal_code_for_ref(ref) == code
