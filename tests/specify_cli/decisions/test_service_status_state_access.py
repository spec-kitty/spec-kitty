"""#6766 / #4848: the decisions service resolves STATUS_STATE write-side only.

Standing invariant pinned by this module (red-first for the removal of the
read-side ``decisions/service.py::_mission_dir``): every
``status.events.jsonl`` access in the decisions service is a WRITE-side
pre-resolution (``_write_mission_dir`` / ``_write_events_path``). PR #6762
(#4848) moved the opened-row existence check onto the pre-resolved
write-side events path, so the module holds no read-side
``placement_seam(...).read_dir(STATUS_STATE)`` call: a second, divergent read
path for the decisions event log is exactly the split-brain the read/write
split removed.

If a future change legitimately needs a read-side STATUS_STATE read in this
module, update this guard in the same PR with the rationale.
"""

from __future__ import annotations

import ast
from pathlib import Path

from specify_cli.decisions import service as decisions_service

_SERVICE_SOURCE = Path(decisions_service.__file__).resolve()

_FAILURE_HINT = (
    "decisions/service.py must not resolve STATUS_STATE through a read-side "
    "placement_seam(...).read_dir(...) call (#6766, #4848): every "
    "status.events.jsonl access in the decisions service is a write-side "
    "pre-resolution (_write_mission_dir / _write_events_path). If a "
    "read-side read is genuinely needed, update this guard in the same PR "
    "with the rationale."
)


def _is_status_state_arg(call: ast.Call) -> bool:
    """True when the call's sole argument is ``MissionArtifactKind.STATUS_STATE``."""
    if len(call.args) != 1:
        return False
    arg = call.args[0]
    return isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and arg.value.id == "MissionArtifactKind" and arg.attr == "STATUS_STATE"


def _status_state_calls(tree: ast.Module, method: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == method and _is_status_state_arg(node)
    ]


def test_no_read_side_status_state_resolution_in_decisions_service() -> None:
    """The decisions service holds no read-side ``read_dir(STATUS_STATE)`` call."""
    tree = ast.parse(_SERVICE_SOURCE.read_text(encoding="utf-8"))
    read_side = _status_state_calls(tree, "read_dir")
    assert not read_side, _FAILURE_HINT


def test_decisions_service_keeps_a_write_side_status_state_resolution() -> None:
    """Positive control: the write-side pre-resolution is still routed through the seam.

    Without this, the read-side guard above could pass vacuously if the
    module stopped resolving STATUS_STATE at all.
    """
    tree = ast.parse(_SERVICE_SOURCE.read_text(encoding="utf-8"))
    write_side = _status_state_calls(tree, "write_dir")
    assert write_side, (
        "decisions/service.py is expected to resolve STATUS_STATE through "
        "placement_seam(...).write_dir(...) (_write_mission_dir); if that "
        "moved, re-point this guard in the same PR."
    )
