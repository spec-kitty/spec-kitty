"""Mission-create decision branches no other test exercises (branch-coverage guard).

Each test pins one decision branch of ``specify_cli.core.mission_creation``
that no test exercised before the decomposition (research
``test-remediation.md`` §3, "Missing seam coverage"). Every test passes on
the unchanged base and goes red on a planted break of its branch.

Routes are real wherever a real reproduction exists (real temporary git
repositories, real refs, real git hooks, real on-disk scaffolds). Row 3
(topology corroboration failure) fixes the identity through the private
``_mission_id`` input of ``_create_mission_core_failure_atomic`` (no
patch), so a stale ``meta.json`` can be planted in the exact scaffold
directory the create composes; the corroboration itself runs for real against
that stale meta. One row has no real route and uses fault injection on a
single façade name, with ``raising=True`` so a rename fails loudly:

Patched façade names:
    - ``specify_cli.core.mission_creation.build_mission_created_payload`` --
      row 4 (MissionCreated persisted-payload mismatch): the expected-snapshot
      builder is wrapped so the persisted event differs from it in one field.

Rows 9 and 10 call private helpers directly (``_plan_orphan_scaffold_removal``,
``_rollback_coordination_surface``); the pure decision cores sit behind
those seams.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from ulid import ULID

from mission_runtime import MissionTopology
from specify_cli.core import adapters as origin_adapters
from specify_cli.core import mission_creation
from specify_cli.core.mission_creation import (
    MissionAlreadyExistsError,
    MissionCreationError,
    ProtectedMintRefusedError,
    create_mission_core,
)
from specify_cli.lanes.branch_naming import mission_branch_name, mission_dir_name, resolve_mid8
from specify_cli.mission_metadata import write_meta
from tests._factories.coord_mission import _init_repo_with_target

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MAIN = "main"
_TOPIC = "topic"
_SPECS = "kitty-specs"
_MISSION_BRANCH_GLOB = "kitty/mission-*"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _git_rc(repo: Path, *args: str) -> int:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False).returncode


def _mission_branches(repo: Path) -> list[str]:
    out = _git(repo, "branch", "--list", _MISSION_BRANCH_GLOB, "--format=%(refname:short)")
    return [line for line in out.splitlines() if line.strip()]


def _create(repo: Path, slug: str, *, topology: MissionTopology, target_branch: str, mission_id: str | None = None) -> mission_creation.MissionCreationResult:
    """Create through the public entry, or, when ``mission_id`` fixes the identity, through
    its failure-atomic body's private identity input (no patch)."""
    if mission_id is None:
        return create_mission_core(repo, slug, topology=topology, target_branch=target_branch, allow_worktree_context=True)
    return mission_creation._create_mission_core_failure_atomic(
        repo,
        slug,
        topology=topology,
        target_branch=target_branch,
        allow_worktree_context=True,
        _mission_id=mission_id,
    )


def _commit_gitkeep_under_specs(repo: Path) -> None:
    """Track ``kitty-specs/`` so ``git status`` lists its children individually.

    Without a tracked entry git collapses a wholly-untracked ``kitty-specs/``
    to one line, which hides the component-wise overlap the tests probe.
    """
    (repo / _SPECS).mkdir(exist_ok=True)
    (repo / _SPECS / ".gitkeep").touch()
    _git(repo, "add", f"{_SPECS}/.gitkeep")
    _git(repo, "commit", "-m", "chore(fixture): track kitty-specs")


def _plant_prior_mission(
    repo: Path,
    dir_name: str,
    *,
    meta: dict[str, Any] | None,
    commit_spec: bool,
    status_log: str | None = None,
) -> Path:
    """Write a prior same-key mission directory on disk (raw git, no create path)."""
    prior = repo / _SPECS / dir_name
    prior.mkdir(parents=True)
    (prior / "spec.md").write_text("# Prior spec\n\nSubstantive content.\n", encoding="utf-8")
    if meta is not None:
        (prior / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if status_log is not None:
        (prior / "status.events.jsonl").write_text(status_log, encoding="utf-8")
    if commit_spec:
        _git(repo, "add", f"{_SPECS}/{dir_name}/spec.md")
        _git(repo, "commit", "-m", f"chore(fixture): commit prior {dir_name} spec")
    return prior


# ---------------------------------------------------------------------------
# Protected-mint branches (rows 1-2)
# ---------------------------------------------------------------------------


class TestProtectedMintBranches:
    """Rows 1-2: ``_mint_protected_single_branch_mission_branch`` refusals."""

    def test_row1_dirty_checkout_outside_scaffold_refuses_mint(self, tmp_path: Path) -> None:
        """Row 1: operator dirt outside the scaffold refuses the protected mint, naming the path."""
        repo = _init_repo_with_target(tmp_path, target_branch=_MAIN, protected_primary=True)
        (repo / "operator-notes.txt").write_text("unrelated work in progress\n", encoding="utf-8")
        main_tip = _git(repo, "rev-parse", _MAIN)

        with pytest.raises(MissionCreationError) as excinfo:
            _create(repo, "row-one", topology=MissionTopology.SINGLE_BRANCH, target_branch=_MAIN)

        message = str(excinfo.value)
        assert type(excinfo.value) is ProtectedMintRefusedError  # #5704: disposable, no orphan scaffold
        assert "Cannot mint the protected-target mission branch" in message
        assert "has uncommitted changes outside this mission's own scaffold: operator-notes.txt" in message
        assert "Commit or discard them, then retry." in message
        # Refused before any ref mutation: still on main, no mission branch.
        assert _git(repo, "branch", "--show-current") == _MAIN
        assert _git(repo, "rev-parse", _MAIN) == main_tip
        assert _mission_branches(repo) == []

    def test_row1_untracked_files_inside_own_scaffold_are_not_dirt(self, tmp_path: Path) -> None:
        """Row 1 overlap rule: untracked files inside this mission's own scaffold (and ``.kittify``)
        never count as dirty, while a same-prefix sibling directory does."""
        repo = _init_repo_with_target(tmp_path, target_branch=_MAIN, protected_primary=True)
        _commit_gitkeep_under_specs(repo)
        mission_id = str(ULID())
        slug_formatted = mission_dir_name("row-one", mid8=resolve_mid8("", mission_id=mission_id))
        own = repo / _SPECS / slug_formatted
        (own / "tasks").mkdir(parents=True)
        (own / "spec.md").write_text("scaffold\n", encoding="utf-8")
        (own / "tasks" / "extra-untracked.md").write_text("still this mission's own scaffold\n", encoding="utf-8")
        (repo / ".kittify" / "untracked-runtime.txt").write_text("owned\n", encoding="utf-8")

        meta: dict[str, Any] = {}
        mission_creation._mint_protected_single_branch_mission_branch(
            repo,
            slug_formatted,
            mission_id=mission_id,
            target_branch=_MAIN,
            meta=meta,
        )

        minted = mission_branch_name(slug_formatted, mission_id=mission_id)
        assert meta["mission_branch"] == minted
        assert _git(repo, "branch", "--show-current") == minted

        # Precision: a sibling mission dir sharing the prefix is NOT this scaffold.
        _git(repo, "checkout", _MAIN)
        _git(repo, "branch", "-D", minted)
        sibling = repo / _SPECS / f"{slug_formatted}-sibling"
        sibling.mkdir()
        (sibling / "notes.md").write_text("someone else's work\n", encoding="utf-8")
        with pytest.raises(MissionCreationError, match="outside this mission's own scaffold"):
            mission_creation._mint_protected_single_branch_mission_branch(
                repo,
                slug_formatted,
                mission_id=mission_id,
                target_branch=_MAIN,
                meta={},
            )

    def test_row2_checkout_b_failure_raises_typed_error(self, tmp_path: Path) -> None:
        """Row 2: a branch literally named ``kitty`` makes ``refs/heads/kitty/...`` uncreatable
        (directory/file ref conflict): the existence probe says "absent", then ``checkout -b`` fails."""
        repo = _init_repo_with_target(tmp_path, target_branch=_MAIN, protected_primary=True)
        _git(repo, "branch", "kitty")
        main_tip = _git(repo, "rev-parse", _MAIN)

        with pytest.raises(MissionCreationError) as excinfo:
            _create(repo, "row-two", topology=MissionTopology.SINGLE_BRANCH, target_branch=_MAIN)

        message = str(excinfo.value)
        assert type(excinfo.value) is MissionCreationError
        assert message.startswith("Failed to create and check out mission branch 'kitty/mission-row-two-")
        assert "from 'main'" in message
        assert "cannot lock ref" in message
        assert _git(repo, "branch", "--show-current") == _MAIN
        assert _git(repo, "rev-parse", _MAIN) == main_tip
        assert _mission_branches(repo) == []


# ---------------------------------------------------------------------------
# Meta and event branches (rows 3-6)
# ---------------------------------------------------------------------------


_HOOK_REFUSE = 'case "$(git rev-parse --abbrev-ref HEAD)" in\n  kitty/mission-*) echo "refused by test hook" >&2; exit 1 ;;\nesac\nexit 0\n'


def _install_hook_refusing_mission_branch_commits(repo: Path) -> None:
    """Real fault: a ``pre-commit`` hook that refuses any commit on ``kitty/mission-*``.

    Hooks live in the common git dir, so the coordination worktree runs it too.
    ``core.hooksPath`` is pinned repo-locally so a global setting cannot bypass it.
    """
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook = hooks_dir / "pre-commit"
    hook.write_text("#!/bin/sh\n" + _HOOK_REFUSE, encoding="utf-8")
    hook.chmod(0o755)
    _git(repo, "config", "core.hooksPath", str(hooks_dir))


class _RecordingOriginConsumer:
    """A pending-origin consumer registered through the public ``core.adapters`` API."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, repo_root: Path, feature_dir: Path, meta: dict[str, Any]) -> tuple[bool, bool, str | None, dict[str, Any]]:
        self.calls.append({"repo_root": repo_root, "feature_dir": feature_dir})
        bound = dict(meta)
        bound["origin_ticket"] = {"provider": "test", "key": "branch-cov-1"}
        write_meta(feature_dir, bound)
        return True, True, None, bound


@pytest.fixture
def origin_consumer() -> Any:
    """Register a recording consumer; restore whatever was registered before."""
    previous = origin_adapters._origin_consumer
    consumer = _RecordingOriginConsumer()
    origin_adapters.register_pending_origin_consumer(consumer)
    try:
        yield consumer
    finally:
        if previous is None:
            origin_adapters.reset_origin_consumer()
        else:
            origin_adapters.register_pending_origin_consumer(previous)


class TestMetaAndEventBranches:
    """Rows 3-6: ``_build_create_meta``, ``_emit_create_events``,
    ``_commit_coord_create_events`` and ``_commit_create_scaffold`` branches."""

    def test_row3_topology_corroboration_failure_refuses(self, tmp_path: Path) -> None:
        """Row 3: a stale ``meta.json`` carrying a ``coordination_branch`` in the exact scaffold
        dir makes a SINGLE_BRANCH create corroborate as COORD, which is refused."""
        repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC, protected_primary=True)
        pinned = ULID()
        slug_formatted = mission_dir_name("row-three", mid8=resolve_mid8("", mission_id=str(pinned)))
        # Genesis-shaped stale prior (spec uncommitted, no events): the #4033
        # guard treats it as abandoned, so the create reaches the corroboration.
        _plant_prior_mission(
            repo,
            slug_formatted,
            meta={"mission_type": "software-dev", "coordination_branch": "kitty/mission-stale-coord"},
            commit_spec=False,
        )

        with pytest.raises(MissionCreationError) as excinfo:
            _create(repo, "row-three", topology=MissionTopology.SINGLE_BRANCH, target_branch=_TOPIC, mission_id=str(pinned))

        assert type(excinfo.value) is MissionCreationError
        assert str(excinfo.value) == (
            f"Topology corroboration failed for '{slug_formatted}': stored 'single_branch' but the minted coordination state classifies as 'coord'."
        )

    def test_row4_persisted_mission_created_payload_mismatch_refuses(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Row 4: the persisted MissionCreated payload differs from the canonical snapshot."""
        repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC, protected_primary=True)
        real_builder = mission_creation.build_mission_created_payload

        def _drifted_snapshot(**kwargs: Any) -> dict[str, Any]:
            payload: dict[str, Any] = dict(real_builder(**kwargs))
            payload["friendly_name"] = "drifted from the persisted event"
            return payload

        monkeypatch.setattr(mission_creation, "build_mission_created_payload", _drifted_snapshot, raising=True)

        with pytest.raises(MissionCreationError) as excinfo:
            _create(repo, "row-four", topology=MissionTopology.SINGLE_BRANCH, target_branch=_TOPIC)

        message = str(excinfo.value)
        assert message.startswith("Local canonical MissionCreated persistence failed for 'row-four-")
        assert "persisted MissionCreated event does not match the canonical creation snapshot" in message
        assert isinstance(excinfo.value.__cause__, MissionCreationError)
        assert str(excinfo.value.__cause__) == "persisted MissionCreated event does not match the canonical creation snapshot"

    def test_row5_coordination_commit_failure_rolls_back_coord_surface(self, tmp_path: Path) -> None:
        """Row 5: the creation-events commit onto the coordination branch fails (a real
        ``pre-commit`` hook refuses it); the failed-create rollback leaves no coordination
        branch or worktree behind (a create invariant)."""
        repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC, protected_primary=True)
        _install_hook_refusing_mission_branch_commits(repo)
        topic_tip = _git(repo, "rev-parse", _TOPIC)

        with pytest.raises(MissionCreationError) as excinfo:
            _create(repo, "row-five", topology=MissionTopology.COORD, target_branch=_TOPIC)

        message = str(excinfo.value)
        assert message.startswith("Failed to commit mission-creation events onto the coordination branch for 'row-five-")
        assert "status='error'" in message
        assert "refused by test hook" in message
        assert _mission_branches(repo) == []
        assert "row-five" not in _git(repo, "worktree", "list", "--porcelain")
        assert list(repo.glob(".worktrees/row-five*")) == []
        assert _git(repo, "branch", "--show-current") == _TOPIC
        assert _git(repo, "rev-parse", _TOPIC) == topic_tip

    def test_row6_scaffold_commit_bootstrap_skip_on_protected_target(self, tmp_path: Path) -> None:
        """Row 6a: LANES on protected ``main`` -- the scaffold commit is a disclosed bootstrap
        skip (``ProtectedBranchRefused``): no commit lands, the scaffold is reported uncommitted."""
        repo = _init_repo_with_target(tmp_path, target_branch=_MAIN, protected_primary=True)
        main_tip = _git(repo, "rev-parse", _MAIN)

        result = _create(repo, "row-six", topology=MissionTopology.LANES, target_branch=_MAIN)

        feature_dir = result.feature_dir
        assert _git(repo, "rev-parse", _MAIN) == main_tip, "a bootstrap skip must not create any commit"
        assert _git(repo, "branch", "--show-current") == _MAIN
        assert set(result.uncommitted_files) == {
            feature_dir / "spec.md",
            feature_dir / "meta.json",
            feature_dir / "tasks" / "README.md",
            feature_dir / "tasks" / ".gitkeep",
            feature_dir / "status.events.jsonl",
        }
        assert _git(repo, "ls-files", f"{_SPECS}/{result.mission_slug}") == ""
        assert (feature_dir / "meta.json").is_file()

    def test_row6_origin_binding_commit_bootstrap_skip(self, tmp_path: Path, origin_consumer: _RecordingOriginConsumer) -> None:
        """Row 6b (``:1821-1822``): after a successful origin binding, the origin-ticket meta
        commit is ALSO a disclosed bootstrap skip on the protected target -- no commit, no raise."""
        repo = _init_repo_with_target(tmp_path, target_branch=_MAIN, protected_primary=True)
        main_tip = _git(repo, "rev-parse", _MAIN)

        result = _create(repo, "row-six-origin", topology=MissionTopology.LANES, target_branch=_MAIN)

        assert len(origin_consumer.calls) == 1
        assert result.origin_binding_attempted is True
        assert result.origin_binding_succeeded is True
        assert result.origin_binding_error is None
        assert result.meta["origin_ticket"] == {"provider": "test", "key": "branch-cov-1"}
        assert _git(repo, "rev-parse", _MAIN) == main_tip, "neither the scaffold nor the origin-binding commit may land"
        meta_file = result.feature_dir / "meta.json"
        assert meta_file in result.uncommitted_files
        assert json.loads(meta_file.read_text(encoding="utf-8"))["origin_ticket"]["key"] == "branch-cov-1"
        assert _git(repo, "ls-files", f"{_SPECS}/{result.mission_slug}") == ""


# ---------------------------------------------------------------------------
# Duplicates and rollback branches (rows 7-10)
# ---------------------------------------------------------------------------


class TestDuplicateAndRollbackBranches:
    """Rows 7-10: duplicate scan, abandonment read, orphan planning, coord rollback."""

    def test_row7_duplicate_scan_fails_closed_on_missing_meta(self, tmp_path: Path) -> None:
        """Row 7: a same-slug prior dir with NO ``meta.json`` is treated as LIVE."""
        repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC, protected_primary=True)
        _plant_prior_mission(repo, "row-seven-ABCDEFGH", meta=None, commit_spec=True)

        with pytest.raises(MissionAlreadyExistsError) as excinfo:
            _create(repo, "row-seven", topology=MissionTopology.SINGLE_BRANCH, target_branch=_TOPIC)

        assert excinfo.value.error_code == "MISSION_ALREADY_EXISTS"
        assert "already exists and is not abandoned: row-seven-ABCDEFGH (mid8 ABCDEFGH)" in str(excinfo.value)
        assert sorted(p.name for p in (repo / _SPECS).iterdir()) == ["row-seven-ABCDEFGH"], "refused before any scaffold write"

    def test_row8_abandonment_read_failure_treats_prior_as_live(self, tmp_path: Path) -> None:
        """Row 8: a prior whose ``status.events.jsonl`` is corrupt cannot be classified, so it is LIVE.

        The prior is otherwise genesis-shaped (spec.md deliberately NOT committed,
        unlike the other duplicate setups): were the corrupt
        log read as "no events", the prior would be abandoned and the create
        allowed, so only the fail-closed ``StoreError`` branch refuses here.
        """
        repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC, protected_primary=True)
        _plant_prior_mission(
            repo,
            "row-eight-ABCDEFGH",
            meta={"mission_type": "software-dev", "mid8": "ABCDEFGH"},
            commit_spec=False,
            status_log="this line is not json\n",
        )

        with pytest.raises(MissionAlreadyExistsError) as excinfo:
            _create(repo, "row-eight", topology=MissionTopology.SINGLE_BRANCH, target_branch=_TOPIC)

        assert "already exists and is not abandoned: row-eight-ABCDEFGH (mid8 ABCDEFGH)" in str(excinfo.value)
        assert sorted(p.name for p in (repo / _SPECS).iterdir()) == ["row-eight-ABCDEFGH"]

    def test_row9_orphan_planning_skips_same_prefix_neighbour(self, tmp_path: Path) -> None:
        """Row 9: ``task-list`` plans ``task-list-<mid8>`` but never ``task-list-api-<mid8>``."""
        repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC, protected_primary=True)
        own = repo / _SPECS / "task-list-01ABCDEF"
        neighbour = repo / _SPECS / "task-list-api-01ABCDEF"
        for scaffold in (own, neighbour):
            scaffold.mkdir(parents=True)
            (scaffold / "spec.md").write_text("untracked scaffold\n", encoding="utf-8")

        planned = mission_creation._plan_orphan_scaffold_removal(
            repo,
            mission_slug="task-list",
            pre_existing_scaffolds=frozenset(),
        )

        assert planned == (own,)

    def test_row10_coord_rollback_without_anchor_leaves_reused_branch_alone(self, tmp_path: Path) -> None:
        """Row 10: a reused (not created) coordination branch with no recorded pre-seed tip is
        neither deleted nor reset by the coordination rollback."""
        repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC, protected_primary=True)
        coordination_branch = "kitty/mission-row-ten-01ABCDEF"
        _git(repo, "branch", coordination_branch, _TOPIC)
        # Move the branch past the topic tip so any reset/delete is observable.
        _git(repo, "checkout", "-q", coordination_branch)
        (repo / "coord-history.txt").write_text("another create's history\n", encoding="utf-8")
        _git(repo, "add", "coord-history.txt")
        _git(repo, "commit", "-q", "-m", "chore: prior coordination history")
        _git(repo, "checkout", "-q", _TOPIC)
        tip_before = _git(repo, "rev-parse", coordination_branch)

        ctx = mission_creation._CoordCreateRollbackContext(
            repo_root=repo,
            mission_slug_formatted="row-ten-01ABCDEF",
            mid8="01ABCDEF",
            coordination_branch=coordination_branch,
            coordination_branch_created=False,
            pre_seed_coord_tip=None,
        )
        mission_creation._rollback_coordination_surface(ctx)

        assert _git_rc(repo, "rev-parse", "--verify", f"refs/heads/{coordination_branch}") == 0
        assert _git(repo, "rev-parse", coordination_branch) == tip_before
