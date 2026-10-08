"""Single skill-catalog seam gate (mission pack-skills-kind-01M43419, WP04 T018).

Pack skills are rendered into a staged root and merged with the shipped catalog
by ``specify_cli.skills.catalog.resolve_project_skill_catalog``. Any install,
assess, verify or repair path that builds its own registry sees only the shipped
skills, and the retiring installer then deletes every projected pack skill
(issue #5193). So no module outside the seam may reach the registry factories:

* no ``SkillRegistry.from_package`` / ``from_local_repo`` call, attribute access
  (``else SkillRegistry.from_package``) or ``getattr(..., "from_package")``;
* no ``SkillRegistry(...)`` construction (including through an import alias).

The seam also exports ``resolve_builtin_skill_catalog``, a catalog of shipped skills
only. Handed to a project-scope ``assess_project_skills(retire=True)`` it would retire
every pack-origin manifest entry, so it is a second door to the same hazard: only
``catalog.py`` and ``runtime/agent_skills.py`` (global roots, where no pack skill is
ever installed) may reference it.

Only ``catalog.py`` (the seam) and ``registry.py`` (the definition) are exempt.
The allowlist is empty: a new entry needs a reviewed read-only-listing rationale.
Subclassing ``SkillRegistry`` (the installer's captured registry) is not a
construction and stays legal.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architectural._ast_scan import parse_source, read_and_parse

pytestmark = pytest.mark.architectural

_SRC = Path(__file__).resolve().parents[2] / "src"
_SEAM_FILES = frozenset({"src/specify_cli/skills/catalog.py", "src/specify_cli/skills/registry.py"})

#: Reviewed read-only listings that may bypass the seam, as ``"<relpath>:<lineno>"`` -> rationale.
_ALLOWLIST: dict[str, str] = {}

_FACTORIES = frozenset({"from_package", "from_local_repo"})
_CLASS = "SkillRegistry"

#: The seam function that returns shipped skills only, and the modules that may use it.
#: ``_charter_pack_cutover_skills.py`` (#3732) reads only the shipped skill *names*, to
#: skip a removed name the installed CLI still ships; it never passes the catalog to
#: ``assess_project_skills`` and a pack skill cannot carry a reserved ``spk-`` name.
_BUILTIN_ONLY = "resolve_builtin_skill_catalog"
_BUILTIN_ONLY_ALLOWED = frozenset(
    {
        "src/specify_cli/skills/catalog.py",
        "src/specify_cli/runtime/agent_skills.py",
        "src/specify_cli/upgrade/migrations/_charter_pack_cutover_skills.py",
    }
)


def _class_aliases(tree: ast.Module) -> set[str]:
    """Local names bound to ``SkillRegistry`` (the class name plus any ``as`` alias)."""
    aliases = {_CLASS}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            aliases.update(alias.asname or alias.name for alias in node.names if alias.name == _CLASS)
    return aliases


def _is_class_reference(node: ast.expr, aliases: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in aliases
    return isinstance(node, ast.Attribute) and node.attr == _CLASS


def find_bypasses(tree: ast.Module) -> list[tuple[int, str]]:
    """Return ``(lineno, description)`` for every registry-factory bypass in *tree*."""
    aliases = _class_aliases(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _FACTORIES and _is_class_reference(node.value, aliases):
            found.append((node.lineno, f"{_CLASS}.{node.attr}"))
        elif isinstance(node, ast.Call):
            if _is_class_reference(node.func, aliases):
                found.append((node.lineno, f"{_CLASS}(...) construction"))
            elif isinstance(node.func, ast.Name) and node.func.id == "getattr" and _getattr_factory(node, aliases):
                found.append((node.lineno, "getattr factory access"))
    return sorted(found)


def _getattr_factory(call: ast.Call, aliases: set[str]) -> bool:
    return len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) and call.args[1].value in _FACTORIES and _is_class_reference(call.args[0], aliases)


def _scan_src() -> tuple[list[str], int]:
    violations: list[str] = []
    scanned = 0
    for path in sorted(_SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(_SRC.parent).as_posix()
        if relative in _SEAM_FILES:
            continue
        scanned += 1
        _, tree = read_and_parse(path)
        violations.extend(f"{relative}:{lineno}  {what}" for lineno, what in find_bypasses(tree) if f"{relative}:{lineno}" not in _ALLOWLIST)
    return violations, scanned


def test_nothing_outside_the_seam_builds_a_skill_registry() -> None:
    violations, scanned = _scan_src()
    assert scanned > 500, "the scan must actually cover src/"
    assert not violations, "Resolve skill catalogs through specify_cli.skills.catalog.resolve_project_skill_catalog (retire hazard, #5193):\n" + "\n".join(
        violations
    )


def test_the_allowlist_is_empty_or_every_row_is_a_reviewed_live_site() -> None:
    assert not _ALLOWLIST, "an allowlisted bypass needs a reviewed read-only-listing rationale; prefer migrating it to the seam"


def test_the_seam_files_really_contain_the_patterns_the_scan_hunts() -> None:
    """Non-vacuity: the exempt files carry the factories, so the scanner is not blind to them."""
    _, tree = read_and_parse(_SRC.parent / "src/specify_cli/skills/catalog.py")
    seam = find_bypasses(tree)
    kinds = {what for _, what in seam}
    assert f"{_CLASS}.from_package" in kinds and f"{_CLASS}.from_local_repo" in kinds and f"{_CLASS}(...) construction" in kinds


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from specify_cli.skills.registry import SkillRegistry\nr = SkillRegistry.from_package()\n", ["SkillRegistry.from_package"]),
        ("from specify_cli.skills.registry import SkillRegistry\nf = SkillRegistry.from_package\n", ["SkillRegistry.from_package"]),
        ("from specify_cli.skills.registry import SkillRegistry\nr = SkillRegistry.from_local_repo(p)\n", ["SkillRegistry.from_local_repo"]),
        ("from specify_cli.skills.registry import SkillRegistry\nr = SkillRegistry(p)\n", ["SkillRegistry(...) construction"]),
        ("from specify_cli.skills.registry import SkillRegistry as SR\nf = getattr(SR, 'from_local_repo')\n", ["getattr factory access"]),
        (
            "from specify_cli.skills.registry import SkillRegistry as SR\nr = SR(p)\nq = SR.from_package()\n",
            ["SkillRegistry(...) construction", "SkillRegistry.from_package"],
        ),
        (
            "import specify_cli.skills.registry as reg\nr = reg.SkillRegistry(p)\nq = reg.SkillRegistry.from_package()\n",
            ["SkillRegistry(...) construction", "SkillRegistry.from_package"],
        ),
        ("from specify_cli.skills.registry import SkillRegistry\nf = getattr(SkillRegistry, 'from_package')\n", ["getattr factory access"]),
        ("class Captured(SkillRegistry):\n    def __init__(self):\n        pass\n", []),
        ("def f(registry: SkillRegistry):\n    return registry.discover_skills()\n", []),
        ("x = Other.from_package()\n", []),
    ],
)
def test_the_scanner_detects_each_bypass_shape(source: str, expected: list[str]) -> None:
    found = [what for _, what in find_bypasses(parse_source(source, display="<probe>"))]
    assert sorted(found) == sorted(expected)


def find_builtin_only_references(tree: ast.Module) -> list[int]:
    """Line numbers where *tree* names the built-in-only catalog: a name, attribute, import or string."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if (
            (isinstance(node, ast.Name) and node.id == _BUILTIN_ONLY)
            or (isinstance(node, ast.Attribute) and node.attr == _BUILTIN_ONLY)
            or (isinstance(node, ast.alias) and node.name == _BUILTIN_ONLY)
            or (isinstance(node, ast.Constant) and node.value == _BUILTIN_ONLY)
        ):
            lines.append(getattr(node, "lineno", 0))
    return lines


def test_the_built_in_only_catalog_is_not_a_second_door_around_the_seam() -> None:
    referencing = {
        path.relative_to(_SRC.parent).as_posix()
        for path in sorted(_SRC.rglob("*.py"))
        if "__pycache__" not in path.parts and find_builtin_only_references(read_and_parse(path)[1])
    }
    assert referencing == _BUILTIN_ONLY_ALLOWED, (
        f"{_BUILTIN_ONLY} returns shipped skills only; a project-scope caller passing it to assess_project_skills(retire=True) "
        f"retires every pack skill (#5193). Unexpected or missing: {sorted(referencing ^ _BUILTIN_ONLY_ALLOWED)}"
    )

    planted = parse_source(
        f"from specify_cli.skills.catalog import {_BUILTIN_ONLY}\nimport specify_cli.skills.catalog as c\nc.{_BUILTIN_ONLY}()\ngetattr(c, '{_BUILTIN_ONLY}')\n",
        display="<probe>",
    )
    assert len(find_builtin_only_references(planted)) == 3  # the import, the attribute call, the getattr string
    assert find_builtin_only_references(parse_source("from specify_cli.skills.catalog import resolve_project_skill_catalog\n", display="<probe>")) == []
