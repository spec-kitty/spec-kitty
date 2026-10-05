"""WP02 (#2533 write-side twin) -- partition-aware planning-artifact commit.

FR-003 / INV-1: ``_commit_planning_artifacts_transaction`` (implement.py)
pre-fix committed EVERY file in ``files_to_commit`` through ONE
``BookkeepingTransaction`` to ONE ``destination_ref``. On a coord mission
that ref is the coordination branch, so a genuinely-dirty PRIMARY artifact
(e.g. ``spec.md``) would be committed onto coordination -- never the
primary/target branch. This module pins the fix: the commit is partitioned
into a PRIMARY group (-> the mission's target/planning branch) and a
COORD-residue group (-> the coordination branch), using the SAME
``is_coordination_artifact_residue_path`` predicate WP01 wired into the
read-side ``resolve_precondition_ref`` (one authority, NFR-004).

Modeled on ``test_implement_placement_routing.py``'s
``TestEnsurePlanningArtifactsRoutesThroughPlacementRef`` (monkeypatch
``BookkeepingTransaction`` to capture each ``acquire()`` call's
``destination_ref`` + the paths written under it, rather than driving a real
coordination-branch commit through the full policy/lock machinery).

Realistic ``planning_branch``: a real mission's target/feature branch is
NEVER ``main``/``master`` (see this mission's own ``meta.json``
``target_branch``: ``mission/2533-pr-bound-coord-claim-precondition``) --
``main``/``master`` are protected by default and
``BookkeepingTransaction``/``safe_commit`` refuse ANY commit onto a
protected ref under standard capability (mirrored by
``commit_router._commit_partition_group``'s own protected-primary-target
refusal). Every test below therefore uses a non-protected, mission-branch-
shaped ``planning_branch``, matching real dogfooding data.
"""

from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_PLANNING_BRANCH = "mission/2533-wp02-writeside-demo"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(repo: Path, *, branch: str) -> None:
    repo.mkdir()
    _git(repo, "init", "-q", "-b", branch)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "initial")


def _make_meta(
    feature_dir: Path,
    *,
    with_coord: bool,
    mission_id: str,
    mission_slug: str,
    target_branch: str,
) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "mission_id": mission_id,
        "mission_slug": mission_slug,
        "mid8": mission_id[:8],
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "created_at": "2026-07-14T00:00:00+00:00",
        "friendly_name": "WP02 write-side partition test",
    }
    if with_coord:
        payload["coordination_branch"] = f"kitty/mission-{mission_slug}-{mission_id[:8]}"
    (feature_dir / "meta.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


class _FakeTxn:
    """Records the (destination_ref, [paths written]) of one ``acquire()`` call."""

    def __init__(self, destination_ref: str, calls: list[tuple[str, list[str]]]) -> None:
        self._destination_ref = destination_ref
        self._paths: list[str] = []
        self._calls = calls

    def __enter__(self) -> _FakeTxn:
        return self

    def __exit__(self, *_exc: object) -> bool:
        self._calls.append((self._destination_ref, list(self._paths)))
        return False

    def write_artifact(self, repo_path: Path, _content: bytes) -> None:
        self._paths.append(repo_path.as_posix())

    def commit(self, _msg: str) -> None:
        return None

    def commit_idempotent(self, _msg: str) -> None:
        # WP02 / T009: ``_run_planning_artifact_commit`` now uses the
        # crash-recovery-safe idempotent re-drive; the fake records the same way.
        return None


def _fake_bookkeeping_transaction(calls: list[tuple[str, list[str]]]) -> type:
    class _FakeBookkeepingTransaction:
        @classmethod
        def acquire(cls, **kwargs: object) -> _FakeTxn:
            return _FakeTxn(str(kwargs["destination_ref"]), calls)

    return _FakeBookkeepingTransaction


def _seeded_coord_mission(
    tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, str, str, str, list[tuple[str, list[str]]]]:
    """Build a coord mission with a committed ``spec.md`` baseline and a
    real (but empty) coordination branch, then monkeypatch
    ``BookkeepingTransaction`` to record every ``acquire()`` call.

    Module-level (not a method) so it can be shared across test classes --
    including ``TestNarrowTripleProtectedPlanningBranchFailsClosed`` (#2648
    / WP01) -- without a ``self``-type mismatch under ``mypy --strict``.

    Returns ``(repo, feature_dir, mission_slug, spec_rel, events_rel, calls)``.
    """
    repo = tmp_path / "repo"
    _init_repo(repo, branch=_PLANNING_BRANCH)

    mission_slug = "wp02-writeside-demo"
    mission_id = "01J9WP02WRITESIDEXXXXXXXXX"
    mid8 = mission_id[:8]
    coord_branch = f"kitty/mission-{mission_slug}-{mid8}"
    _git(repo, "branch", coord_branch)

    feature_dir = repo / "kitty-specs" / mission_slug
    _make_meta(
        feature_dir,
        with_coord=True,
        mission_id=mission_id,
        mission_slug=mission_slug,
        target_branch=_PLANNING_BRANCH,
    )

    spec_md = feature_dir / "spec.md"
    spec_md.write_text("# Spec\noriginal\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed feature dir")

    # Genuinely-dirty PRIMARY artifact: differs from the committed HEAD
    # baseline, uncommitted in the working tree.
    spec_md.write_text("# Spec\nrevised\n", encoding="utf-8")

    # Dirty COORD-residue artifact: new/untracked.
    status_events = feature_dir / "status.events.jsonl"
    status_events.write_text('{"event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV"}\n', encoding="utf-8")

    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        "specify_cli.coordination.transaction.BookkeepingTransaction",
        _fake_bookkeeping_transaction(calls),
    )

    spec_rel = f"kitty-specs/{mission_slug}/spec.md"
    events_rel = f"kitty-specs/{mission_slug}/status.events.jsonl"
    return repo, feature_dir, mission_slug, spec_rel, events_rel, calls


class TestPartitionAwarePlanningArtifactCommit:
    """T006/T007: a genuinely-dirty PRIMARY artifact lands on the
    primary/target ref; a dirty COORD-residue artifact still lands on the
    coordination ref -- via two transactions, not one collapsed commit.
    """

    def test_dirty_primary_lands_on_target_dirty_coord_lands_on_coord(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RED (pre-fix): both files commit through ONE transaction to the
        coordination branch -- ``spec.md`` (a PRIMARY kind) would land on
        coordination, never ``_PLANNING_BRANCH``. GREEN (post-fix): the
        batch is partitioned into two transactions -- ``spec.md`` lands on
        ``_PLANNING_BRANCH``, ``status.events.jsonl`` lands on the
        coordination branch.
        """
        from specify_cli.cli.commands.implement_planning_commit import _commit_planning_artifacts_transaction

        repo, feature_dir, mission_slug, spec_rel, events_rel, calls = _seeded_coord_mission(
            tmp_path, monkeypatch=monkeypatch
        )
        mission_id = "01J9WP02WRITESIDEXXXXXXXXX"
        coord_branch = f"kitty/mission-{mission_slug}-{mission_id[:8]}"

        _commit_planning_artifacts_transaction(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            planning_branch=_PLANNING_BRANCH,
            files_to_commit=[spec_rel, events_rel],
            commit_msg="chore: planning artifacts for wp02-writeside-demo",
            placement_ref=None,
        )

        spec_destinations = [ref for ref, paths in calls if spec_rel in paths]
        events_destinations = [ref for ref, paths in calls if events_rel in paths]

        assert spec_destinations == [_PLANNING_BRANCH], (
            f"expected spec.md (PRIMARY) to be committed to the primary/target "
            f"ref {_PLANNING_BRANCH!r}; got {spec_destinations!r} (all calls: {calls!r})"
        )
        assert events_destinations == [coord_branch], (
            f"expected status.events.jsonl (COORD-residue) to be committed to "
            f"the coordination branch {coord_branch!r}; got {events_destinations!r} "
            f"(all calls: {calls!r})"
        )
        # Two separate transactions -- never a single collapsed commit that
        # mixes both partitions under one destination_ref.
        assert len(calls) == 2, f"expected two transactions, got {calls!r}"

    def test_only_dirty_primary_uses_a_single_transaction(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the batch is entirely PRIMARY, only one transaction runs, to
        the primary/target ref -- no spurious empty coordination commit."""
        from specify_cli.cli.commands.implement_planning_commit import _commit_planning_artifacts_transaction

        repo, feature_dir, mission_slug, spec_rel, _events_rel, calls = _seeded_coord_mission(
            tmp_path, monkeypatch=monkeypatch
        )

        _commit_planning_artifacts_transaction(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            planning_branch=_PLANNING_BRANCH,
            files_to_commit=[spec_rel],
            commit_msg="chore: planning artifacts for wp02-writeside-demo",
            placement_ref=None,
        )

        assert calls == [(_PLANNING_BRANCH, [spec_rel])]


class TestNonCoordinationMissionCommitCollapsesToOneTransaction:
    """Regression guard: single-branch/flat/legacy missions (no
    ``coordination_branch``) must keep committing everything through ONE
    transaction to ``planning_branch`` -- the partition split is additive and
    must not touch this path (mirrors ``commit_router._group_files_by_partition``'s
    own fast-path collapse when there is no genuine ref divergence)."""

    def test_no_coord_branch_collapses_primary_and_coord_shaped_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.cli.commands.implement_planning_commit import _commit_planning_artifacts_transaction

        repo = tmp_path / "repo"
        _init_repo(repo, branch=_PLANNING_BRANCH)

        mission_slug = "wp02-flat-demo"
        mission_id = "01J9WP02FLATDEMOXXXXXXXXXX"
        feature_dir = repo / "kitty-specs" / mission_slug
        _make_meta(
            feature_dir,
            with_coord=False,
            mission_id=mission_id,
            mission_slug=mission_slug,
            target_branch=_PLANNING_BRANCH,
        )
        spec_md = feature_dir / "spec.md"
        spec_md.write_text("# Spec\n", encoding="utf-8")
        status_events = feature_dir / "status.events.jsonl"
        status_events.write_text('{"event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAW"}\n', encoding="utf-8")

        calls: list[tuple[str, list[str]]] = []
        monkeypatch.setattr(
            "specify_cli.coordination.transaction.BookkeepingTransaction",
            _fake_bookkeeping_transaction(calls),
        )

        spec_rel = f"kitty-specs/{mission_slug}/spec.md"
        events_rel = f"kitty-specs/{mission_slug}/status.events.jsonl"

        _commit_planning_artifacts_transaction(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            planning_branch=_PLANNING_BRANCH,
            files_to_commit=[spec_rel, events_rel],
            commit_msg="chore: planning artifacts for wp02-flat-demo",
            placement_ref=None,
        )

        # Even a coord-shaped path (status.events.jsonl) collapses onto the
        # single planning_branch transaction -- there is no coordination
        # branch for a flat/legacy mission to divide between.
        assert calls == [(_PLANNING_BRANCH, [spec_rel, events_rel])]


class TestNarrowTripleProtectedPlanningBranchFailsClosed:
    """#2648 (WP01): the narrow triple -- ``placement_ref is None`` AND the
    meta-derived ``coord_branch`` is truthy AND ``is_protected(planning_branch)``
    -- must fail closed with :class:`PlacementResolutionRequired` instead of
    silently diverting the whole dirty-PRIMARY batch to the coordination
    branch (the pre-fix ``767`` arm). This is EXACTLY the precondition where
    the status-commit half (``_resolve_claim_commit_target``) already raises,
    so both halves of a claim now agree.

    Uses the same module-level ``_seeded_coord_mission`` harness as
    ``TestPartitionAwarePlanningArtifactCommit`` (coord mission, genuinely-
    dirty PRIMARY ``spec.md``) but passes a protected ``planning_branch``
    (``"main"``) instead of the harness's non-protected default -- this
    function only ever inspects the ``planning_branch`` *string* via
    ``ProtectionPolicy.is_protected``, never the repo's actual checked-out
    branch, so overriding the argument is sufficient to hit the narrow
    triple without re-seeding the repo on ``main``.
    """

    def test_protected_planning_branch_raises_placement_resolution_required(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.cli.commands.implement_planning_commit import _commit_planning_artifacts_transaction
        from specify_cli.cli.commands.implement_cores import (
            _resolve_claim_commit_target,
        )
        from specify_cli.core.errors import PlacementResolutionRequired

        repo, feature_dir, mission_slug, spec_rel, events_rel, calls = _seeded_coord_mission(
            tmp_path, monkeypatch=monkeypatch
        )

        with pytest.raises(PlacementResolutionRequired) as excinfo:
            _commit_planning_artifacts_transaction(
                repo_root=repo,
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                planning_branch="main",
                files_to_commit=[spec_rel, events_rel],
                commit_msg="chore: planning artifacts for wp02-writeside-demo",
                placement_ref=None,
            )

        # SC-002: byte-identical operator remediation message as the
        # status-commit half, so both halves are indistinguishable to the
        # operator.
        try:
            _resolve_claim_commit_target(None, mission_slug=mission_slug)
        except PlacementResolutionRequired as status_half_exc:
            assert str(excinfo.value) == str(status_half_exc)
        else:  # pragma: no cover -- _resolve_claim_commit_target(None) always raises
            pytest.fail("_resolve_claim_commit_target(None) unexpectedly did not raise")

        # No transaction of any kind (coord or primary) ran -- the fail-close
        # is loud, not a partial/silent commit to either ref.
        assert calls == []


class TestSeamAPartitionGuard:
    """WP02 / T011 / FR-002 / C-008: the Seam-A guard on the kind-agnostic
    ``BookkeepingTransaction`` planning-commit seam. A PRIMARY kind reaching the
    coord commit (or a COORD kind reaching a primary/lane commit) raises the SAME
    ``PrimaryKindReachedCoordStagingError`` the ``commit_for_mission`` classifier
    already raises -- with ``meta.json`` (and spec-kitty's other self-bookkeeping)
    exempted BEFORE kind classification so a coord status commit co-travelling
    ``meta.json`` is NOT falsely refused.
    """

    _SLUG = "seam-a-demo"

    def _p(self, name: str) -> str:
        return f"kitty-specs/{self._SLUG}/{name}"

    def test_coord_status_commit_with_meta_cotravel_succeeds(self) -> None:
        """POSITIVE (C-008): a COORD-destination commit carrying the status log
        AND ``meta.json`` must NOT raise -- ``meta.json`` is self-bookkeeping,
        exempted before the ``PRIMARY_METADATA``->coord classification."""
        from specify_cli.coordination.planning_commit import guard_planning_commit_partition

        # No raise.
        guard_planning_commit_partition(
            [self._p("status.events.jsonl"), self._p("meta.json")],
            destination_is_coord=True,
        )

    def test_primary_kind_reaching_coord_raises(self) -> None:
        """NEGATIVE (PRIMARY->coord): a PRIMARY ``lanes.json`` on a coord
        destination is the #3371 mis-route -- fail loud."""
        from specify_cli.coordination.planning_commit import guard_planning_commit_partition
        from specify_cli.coordination.commit_router import (
            PrimaryKindReachedCoordStagingError,
        )

        with pytest.raises(PrimaryKindReachedCoordStagingError):
            guard_planning_commit_partition(
                [self._p("lanes.json")], destination_is_coord=True
            )

    def test_coord_kind_reaching_primary_or_lane_raises(self) -> None:
        """NEGATIVE (COORD->primary/lane): a coord-residue status file on a
        PRIMARY/lane destination is the #2549 mis-route -- fail loud."""
        from specify_cli.coordination.planning_commit import guard_planning_commit_partition
        from specify_cli.coordination.commit_router import (
            PrimaryKindReachedCoordStagingError,
        )

        with pytest.raises(PrimaryKindReachedCoordStagingError):
            guard_planning_commit_partition(
                [self._p("status.events.jsonl")], destination_is_coord=False
            )

    def test_primary_commit_with_meta_and_lanes_succeeds(self) -> None:
        """POSITIVE: a PRIMARY-destination commit carrying ``lanes.json`` +
        ``meta.json`` is the correct partition -- no raise."""
        from specify_cli.coordination.planning_commit import guard_planning_commit_partition

        guard_planning_commit_partition(
            [self._p("lanes.json"), self._p("meta.json")],
            destination_is_coord=False,
        )


class TestBannerConstantsHoisted:
    """S1192 campsite (T008): the workspace-ready banner's rich-markup
    open/close tags were repeated ~8x in ``_print_workspace_ready_banner`` --
    hoisted to ``_BANNER_OPEN``/``_BANNER_CLOSE`` module constants. The
    distinct ``title="[bold yellow]...[/]"`` uses elsewhere in this module
    (bulk-edit inference banners) use a different close tag and are
    untouched."""

    def test_banner_constants_match_the_original_markup(self) -> None:
        from specify_cli.cli.commands.implement import _BANNER_CLOSE, _BANNER_OPEN

        assert _BANNER_OPEN == "[bold yellow]"
        assert _BANNER_CLOSE == "[/bold yellow]"

    def test_print_workspace_ready_banner_uses_the_constants(self) -> None:
        from specify_cli.cli.commands.implement import _print_workspace_ready_banner

        source = inspect.getsource(_print_workspace_ready_banner)
        assert "_BANNER_OPEN" in source
        assert "_BANNER_CLOSE" in source
        # No more inline literal restatements of the banner markup inside
        # this function -- the campsite fold replaced every one of them.
        assert '"[bold yellow]"' not in source
        assert '"[/bold yellow]"' not in source


class TestRepoRootBannerWording:
    """A5: a single_branch repo-root code WP (lane_id set, branch set, repo_root
    resolution) must get repo-root wording, never the self-contradicting lane
    worktree banner."""

    @staticmethod
    def _render(**overrides: object) -> str:
        from types import SimpleNamespace

        from specify_cli.cli.commands import implement as impl

        result = SimpleNamespace(lane_id="lane-planning", resolution_kind="repo_root", branch_name="issue-5100-work", lane_test_env={})
        for key, value in overrides.items():
            setattr(result, key, value)
        with impl.console.capture() as capture:
            impl._print_workspace_ready_banner(result, Path("."))
        return capture.get()

    def test_repo_root_code_wp_uses_repo_root_wording(self) -> None:
        text = self._render()
        assert "Lane worktree ready" not in text
        assert "lane worktree" not in text.lower()
        assert "critical error" not in text.lower()
        assert "repository root checkout on branch issue-5100-work" in text

    def test_real_lane_worktree_keeps_lane_banner(self) -> None:
        text = self._render(lane_id="lane-a", resolution_kind="lane_workspace")
        assert "Lane worktree ready" in text


class TestPlanningCommitBranch:
    """A3: the "planning artifacts must be committed on <branch>" message and
    commit target name the ACTUAL write branch for mission-branch missions."""

    @staticmethod
    def _resolve(monkeypatch: pytest.MonkeyPatch, meta: dict[str, object] | None) -> str:
        from specify_cli.cli.commands import implement_planning_commit as impl
        from specify_cli.coordination import planning_commit

        monkeypatch.setattr(planning_commit, "load_primary_anchored_mission_meta", lambda _r, _s: meta)
        return impl._planning_commit_branch(Path("."), "m", "main")

    def test_single_branch_mission_branch_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        meta = {"topology": "single_branch", "mission_branch": "kitty/mission-m-01ABCDEF"}
        assert self._resolve(monkeypatch, meta) == "kitty/mission-m-01ABCDEF"

    def test_single_branch_without_mission_branch_keeps_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._resolve(monkeypatch, {"topology": "single_branch"}) == "main"

    def test_other_topology_or_missing_meta_keeps_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._resolve(monkeypatch, {"topology": "lanes", "mission_branch": "x"}) == "main"
        assert self._resolve(monkeypatch, None) == "main"

    def test_refusal_message_names_the_mission_branch_not_the_protected_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Full message path: the branch fed to the "must be committed on" refusal
        is the mission branch, so it names it and never the protected ``main``."""
        import typer

        from specify_cli.cli.commands import implement_planning_commit as impl
        from specify_cli.coordination import planning_commit

        mission_branch = "kitty/mission-m-01ABCDEF"
        meta = {"topology": "single_branch", "mission_branch": mission_branch}
        monkeypatch.setattr(planning_commit, "load_primary_anchored_mission_meta", lambda _r, _s: meta)
        planning_branch = impl._planning_commit_branch(Path("."), "m", "main")

        with impl.console.capture() as capture, pytest.raises(typer.Exit):
            impl._print_planning_artifact_commit_instructions("some-other-branch", planning_branch, True, Path("kitty-specs/m"), "m")
        text = capture.get()

        assert f"Planning artifacts must be committed on {mission_branch}" in text
        assert "committed on main" not in text
