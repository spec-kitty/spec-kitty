"""WP03 coordination-branch tests for ``agent mission create``.

Issue #1348 — these tests exercise the topology foundation: every mission
must mint a deterministic per-mission coordination branch
``kitty/mission-<slug>-<mid8>`` parented off the target branch, persist the
ref in ``meta.json``, expose it in the ``--json`` output, and refuse a
divergent re-create unless the operator explicitly opts in.

The pure-helper tests (``ensure_coordination_branch``) cover idempotency,
divergence detection, and force-recreate semantics without booting the CLI.
The integration tests cover the end-to-end behaviour through
``create_mission_core`` and the typer CLI surface.
"""

from __future__ import annotations

import json
import subprocess
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.core.mission_creation import MissionCreationResult

from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.core.mission_creation import create_mission_core
from specify_cli.core.paths import MissionMetaReadError
from specify_cli.missions._create import (
    CoordinationBranchDiverged,
    coordination_branch_name,
    ensure_coordination_branch,
)


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CORE_MODULE = "specify_cli.core.mission_creation"


# ---------------------------------------------------------------------------
# Repo + mission helpers
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(repo: Path) -> None:
    (repo / ".kittify").mkdir(exist_ok=True)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    # A usable project is provisioned: mission creation resolves its mission
    # type through the project's activation set. The WP04 construction-total
    # pivot moved the empty-activation fail-closed to the create boundary
    # (``create_mission_core``), so an unprovisioned fixture now blocks
    # creation with ``CharterPackConfigError`` exactly as a real
    # unprovisioned project would. Declare the built-ins the create tests use.
    (repo / ".kittify" / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n  - documentation\n  - research\n  - plan\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True, check=True)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "commit", "-m", "init", "--allow-empty")


def _mission_summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ").title()
    return {
        "friendly_name": title,
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (f"This mission delivers {title} so product and engineering can move forward with a clear outcome and shared understanding."),
    }


def _mission_summary_args(title: str) -> list[str]:
    """CLI-flag form of ``_mission_summary`` for driving the typer entry point."""
    return [
        "--friendly-name",
        title,
        "--purpose-tldr",
        f"Deliver {title} cleanly for the team.",
        "--purpose-context",
        (f"This mission delivers {title} so product and engineering can move forward with a clear outcome and shared understanding."),
    ]


def _patch_repo_environment(repo: Path) -> list[AbstractContextManager[Any]]:
    """Common patch stack for ``create_mission_core`` against ``repo``."""
    return [
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=repo),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value="main"),
        patch(f"{_CORE_MODULE}._commit_feature_file"),
    ]


def _create(repo: Path, slug: str, **kwargs: Any) -> MissionCreationResult:
    patches = _patch_repo_environment(repo)
    for p in patches:
        p.__enter__()
    try:
        return create_mission_core(repo, slug, **_mission_summary(slug), **kwargs)
    finally:
        for p in reversed(patches):
            p.__exit__(None, None, None)


def _branch_exists(repo: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _branch_sha(repo: Path, branch: str) -> str:
    return _git(repo, "rev-parse", branch).stdout.strip()


def _json_payload_from_output(output: str) -> dict[str, Any]:
    """Return the first JSON object emitted by the CLI."""
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    pytest.fail(f"No JSON payload in CLI output: {output!r}")


# ---------------------------------------------------------------------------
# Pure-helper tests (no CLI, no mission scaffold)
# ---------------------------------------------------------------------------


def test_coordination_branch_name_uses_mid8(tmp_path: Path) -> None:
    """The branch name must include the 8-char ULID prefix as the disambiguator (FR-015)."""
    mission_id = "01KSPTVWZ9ABCDEFGHJKMNPQRS"
    name = coordination_branch_name("my-feature-01KSPTVW", mission_id)
    assert name == "kitty/mission-my-feature-01KSPTVW"
    assert "01KSPTVW" in name
    assert name.startswith("kitty/mission-")


def test_ensure_creates_branch_when_missing(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    main_sha = _branch_sha(tmp_path, "main")

    outcome = ensure_coordination_branch(
        repo_root=tmp_path,
        mission_slug="my-feature-01KSPTVW",
        mission_id="01KSPTVWZ9ABCDEFGHJKMNPQRS",
        target_branch="main",
    )
    assert outcome.created is True
    assert outcome.force_recreated is False
    assert _branch_exists(tmp_path, outcome.branch_name)
    assert _branch_sha(tmp_path, outcome.branch_name) == main_sha


def test_ensure_is_idempotent_when_branch_at_target(tmp_path: Path) -> None:
    """Re-running against an existing branch that is at the target is a silent no-op."""
    _init_repo(tmp_path)
    args = {
        "repo_root": tmp_path,
        "mission_slug": "my-feature-01KSPTVW",
        "mission_id": "01KSPTVWZ9ABCDEFGHJKMNPQRS",
        "target_branch": "main",
    }

    first = ensure_coordination_branch(**args)
    sha_after_first = _branch_sha(tmp_path, first.branch_name)

    second = ensure_coordination_branch(**args)
    assert second.created is False
    assert second.force_recreated is False
    assert second.branch_name == first.branch_name
    assert _branch_sha(tmp_path, second.branch_name) == sha_after_first


def test_ensure_raises_when_branch_diverged(tmp_path: Path) -> None:
    """A branch advanced past the target raises CoordinationBranchDiverged with structured fields."""
    _init_repo(tmp_path)
    args = {
        "repo_root": tmp_path,
        "mission_slug": "my-feature-01KSPTVW",
        "mission_id": "01KSPTVWZ9ABCDEFGHJKMNPQRS",
        "target_branch": "main",
    }
    first = ensure_coordination_branch(**args)
    branch = first.branch_name

    # Advance the coordination branch off the target so it diverges.
    _git(tmp_path, "checkout", branch)
    (tmp_path / "drift.txt").write_text("drifted", encoding="utf-8")
    _git(tmp_path, "add", "drift.txt")
    _git(tmp_path, "commit", "-m", "drift")
    _git(tmp_path, "checkout", "main")

    with pytest.raises(CoordinationBranchDiverged) as exc_info:
        ensure_coordination_branch(**args)

    err = exc_info.value
    assert err.error_code == "COORDINATION_BRANCH_DIVERGED"
    assert err.coordination_branch == branch
    assert err.target_branch == "main"
    payload = err.to_dict()
    assert payload["error_code"] == "COORDINATION_BRANCH_DIVERGED"
    assert payload["coordination_branch"] == branch
    assert payload["target_branch"] == "main"
    assert "next_step" in payload and payload["next_step"]


def test_force_recreate_resets_diverged_branch_to_target(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    args = {
        "repo_root": tmp_path,
        "mission_slug": "my-feature-01KSPTVW",
        "mission_id": "01KSPTVWZ9ABCDEFGHJKMNPQRS",
        "target_branch": "main",
    }
    first = ensure_coordination_branch(**args)
    branch = first.branch_name

    _git(tmp_path, "checkout", branch)
    (tmp_path / "drift.txt").write_text("drifted", encoding="utf-8")
    _git(tmp_path, "add", "drift.txt")
    _git(tmp_path, "commit", "-m", "drift")
    _git(tmp_path, "checkout", "main")

    main_sha = _branch_sha(tmp_path, "main")
    outcome = ensure_coordination_branch(**args, force_recreate=True)
    assert outcome.created is True
    assert outcome.force_recreated is True
    # Reset to target sha — the drift commit is gone from the branch tip.
    assert _branch_sha(tmp_path, outcome.branch_name) == main_sha


# ---------------------------------------------------------------------------
# Integration tests (via create_mission_core)
# ---------------------------------------------------------------------------


def test_mission_create_mints_coordination_branch(tmp_path: Path) -> None:
    """A fresh mission_create call leaves the coordination branch on disk."""
    _init_repo(tmp_path)
    result = _create(tmp_path, "auth-flow")

    assert result.coordination_branch is not None
    assert result.coordination_branch_created is True
    assert result.coordination_branch.startswith("kitty/mission-auth-flow-")
    assert _branch_exists(tmp_path, result.coordination_branch)


def test_mission_create_idempotent_second_run(tmp_path: Path) -> None:
    """Re-creating the same mission slug (slug collision permitted in same dir) is a no-op for the branch.

    Because each ``mission create`` mints a fresh ULID, two calls with the
    same input slug yield *different* mission directories and therefore
    different coordination branch names. The idempotency guarantee at the
    branch level is exercised by directly invoking
    ``ensure_coordination_branch`` twice for the same identity (already
    covered above), and at the mission level we assert that re-running with
    the *same* identity (same mission_id) does not raise.
    """
    _init_repo(tmp_path)
    result = _create(tmp_path, "twice-run")
    mission_id = result.meta["mission_id"]

    # Direct second invocation with the same identity: no error, no churn.
    second = ensure_coordination_branch(
        repo_root=tmp_path,
        mission_slug=result.mission_slug,
        mission_id=mission_id,
        target_branch="main",
    )
    assert second.created is False
    assert second.branch_name == result.coordination_branch


def test_meta_json_contains_coordination_branch(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    result = _create(tmp_path, "persist-meta")

    meta_path = result.feature_dir / "meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    assert meta["coordination_branch"] == result.coordination_branch
    assert meta["coordination_branch"].startswith("kitty/mission-persist-meta-")


def test_create_json_output_contains_coordination_branch(tmp_path: Path) -> None:
    """The CLI ``--json`` payload exposes ``coordination_branch`` at the top level."""
    _init_repo(tmp_path)

    # Patch the CLI's view of project root + branch context so we drive the
    # actual typer entry point through a tmp repo.
    runner = CliRunner()
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value="main"),
        patch(f"{_CORE_MODULE}._commit_feature_file"),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.mission.get_current_branch", return_value="main"),
    ):
        result = runner.invoke(
            mission_app,
            [
                "create",
                "cli-json-test",
                "--json",
                "--target-branch",
                "main",
                "--friendly-name",
                "CLI JSON Test",
                "--purpose-tldr",
                "Validate JSON output includes coordination_branch.",
                "--purpose-context",
                "Issue #1348 — downstream tooling needs the canonical ref in the CLI JSON.",
            ],
        )

    assert result.exit_code == 0, result.output
    # Some lines in stdout may be informational; find the JSON payload.
    payload = None
    for line in result.output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    assert payload is not None, f"No JSON payload in CLI output: {result.output!r}"
    assert payload.get("result") == "success"
    assert "coordination_branch" in payload
    assert payload["coordination_branch"].startswith("kitty/mission-cli-json-test-")
    assert payload["coordination_branch_created"] is True
    assert payload["scaffold_only"] is True
    assert payload["requires_agent_authoring"] is True
    assert payload["plan_guard"] == "SPEC_NOT_SUBSTANTIVE_OR_UNCOMMITTED"


# ---------------------------------------------------------------------------
# Issue #2581 — context-derived topology default
#
# Coordination-bearing topology (coord) mints a coordination branch that a
# non-primary-branch mission (created without --pr-bound) has to be manually
# flattened out of afterwards. The default must instead be derived from
# context: single_branch on a non-primary feature/fork branch with no
# --pr-bound; coord everywhere else (primary branch, --pr-bound, or an
# explicit --topology choice).
# ---------------------------------------------------------------------------


def test_create_on_non_primary_branch_without_pr_bound_defaults_to_single_branch(
    tmp_path: Path,
) -> None:
    """RED before #2581: a feature-branch create with no ``--topology``/``--pr-bound``
    must default to ``single_branch`` and mint NO coordination branch.

    The on-disk repo stays on ``main`` (``resolve_primary_branch`` falls back to
    the real current branch when no ``origin`` is configured); the CLI's view of
    "current branch" is mocked to a feature branch so the derivation sees a
    genuine primary/non-primary mismatch.
    """
    _init_repo(tmp_path)

    runner = CliRunner()
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value="feature/my-fix"),
        patch(f"{_CORE_MODULE}._commit_feature_file"),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.mission.get_current_branch", return_value="feature/my-fix"),
    ):
        result = runner.invoke(
            mission_app,
            [
                "create",
                "feature-branch-default",
                "--json",
                "--target-branch",
                "feature/my-fix",
                *_mission_summary_args("Feature Branch Default"),
            ],
        )

    assert result.exit_code == 0, result.output
    payload = _json_payload_from_output(result.output)
    assert payload["topology"] == "single_branch", payload
    assert payload.get("coordination_branch") is None, payload
    assert payload.get("coordination_branch_created") is False, payload


def test_create_on_primary_branch_still_defaults_to_coord(tmp_path: Path) -> None:
    """Non-regression: a primary-branch create with no ``--topology`` still gets ``coord``."""
    _init_repo(tmp_path)

    runner = CliRunner()
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value="main"),
        patch(f"{_CORE_MODULE}._commit_feature_file"),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.mission.get_current_branch", return_value="main"),
    ):
        result = runner.invoke(
            mission_app,
            [
                "create",
                "primary-branch-default",
                "--json",
                "--target-branch",
                "main",
                *_mission_summary_args("Primary Branch Default"),
            ],
        )

    assert result.exit_code == 0, result.output
    payload = _json_payload_from_output(result.output)
    assert payload["topology"] == "coord", payload
    assert payload["coordination_branch"].startswith("kitty/mission-primary-branch-default-")
    assert payload["coordination_branch_created"] is True


def test_create_pr_bound_on_non_primary_branch_still_defaults_to_coord(tmp_path: Path) -> None:
    """Tripwire (WP02/#2533): ``--pr-bound`` keeps ``coord`` when the primary TARGET is protected.

    FROZEN — this MUST stay green. The checkout is a non-primary feature branch
    (``feature/my-fix``) but the primary target resolves to ``main``, which is in
    the default protected set. ``_resolve_default_topology_phase`` keys
    ``coord_topology_reachable`` on the **primary-target** protection, NOT the
    checkout, so ``coord_topology_reachable(pr_bound=True, primary_protected=True,
    current_is_primary=False)`` is ``True`` → ``coord``.

    If this test FLIPS to ``single_branch`` you keyed on the current checkout
    (unprotected) instead of the primary target (protected) — that is the bug this
    tripwire guards against; fix the keying, do not relax the assertion. The
    complementary "unprotected target → single_branch" case is proven by
    ``tests/regression/test_coord_topology_no_strand.py``.
    """
    _init_repo(tmp_path)

    runner = CliRunner()
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value="feature/my-fix"),
        patch(f"{_CORE_MODULE}._commit_feature_file"),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.mission.get_current_branch", return_value="feature/my-fix"),
    ):
        result = runner.invoke(
            mission_app,
            [
                "create",
                "pr-bound-non-primary",
                "--pr-bound",
                "--json",
                "--target-branch",
                "main",
                *_mission_summary_args("PR Bound Non Primary"),
            ],
        )

    assert result.exit_code == 0, result.output
    payload = _json_payload_from_output(result.output)
    assert payload["topology"] == "coord", payload
    assert payload["coordination_branch"].startswith("kitty/mission-pr-bound-non-primary-")
    assert payload["coordination_branch_created"] is True


def test_create_explicit_topology_overrides_context_derivation(tmp_path: Path) -> None:
    """An explicit ``--topology single_branch`` wins even on the primary branch."""
    _init_repo(tmp_path)

    runner = CliRunner()
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value="main"),
        patch(f"{_CORE_MODULE}._commit_feature_file"),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.mission.get_current_branch", return_value="main"),
    ):
        result = runner.invoke(
            mission_app,
            [
                "create",
                "explicit-topology-override",
                "--json",
                "--target-branch",
                "main",
                "--topology",
                "single_branch",
                *_mission_summary_args("Explicit Topology Override"),
            ],
        )

    assert result.exit_code == 0, result.output
    payload = _json_payload_from_output(result.output)
    assert payload["topology"] == "single_branch", payload
    assert payload.get("coordination_branch") is None, payload


def test_pr_bound_create_json_refuses_with_json_instead_of_prompt_abort(tmp_path: Path) -> None:
    """Issue #1451: ``--pr-bound --json`` must not call the interactive prompt."""
    _init_repo(tmp_path)

    runner = CliRunner()
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value="main"),
        patch(f"{_CORE_MODULE}._commit_feature_file"),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.mission.get_current_branch", return_value="main"),
    ):
        result = runner.invoke(
            mission_app,
            [
                "create",
                "json-pr-bound",
                "--pr-bound",
                "--json",
                "--target-branch",
                "main",
                "--friendly-name",
                "JSON PR Bound",
                "--purpose-tldr",
                "Validate JSON branch-strategy refusal.",
                "--purpose-context",
                "Issue #1451 — scripted callers need machine-parseable output.",
            ],
            input="",
        )

    assert result.exit_code == 1
    assert "Aborted" not in result.output
    assert "Proceed anyway?" not in result.output
    payload = _json_payload_from_output(result.output)
    assert payload["error_code"] == "BRANCH_STRATEGY_CONFIRMATION_REQUIRED"
    assert payload["branch_strategy_gate"] == "confirmation_required"
    assert "already-confirmed" in payload["remediation"]


def test_pr_bound_create_json_already_confirmed_preserves_success_path(tmp_path: Path) -> None:
    """The non-interactive JSON refusal must not break the explicit automation bypass."""
    _init_repo(tmp_path)

    runner = CliRunner()
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value="main"),
        patch(f"{_CORE_MODULE}._commit_feature_file"),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.mission.get_current_branch", return_value="main"),
    ):
        result = runner.invoke(
            mission_app,
            [
                "create",
                "json-pr-bound-confirmed",
                "--pr-bound",
                "--branch-strategy",
                "already-confirmed",
                "--json",
                "--target-branch",
                "main",
                "--friendly-name",
                "JSON PR Bound Confirmed",
                "--purpose-tldr",
                "Validate confirmed PR-bound create.",
                "--purpose-context",
                "Automation can bypass the gate explicitly and still receive JSON.",
            ],
            input="",
        )

    assert result.exit_code == 0, result.output
    payload = _json_payload_from_output(result.output)
    assert payload["result"] == "success"
    meta = json.loads(Path(str(payload["meta_file"])).read_text(encoding="utf-8"))
    assert meta["pr_bound"] is True


def test_pr_bound_create_start_branch_switches_before_scaffold_writes(tmp_path: Path) -> None:
    """Issue #765: recommended PR-bound path must not write mission artifacts on main."""
    _init_repo(tmp_path)

    runner = CliRunner()
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
    ):
        result = runner.invoke(
            mission_app,
            [
                "create",
                "json-pr-bound-branch",
                "--pr-bound",
                "--branch-strategy",
                "already-confirmed",
                "--start-branch",
                "feat/json-pr-bound-branch",
                "--json",
                "--friendly-name",
                "JSON PR Bound Branch",
                "--purpose-tldr",
                "Validate PR-bound feature-branch creation.",
                "--purpose-context",
                "Automation starts a feature branch before writing mission artifacts.",
            ],
            input="",
        )

    assert result.exit_code == 0, result.output
    assert _git(tmp_path, "branch", "--show-current").stdout.strip() == "feat/json-pr-bound-branch"
    payload = _json_payload_from_output(result.output)
    assert payload["result"] == "success"
    assert payload["current_branch"] == "feat/json-pr-bound-branch"
    assert payload["target_branch"] == "feat/json-pr-bound-branch"
    meta_path = Path(str(payload["meta_file"]))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["pr_bound"] is True
    assert meta["target_branch"] == "feat/json-pr-bound-branch"

    rel_meta = meta_path.relative_to(tmp_path).as_posix()
    assert (
        subprocess.run(
            ["git", "-C", str(tmp_path), "cat-file", "-e", f"main:{rel_meta}"],
            capture_output=True,
            check=False,
        ).returncode
        != 0
    )
    assert (
        subprocess.run(
            ["git", "-C", str(tmp_path), "cat-file", "-e", f"feat/json-pr-bound-branch:{rel_meta}"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    committed_meta = json.loads(
        _git(
            tmp_path,
            "show",
            f"feat/json-pr-bound-branch:{rel_meta}",
        ).stdout
    )
    assert committed_meta["pr_bound"] is True
    assert committed_meta["target_branch"] == "feat/json-pr-bound-branch"


def test_start_branch_target_branch_mismatch_refuses_before_switch(tmp_path: Path) -> None:
    """Avoid recording a planning target that differs from the checkout branch."""
    _init_repo(tmp_path)

    runner = CliRunner()
    with patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path):
        result = runner.invoke(
            mission_app,
            [
                "create",
                "json-pr-bound-mismatch",
                "--json",
                "--target-branch",
                "main",
                "--start-branch",
                "feat/json-pr-bound-mismatch",
                "--friendly-name",
                "JSON PR Bound Mismatch",
                "--purpose-tldr",
                "Validate mismatch refusal.",
                "--purpose-context",
                "The CLI must refuse before switching branches or writing artifacts.",
            ],
            input="",
        )

    assert result.exit_code == 1
    payload = _json_payload_from_output(result.output)
    assert payload["error_code"] == "START_BRANCH_TARGET_MISMATCH"
    assert _git(tmp_path, "branch", "--show-current").stdout.strip() == "main"
    assert not _branch_exists(tmp_path, "feat/json-pr-bound-mismatch")
    assert list((tmp_path / "kitty-specs").iterdir()) == []


@pytest.mark.parametrize("branch_preexists", [False, True])
def test_failed_create_restores_original_branch_without_deleting_preexisting_start_branch(
    tmp_path: Path,
    branch_preexists: bool,
) -> None:
    """Issue #3619: early create must roll back its bootstrap branch on failure."""
    _init_repo(tmp_path)
    start_branch = "feat/failing-early-create"
    if branch_preexists:
        _git(tmp_path, "branch", start_branch)

    runner = CliRunner()
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
    ):
        result = runner.invoke(
            mission_app,
            [
                "create",
                "failing-early-create",
                "--start-branch",
                start_branch,
                "--json",
                "--friendly-name",
                "",
                "--purpose-tldr",
                "A valid purpose that reaches core validation.",
                "--purpose-context",
                "A valid context that leaves friendly-name validation as the failure.",
            ],
        )

    assert result.exit_code == 1
    assert "non-empty friendly_name" in result.output
    assert _git(tmp_path, "branch", "--show-current").stdout.strip() == "main"
    assert _branch_exists(tmp_path, start_branch) is branch_preexists
    assert list((tmp_path / "kitty-specs").iterdir()) == []


def test_resume_probe_command_reports_not_found_amid_unrelated_mission(tmp_path: Path) -> None:
    """A successful absence probe stays distinct from generic resolution errors."""
    _init_repo(tmp_path)
    _create(tmp_path, "existing-one")

    runner = CliRunner()
    with (
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.mission._enforce_git_preflight"),
    ):
        result = runner.invoke(
            mission_app,
            [
                "check-prerequisites",
                "--mission",
                "new-one",
                "--resume-probe",
                "--json",
            ],
        )

    assert result.exit_code == 0, result.output
    payload = _json_payload_from_output(result.output)
    assert payload["result"] == "success"
    assert payload["resume_state"] == "not_found"
    assert payload["handle"] == "new-one"


def test_resume_probe_command_returns_nonzero_for_malformed_partial_scaffold(tmp_path: Path) -> None:
    """A partial write is recoverable evidence, never permission to duplicate."""
    _init_repo(tmp_path)
    partial = tmp_path / "kitty-specs" / "partial-01ABCDEF"
    partial.mkdir()
    (partial / "spec.md").write_text("# Partial\n", encoding="utf-8")

    runner = CliRunner()
    with (
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.mission._enforce_git_preflight"),
    ):
        result = runner.invoke(
            mission_app,
            [
                "check-prerequisites",
                "--mission",
                "partial",
                "--resume-probe",
                "--json",
            ],
        )

    assert result.exit_code == 1
    payload = _json_payload_from_output(result.output)
    assert payload["resume_state"] == "malformed"
    assert payload["error_code"] == "MISSION_RESUME_MALFORMED"


@pytest.mark.parametrize("meta_text", ["{not-json}", "[]"])
def test_resume_probe_command_rejects_corrupt_or_non_object_meta(
    tmp_path: Path,
    meta_text: str,
) -> None:
    """Invalid metadata never degrades into duplicate-creation permission."""
    _init_repo(tmp_path)
    feature_dir = tmp_path / "kitty-specs" / "invalid-meta-01ABCDEF"
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text(meta_text, encoding="utf-8")
    (feature_dir / "spec.md").write_text("# Partial\n", encoding="utf-8")

    runner = CliRunner()
    with (
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.mission._enforce_git_preflight"),
    ):
        result = runner.invoke(
            mission_app,
            [
                "check-prerequisites",
                "--mission",
                "invalid-meta",
                "--resume-probe",
                "--json",
            ],
        )

    assert result.exit_code == 1
    payload = _json_payload_from_output(result.output)
    assert payload["resume_state"] == "malformed"
    assert payload["error_code"] == "MISSION_RESUME_MALFORMED"
    assert [path.name for path in (tmp_path / "kitty-specs").iterdir()] == [feature_dir.name]


def test_resume_probe_command_rejects_unreadable_meta(tmp_path: Path) -> None:
    """A typed I/O failure stays fail-closed at the public CLI boundary."""
    _init_repo(tmp_path)
    feature_dir = tmp_path / "kitty-specs" / "unreadable-meta-01ABCDEF"
    feature_dir.mkdir()
    meta_path = feature_dir / "meta.json"
    meta_path.write_text("{}", encoding="utf-8")
    (feature_dir / "spec.md").write_text("# Partial\n", encoding="utf-8")
    read_error = MissionMetaReadError(meta_path, OSError("permission denied"))

    runner = CliRunner()
    with (
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.mission._enforce_git_preflight"),
        patch("specify_cli.core.paths.load_meta_fail_closed", side_effect=read_error),
    ):
        result = runner.invoke(
            mission_app,
            [
                "check-prerequisites",
                "--mission",
                "unreadable-meta",
                "--resume-probe",
                "--json",
            ],
        )

    assert result.exit_code == 1
    payload = _json_payload_from_output(result.output)
    assert payload["resume_state"] == "malformed"
    assert payload["error_code"] == "MISSION_RESUME_MALFORMED"
    assert "permission denied" in " ".join(payload["problems"])
    assert [path.name for path in (tmp_path / "kitty-specs").iterdir()] == [feature_dir.name]


def test_explicit_research_create_keeps_scaffold_meta_and_event_type_coherent(tmp_path: Path) -> None:
    """The pre-create type selection must reach every canonical creation surface."""
    _init_repo(tmp_path)

    result = _create(tmp_path, "research-bootstrap", mission="research")

    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    spec = (result.feature_dir / "spec.md").read_text(encoding="utf-8")
    events = [json.loads(line) for line in (result.feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    created = next(event for event in events if event["event_type"] == "MissionCreated")

    assert meta["mission_type"] == "research"
    assert "# Research Specification" in spec
    assert created["payload"]["mission_type"] == "research"
    assert created["payload"]["mission_slug"] == meta["mission_slug"]
    assert created["payload"]["friendly_name"] == meta["friendly_name"]
    assert created["payload"]["purpose_tldr"] == meta["purpose_tldr"]
    assert created["payload"]["purpose_context"] == meta["purpose_context"]


@pytest.mark.parametrize("branch_preexists", [False, True])
def test_mission_created_persistence_failure_is_nonzero_and_probe_recoverable(
    tmp_path: Path,
    branch_preexists: bool,
) -> None:
    """Create cannot report success without its canonical identity event."""
    _init_repo(tmp_path)
    start_branch = "feat/event-persistence-failure"
    (tmp_path / "user-change.txt").write_text("preserve me\n", encoding="utf-8")
    _git(tmp_path, "add", "user-change.txt")
    staged_before = _git(tmp_path, "diff", "--cached", "--name-only").stdout.splitlines()
    original_start_tip: str | None = None
    if branch_preexists:
        _git(tmp_path, "branch", start_branch)
        original_start_tip = _git(tmp_path, "rev-parse", start_branch).stdout.strip()

    runner = CliRunner()
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch("specify_cli.status.emit_mission_created_local", return_value=None),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
    ):
        result = runner.invoke(
            mission_app,
            [
                "create",
                "event-persistence-failure",
                "--start-branch",
                start_branch,
                "--json",
                *_mission_summary_args("Event Persistence Failure"),
            ],
        )

        probe = runner.invoke(
            mission_app,
            [
                "check-prerequisites",
                "--mission",
                "event-persistence-failure",
                "--resume-probe",
                "--json",
            ],
        )

    assert result.exit_code == 1
    assert "Local canonical MissionCreated persistence failed" in result.output
    assert _git(tmp_path, "branch", "--show-current").stdout.strip() == "main"
    assert _branch_exists(tmp_path, start_branch) is branch_preexists
    if original_start_tip is not None:
        assert _git(tmp_path, "rev-parse", start_branch).stdout.strip() == original_start_tip
    assert _git(tmp_path, "diff", "--cached", "--name-only").stdout.splitlines() == staged_before
    partial_dirs = list((tmp_path / "kitty-specs").iterdir())
    assert len(partial_dirs) == 1

    assert probe.exit_code == 1
    probe_payload = _json_payload_from_output(probe.output)
    assert probe_payload["resume_state"] == "malformed"
    assert "MissionCreated" in " ".join(probe_payload["problems"])
