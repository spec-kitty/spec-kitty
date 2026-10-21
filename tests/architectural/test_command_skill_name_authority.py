"""Architectural gate: one composer of the command-skill name and path (#6475, FR-002).

``src/specify_cli/skills/command_skill_names.py`` is the only module allowed to
compose or parse a generated command skill's name (``spec-kitty-<cmd>``, and the
legacy ``spec-kitty.<cmd>``), its ``.agents/skills/.../SKILL.md`` path, or a
skill-agent invocation token (``$spec-kitty…`` / ``/skill:spec-kitty…``).

The scan reads code string literals only (docstrings are skipped, comments are
not in the AST) and matches the *command-skill* shapes precisely, so the
slash-command file producers (``spec-kitty.<cmd>.md`` under an agent's command
directory, C-001) are not caught by path allowlist but by not matching:

* any literal containing ``.agents/skills/spec-kitty.`` or ``.agents/skills/spec-kitty-``;
* an f-string ``…spec-kitty[.-]{x}/SKILL.md``;
* an f-string ``name: spec-kitty[.-]{x}`` (frontmatter);
* an f-string starting ``$spec-kitty[.-]{x}`` or ``/skill:spec-kitty[.-]{x}``;
* a path expression ``… / f"spec-kitty[.-]{x}" / "SKILL.md"``;
* the canonical name f-string ``f"spec-kitty-{x}"`` on its own. The bare dotted
  ``f"spec-kitty.{x}"`` is not gated, because the slash-command file producers use it.

Shipped historical migrations (``upgrade/migrations/m_[0-3]_*``) are frozen
(DIRECTIVE_044, drift is audit-only) and excluded.

There is no pending list: WP03 of mission
``command-skill-names-and-antigravity-01M5DBWT`` routed every former offender
through the authority, so the offender set must be empty.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.architectural._ast_scan import parse_source, read_source

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_AUTHORITY = "src/specify_cli/skills/command_skill_names.py"

#: Frozen historical migrations (pre-4.x): never edited, so never scanned.
_FROZEN_MIGRATION = re.compile(r"^src/specify_cli/upgrade/migrations/m_[0-3]_[^/]*\.py$")

_PLACEHOLDER = "{}"
_TEXT_SHAPES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\.agents/skills/spec-kitty[.\-]"),
    re.compile(r"(?:^|/)spec-kitty[.\-]\{\}/SKILL\.md"),
    re.compile(r"name: spec-kitty[.\-]\{\}"),
    re.compile(r"^(?:\$|/skill:)spec-kitty[.\-]\{\}"),
    # The canonical name itself. The bare dotted f-string stays ungated: the slash-command
    # file producers (``runtime/agent_commands.py``, ``migration/rewrite_shims.py``) build
    # ``spec-kitty.<cmd>`` file stems with exactly that shape (C-001, #6471).
    re.compile(r"^spec-kitty-\{\}$"),
)
_BARE_NAME = re.compile(r"^spec-kitty[.\-]\{\}$")


def _literal_text(node: ast.AST) -> str | None:
    """Flatten a str constant or f-string into text with ``{}`` placeholders."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else _PLACEHOLDER for part in node.values)
    return None


def _docstring_nodes(tree: ast.AST) -> set[int]:
    owners = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, owners) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def _div_operands(node: ast.BinOp) -> list[ast.AST]:
    operands: list[ast.AST] = []
    for side in (node.left, node.right):
        if isinstance(side, ast.BinOp) and isinstance(side.op, ast.Div):
            operands.extend(_div_operands(side))
        else:
            operands.append(side)
    return operands


def _is_path_composition(node: ast.BinOp) -> bool:
    texts = [_literal_text(operand) for operand in _div_operands(node)]
    return "SKILL.md" in texts and any(text is not None and _BARE_NAME.match(text) for text in texts)


def offenders_in_source(source: str, label: str = "<memory>") -> list[int]:
    """Return the line numbers of command-skill name compositions in *source*."""
    tree = parse_source(source, display=label)
    docstrings = _docstring_nodes(tree)
    inner_parts = {id(part) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr) for part in node.values}
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and _is_path_composition(node):
            lines.add(node.lineno)
            continue
        if id(node) in docstrings or id(node) in inner_parts:
            continue
        text = _literal_text(node)
        if text is not None and any(shape.search(text) for shape in _TEXT_SHAPES):
            lines.add(getattr(node, "lineno", 0))
    return sorted(lines)


def _scanned_files() -> list[str]:
    files = []
    for path in sorted(_SRC.rglob("*.py")):
        rel = path.relative_to(_REPO_ROOT).as_posix()
        if rel == _AUTHORITY or _FROZEN_MIGRATION.match(rel):
            continue
        files.append(rel)
    return files


def _offending_files() -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for rel in _scanned_files():
        lines = offenders_in_source(read_source(_REPO_ROOT / rel, display=rel), rel)
        if lines:
            found[rel] = lines
    return found


def test_no_module_outside_the_authority_composes_the_command_skill_name() -> None:
    unexpected = _offending_files()
    assert not unexpected, (
        "Compose command-skill names, paths and skill-agent invocation tokens through "
        f"specify_cli.skills.command_skill_names only; offenders (file: lines): {unexpected}"
    )


def test_scan_covers_real_source() -> None:
    files = _scanned_files()
    assert "src/specify_cli/skills/command_renderer.py" in files
    assert "src/specify_cli/skills/pack_skill_renderer.py" in files
    assert _AUTHORITY not in files
    assert (_REPO_ROOT / _AUTHORITY).is_file()


@pytest.mark.parametrize(
    "snippet",
    [
        'name = f"spec-kitty-{command}"',
        'x = ".agents/skills/spec-kitty."',
        'rel = f".agents/skills/spec-kitty-{command}/SKILL.md"',
        'rel = f"{root}/spec-kitty.{cmd}/SKILL.md"',
        'fm = f"---\\nname: spec-kitty-{command}\\n"',
        'token = f"$spec-kitty-{command}"',
        'token = f"/skill:spec-kitty.{command}"',
        'path = root / f"spec-kitty-{command}" / "SKILL.md"',
        'prefix = ".agents/skills/spec-kitty-"',
    ],
)
def test_gate_detects_a_synthetic_offender(snippet: str) -> None:
    """Self-mutation: each command-skill composition shape is caught."""
    assert offenders_in_source(snippet)


@pytest.mark.parametrize(
    "snippet",
    [
        'def f():\n    """Writes .agents/skills/spec-kitty-<cmd>/SKILL.md."""\n',
        'filename = f"spec-kitty.{command}.md"',
        'filename = f"spec-kitty.{stem}.{ext}"',
        'token = f"/spec-kitty.{command}"',
        'tmp = f".spec-kitty-{ulid}.tmp"',
        'p = root / f"spec-kitty.{command}.md"',
        "# .agents/skills/spec-kitty.plan/SKILL.md in a comment\nx = 1",
    ],
)
def test_gate_ignores_slash_command_files_docstrings_and_comments(snippet: str) -> None:
    assert offenders_in_source(snippet) == []
