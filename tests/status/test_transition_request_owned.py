"""``TransitionRequest.owned`` and the FR-003 / NFR-002 single-validation guarantee.

Owned-checkout-lifecycle-authority WP07 (status pipeline takes the fact).

Covers, in commit order:

- T037: the exactly-one-ownership-validation CLI proof (``finalize-tasks`` /
  ``move-task``), recorded red on the base before T033/T034 land.
- T032: ``TransitionRequest.owned``.
- T033: ``_identity_for_request`` builds the transactional identity from the
  fact with zero re-validation (tripwire), and the mismatch guard.
- T034: the pipeline readers (``bootstrap_canonical_state``,
  ``prepare_transition``) consume the fact without re-validating.
- T035: ``commit_for_mission`` accepts ``owned=`` and commits with zero claim
  calls.
- T036: ``MissionHandle.owned`` threads through the ports.

Facts are minted with ``OwnedCheckout._mint`` directly (contract §1 allows a
``tests/`` helper), mirroring ``tests/mission_runtime/test_owned_checkout.py``.
Never call ``OwnedCheckout(...)`` -- it raises ``TypeError`` by design.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import OwnedCheckout
from mission_runtime.context import MissionTopology
from specify_cli.status.models import TransitionRequest
from tests._owned_fixtures import RSnapshotter
from tests.integration.conftest import (
    OwnedCheckouts,
    make_owned_checkouts,
    make_r_snapshot,
    owned_checkouts,
    r_snapshot,
)

__all__ = ["make_owned_checkouts", "make_r_snapshot", "owned_checkouts", "r_snapshot"]

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


def _mint(
    tmp_path: Path,
    *,
    slug: str = "owned-01M1A900",
    repository_root: Path | None = None,
    owned_root: Path | None = None,
    mission_dir: Path | None = None,
    mission_slug: str | None = None,
    topology: MissionTopology = MissionTopology.SINGLE_BRANCH,
    target_branch: str = "codex/owned",
) -> OwnedCheckout:
    """Mint an ``OwnedCheckout`` fact over a fresh ``tmp_path`` layout.

    Mirrors ``tests/mission_runtime/test_owned_checkout.py::_mint``: every
    field is independently overridable so mismatch cases can construct a
    fact that intentionally disagrees with a request's legacy fields.
    """
    repo = repository_root if repository_root is not None else tmp_path / "repo"
    owned = owned_root if owned_root is not None else tmp_path / "owned"
    mission = mission_dir if mission_dir is not None else owned / "kitty-specs" / slug
    repo.mkdir(parents=True, exist_ok=True)
    mission.mkdir(parents=True, exist_ok=True)
    return OwnedCheckout._mint(
        repository_root=repo,
        owned_root=owned,
        mission_dir=mission,
        mission_slug=mission_slug if mission_slug is not None else mission.name,
        topology=topology,
        write_branch=target_branch,
    )


# ---------------------------------------------------------------------------
# T032 -- TransitionRequest.owned
# ---------------------------------------------------------------------------


def test_owned_field_carries_the_fact(tmp_path: Path) -> None:
    fact = _mint(tmp_path)
    request = TransitionRequest(owned=fact)
    assert request.owned is fact


def test_no_owned_field_is_unchanged(tmp_path: Path) -> None:
    request = TransitionRequest()
    assert request.owned is None


def test_post_construction_mutation_is_visible(tmp_path: Path) -> None:
    """Existing callers set ``owned`` post-construction (a plain mutable dataclass field).

    ``tests/specify_cli/coordination/test_status_transition.py`` relies on it.
    """
    fact = _mint(tmp_path)
    request = TransitionRequest()
    assert request.owned is None
    request.owned = fact
    assert request.owned is fact


# ---------------------------------------------------------------------------
# T033 -- _identity_for_request builds the transactional identity from the
# fact with ZERO re-validation (FR-003, contract §2).
# ---------------------------------------------------------------------------


def _mint_owned_git(tmp_path: Path, *, slug: str = "owned-git-01M1A900") -> OwnedCheckout:
    """Mint a fact whose ``owned_root`` is a real (unmaterialised-meta) git repo.

    ``_identity_for_request`` reads ``meta.json`` under the fact's
    ``mission_dir`` (absent here -> ``meta_exists=False``, exercised fine) and
    -- for the non-legacy branches this WP adds -- never shells out to git for
    ownership at all, so a plain ``git init`` is enough.
    """
    owned_root = tmp_path / "owned-repo"
    repository_root = tmp_path / "primary-repo"
    _init_git_repo(owned_root)
    _init_git_repo(repository_root)
    mission_dir = owned_root / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    return OwnedCheckout._mint(
        repository_root=repository_root,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=slug,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="main",
    )


def _mint_owned_linked_worktree(tmp_path: Path, *, slug: str = "owned-linked-01M1A900") -> OwnedCheckout:
    """Mint a fact whose ``owned_root`` is a REAL ``git worktree`` of ``repository_root``.

    Unlike :func:`_mint_owned_git`, this gives the two roots one shared git
    object database -- required for a real (non-mocked)
    ``BookkeepingTransaction`` commit, which resolves the coordination
    worktree from the primary repository's own worktree list.
    """
    repository_root = tmp_path / "primary-repo"
    _init_git_repo(repository_root)
    (repository_root / "seed.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=repository_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repository_root, check=True)

    owned_root = tmp_path / "owned-checkout"
    subprocess.run(
        ["git", "worktree", "add", "-b", "owned/checkout", str(owned_root), "main"],
        cwd=repository_root,
        check=True,
    )
    mission_dir = owned_root / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    return OwnedCheckout._mint(
        repository_root=repository_root,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=slug,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="main",
    )


def test_identity_for_request_builds_from_the_fact_with_zero_revalidation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A fact-carrying request never re-derives ownership (FR-003 / T033a)."""
    from specify_cli.coordination import status_transition as st

    def _must_not_run(*_a: object, **_k: object) -> object:
        raise AssertionError("an owned fact must never be re-validated")

    monkeypatch.setattr("specify_cli.core.checkout_ownership.resolve_ownership_claim", _must_not_run, raising=False)
    monkeypatch.setattr("specify_cli.core.owned_mission.resolve_owned_mission", _must_not_run)
    monkeypatch.setattr(st, "_repo_root_for_feature", _must_not_run)

    fact = _mint_owned_git(tmp_path)
    request = TransitionRequest(
        feature_dir=fact.mission_dir,
        mission_slug=fact.mission_slug,
        wp_id="WP01",
        to_lane="claimed",
        actor="t033-test",
        owned=fact,
    )
    identity = st._identity_for_request(request)

    assert identity.feature_dir == fact.mission_dir
    assert identity.repo_root == fact.owned_root
    assert identity.owned is fact


def test_identity_for_request_mismatch_on_mission_slug_refuses(tmp_path: Path) -> None:
    """A fact naming a different mission than the request refuses (T033b)."""
    from mission_runtime import ActionContextError
    from specify_cli.coordination import status_transition as st

    fact = _mint_owned_git(tmp_path)
    request = TransitionRequest(
        feature_dir=fact.mission_dir,
        mission_slug="a-different-mission",
        wp_id="WP01",
        to_lane="claimed",
        actor="t033-test",
        owned=fact,
    )

    with pytest.raises(ActionContextError) as refused:
        st._identity_for_request(request)
    assert refused.value.code == "OWNED_MISSION_PATH_REFUSED"


def test_read_events_transactional_with_owned_fact_is_zero_revalidation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``read_events_transactional(owned=fact)`` reads P's events with no re-validation (T033c)."""
    from specify_cli.coordination.status_transition import read_events_transactional

    def _must_not_run(*_a: object, **_k: object) -> object:
        raise AssertionError("an owned fact must never be re-validated")

    monkeypatch.setattr("specify_cli.core.owned_mission.resolve_owned_mission", _must_not_run)

    fact = _mint_owned_git(tmp_path)
    events = read_events_transactional(
        feature_dir=fact.mission_dir,
        mission_slug=fact.mission_slug,
        owned=fact,
    )
    assert events == []


# ---------------------------------------------------------------------------
# T034 -- bootstrap_canonical_state seeds with zero re-validation calls.
# ---------------------------------------------------------------------------


def test_bootstrap_canonical_state_seeds_with_zero_revalidation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``bootstrap_canonical_state(owned=fact)`` seeds WP rows with zero re-derivation (T034)."""
    from specify_cli.status.bootstrap import bootstrap_canonical_state

    def _must_not_run(*_a: object, **_k: object) -> object:
        raise AssertionError("an owned fact must never be re-validated")

    monkeypatch.setattr("specify_cli.core.owned_mission.resolve_owned_mission", _must_not_run)

    import json

    fact = _mint_owned_linked_worktree(tmp_path)
    tasks_dir = fact.mission_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01-example.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Example\n---\nbody\n",
        encoding="utf-8",
    )
    from specify_cli.coordination.workspace import CoordinationWorkspace

    mid8 = fact.mission_slug[:8]
    coord_branch = CoordinationWorkspace.branch_name(fact.mission_slug, mid8)
    (fact.mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": fact.mission_slug,
                "mission_id": fact.mission_slug,
                "mid8": mid8,
                "coordination_branch": coord_branch,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "kitty-specs"], cwd=fact.owned_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=fact.owned_root, check=True)
    subprocess.run(["git", "branch", coord_branch], cwd=fact.repository_root, check=True)

    from specify_cli.core.commit_guard import GuardCapability

    result = bootstrap_canonical_state(
        fact.mission_dir,
        fact.mission_slug,
        owned=fact,
        capability=GuardCapability.TEST_MODE,
    )
    assert result.newly_seeded == 1


# ---------------------------------------------------------------------------
# T035 -- commit_for_mission(owned=fact) commits with zero claim calls.
# ---------------------------------------------------------------------------


def test_commit_for_mission_with_owned_fact_makes_zero_claim_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``commit_for_mission(owned=fact)`` commits on P's branch with no re-validation (T035)."""
    from unittest.mock import patch

    from mission_runtime import CommitTarget
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy

    def _must_not_run(*_a: object, **_k: object) -> object:
        raise AssertionError("an owned fact must never be re-validated")

    monkeypatch.setattr("specify_cli.core.checkout_ownership.resolve_ownership_claim", _must_not_run, raising=False)
    monkeypatch.setattr("specify_cli.core.owned_mission.resolve_owned_mission", _must_not_run)

    fact = _mint_owned_git(tmp_path)
    # The owned arm folds protection through ProtectionPolicy.resolve_for_owned
    # (the fact's two roots' configs): declare "nothing protected" in both.
    for root in (fact.repository_root, fact.owned_root):
        (root / ".kittify").mkdir(parents=True, exist_ok=True)
        (root / ".kittify" / "config.yaml").write_text("protection:\n  protected_branches: []\n", encoding="utf-8")
    plan = fact.mission_dir / "plan.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    policy = ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False)
    placement = CommitTarget(ref="main")

    with (
        patch("specify_cli.coordination.commit_router.resolve_placement_only", return_value=placement),
        patch("specify_cli.coordination.commit_router.safe_commit", return_value=None),
    ):
        from mission_runtime import MissionArtifactKind

        result = commit_for_mission(
            fact.repository_root,
            fact.mission_slug,
            (plan,),
            "Add plan",
            policy,
            kind=MissionArtifactKind.FINALIZED_EXECUTION_PLAN,
            owned=fact,
        )

    assert result.status == "committed"


# ---------------------------------------------------------------------------
# T036 -- MissionHandle.owned threads through the task-command ports
# (review cycle 1 HIGH-2: T036 shipped with zero tests; added here, red-first
# against the pre-T036 source at commit 09f94b0eb, per the Activity Log).
# ---------------------------------------------------------------------------


def test_real_fs_reader_planning_read_dir_routes_through_the_fact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``RealFsReader.planning_read_dir`` with an ``owned`` handle resolves
    P's own mission dir, never the legacy bare-root resolver."""
    from mission_runtime import MissionArtifactKind
    from specify_cli.agent_tasks_ports import MissionHandle, RealFsReader

    def _must_not_run(*_a: object, **_k: object) -> object:
        raise AssertionError("an owned handle must not route through resolve_feature_dir_for_mission")

    monkeypatch.setattr("specify_cli.agent_tasks_ports.resolve_feature_dir_for_mission", _must_not_run)

    fact = _mint_owned_git(tmp_path)
    handle = MissionHandle(fact.repository_root, fact.mission_slug, owned=fact)
    result = RealFsReader().planning_read_dir(handle, kind=MissionArtifactKind.TASKS_INDEX)
    assert result == fact.mission_dir


def test_real_coord_commit_router_feature_write_dir_routes_through_the_fact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``feature_write_dir`` with an ``owned`` handle resolves P's own
    STATUS dir, never the legacy non-owned resolver."""
    from specify_cli.agent_tasks_ports import MissionHandle, RealCoordCommitRouter

    def _must_not_run(*_a: object, **_k: object) -> object:
        raise AssertionError("an owned handle must not route through resolve_feature_dir_for_mission")

    monkeypatch.setattr("specify_cli.agent_tasks_ports.resolve_feature_dir_for_mission", _must_not_run)

    fact = _mint_owned_git(tmp_path)
    handle = MissionHandle(fact.repository_root, fact.mission_slug, owned=fact)
    result = RealCoordCommitRouter().feature_write_dir(handle)
    assert result == fact.mission_dir


def test_commit_artifact_threads_owned_only_for_an_owned_handle(tmp_path: Path) -> None:
    """``commit_artifact`` passes ``owned=fact`` to the injected ``commit_fn``
    for an owned handle, and NO ``owned``/``effective_root`` kwarg at all for
    a non-owned handle (C-001 byte-parity)."""
    from mission_runtime import MissionArtifactKind
    from specify_cli.agent_tasks_ports import MissionHandle, RealCoordCommitRouter
    from specify_cli.git.protection_policy import ProtectionPolicy

    recorded: list[dict[str, object]] = []

    def _record_commit(*_args: object, **kwargs: object) -> object:
        recorded.append(kwargs)
        return type("R", (), {"status": "committed", "placement_ref": "main", "commit_hash": None, "diagnostic": None})()

    fact = _mint_owned_git(tmp_path)
    policy = ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False)

    owned_handle = MissionHandle(fact.repository_root, fact.mission_slug, owned=fact)
    router = RealCoordCommitRouter(commit_fn=_record_commit)
    router.commit_artifact(owned_handle, [fact.mission_dir / "plan.md"], "msg", kind=MissionArtifactKind.FINALIZED_EXECUTION_PLAN, policy=policy)
    assert recorded[-1].get("owned") is fact
    assert "effective_root" not in recorded[-1]

    non_owned_handle = MissionHandle(fact.repository_root, fact.mission_slug)
    router.commit_artifact(non_owned_handle, [fact.mission_dir / "plan.md"], "msg", kind=MissionArtifactKind.FINALIZED_EXECUTION_PLAN, policy=policy)
    assert "owned" not in recorded[-1]
    assert "effective_root" not in recorded[-1]


def test_owned_kwargs_helper_is_empty_for_a_non_owned_mission(tmp_path: Path) -> None:
    from specify_cli.agent_tasks_ports import MissionHandle, _owned_kwargs

    handle = MissionHandle(tmp_path / "repo", "some-mission")
    assert _owned_kwargs(handle) == {}


def test_owned_kwargs_helper_carries_the_fact(tmp_path: Path) -> None:
    from specify_cli.agent_tasks_ports import MissionHandle, _owned_kwargs

    fact = _mint_owned_git(tmp_path)
    handle = MissionHandle(fact.repository_root, fact.mission_slug, owned=fact)
    assert _owned_kwargs(handle) == {"owned": fact}


# ---------------------------------------------------------------------------
# T037 -- NFR-002 exactly-one-ownership-validation proof through the real CLI.
# ---------------------------------------------------------------------------


@pytest.fixture
def claim_counter(monkeypatch: pytest.MonkeyPatch) -> list[Path | None]:
    """Count real calls to ``resolve_ownership_claim`` (T037).

    Patches the module attribute directly (``resolve_owned_mission`` imports
    it lazily inside its function body, per ``owned_mission.py``), so this
    counting wrapper intercepts every call regardless of caller.
    """
    from specify_cli.core import checkout_ownership

    calls: list[Path | None] = []
    original = checkout_ownership.resolve_ownership_claim

    def _counting(claimed_checkout: Path | None, *, resolved_primary: Path) -> object:
        calls.append(claimed_checkout)
        return original(claimed_checkout, resolved_primary=resolved_primary)

    monkeypatch.setattr(checkout_ownership, "resolve_ownership_claim", _counting)
    return calls


def _write_finalizable_tasks_md(checkouts: OwnedCheckouts) -> None:
    """Give the WP02 fixture's ``tasks.md`` real ``## WP<n>`` sections and
    non-empty ``owned_files`` (T037 needs a real, non-``--validate-only``
    ``finalize-tasks`` to run cleanly).

    ``make_owned_checkouts`` writes a bare ``# Tasks\n\n`` placeholder and
    ``owned_files: []`` (fine for tests that never run a real
    ``finalize-tasks``); this WP's T037 proof does, so both are repaired for
    every fixture WP file.
    """
    mission_dir = checkouts.mission_dir
    sections = "\n".join(f"## {wp_id}\n\n**Dependencies**: None\n" for wp_id in ("WP01", "WP02"))
    (mission_dir / "tasks.md").write_text(f"# Tasks\n\n{sections}\n", encoding="utf-8")
    for wp_id in ("WP01", "WP02"):
        wp_file = mission_dir / "tasks" / f"{wp_id}-owned.md"
        wp_file.write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Owned fixture task\ndependencies: []\n"
            f"requirement_refs: [FR-001]\nsubtasks: []\nowned_files: [{wp_id.lower()}.py]\n"
            f"authoritative_surface: {wp_id.lower()}.py\nexecution_mode: code_change\n"
            f"create_intent:\n  - {wp_id.lower()}.py\n---\n\n# Task\n",
            encoding="utf-8",
        )
    subprocess.run(["git", "add", "tasks.md", "tasks"], cwd=mission_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture: WP task sections"], cwd=mission_dir, check=True)


class TestExactlyOneOwnershipValidation:
    """FR-003 / NFR-002 through the real ``finalize-tasks`` / ``move-task`` CLI.

    Uses the WP02 owned-checkout fixture factory (``tests/integration/
    conftest.py``), imported explicitly and re-exported through ``__all__``
    -- fixtures defined in ``tests/integration/conftest.py`` are not
    auto-discovered from ``tests/status/``.
    """

    pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

    def test_finalize_tasks_validates_ownership_exactly_once(
        self,
        owned_checkouts: OwnedCheckouts,
        claim_counter: list[Path | None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.mission import app as mission_app
        from specify_cli.workspace.context import clear_workspace_resolution_caches

        _write_finalizable_tasks_md(owned_checkouts)
        monkeypatch.chdir(owned_checkouts.repository_root)
        clear_workspace_resolution_caches()
        claim_counter.clear()
        result = CliRunner().invoke(
            mission_app,
            [
                "finalize-tasks",
                "--mission",
                owned_checkouts.mission_slug,
                "--owned-checkout",
                str(owned_checkouts.owned_root),
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        assert len(claim_counter) == 1, (
            f"expected exactly one ownership validation; got {len(claim_counter)}. "
            "On the pre-WP07 base this was >= 2: mission_finalize.py's own "
            "validation, plus a re-validation inside bootstrap_canonical_state's "
            "read (bootstrap.py:151-155 -> read_events_transactional(..., "
            "effective_root=P) without the fact)."
        )

    def test_finalize_tasks_flagless_adoption_validates_ownership_exactly_once(
        self,
        owned_checkouts: OwnedCheckouts,
        claim_counter: list[Path | None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """WP13 T074 (FR-021): flagless adoption is ALSO exactly one validation.

        Same fixture and assertion as :meth:`test_finalize_tasks_validates_
        ownership_exactly_once` above, extended (not duplicated) for the
        flagless path: ``cwd`` is P itself and no ``--owned-checkout`` is
        passed, so ``resolve_owned_or_adopt`` takes its ``adopt_owned_
        checkout`` branch instead of its explicit one.
        """
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.mission import app as mission_app
        from specify_cli.workspace.context import clear_workspace_resolution_caches

        _write_finalizable_tasks_md(owned_checkouts)
        monkeypatch.chdir(owned_checkouts.owned_root)
        clear_workspace_resolution_caches()
        claim_counter.clear()
        result = CliRunner().invoke(
            mission_app,
            [
                "finalize-tasks",
                "--mission",
                owned_checkouts.mission_slug,
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        assert len(claim_counter) == 1, f"expected exactly one ownership validation on the flagless path; got {len(claim_counter)}."

    def test_finalize_tasks_without_owned_checkout_validates_zero_times(
        self,
        claim_counter: list[Path | None],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Positive control: proves the counter actually fires (non-vacuity).

        An ORDINARY (non-owned, non-worktree) mission in a fresh repo: the
        ordinary finalize-tasks path must never call the ownership-claim
        primitive at all.
        """
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.mission import app as mission_app
        from specify_cli.workspace.context import clear_workspace_resolution_caches

        repo = tmp_path / "plain-repo"
        _init_git_repo(repo)
        subprocess.run(["git", "checkout", "-qb", "codex/control"], cwd=repo, check=True)
        slug = "control-01M2D999"
        mission_dir = repo / "kitty-specs" / slug
        (mission_dir / "tasks").mkdir(parents=True)
        (mission_dir / "meta.json").write_text(
            '{"mission_id": "01M2D999000000000000000001", "mission_slug": "' + slug + '", '
            '"slug": "' + slug + '", "mission_type": "software-dev", "topology": "single_branch", '
            '"target_branch": "codex/control", "flattened": false}',
            encoding="utf-8",
        )
        (mission_dir / "spec.md").write_text(
            "# Spec\n\n## Functional Requirements\n| ID | Requirement | Acceptance Criteria | Status |\n"
            "|---|---|---|---|\n| FR-001 | Control | Correct path | proposed |\n",
            encoding="utf-8",
        )
        (mission_dir / "plan.md").write_text("# Plan\n\nControl.\n", encoding="utf-8")
        (mission_dir / "tasks.md").write_text("# Tasks\n\n## WP01\n\n**Dependencies**: None\n", encoding="utf-8")
        (mission_dir / "tasks" / "WP01-control.md").write_text(
            "---\nwork_package_id: WP01\ntitle: Control task\ndependencies: []\n"
            "requirement_refs: [FR-001]\nsubtasks: []\nowned_files: [control.py]\n"
            "authoritative_surface: control.py\nexecution_mode: code_change\n"
            "create_intent:\n  - control.py\n---\n\n# Task\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "control mission"], cwd=repo, check=True)

        monkeypatch.chdir(repo)
        clear_workspace_resolution_caches()
        claim_counter.clear()
        result = CliRunner().invoke(
            mission_app,
            ["finalize-tasks", "--mission", slug, "--json"],
        )
        assert result.exit_code == 0, result.output
        assert len(claim_counter) == 0

    def test_move_task_validates_ownership_exactly_once(
        self,
        owned_checkouts: OwnedCheckouts,
        claim_counter: list[Path | None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.mission import app as mission_app
        from specify_cli.cli.commands.agent.tasks import app as tasks_app
        from specify_cli.workspace.context import clear_workspace_resolution_caches

        _write_finalizable_tasks_md(owned_checkouts)
        monkeypatch.chdir(owned_checkouts.repository_root)
        clear_workspace_resolution_caches()
        claim_counter.clear()
        finalize_result = CliRunner().invoke(
            mission_app,
            [
                "finalize-tasks",
                "--mission",
                owned_checkouts.mission_slug,
                "--owned-checkout",
                str(owned_checkouts.owned_root),
                "--json",
            ],
        )
        assert finalize_result.exit_code == 0, finalize_result.output

        clear_workspace_resolution_caches()
        claim_counter.clear()
        result = CliRunner().invoke(
            tasks_app,
            [
                "move-task",
                "WP01",
                "--to",
                "claimed",
                "--mission",
                owned_checkouts.mission_slug,
                "--owned-checkout",
                str(owned_checkouts.owned_root),
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        # [ratchet] (NFR-002 / FR-003): move-task validates ownership exactly
        # once. WP16 moved the four task commands' validation to their Typer
        # edge and threaded the fact through every MissionHandle / seam call,
        # tightening the WP07-era baseline of 5 to 1.
        assert len(claim_counter) == 1, f"expected exactly one ownership validation; got {len(claim_counter)}"

    def test_r_snapshot_unchanged_around_owned_finalize(
        self,
        owned_checkouts: OwnedCheckouts,
        r_snapshot: RSnapshotter,
        claim_counter: list[Path | None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NFR-001: R's own tree is untouched by an owned invocation."""
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.mission import app as mission_app
        from specify_cli.workspace.context import clear_workspace_resolution_caches

        _write_finalizable_tasks_md(owned_checkouts)
        monkeypatch.chdir(owned_checkouts.repository_root)
        clear_workspace_resolution_caches()
        before = r_snapshot.take()
        result = CliRunner().invoke(
            mission_app,
            [
                "finalize-tasks",
                "--mission",
                owned_checkouts.mission_slug,
                "--owned-checkout",
                str(owned_checkouts.owned_root),
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        after = r_snapshot.take()
        r_snapshot.assert_unchanged(before, after, tolerate_status_mutex_for=owned_checkouts.mission_slug)
