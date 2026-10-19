"""One language vocabulary: no dict/set/tuple literal outside the catalog repeats it (#6444, FR-009).

``charter.offering.shared.language_catalog`` is the only place a language token or
source extension table may live. This AST scan flags any dict, set or tuple literal in
``src/`` that holds three or more catalog language tokens or source extensions. It
counts string constants anywhere inside the literal, nested tuples and dicts included:
a ``(token, patterns)`` pair table such as the former ``_LANGUAGE_PATTERNS`` is a tuple
of tuples, and a flat scan would miss it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from charter.offering.shared.language_catalog import LANGUAGES
from tests.architectural._ast_scan import parse_file

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_SRC = Path(__file__).resolve().parents[2] / "src"
_CATALOG = _SRC / "charter" / "offering" / "shared" / "language_catalog.py"
_THRESHOLD = 3

#: path (relative to src/) -> why it is a different concept.
_ALLOWLIST: dict[str, str] = {
    "specify_cli/review/fix_prompt.py": (
        "markdown fence-language map (file extension -> code-fence info string); a rendering concern, not the charter language vocabulary"
    ),
}

_VOCABULARY: frozenset[str] = frozenset(spec.token for spec in LANGUAGES) | frozenset(extension for spec in LANGUAGES for extension in spec.extensions)


def _vocabulary_hits(node: ast.AST) -> set[str]:
    return {child.value for child in ast.walk(node) if isinstance(child, ast.Constant) and isinstance(child.value, str) and child.value in _VOCABULARY}


def _flagged_literals(tree: ast.AST) -> list[tuple[int, set[str]]]:
    """Return the outermost literals holding at least ``_THRESHOLD`` vocabulary tokens."""
    flagged: list[tuple[int, set[str]]] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.Dict, ast.Set, ast.Tuple)):
            hits = _vocabulary_hits(node)
            if len(hits) >= _THRESHOLD:
                flagged.append((node.lineno, hits))
                return
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return flagged


def _violations() -> list[str]:
    found: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        if path == _CATALOG or path.relative_to(_SRC).as_posix() in _ALLOWLIST:
            continue
        for lineno, hits in _flagged_literals(parse_file(path)):
            found.append(f"{path.relative_to(_SRC).as_posix()}:{lineno} repeats {sorted(hits)}")
    return found


def test_no_language_table_outside_the_catalog() -> None:
    violations = _violations()

    assert not violations, "language vocabulary must live only in language_catalog.py:\n" + "\n".join(violations)


def test_allowlisted_files_exist_and_carry_a_rationale() -> None:
    for relative, rationale in _ALLOWLIST.items():
        assert (_SRC / relative).is_file(), f"stale allowlist entry {relative}"
        assert rationale.strip()


def test_scan_sees_nested_pair_tables() -> None:
    """The scan must catch a tuple-of-pairs table (the shape of the former ``_LANGUAGE_PATTERNS``)."""
    tree = ast.parse('X = (("python", ("a",)), ("rust", ("b",)), ("java", ("c",)))')

    assert [hits for _line, hits in _flagged_literals(tree)] == [{"python", "rust", "java"}]


def test_scan_ignores_literals_below_the_threshold() -> None:
    tree = ast.parse('X = {"python": 1, "go": 2}')

    assert _flagged_literals(tree) == []
