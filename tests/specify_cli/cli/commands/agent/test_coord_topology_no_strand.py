"""Guard (#2533 / WP02, fixed): a pr-bound mission on an UNPROTECTED primary mints no coord branch.

A permanent behavioral guard against the #2533 defect recurring — the fix
shipped with this test, so it is green by construction, not a red-first
reproduction (it therefore lives in its functional home under
``tests/specify_cli/cli/commands/agent/`` beside its sibling create-time
tripwire, and carries the ``integration``/``git_repo`` marks — never
``regression``).

The #2533 split-brain (and the B16-clause-2 "cross-contamination" appearance,
research D-002) came from ``--pr-bound`` unconditionally minting a ``coord``
topology — stranding a ``kitty/mission-<slug>-<mid8>`` coordination branch even
when coordination routing was never reachable (unprotected primary target). WP02
keys the create-time default on :func:`coord_topology_reachable`, so a pr-bound
mission created off an unprotected primary defaults away from ``coord``. WP06
(#2602, binding decision #5100 comment 5870360497) re-keyed that unreachable
arm from ``single_branch`` to ``lanes`` — ``single_branch`` is now
explicit-only (``--topology single_branch`` or ``--owned-checkout``) — so the
mission still lands on the branch-flat side (no coordination branch), just as
``lanes`` rather than ``single_branch``.

These tests assert the mint **decision** by construction (topology + no
``coordination_branch`` in meta + no ``kitty/*`` branch on disk), not merely the
absence of a stranded branch after the fact — closing the defect class rather
than one instance (DIR-043). The complementary "protected target → coord"
keying is proven by the tripwire ``test_create_pr_bound_on_non_primary_branch_
still_defaults_to_coord`` in ``tests/specify_cli/cli/commands/agent/``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app as mission_app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CORE_MODULE = "specify_cli.core.mission_creation"

# The pr-bound feature checkout the mission is created from. It is deliberately
# NOT the resolved primary target ("main"), so ``current_is_primary`` is False —
# leaving primary-target protection as the sole lever on reachability.
_FEATURE_CHECKOUT = "fix/unprotected-x"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo_unprotected(repo: Path) -> None:
    """Provision a project whose primary ("main") is UNPROTECTED.

    ``protection.protected_branches: []`` resolves to an empty protected set (see
    ``ProtectionPolicy`` resolution table), so ``is_protected("main")`` is False
    regardless of the default ``{main, master}`` union — modelling a pr-bound
    mission created off an unprotected feature branch.
    """
    (repo / ".kittify").mkdir(exist_ok=True)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    (repo / ".kittify" / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n  - documentation\n  - research\n  - plan\nprotection:\n  protected_branches: []\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True, check=True)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "commit", "-m", "init", "--allow-empty")


def _mission_summary_args(title: str) -> list[str]:
    return [
        "--friendly-name",
        title,
        "--purpose-tldr",
        f"Deliver {title} cleanly for the team.",
        "--purpose-context",
        (f"This mission delivers {title} so product and engineering can move forward with a clear outcome and shared understanding."),
    ]


def _json_payload(output: str) -> dict[str, object]:
    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"No JSON object found in CLI output:\n{output}")


def _create_pr_bound(repo: Path, slug: str) -> dict[str, object]:
    """Create a ``--pr-bound`` mission from the unprotected feature checkout."""
    runner = CliRunner()
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=repo),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value=_FEATURE_CHECKOUT),
        patch(f"{_CORE_MODULE}._commit_feature_file"),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=repo),
        patch(
            "specify_cli.cli.commands.agent.mission.get_current_branch",
            return_value=_FEATURE_CHECKOUT,
        ),
    ):
        result = runner.invoke(
            mission_app,
            [
                "create",
                slug,
                "--pr-bound",
                "--json",
                "--target-branch",
                "main",
                *_mission_summary_args(slug.replace("-", " ").title()),
            ],
        )
    assert result.exit_code == 0, result.output
    return _json_payload(result.output)


def _kitty_branches(repo: Path) -> list[str]:
    out = _git(repo, "branch", "--list", "kitty/*").stdout
    return [line.strip().lstrip("* ").strip() for line in out.splitlines() if line.strip()]


def test_pr_bound_unprotected_primary_mints_lanes_no_coord(tmp_path: Path) -> None:
    """pr-bound + unprotected primary → LANES, no coord branch minted (#2533, re-keyed WP06/#2602).

    Was ``SINGLE_BRANCH`` before the #5100 binding decision (comment
    5870360497): ``single_branch`` is now explicit-only, so the unreachable
    arm defaults to ``lanes`` instead.
    """
    _init_repo_unprotected(tmp_path)

    payload = _create_pr_bound(tmp_path, "no-strand-single")

    # The mint DECISION: coordination routing is unreachable, so no coord topology.
    assert payload["topology"] == "lanes", payload
    assert payload.get("coordination_branch") is None, payload
    assert payload.get("coordination_branch_created") is False, payload
    # No stranded/mislabelled coordination branch exists on disk.
    assert _kitty_branches(tmp_path) == [], _kitty_branches(tmp_path)


def test_two_concurrent_pr_bound_missions_strand_no_coord_branch(tmp_path: Path) -> None:
    """Two concurrent pr-bound missions on an unprotected primary strand no coord branch."""
    _init_repo_unprotected(tmp_path)

    first = _create_pr_bound(tmp_path, "no-strand-concurrent-a")
    second = _create_pr_bound(tmp_path, "no-strand-concurrent-b")

    for payload in (first, second):
        assert payload["topology"] == "lanes", payload
        assert payload.get("coordination_branch") is None, payload
        assert payload.get("coordination_branch_created") is False, payload

    # Neither mission left a stranded (or cross-labelled) ``kitty/*`` coord branch.
    assert _kitty_branches(tmp_path) == [], _kitty_branches(tmp_path)
