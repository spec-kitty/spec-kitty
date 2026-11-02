"""Structural guard for the lane-adoption seam (#6898).

``implement_support.reenter_lane_self_heal`` used to re-enter the allocator's
internals directly -- importing ``_merge_recorded_planning_commit``,
``_merge_dependency_lane_tips`` and ``_validate_worktree_clean`` -- so that a
retry self-heal could adopt the recorded planning commit and the approved
dependency lane tips without inheriting the allocator's *new-work-package*
clean-worktree precondition. That is a second entry into allocator internals
standing in for a seam the allocator did not expose: two authorities for "make
a reused lane current", invisible to the allocator's own review surface, and
free to drift on ordering, on the pre-condition and on what is recorded
afterwards.

The seam is now public and singular -- ``adopt_lane_ancestry()`` -- with the
clean-worktree policy an explicit, documented parameter of the seam (self-heal
may be less strict, but the allocator owns the decision). This guard keeps the
seam in place and the second entry gone:

* the allocator defines the seam, with a required keyword-only policy whose
  only values are the two named policies;
* every adoption site reaches the seam (a floor of three allocator routes plus
  the ``implement_support`` self-heal re-entry), so the gate cannot pass on a
  seam nobody calls;
* no module under ``src/`` other than the allocator imports any adoption
  helper, in any ``ImportFrom`` spelling (aliased, parenthesised, relative).

Synthetic fixtures prove the checker fires on the exact import shape the
defect used and stays quiet on a clean module -- a gate that cannot report its
own violation is not a gate.

Scope (deliberate): this polices the ADOPTION trio the issue names. Other
private imports from the same module (``_read_coordination_branch``,
``_git_status_entries``, ``_recover_lane_worktree``) are different decisions
with their own documented reasons and are not silently baselined here.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_ALLOCATOR = _SRC / "specify_cli" / "lanes" / "worktree_allocator.py"
_SELF_HEAL = _SRC / "specify_cli" / "lanes" / "implement_support.py"

_SEAM = "adopt_lane_ancestry"
_POLICY_PARAM = "clean_worktree_policy"
_REQUIRED_POLICIES = ("refuse-dirty", "allow-dirty")

#: The private helpers that make up the adoption step. Nothing outside the
#: allocator may import them: the seam is the only way in.
_ADOPTION_HELPERS = frozenset(
    {
        "_merge_recorded_planning_commit",
        "_merge_dependency_lane_tips",
        "_validate_worktree_clean",
    }
)

#: The module those helpers live in, as spelled by an absolute import.
_ALLOCATOR_MODULE = "specify_cli.lanes.worktree_allocator"

#: Bindings that name the allocator MODULE (rather than importing its names):
#: ``import specify_cli.lanes.worktree_allocator as wa`` and ``from
#: specify_cli.lanes import worktree_allocator``. Reaching a private helper
#: through one of these (``wa._merge_...``) is the same second entry, so the
#: checker flags attribute use on them too.
_ALLOCATOR_MODULE_NAME = "worktree_allocator"

#: Floor for the allocator's own adoption sites: REUSE, CRASH_RECOVERY and
#: FRESH all reach the seam, so a "seam" that nothing calls cannot pass.
_MIN_ALLOCATOR_SEAM_CALLS = 3


@dataclass(frozen=True)
class Violation:
    """A flagged second entry into the adoption step."""

    label: str
    lineno: int
    name: str

    def __str__(self) -> str:
        return f"{self.label}:{self.lineno} imports {self.name}"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _is_allocator_module(module: str | None, level: int) -> bool:
    """Whether an ``ImportFrom`` header addresses the allocator module.

    Covers the absolute spelling, and the relative spellings a sibling module
    would use (``from .worktree_allocator import ...``, ``from . import
    worktree_allocator`` is handled by the caller because it binds a module,
    not names).
    """
    if module is None:
        return False
    if module == _ALLOCATOR_MODULE:
        return True
    if level == 0:
        return module == "worktree_allocator"
    return module == "worktree_allocator" or module.endswith(".worktree_allocator")


def _adoption_imports(tree: ast.Module, label: str) -> list[Violation]:
    """Flag every route from *tree* to an adoption helper.

    Covers the import-of-name spellings (absolute, parenthesised, aliased,
    relative) and the two module-binding spellings followed by attribute
    access, so the checker cannot be stepped around by a legal import form.
    """
    violations: list[Violation] = []
    module_bindings: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == _ALLOCATOR_MODULE_NAME:
                    module_bindings.add(alias.asname or alias.name)
                elif _is_allocator_module(node.module, node.level) and alias.name in _ADOPTION_HELPERS:
                    violations.append(Violation(label, node.lineno, f"{node.module or ''}.{alias.name}"))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _ALLOCATOR_MODULE:
                    module_bindings.add(alias.asname or alias.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _ADOPTION_HELPERS:
            receiver = node.value
            if isinstance(receiver, ast.Name) and receiver.id in module_bindings:
                violations.append(Violation(label, node.lineno, f"{receiver.id}.{node.attr}"))
    return violations


def _external_adoption_imports(src_root: Path, allocator: Path) -> list[Violation]:
    """Scan every module under *src_root* except the allocator itself."""
    violations: list[Violation] = []
    for path in sorted(src_root.rglob("*.py")):
        if path == allocator:
            continue
        violations.extend(_adoption_imports(_parse(path), str(path.relative_to(src_root.parent))))
    return violations


def _seam_function(tree: ast.Module) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == _SEAM:
            return node
    return None


def _policy_argument(function: ast.FunctionDef) -> tuple[ast.arg | None, int | None]:
    """Return ``(arg, position in kwonlyargs)`` for the policy parameter."""
    for index, argument in enumerate(function.args.kwonlyargs):
        if argument.arg == _POLICY_PARAM:
            return argument, index
    return None, None


def _policy_violations(tree: ast.Module, label: str) -> list[str]:
    """Report every way the seam's policy parameter fails its contract."""
    function = _seam_function(tree)
    if function is None:
        return [f"{label}: no {_SEAM}() defined"]
    argument, index = _policy_argument(function)
    if argument is None or index is None:
        return [f"{label}: {_SEAM}() has no keyword-only {_POLICY_PARAM} parameter"]
    problems: list[str] = []
    if len(function.args.kw_defaults) > index and function.args.kw_defaults[index] is not None:
        problems.append(f"{label}: {_POLICY_PARAM} must be required (no default)")
    annotation = ast.unparse(argument.annotation) if argument.annotation is not None else ""
    if not annotation.startswith("Literal["):
        problems.append(f"{label}: {_POLICY_PARAM} must annotate a Literal, got {annotation!r}")
    for policy in _REQUIRED_POLICIES:
        if policy not in annotation:
            problems.append(f"{label}: {_POLICY_PARAM} Literal is missing {policy!r}")
    return problems


def _seam_call_count(tree: ast.Module) -> int:
    """Count calls to the seam (never the definition itself)."""
    return sum(1 for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == _SEAM)


_DIRTY_DEFECT_FIXTURE = """
from specify_cli.lanes.worktree_allocator import (
    _merge_dependency_lane_tips,
    _merge_recorded_planning_commit,
)


def reenter(repo_root, worktree, lane, manifest):
    _merge_recorded_planning_commit(repo_root, worktree, lane.lane_id, manifest.planning_commit_sha)
    _merge_dependency_lane_tips(repo_root, worktree, "mission", lane, manifest)
"""

_ALIASED_DEFECT_FIXTURE = """
from specify_cli.lanes.worktree_allocator import _validate_worktree_clean as _clean


def reenter(worktree, lane_id):
    _clean(worktree, lane_id)
"""

_RELATIVE_DEFECT_FIXTURE = """
from .worktree_allocator import _merge_dependency_lane_tips


def reenter(repo_root, worktree, mission_slug, lane, manifest):
    _merge_dependency_lane_tips(repo_root, worktree, mission_slug, lane, manifest)
"""

_MODULE_ALIAS_DEFECT_FIXTURE = """
import specify_cli.lanes.worktree_allocator as wa


def reenter(repo_root, worktree, lane_id, planning_sha):
    wa._merge_recorded_planning_commit(repo_root, worktree, lane_id, planning_sha)
"""

_MODULE_IMPORT_DEFECT_FIXTURE = """
from specify_cli.lanes import worktree_allocator


def reenter(worktree, lane_id):
    worktree_allocator._validate_worktree_clean(worktree, lane_id)
"""

_CLEAN_FIXTURE = """
from specify_cli.lanes.worktree_allocator import adopt_lane_ancestry


def reenter(repo_root, worktree, mission_slug, lane, manifest):
    adopt_lane_ancestry(
        repo_root,
        worktree,
        mission_slug,
        lane,
        manifest,
        clean_worktree_policy="allow-dirty",
    )
"""

_CLEAN_SEAM_FIXTURE = """
from typing import Literal


def adopt_lane_ancestry(
    repo_root,
    worktree_path,
    mission_slug,
    lane,
    lanes_manifest,
    *,
    clean_worktree_policy: Literal["refuse-dirty", "allow-dirty"],
    target_tip=None,
):
    pass
"""

_DEFAULTED_POLICY_FIXTURE = """
from typing import Literal


def adopt_lane_ancestry(
    repo_root,
    worktree_path,
    mission_slug,
    lane,
    lanes_manifest,
    *,
    clean_worktree_policy: Literal["refuse-dirty", "allow-dirty"] = "allow-dirty",
):
    pass
"""

_BOOL_POLICY_FIXTURE = """
def adopt_lane_ancestry(
    repo_root,
    worktree_path,
    mission_slug,
    lane,
    lanes_manifest,
    *,
    clean_worktree_policy: bool,
):
    pass
"""


def test_allocator_defines_the_seam_with_a_required_named_policy() -> None:
    assert _policy_violations(_parse(_ALLOCATOR), "worktree_allocator.py") == []


def test_every_adoption_site_reaches_the_seam() -> None:
    allocator_calls = _seam_call_count(_parse(_ALLOCATOR))
    self_heal_calls = _seam_call_count(_parse(_SELF_HEAL))
    assert allocator_calls >= _MIN_ALLOCATOR_SEAM_CALLS, (
        f"only {allocator_calls} allocator adoption site(s) call {_SEAM}(); REUSE, CRASH_RECOVERY and FRESH must all reach it"
    )
    assert self_heal_calls >= 1, f"implement_support.reenter_lane_self_heal no longer calls {_SEAM}()"


def test_no_module_outside_the_allocator_imports_an_adoption_helper() -> None:
    violations = _external_adoption_imports(_SRC, _ALLOCATOR)
    assert not violations, "second entry into the adoption step:\n" + "\n".join(str(violation) for violation in violations)


def test_adoption_import_checker_flags_every_import_spelling() -> None:
    expected = {
        _DIRTY_DEFECT_FIXTURE: {
            "specify_cli.lanes.worktree_allocator._merge_recorded_planning_commit",
            "specify_cli.lanes.worktree_allocator._merge_dependency_lane_tips",
        },
        _ALIASED_DEFECT_FIXTURE: {"specify_cli.lanes.worktree_allocator._validate_worktree_clean"},
        _RELATIVE_DEFECT_FIXTURE: {"worktree_allocator._merge_dependency_lane_tips"},
        _MODULE_ALIAS_DEFECT_FIXTURE: {"wa._merge_recorded_planning_commit"},
        _MODULE_IMPORT_DEFECT_FIXTURE: {"worktree_allocator._validate_worktree_clean"},
    }
    for source, names in expected.items():
        violations = _adoption_imports(ast.parse(source), "<synthetic>")
        assert {violation.name for violation in violations} == names, (source, violations)


def test_adoption_import_checker_passes_the_seam() -> None:
    assert _adoption_imports(ast.parse(_CLEAN_FIXTURE), "<clean>") == []


def test_policy_checker_is_non_vacuous() -> None:
    assert _policy_violations(ast.parse(_CLEAN_SEAM_FIXTURE), "<clean>") == []
    assert _policy_violations(ast.parse(_DEFAULTED_POLICY_FIXTURE), "<defaulted>")
    assert _policy_violations(ast.parse(_BOOL_POLICY_FIXTURE), "<bool>")
    assert _policy_violations(ast.parse("def other():\n    pass\n"), "<absent>")
