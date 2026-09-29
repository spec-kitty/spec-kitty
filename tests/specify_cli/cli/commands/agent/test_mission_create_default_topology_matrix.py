"""Default-topology matrix for ``_resolve_default_topology_phase`` (WP06, #2602, FR-013).

Binding decision (#5100 comment 5870360497): ``single_branch`` is minted ONLY
from an explicit ``--topology single_branch`` or from ``--owned-checkout``.
Both implicit ``SINGLE_BRANCH`` returns the pre-WP06 derivation carried — the
non-primary/no-``--pr-bound`` arm and the pr-bound/coordination-unreachable
arm — become ``LANES``, so default users keep worktree isolation (US4).

This is the red-first driver for T025's flip: on the WP06 planning base, the
two ``LANES``-expecting rows below (``non_primary_no_pr_bound`` and
``pr_bound_unreachable``) fail because ``_resolve_default_topology_phase``
still returns ``SINGLE_BRANCH`` for them.

Isolated unit test: ``resolve_primary_branch``, ``ProtectionPolicy.resolve``,
and ``coord_topology_reachable`` are monkeypatched at their deferred-import
source modules so the matrix never touches a real git repo or config file.
Because of that isolation, the ``owned_checkout_no_topology`` row below is a
UNIT-only proof of the ``owned_checkout is not None`` short-circuit — it does
NOT demonstrate what the pre-WP06 code did for a REAL owned checkout (it
cannot: this file never resolves a real primary branch). Correction (#5100
review cycle 1, nit 3): a real owned checkout with no ``origin`` makes
``resolve_primary_branch`` fall back to that checkout's OWN current branch,
so pre-WP06 a real ``--owned-checkout`` create with no ``--topology`` minted
``coord`` (the primary-branch arm), never the non-primary arm's
``single_branch`` — see the CLI-level real-worktree pin in
``tests/agent/test_agent_feature.py::TestCreateFeatureCommand::test_owned_checkout_with_no_topology_flag_still_defaults_to_single_branch``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mission_runtime import MissionTopology
from specify_cli.cli.commands.agent.mission_create import (
    _resolve_default_topology_phase,
)

_PRIMARY_BRANCH = "main"
_FEATURE_BRANCH = "feature/x"
_REPO_ROOT = Path("/repo")
_OWNED_CHECKOUT = Path("/repo/.worktrees/owned")

_RESOLVE_PRIMARY_BRANCH = "specify_cli.core.git_ops.resolve_primary_branch"
_PROTECTION_POLICY_RESOLVE = "specify_cli.git.protection_policy.ProtectionPolicy.resolve"
_COORD_TOPOLOGY_REACHABLE = "specify_cli.coordination.surface_authority.coord_topology_reachable"


class _FakeProtectionPolicy:
    """Stand-in for ``ProtectionPolicy`` — only ``is_protected`` is consulted."""

    def __init__(self, *, protected: bool) -> None:
        self._protected = protected

    def is_protected(self, branch: str) -> bool:
        return self._protected


def _resolve(
    *,
    explicit_topology: MissionTopology | None = None,
    repo_root: Path | None = _REPO_ROOT,
    current_branch: str | None = _FEATURE_BRANCH,
    pr_bound: bool = False,
    owned_checkout: Path | None = None,
    primary_protected: bool = False,
    reachable: bool = False,
) -> MissionTopology:
    call_kwargs: dict[str, object] = {
        "explicit_topology": explicit_topology,
        "repo_root": repo_root,
        "current_branch": current_branch,
        "pr_bound": pr_bound,
    }
    # ``owned_checkout`` is only passed when exercised (T025 adds the
    # parameter): omitting it for every other row lets those rows run — and
    # go red on an assertion, not a TypeError — against the pre-T025 base.
    if owned_checkout is not None:
        call_kwargs["owned_checkout"] = owned_checkout
    with (
        patch(_RESOLVE_PRIMARY_BRANCH, return_value=_PRIMARY_BRANCH),
        patch(
            _PROTECTION_POLICY_RESOLVE,
            return_value=_FakeProtectionPolicy(protected=primary_protected),
        ),
        patch(_COORD_TOPOLOGY_REACHABLE, return_value=reachable),
    ):
        return _resolve_default_topology_phase(**call_kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("case_id", "kwargs", "expected"),
    [
        (
            "non_primary_no_pr_bound",
            {"current_branch": _FEATURE_BRANCH, "pr_bound": False},
            MissionTopology.LANES,
        ),
        (
            "pr_bound_unreachable",
            {"current_branch": _FEATURE_BRANCH, "pr_bound": True, "reachable": False},
            MissionTopology.LANES,
        ),
        (
            "pr_bound_reachable",
            {"current_branch": _FEATURE_BRANCH, "pr_bound": True, "reachable": True},
            MissionTopology.COORD,
        ),
        (
            "primary",
            {"current_branch": _PRIMARY_BRANCH, "pr_bound": False},
            MissionTopology.COORD,
        ),
        (
            "explicit_single_branch",
            {"explicit_topology": MissionTopology.SINGLE_BRANCH},
            MissionTopology.SINGLE_BRANCH,
        ),
        (
            "explicit_lanes",
            {"explicit_topology": MissionTopology.LANES},
            MissionTopology.LANES,
        ),
        (
            "unresolvable_repo",
            {"repo_root": None, "current_branch": None},
            MissionTopology.COORD,
        ),
        (
            "owned_checkout_no_topology",
            {"owned_checkout": _OWNED_CHECKOUT},
            MissionTopology.SINGLE_BRANCH,
        ),
    ],
)
def test_default_topology_matrix(
    case_id: str,
    kwargs: dict[str, object],
    expected: MissionTopology,
) -> None:
    assert _resolve(**kwargs) == expected, case_id  # type: ignore[arg-type]
