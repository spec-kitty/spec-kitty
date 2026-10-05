"""Shared fixtures for tests/integration suite."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterator, Callable

import pytest

from tests._support.charter_warning import rearmed_charter_warning

# Register the coord-topology test fixture + asserters so they are available
# to every test in the tests/integration/ subtree without a per-file import.
# See tests/integration/conftest_coord_topology.py for the registration facade
# and tests/integration/coord_topology_fixture.py for the implementation.
from tests.integration.conftest_coord_topology import (  # noqa: F401
    coord_topology_mission,
    coord_topology_mission_sentinel_meta,
    coord_topology_mission_tasks_husk,
    flat_topology_mission,
)
from tests._owned_fixtures import RSnapshotter


@pytest.fixture(autouse=True)
def _disable_saas_sync_for_integration_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable the SaaS sync boundary preflight for integration tests.

    The root conftest enables SPEC_KITTY_ENABLE_SAAS_SYNC=1 to keep legacy
    sync/auth tests live, but the planning/commit-boundary integration tests
    invoke ``setup-plan`` which gates on the boundary preflight with
    ``require_auth=True``. Tests run without hosted auth credentials, so the
    gate refuses with SAAS_SYNC_UNAUTHENTICATED before the actual behavior
    being tested can run. These tests don't intentionally test the boundary
    preflight, so we disable the gate here.
    """
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")


# ---------------------------------------------------------------------------
# owned-checkout-lifecycle-authority WP02 (T011): shared owned-checkout
# integration fixtures. Every owned acceptance test (WP08, WP09, WP11-WP13,
# WP18, WP19) builds on these instead of hand-rolling its own R/P pair, so
# the R snapshot (NFR-001) and the stale copy are identical everywhere.
# ---------------------------------------------------------------------------

_MISSION_TYPE = "software-dev"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".kittify").mkdir(exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text("agents:\n  available: [codex]\n", encoding="utf-8")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "seed")
    _git(root, "update-ref", "refs/remotes/origin/main", "main")
    _git(root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")


def _write_mission(mission_dir: Path, *, mission_id: str, slug: str, topology: str, target_branch: str, wp_ids: tuple[str, ...]) -> None:
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": slug,
                "slug": slug,
                "mission_type": _MISSION_TYPE,
                "topology": topology,
                "target_branch": target_branch,
                "flattened": False,
            }
        ),
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text(
        "# Spec\n\n## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "|---|---|---|---|\n| FR-001 | Use owned checkout | Correct path | proposed |\n",
        encoding="utf-8",
    )
    (mission_dir / "plan.md").write_text("# Plan\n\nUse the owned checkout.\n", encoding="utf-8")
    (mission_dir / "tasks.md").write_text("# Tasks\n\n", encoding="utf-8")
    (mission_dir / ".gitignore").write_text(".kittify/derived/\n", encoding="utf-8")
    for wp_id in wp_ids:
        (mission_dir / "tasks" / f"{wp_id}-owned.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Owned fixture task\ndependencies: []\n"
            "requirement_refs: [FR-001]\nsubtasks: []\nowned_files: []\n"
            "authoritative_surface: app.py\nexecution_mode: code_change\n---\n\n# Task\n",
            encoding="utf-8",
        )


def _write_single_lane_manifest(
    mission_dir: Path,
    *,
    mission_slug: str,
    mission_id: str,
    target_branch: str,
    wp_ids: tuple[str, ...],
    topology: str = "single_branch",
) -> None:
    """Write P's own ``lanes.json``: ONE lane covering every requested WP.

    Gives ``stale_root_copy`` something real to differ from (spec §Test
    Layout: "a lane map that differs from P's"). A base-tree reader that
    resolves R's ``stale_root_copy`` must see R's (different) lane
    composition, never silently fall through to P's.

    #5100 Invariant T-1: a ``single_branch`` mission's manifest is the ONE
    repo-root ``lane-planning`` lane (never a code lane -- the finalize writer
    refuses to overwrite one with ``SINGLE_BRANCH_CODE_LANES_UNMIGRATED``);
    every other topology keeps the historical ``lane-a`` code lane.
    """
    from specify_cli.lanes.compute import PLANNING_LANE_ID
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    manifest = LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch=target_branch,
        lanes=[
            ExecutionLane(
                lane_id=PLANNING_LANE_ID if topology == "single_branch" else "lane-a",
                wp_ids=tuple(wp_ids),
                write_scope=(),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-28T00:00:00Z",
        computed_from="test",
    )
    write_lanes_json(mission_dir, manifest)


@dataclass(frozen=True)
class OwnedCheckouts:
    """The R/P/S triple built by :func:`make_owned_checkouts`, plus mission identity."""

    repository_root: Path
    owned_root: Path
    sibling: Path
    mission_slug: str
    mission_id: str
    mid8: str
    target_branch: str
    mission_dir: Path


_DEFAULT_MISSION_ID = "01M2D900000000000000000001"


@pytest.fixture
def make_owned_checkouts(tmp_path: Path) -> Callable[..., OwnedCheckouts]:
    """Factory fixture building an R/P/S owned-checkout triple, without ``spec-kitty init``."""

    def _make(
        *,
        topology: str = "single_branch",
        placement: str = "sibling",
        wp_ids: tuple[str, ...] = ("WP01", "WP02"),
        protected_target: bool = False,
        mission_slug: str = "owned-fixture-01M2D900",
        mission_id: str = _DEFAULT_MISSION_ID,
        target_branch: str = "codex/owned",
    ) -> OwnedCheckouts:
        r_root = tmp_path / "primary"
        _init_repo(r_root)
        if protected_target:
            (r_root / ".kittify" / "config.yaml").write_text(
                f"agents:\n  available: [codex]\nprotection:\n  protected_branches: [{target_branch}]\n",
                encoding="utf-8",
            )
            _git(r_root, "add", ".")
            _git(r_root, "commit", "-qm", "protect target")

        p_root = r_root / ".worktrees" / "owned-a" if placement == "under_worktrees" else tmp_path / "owned"
        _git(r_root, "worktree", "add", "-qb", target_branch, str(p_root))

        sibling = tmp_path / "sibling"
        _git(r_root, "worktree", "add", "-qb", "codex/sibling", str(sibling))

        mission_dir = p_root / "kitty-specs" / mission_slug
        _write_mission(
            mission_dir,
            mission_id=mission_id,
            slug=mission_slug,
            topology=topology,
            target_branch=target_branch,
            wp_ids=wp_ids,
        )
        _write_single_lane_manifest(
            mission_dir,
            mission_slug=mission_slug,
            mission_id=mission_id,
            target_branch=target_branch,
            wp_ids=wp_ids,
            topology=topology,
        )
        _git(p_root, "add", ".")
        _git(p_root, "commit", "-qm", "owned mission")

        return OwnedCheckouts(
            repository_root=r_root,
            owned_root=p_root,
            sibling=sibling,
            mission_slug=mission_slug,
            mission_id=mission_id,
            mid8=mission_id[:8],
            target_branch=target_branch,
            mission_dir=mission_dir,
        )

    return _make


@pytest.fixture
def owned_checkouts(make_owned_checkouts: Callable[..., OwnedCheckouts]) -> OwnedCheckouts:
    return make_owned_checkouts()


@pytest.fixture(params=["slug", "mid8", "mission_id"])
def owned_handle(request: pytest.FixtureRequest, owned_checkouts: OwnedCheckouts) -> str:
    return {
        "slug": owned_checkouts.mission_slug,
        "mid8": owned_checkouts.mid8,
        "mission_id": owned_checkouts.mission_id,
    }[request.param]


def _home_for_snapshot() -> Path | None:
    return Path(os.environ["SPEC_KITTY_HOME"]) if os.environ.get("SPEC_KITTY_HOME") else None


@pytest.fixture
def make_r_snapshot(canonical_home: None) -> Callable[[OwnedCheckouts], RSnapshotter]:
    """Factory fixture: build an :class:`RSnapshotter` for ANY :class:`OwnedCheckouts`.

    ``r_snapshot`` below is a convenience binding to the default
    ``owned_checkouts`` fixture (sibling placement); this factory lets a test
    snapshot R around a checkout it built itself with a non-default
    placement (for example ``make_owned_checkouts(placement="under_worktrees")``),
    which the bound ``r_snapshot`` fixture cannot do (review cycle 1 nit).
    """

    def _make(checkouts: OwnedCheckouts) -> RSnapshotter:
        return RSnapshotter(checkouts.repository_root, checkouts.owned_root, _home_for_snapshot())

    return _make


@pytest.fixture
def r_snapshot(owned_checkouts: OwnedCheckouts, make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter]) -> RSnapshotter:
    return make_r_snapshot(owned_checkouts)


_STALE_COPY_WP_IDS: tuple[str, ...] = ("WP01", "WP02", "WP03", "WP04", "WP05")
_STALE_COPY_DIFFERENT_MISSION_ID = "01M2D900000000000000000099"


@pytest.fixture
def stale_root_copy(
    owned_checkouts: OwnedCheckouts,
) -> Callable[..., Path]:
    """Copy P's mission dir into R with the SAME ``mission_id`` (spec US1-AS1).

    R's copy lists WP01-WP05 (P lists only ``owned_checkouts``' ``wp_ids``,
    WP01-WP02 by default) and, when ``with_lanes`` (the default), carries a
    TWO-lane ``lanes.json`` (lane-a WP01-WP03, lane-b WP04-WP05) that is
    genuinely different from P's single-lane manifest written by
    :func:`_write_single_lane_manifest` -- proving a base-tree reader that
    folds to R sees R's own (different) lane composition rather than P's.
    """

    def _make(*, different_id: bool = False, with_lanes: bool = True) -> Path:
        r_root = owned_checkouts.repository_root
        target = r_root / "kitty-specs" / owned_checkouts.mission_slug
        mission_id = _STALE_COPY_DIFFERENT_MISSION_ID if different_id else owned_checkouts.mission_id
        _write_mission(
            target,
            mission_id=mission_id,
            slug=owned_checkouts.mission_slug,
            topology="single_branch",
            target_branch=owned_checkouts.target_branch,
            wp_ids=_STALE_COPY_WP_IDS,
        )
        if with_lanes:
            from specify_cli.lanes.models import ExecutionLane, LanesManifest
            from specify_cli.lanes.persistence import write_lanes_json

            manifest = LanesManifest(
                version=1,
                mission_slug=owned_checkouts.mission_slug,
                mission_id=mission_id,
                mission_branch=f"kitty/mission-{owned_checkouts.mission_slug}",
                target_branch=owned_checkouts.target_branch,
                lanes=[
                    ExecutionLane(
                        lane_id="lane-a",
                        wp_ids=("WP01", "WP02", "WP03"),
                        write_scope=(),
                        predicted_surfaces=(),
                        depends_on_lanes=(),
                        parallel_group=0,
                    ),
                    ExecutionLane(
                        lane_id="lane-b",
                        wp_ids=("WP04", "WP05"),
                        write_scope=(),
                        predicted_surfaces=(),
                        depends_on_lanes=(),
                        parallel_group=1,
                    ),
                ],
                computed_at="2026-09-28T00:00:00Z",
                computed_from="test",
            )
            write_lanes_json(target, manifest)
        _git(r_root, "add", ".")
        _git(r_root, "commit", "-qm", "stale root copy")
        return target

    return _make


@pytest.fixture(params=["repository_root", "owned_checkout", "elsewhere"])
def owned_cwd(request: pytest.FixtureRequest, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = {
        "repository_root": owned_checkouts.repository_root,
        "owned_checkout": owned_checkouts.owned_root,
        "elsewhere": owned_checkouts.sibling,
    }[request.param]
    monkeypatch.chdir(target)
    return target


@pytest.fixture(autouse=True)
def _rearm_charter_ambient_warning() -> Iterator[None]:
    """Re-arm the once-per-process charter warning around each test (#5714; see tests/_support/charter_warning.py)."""
    with rearmed_charter_warning():
        yield
