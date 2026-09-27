"""#5180: one handed-dir STATUS_STATE read authority, no private copies.

The render feedback reads (``workflow_cores``), the move-task verdict read
(``tasks_verdict_persistence``) and the post-merge review-artifact gate
(``review_artifact_consistency``) each once carried their own copy of
"handed feature dir -> STATUS_STATE home"; two of the three lacked the #154
phantom-partition degrade and silently masked review feedback. They now
delegate to ``missions._read_path_resolver.resolve_partition_read_dir``.

This gate keeps it that way: none of the three modules may resolve a
``STATUS_STATE`` read dir through the seam directly (``resolve_artifact_surface``
or ``placement_seam(...).read_dir``), and each named entry point must reach the
authority. The poison arms prove the scan reds on a re-introduced copy of
each seam form. A kind bound to a local alias first is not caught; the
delegation check below is the backstop for that shape.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_SRC = Path(__file__).resolve().parents[2] / "src" / "specify_cli"
_AUTHORITY = "resolve_partition_read_dir"
_SEAM_ATTRS = frozenset({"read_dir", "resolve_artifact_surface", "artifact"})

#: module path -> the function that must delegate to the authority.
_CONSUMERS: dict[Path, str] = {
    _SRC / "cli" / "commands" / "agent" / "workflow_cores.py": "_resolve_status_state_read_dir",
    _SRC / "cli" / "commands" / "agent" / "tasks_verdict_persistence.py": "_resolve_verdict_read_feature_dir",
    _SRC / "post_merge" / "review_artifact_consistency.py": "_resolve_lane_state_read_dir",
}


def _names_status_state(call: ast.Call) -> bool:
    args = [*call.args, *(kw.value for kw in call.keywords)]
    return any(isinstance(arg, ast.Attribute) and arg.attr == "STATUS_STATE" for arg in args)


def _is_direct_status_state_seam_read(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name) and func.id == "resolve_artifact_surface":
        return _names_status_state(call)
    if isinstance(func, ast.Attribute) and func.attr in _SEAM_ATTRS:
        # Any receiver: ``placement_seam(...).read_dir(...)``, the two-step
        # ``seam = placement_seam(...); seam.read_dir(...)`` idiom, the
        # module-qualified ``mission_runtime.resolve_artifact_surface(...)`` and
        # the context-surface ``ctx.artifact(STATUS_STATE)`` form alike.
        return _names_status_state(call)
    return False


def direct_status_state_seam_reads(source: str) -> list[int]:
    """Line numbers of calls resolving a STATUS_STATE dir straight off the seam."""
    return sorted(node.lineno for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call) and _is_direct_status_state_seam_read(node))


def function_calls_authority(source: str, function_name: str) -> bool:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == _AUTHORITY for call in ast.walk(node))
    return False


@pytest.mark.parametrize("module", sorted(_CONSUMERS), ids=lambda p: p.name)
def test_consumer_has_no_private_status_state_resolution(module: Path) -> None:
    hits = direct_status_state_seam_reads(module.read_text(encoding="utf-8"))

    assert hits == [], f"{module.name} resolves STATUS_STATE off the seam at lines {hits}; delegate to {_AUTHORITY} (#5180)"


@pytest.mark.parametrize("module", sorted(_CONSUMERS), ids=lambda p: p.name)
def test_consumer_entry_point_delegates_to_authority(module: Path) -> None:
    function_name = _CONSUMERS[module]

    assert function_calls_authority(module.read_text(encoding="utf-8"), function_name), (
        f"{module.name}::{function_name} no longer delegates to {_AUTHORITY} (#5180)"
    )


_POISON_PLACEMENT_SEAM = """
def _resolve_copy(feature_dir):
    from mission_runtime import MissionArtifactKind, placement_seam
    return placement_seam(feature_dir.parent, feature_dir.name).read_dir(MissionArtifactKind.STATUS_STATE)
"""

_POISON_ARTIFACT_SURFACE = """
def _resolve_copy(feature_dir):
    from mission_runtime import MissionArtifactKind, resolve_artifact_surface
    return resolve_artifact_surface(feature_dir.parent, feature_dir.name, kind=MissionArtifactKind.STATUS_STATE).path
"""

_POISON_TWO_STEP_SEAM = """
def _resolve_copy(feature_dir):
    seam = placement_seam(feature_dir.parent, feature_dir.name)
    return seam.read_dir(MissionArtifactKind.STATUS_STATE)
"""

_POISON_QUALIFIED_SURFACE = """
def _resolve_copy(feature_dir):
    import mission_runtime
    return mission_runtime.resolve_artifact_surface(feature_dir.parent, feature_dir.name, mission_runtime.MissionArtifactKind.STATUS_STATE).path
"""

_POISON_CONTEXT_ARTIFACT = """
def _resolve_copy(ctx):
    from mission_runtime import MissionArtifactKind
    return ctx.artifact(MissionArtifactKind.STATUS_STATE).read_dir
"""

_BENIGN_OTHER_KIND = """
def _planning_dir(feature_dir):
    from mission_runtime import MissionArtifactKind, placement_seam
    return placement_seam(feature_dir.parent, feature_dir.name).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
"""


@pytest.mark.parametrize(
    "poison",
    [_POISON_PLACEMENT_SEAM, _POISON_ARTIFACT_SURFACE, _POISON_TWO_STEP_SEAM, _POISON_QUALIFIED_SURFACE, _POISON_CONTEXT_ARTIFACT],
    ids=["placement_seam", "resolve_artifact_surface", "two_step_seam", "qualified_surface", "context_artifact"],
)
def test_scan_reds_on_a_reintroduced_copy(poison: str) -> None:
    assert direct_status_state_seam_reads(poison) == [4]


def test_scan_ignores_other_kinds() -> None:
    assert direct_status_state_seam_reads(_BENIGN_OTHER_KIND) == []


def test_delegation_check_reds_when_the_adapter_stops_delegating() -> None:
    assert not function_calls_authority(_POISON_PLACEMENT_SEAM, "_resolve_copy")
    assert function_calls_authority("def _resolve_copy(feature_dir):\n    return resolve_partition_read_dir(feature_dir, K.STATUS_STATE)\n", "_resolve_copy")
