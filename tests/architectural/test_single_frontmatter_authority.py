"""Architectural gate: one SKILL.md frontmatter authority (#6475, FR-012, FR-013, plan A-M2).

``src/specify_cli/skills/skill_frontmatter.py`` is the only module allowed to
build ``SKILL.md`` frontmatter or move keys between the top level and
``metadata``. Every writer and verifier (command skills, the managed-skill
installer, the verifier, the global ``~/.agents/skills`` writer, the plugin
bundles) imports it, so the bytes a writer produces and the hash a verifier
expects can never disagree.

The scan reads code string literals only (docstrings are skipped, comments are
not in the AST), flattening f-strings with ``{}`` placeholders, and flags:

* a literal holding a Claude-style frontmatter key (``user-invocable``,
  ``argument-hint``, ``disable-model-invocation``) — the projection decides
  where those keys go;
* a literal opening a frontmatter block with a ``name:`` line (``---\\nname:``);
* a ``def`` of the authority's projection functions anywhere else.

The neutral pack skill renderer (``pack_skill_renderer.py``) is the one
documented exception (plan A-M3: it renders canonical keys once and the
projection is applied per root). The allowlist is otherwise empty.
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
_AUTHORITY = "src/specify_cli/skills/skill_frontmatter.py"

#: The neutral pack renderer (A-M3); nothing else may build SKILL.md frontmatter.
_EXEMPT: frozenset[str] = frozenset({"src/specify_cli/skills/pack_skill_renderer.py"})

_PLACEHOLDER = "{}"
_TEXT_SHAPES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:user-invocable|argument-hint|disable-model-invocation)\b"),
    re.compile(r"(?:^|\n)---\n(?:[^\n]*\n)*?name:"),
)
_AUTHORITY_FUNCTIONS = frozenset({"ensure_skill_frontmatter", "project_for_root", "project_skill_bytes", "render_frontmatter"})


def _literal_text(node: ast.AST) -> str | None:
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


def offenders_in_source(source: str, label: str = "<memory>") -> list[int]:
    """Return the line numbers that build SKILL.md frontmatter outside the authority."""
    tree = parse_source(source, display=label)
    docstrings = _docstring_nodes(tree)
    inner_parts = {id(part) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr) for part in node.values}
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name in _AUTHORITY_FUNCTIONS:
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
        if rel == _AUTHORITY or rel in _EXEMPT:
            continue
        files.append(rel)
    return files


def test_no_module_outside_the_authority_builds_skill_frontmatter() -> None:
    found: dict[str, list[int]] = {}
    for rel in _scanned_files():
        lines = offenders_in_source(read_source(_REPO_ROOT / rel, display=rel), rel)
        if lines:
            found[rel] = lines
    assert not found, f"Build SKILL.md frontmatter and place Claude-style keys through specify_cli.skills.skill_frontmatter only; offenders (file: lines): {found}"


def test_scan_covers_real_source() -> None:
    files = _scanned_files()
    for rel in (
        "src/specify_cli/skills/command_renderer.py",
        "src/specify_cli/skills/command_installer.py",
        "src/specify_cli/skills/installer.py",
        "src/specify_cli/skills/verifier.py",
        "src/specify_cli/runtime/agent_skills.py",
        "src/specify_cli/tool_surface/bundles/_builder.py",
    ):
        assert rel in files
    assert _AUTHORITY not in files
    assert (_REPO_ROOT / _AUTHORITY).is_file()
    assert all((_REPO_ROOT / rel).is_file() for rel in _EXEMPT)


def test_exempt_renderer_still_needs_its_exemption() -> None:
    """The exemption must stay justified: the neutral renderer does emit canonical keys."""
    for rel in _EXEMPT:
        assert offenders_in_source(read_source(_REPO_ROOT / rel, display=rel), rel)


@pytest.mark.parametrize(
    "snippet",
    [
        'fm = "---\\nname: x\\ndescription: y\\n---\\n"',
        'fm = f"---\\nname: {name}\\n"',
        'line = "user-invocable: true"',
        'key = "argument-hint"',
        'lines.append(f"disable-model-invocation: {flag}")',
        "def ensure_skill_frontmatter(content, name):\n    return content\n",
        "def project_for_root(content, *, shared, skill_name):\n    return content\n",
    ],
)
def test_gate_detects_a_synthetic_offender(snippet: str) -> None:
    """Self-mutation: each frontmatter-building shape is caught."""
    assert offenders_in_source(snippet)


@pytest.mark.parametrize(
    "snippet",
    [
        'def f():\n    """Emits ``user-invocable`` under metadata."""\n',
        "# user-invocable: true in a comment\nx = 1",
        'from specify_cli.skills.skill_frontmatter import project_for_root\nx = project_for_root(t, shared=True, skill_name="n")',
        'lines = ["---", f"name: {profile.profile_id}"]',
        'header = "---\\ntitle: x\\n---\\n"',
    ],
)
def test_gate_ignores_non_offenders(snippet: str) -> None:
    assert not offenders_in_source(snippet)
