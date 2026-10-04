"""Single skill-catalog seam gate (mission pack-skills-kind-01M43419, WP04 T018).

Pack skills are rendered into a staged root and merged with the shipped catalog
by ``specify_cli.skills.catalog.resolve_project_skill_catalog``. Any install,
assess, verify or repair path that builds its own registry sees only the shipped
skills, and the retiring installer then deletes every projected pack skill
(issue #5193). So no module outside the seam may reach the registry factories:

* no ``SkillRegistry.from_package`` / ``from_local_repo`` call, attribute access
  (``else SkillRegistry.from_package``) or ``getattr(..., "from_package")``;
* no ``SkillRegistry(...)`` construction (including through an import alias).

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

#: Every module the plan pins as an install/assess caller, with the seam name it must use.
_PINNED_CALLERS = {
    "src/specify_cli/skills/verifier.py": "resolve_project_skill_catalog",
    "src/specify_cli/runtime/agent_skills.py": "resolve_builtin_skill_catalog",
    "src/specify_cli/cli/commands/init.py": "resolve_project_skill_catalog",
    "src/specify_cli/upgrade/migrations/m_2_0_11_install_skills.py": "resolve_project_skill_catalog",
    "src/specify_cli/upgrade/migrations/m_2_1_1_repair_skill_pack.py": "resolve_project_skill_catalog",
    "src/specify_cli/upgrade/migrations/m_3_0_3_globalize_skill_pack.py": "resolve_project_skill_catalog",
    "src/specify_cli/upgrade/migrations/m_3_2_0rc35_spk_skill_pack.py": "resolve_project_skill_catalog",
    "src/specify_cli/upgrade/assessment.py": "resolve_project_skill_catalog",
    "src/specify_cli/tool_surface/providers/managed_skills.py": "resolve_project_skill_catalog",
    "src/specify_cli/tool_surface/providers/plugin_bundle.py": "resolve_project_skill_catalog",
}


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


@pytest.mark.parametrize(("module", "seam_name"), sorted(_PINNED_CALLERS.items()))
def test_every_pinned_caller_resolves_through_the_seam(module: str, seam_name: str) -> None:
    source, _ = read_and_parse(_SRC.parent / module)
    assert seam_name in source, f"{module} no longer references {seam_name}"
