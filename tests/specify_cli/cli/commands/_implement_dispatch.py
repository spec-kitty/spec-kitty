"""Dispatch map for the ``spec-kitty implement`` characterization suite (mission implement-degod, FR-009).

The characterization suite (``test_implement_characterization.py``) pins today's observable
behaviour of ``implement`` through its public entry points.  Most failures are produced with a real
git fixture.  A few cannot be (a ``RuntimeError`` raised by the claim commit, an allocator that
fails after the workspace is half-built); for those the suite injects a replacement through
:func:`patch_collaborator`, addressing a collaborator by a **logical name** and never by a dotted
path.  This module is the one place that knows where each logical collaborator is looked up today.

Rules (binding for every work package of the mission):

* **Scope.**  Only the characterization suite and the F-50 allocation-failure test may import this
  module.  It is not a general patching helper.
* **Counted.**  Every :func:`patch_collaborator` call is a patch site in the SC-002 counter
  (``kitty-specs/implement-degod-01M44488/tools/count_patch_sites.py``).
* **Only a work package updates this map.**  When a work package moves a collaborator's dispatch
  site to another module, it changes the matching ``DISPATCH`` value here, in the same commit, and
  nothing else in the suite.  The characterization test file itself stays frozen (SC-003).
* **No dynamic targets.**  Every value is a plain string literal ``<package>.<module>.<name>`` so
  the widened liveness gate (``test_implement_dispatch_map_targets_are_live``) can prove each target
  is a name its module still looks up.  Never build a target with an f-string or concatenation.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest

#: logical collaborator -> ``<package>.<module>.<name>`` of the module global the command looks up.
DISPATCH: dict[str, str] = {
    # Record the claim: the status pipeline entry point.
    "start_status": "specify_cli.cli.commands.implement_claim.start_implementation_status",
    # Allocate or reuse the lane workspace.
    "allocate": "specify_cli.cli.commands.implement.create_lane_workspace",
    # Record the claim: the auto-commit of the claimed->doing change.
    "claim_commit": "specify_cli.cli.commands.implement_claim._commit_wp_claim_status",
    # The ``safe_commit`` the claim commit calls.
    "safe_commit": "specify_cli.cli.commands.implement_claim.safe_commit",
    # Side-effect-order spies (T007).
    "target_branch": "specify_cli.workspace.context.resolve_mission_target_branch",
    "dependency_gate": "specify_cli.core.dependency_graph.ensure_wp_claim_preconditions",
    "planning_commit": "specify_cli.cli.commands.implement_planning_commit._ensure_planning_artifacts_committed_git",
    "bulk_edit_gate": "specify_cli.cli.commands.implement._run_bulk_edit_gate_and_inference",
    "resolve_workspace": "specify_cli.cli.commands.implement.resolve_workspace_for_wp",
    "vcs_lock": "specify_cli.cli.commands.implement._ensure_vcs_in_meta",
}


def _split(logical: str) -> tuple[str, str]:
    module_path, _, name = DISPATCH[logical].rpartition(".")
    return module_path, name


def original(logical: str) -> Any:
    """The real collaborator currently bound for *logical* (for spies that delegate)."""
    module_path, name = _split(logical)
    return getattr(importlib.import_module(module_path), name)


def patch_collaborator(monkeypatch: pytest.MonkeyPatch, logical: str, replacement: Any) -> None:
    """Replace the collaborator named *logical* for the duration of the test."""
    module_path, name = _split(logical)
    monkeypatch.setattr(importlib.import_module(module_path), name, replacement)
