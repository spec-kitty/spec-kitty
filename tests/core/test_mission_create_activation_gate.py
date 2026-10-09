"""WP04 re-architecture — the mission-create / mission-type-use fail-closed.

The WP04 pivot made ``PackContext`` construction TOTAL (an absent or empty
``mission_type_activations`` key reads as ``frozenset()`` without raising, so
the dozens of read / compose hot paths never crash). The fail-closed for "a
mission requires at least one activated mission type" therefore fires at the
mission-create boundary -- ``create_mission_core`` -- the narrowest funnel every
mission-create path (the CLI ``agent mission create`` command, the ticket-first
``tracker`` flow, and the ``make_mission`` test factory) passes through.

This suite pins that create-boundary contract directly:

* an EMPTY activation set (absent key OR authored ``[]``) blocks creation with
  an actionable ``ActiveCharterConfigError`` naming the provisioning remedy; and
* a PROVISIONED set lets creation pass the gate.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from charter.activation.pack_context import ActiveCharterConfigError
from specify_cli.core.mission_creation import create_mission_core

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _init_git_repo(repo: Path) -> None:
    """Initialize a git repo with the ``.kittify`` / ``kitty-specs`` markers."""
    (repo / ".kittify").mkdir(parents=True, exist_ok=True)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo, check=True
    )


def _write_activations(repo: Path, body: str) -> None:
    (repo / ".kittify" / "config.yaml").write_text(body, encoding="utf-8")


def test_absent_activation_key_blocks_creation_with_actionable_error(
    tmp_path: Path,
) -> None:
    """A project whose ``config.yaml`` omits ``mission_type_activations`` (the
    genuinely-absent-key, unprovisioned case) cannot host a mission: creation
    fails closed with ``ActiveCharterConfigError`` and an actionable message."""
    _init_git_repo(tmp_path)
    _write_activations(tmp_path, "vcs:\n  type: git\n")  # no activations key

    with pytest.raises(ActiveCharterConfigError, match="ACTIVE_CHARTER_CONFIG_INVALID") as exc:
        create_mission_core(tmp_path, "no-types-mission", allow_worktree_context=True)

    # The actionable remediation lives in the structured error's ``body``
    # (``str()`` renders only the stable ``ACTIVE_CHARTER_CONFIG_INVALID`` code).
    body = exc.value.body
    assert "at least one activated mission type" in body
    assert "spec-kitty init" in body


def test_authored_empty_activation_list_blocks_creation(tmp_path: Path) -> None:
    """An authored empty list (``mission_type_activations: []``) is the same
    unusable case as an absent key -- zero activated types -- and is blocked at
    the create boundary just the same (C-008)."""
    _init_git_repo(tmp_path)
    _write_activations(tmp_path, "mission_type_activations: []\n")

    with pytest.raises(ActiveCharterConfigError, match="ACTIVE_CHARTER_CONFIG_INVALID"):
        create_mission_core(tmp_path, "empty-types-mission", allow_worktree_context=True)


def test_provisioned_activation_set_passes_the_create_gate(tmp_path: Path) -> None:
    """A provisioned project (at least one activated mission type) passes the
    create-boundary gate and creates the mission."""
    _init_git_repo(tmp_path)
    _write_activations(tmp_path, "mission_type_activations:\n  - software-dev\n")

    result = create_mission_core(
        tmp_path,
        "provisioned-mission",
        mission="software-dev",
        allow_worktree_context=True,
    )

    assert result.mission_slug.startswith("provisioned-mission-")
    assert (result.feature_dir / "meta.json").exists()
