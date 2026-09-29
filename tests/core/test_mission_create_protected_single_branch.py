"""Protected-target single_branch mission-branch mint (WP08 / #5100 T034-T036).

Covers:

* T034 (remainder) -- ``read_commit_to_target``: absent -> ``False``; a
  non-bool value raises ``CommitToTargetMetaError`` (fail-closed, never
  truthiness-coerced).
* T035 -- ``mission create``'s create-time mint: a protected-target
  single_branch mission mints and checks out
  ``kitty/mission-<slug>-<mid8>``, records it in ``meta.json``, and refuses
  when that branch already exists; ``--commit-to-target`` skips the mint;
  an unprotected target and a ``lanes``-topology mission are unaffected
  (controls).
* T036 -- the write-target arm: ``core.owned_mission.expected_write_branch``
  resolves ``mission_branch`` over ``target_branch`` when set; a status
  transition on a protected single_branch mission commits to
  ``mission_branch`` with no ``SafeCommitHeadMismatch``; switching the write
  checkout to the target branch makes ``implement`` refuse, naming
  ``mission_branch``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionTopology
from specify_cli import app as root_app
from specify_cli.core.mission_creation import MissionCreationError, create_mission_core

from tests._factories import make_mission, provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _seed_repo(tmp_path: Path, *, name: str, branch: str = "main") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-b", branch)
    _git(repo, "config", "user.email", "wp08@example.invalid")
    _git(repo, "config", "user.name", "WP08 Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo


def _minted_branch_name(slug: str, mission_id: str) -> str:
    from specify_cli.lanes.branch_naming import mission_branch_name

    return mission_branch_name(slug, mission_id=mission_id)


# ---------------------------------------------------------------------------
# T034 (remainder): read_commit_to_target
# ---------------------------------------------------------------------------


def test_read_commit_to_target_absent_is_false() -> None:
    from specify_cli.core.paths import read_commit_to_target

    assert read_commit_to_target(None) is False
    assert read_commit_to_target({}) is False
    assert read_commit_to_target({"other_field": 1}) is False


def test_read_commit_to_target_true() -> None:
    from specify_cli.core.paths import read_commit_to_target

    assert read_commit_to_target({"commit_to_target": True}) is True


def test_read_commit_to_target_non_bool_raises() -> None:
    from specify_cli.core.paths import CommitToTargetMetaError, read_commit_to_target

    with pytest.raises(CommitToTargetMetaError):
        read_commit_to_target({"commit_to_target": "true"})
    with pytest.raises(CommitToTargetMetaError):
        read_commit_to_target({"commit_to_target": 1})


# ---------------------------------------------------------------------------
# T035: create-time mint
# ---------------------------------------------------------------------------


def test_protected_target_mints_and_checks_out_mission_branch(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, name="protected-mint")
    result = make_mission(
        repo,
        "protected-mint-mission",
        topology=MissionTopology.SINGLE_BRANCH,
        target_branch="main",
    )

    minted = _minted_branch_name(result.mission_slug, str(result.meta.get("mission_id", "")))
    assert _git(repo, "branch", "--show-current") == minted
    assert result.meta.get("mission_branch") == minted
    assert not (repo / ".worktrees").exists()
    # The scaffold commit landed on the minted branch, not on main: main's
    # tip must still be the original seed commit.
    main_tip = _git(repo, "rev-parse", "main")
    seed_tip = _git(repo, "rev-list", "--max-parents=0", "HEAD")
    assert main_tip == seed_tip


def test_commit_to_target_flag_skips_mint(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, name="commit-to-target")
    result = make_mission(
        repo,
        "commit-to-target-mission",
        topology=MissionTopology.SINGLE_BRANCH,
        target_branch="main",
        commit_to_target=True,
    )

    assert result.meta.get("mission_branch") is None
    assert result.meta.get("commit_to_target") is True
    assert _git(repo, "branch", "--show-current") == "main"
    mission_refs = _git(repo, "for-each-ref", "--format=%(refname)", "refs/heads/kitty/mission-*")
    assert mission_refs == ""


@pytest.mark.parametrize("topology", [MissionTopology.LANES, MissionTopology.COORD])
def test_commit_to_target_rejected_unless_single_branch(tmp_path: Path, topology: MissionTopology) -> None:
    """A4: ``--commit-to-target`` is single_branch-only; create refuses it for
    any other topology and persists nothing."""
    repo = _seed_repo(tmp_path, name=f"ctt-{topology.value}")

    with pytest.raises(MissionCreationError, match="single_branch"):
        make_mission(repo, "ctt-wrong-topology", topology=topology, target_branch="main", commit_to_target=True)

    assert not (repo / "kitty-specs" / "ctt-wrong-topology").exists()


def test_existing_mission_branch_name_refuses_create(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pre-existing branch matching the deterministic mint name refuses
    create with MISSION_BRANCH_EXISTS, naming the branch. A fixed ULID
    (monkeypatched) makes the minted name deterministic so the collision can
    be pre-created."""
    from ulid import ULID as _ULID

    repo = _seed_repo(tmp_path, name="existing-branch")
    provision_test_charter(repo)

    from specify_cli.lanes.branch_naming import mission_branch_name

    fixed_mission_id = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    forced_name = mission_branch_name("existing-branch-b", mission_id=fixed_mission_id)
    _git(repo, "branch", forced_name)

    monkeypatch.setattr(
        "specify_cli.core.mission_creation.ULID",
        lambda: _ULID.from_str(fixed_mission_id),
    )
    with pytest.raises(MissionCreationError, match="already exists") as exc_info:
        create_mission_core(
            repo,
            "existing-branch-b",
            topology=MissionTopology.SINGLE_BRANCH,
            target_branch="main",
            allow_worktree_context=True,
            friendly_name="Existing Branch B",
            purpose_tldr="Refused by an existing mission branch.",
            purpose_context="This mission must be refused because its minted branch name already exists on disk.",
        )
    # Discriminates the DEDICATED pre-check (error_code) from git's own
    # generic `checkout -b` failure, which would ALSO raise a
    # MissionCreationError matching "already exists" in its message (a
    # weaker assertion a mutation deleting the dedicated check can still
    # satisfy).
    assert exc_info.value.error_code == "MISSION_BRANCH_EXISTS"
    assert forced_name in str(exc_info.value)


def test_unprotected_target_no_mint(tmp_path: Path) -> None:
    """Control: an UNPROTECTED target never mints a mission branch."""
    repo = _seed_repo(tmp_path, name="unprotected")
    _git(repo, "checkout", "-b", "issue-work")
    result = make_mission(
        repo,
        "unprotected-mission",
        topology=MissionTopology.SINGLE_BRANCH,
        target_branch="issue-work",
    )
    assert result.meta.get("mission_branch") is None
    mission_refs = _git(repo, "for-each-ref", "--format=%(refname)", "refs/heads/kitty/mission-*")
    assert mission_refs == ""


def test_lanes_topology_protected_target_unchanged(tmp_path: Path) -> None:
    """Control: a `lanes`-topology mission on a protected target is
    untouched by the single_branch mint -- no `mission_branch` field."""
    repo = _seed_repo(tmp_path, name="lanes-protected")
    result = make_mission(
        repo,
        "lanes-protected-mission",
        topology=MissionTopology.LANES,
        target_branch="main",
    )
    assert result.meta.get("mission_branch") is None
    assert _git(repo, "branch", "--show-current") == "main"


# ---------------------------------------------------------------------------
# T036: expected_write_branch / write-target arm
# ---------------------------------------------------------------------------


def test_expected_write_branch_prefers_mission_branch() -> None:
    from specify_cli.core.owned_mission import expected_write_branch
    from specify_cli.git.protection_policy import ProtectionPolicy

    meta = {"target_branch": "main", "mission_branch": "kitty/mission-x-aaaaaaaa"}
    policy = ProtectionPolicy(protected_branches=frozenset({"main"}), operator_hatch_active=False)
    assert expected_write_branch(meta, policy, "main") == "kitty/mission-x-aaaaaaaa"


def test_expected_write_branch_falls_back_to_target() -> None:
    from specify_cli.core.owned_mission import expected_write_branch
    from specify_cli.git.protection_policy import ProtectionPolicy

    meta = {"target_branch": "issue-work"}
    policy = ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False)
    assert expected_write_branch(meta, policy, "main") == "issue-work"


def _finalized_protected_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, **create_overrides: object) -> tuple[Path, str, str, Path]:
    """Protected single_branch mission with one code WP, finalized, checkout on mission_branch."""
    repo = _seed_repo(tmp_path, name=name)
    result = make_mission(repo, f"{name}-mission", topology=MissionTopology.SINGLE_BRANCH, target_branch="main", **create_overrides)
    slug, feature_dir = result.mission_slug, result.feature_dir
    minted = str(result.meta["mission_branch"])
    (feature_dir / "spec.md").write_text("# Spec\n\n## Functional Requirements\n\n- **FR-001**: repro.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n\n**Language/Version**: Python 3.11\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n\n- [ ] T001 alpha\n", encoding="utf-8")
    (feature_dir / "tasks").mkdir(exist_ok=True)
    (feature_dir / "tasks" / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: First code WP\ndependencies: []\n"
        "requirement_refs: [FR-001]\nexecution_mode: code_change\nowned_files: [src/wp01.py]\n"
        "authoritative_surface: src/wp01.py\nsubtasks: [T001]\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "wp01.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"seed mission {slug}")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    finalize = runner.invoke(root_app, ["agent", "mission", "finalize-tasks", "--mission", slug, "--json"], catch_exceptions=False)
    assert finalize.exit_code == 0, finalize.output
    return repo, slug, minted, feature_dir


def test_status_transition_commits_to_mission_branch_not_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """W1: the REAL committing status path (`implement` claim via the commit
    router) lands a NEW commit carrying the status change on `mission_branch`;
    the protected target never moves."""
    repo, slug, minted, _feature_dir = _finalized_protected_mission(tmp_path, monkeypatch, "status-commit")
    main_before = _git(repo, "rev-parse", "main")
    tip_before = _git(repo, "rev-parse", minted)

    implement = runner.invoke(root_app, ["implement", "WP01", "--mission", slug, "--json"])
    assert implement.exit_code == 0, implement.output

    tip_after = _git(repo, "rev-parse", minted)
    assert tip_after != tip_before, "the claim transition must commit a NEW tip on mission_branch"
    changed = _git(repo, "diff", "--name-only", tip_before, tip_after).splitlines()
    assert any(path.endswith("status.events.jsonl") for path in changed), changed
    assert _git(repo, "rev-parse", "main") == main_before, "the protected target must never move"
    assert _git(repo, "branch", "--show-current") == minted


def test_implement_wrong_branch_refused_naming_mission_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US3.2: with the write checkout switched to another branch, `implement`
    on the protected mission is refused, naming `mission_branch`."""
    repo, mission_slug, minted, _feature_dir = _finalized_protected_mission(tmp_path, monkeypatch, "wrong-branch")

    # Switch the write checkout to a branch OTHER than the expected
    # mission_branch. `kitty-specs/<mission>/` only exists on `mission_branch`
    # pre-consolidate, so a bare `git checkout main` would make the mission
    # itself unresolvable (a different failure entirely) -- merge the mission
    # branch's content onto a fresh branch off `main` instead, so the
    # mission is resolvable but the CURRENT branch name still mismatches.
    _git(repo, "checkout", "-b", "operator-mistake", "main")
    _git(repo, "merge", "--no-ff", "-m", "merge for wrong-branch test", minted)

    implement_result = runner.invoke(root_app, ["implement", "WP01", "--mission", mission_slug])

    assert implement_result.exit_code != 0
    assert minted in implement_result.output, implement_result.output


# ---------------------------------------------------------------------------
# W2: context resolver's authoritative_ref honours mission_branch
# ---------------------------------------------------------------------------


def _resolver_project(tmp_path: Path, *, mission_branch: str | None) -> tuple[Path, str]:
    import json

    from tests.lane_test_utils import write_single_lane_manifest

    slug = "047-resolver-mission"
    (tmp_path / ".kittify").mkdir(parents=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("vcs:\n  type: git\nproject:\n  uuid: test-uuid-resolver-0001\n  slug: test-proj\n", encoding="utf-8")
    feature_dir = tmp_path / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_slug": slug,
        "mission": "software-dev",
        "target_branch": "main",
        "topology": "single_branch",
        "created_at": "2026-03-27T16:00:00+00:00",
    }
    if mission_branch:
        meta["mission_branch"] = mission_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (feature_dir / "tasks" / "WP01-x.md").write_text(
        '---\nwork_package_id: WP01\ntitle: T\nlane: planned\ndependencies: []\nexecution_mode: code_change\nowned_files:\n- "src/**"\n---\n\n# WP01\n',
        encoding="utf-8",
    )
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), lane_id="lane-planning", mission_id=slug, predicted_surfaces=("src",))
    return tmp_path, slug


def test_authoritative_ref_is_mission_branch_for_protected_mission(tmp_path: Path) -> None:
    from specify_cli.context import resolve_context

    repo, slug = _resolver_project(tmp_path, mission_branch="kitty/mission-x-01ARZ3ND")
    ctx = resolve_context("WP01", slug, "claude", repo)
    assert ctx.authoritative_ref == "kitty/mission-x-01ARZ3ND"
    assert ctx.target_branch == "main", "the mission's real target must not be rewritten"


def test_authoritative_ref_is_target_when_no_mission_branch(tmp_path: Path) -> None:
    """Control: unprotected / commit_to_target mission keeps the target branch."""
    from specify_cli.context import resolve_context

    repo, slug = _resolver_project(tmp_path, mission_branch=None)
    assert resolve_context("WP01", slug, "claude", repo).authoritative_ref == "main"


# ---------------------------------------------------------------------------
# Recovery + doctor never classify the minted mission_branch as lane/coord/orphan
# (branch name is shared with the coord branch by design -- readers key on topology)
# ---------------------------------------------------------------------------


def test_minted_mission_branch_not_classified_by_recovery_or_doctor(tmp_path: Path) -> None:
    from specify_cli.cli.commands._coordination_doctor import _collect_coordination_findings
    from specify_cli.cli.commands._identity_audit import _topology_finding
    from specify_cli.lanes.recovery import _list_mission_branches, scan_recovery_state
    from tests.lane_test_utils import write_single_lane_manifest

    repo = _seed_repo(tmp_path, name="recovery-doctor")
    result = make_mission(repo, "recovery-doctor-mission", topology=MissionTopology.SINGLE_BRANCH, target_branch="main")
    slug, minted = result.mission_slug, str(result.meta["mission_branch"])
    write_single_lane_manifest(result.feature_dir, wp_ids=("WP01",), lane_id="lane-planning", mission_id=slug)

    # Non-vacuous precondition: the recovery glob DOES see the minted branch.
    assert minted in _list_mission_branches(repo, slug)

    # Recovery: not a lane branch -> no recovery state for it.
    assert scan_recovery_state(repo, slug, consult_status_events=False) == []

    # Doctor: no topology finding, and no coordination finding names the branch.
    assert _topology_finding("single_branch", result.feature_dir) is None
    findings = _collect_coordination_findings(repo, mission_filter=slug)
    assert not [f for f in findings if minted in str(f.message) or minted in str(f.extra)], findings
