"""Shared real-allocator divergent-shape fixture builders (#5108).

Mission ``lane-branch-naming-authority-01M3EVC4``. Every builder here produces
one of US1's divergent lane-naming shapes through the **real lane-creation
path** (:func:`allocate_lane_worktree`) — never by hand-composing a branch
name with a Mission identity. That is exactly the defect this mission fixes
(the reconciliation claim reading a name built from ``mission_id`` instead of
the lane's *created* branch), so the fixture must not reproduce it.

A leading underscore keeps this module out of pytest collection (it is a
helper module, not a test file) — see ``tests/merge/test_reconciliation_divergent.py``
for its consumer today; other consumers are expected to import it too.

Each shape pins a mission slug / mission_id / recorded ``mission_branch``
combination from the divergent-naming spec's literal table. The lane branches and
worktrees always come from the allocator's own return value — a shape never
asserts a lane branch as a fixture literal.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kernel.clock import now_utc_iso
from specify_cli.lanes.branch_naming import strip_numeric_prefix
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.models import ReviewResult, TransitionRequest

_TARGET_BRANCH = "main"
_APPROVE_LANES: tuple[str, ...] = ("claimed", "in_progress", "for_review", "in_review")


@dataclass(frozen=True)
class DivergentMission:
    """One divergent-shape mission built through the real allocator.

    Attributes:
        repo_root: The tmp git repo root.
        feature_dir: ``kitty-specs/<slug>`` inside *repo_root*.
        slug: The mission slug recorded in ``lanes.json`` / ``meta.json``.
        mission_id: The (possibly invalid) mission identity recorded alongside
            the slug — a divergence input, never a naming input.
        manifest: The written :class:`LanesManifest`.
        lanes: ``lane_id -> (worktree_path_or_repo_root, branch)``, exactly
            what :func:`allocate_lane_worktree` returned (or, for the
            planning lane, ``(repo_root, target_branch)``).
        coord_base_sha: The commit the lane branches diverge from.
    """

    repo_root: Path
    feature_dir: Path
    slug: str
    mission_id: str
    manifest: LanesManifest
    lanes: dict[str, tuple[Path, str]]
    coord_base_sha: str


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _rev(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref)


def _init_repo(tmp_path: Path) -> Path:
    """Follows the real-git fixture pattern in ``tests/merge/test_reconciliation.py``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-qb", _TARGET_BRANCH, str(repo)], check=True)
    _git(repo, "config", "user.email", "divergent-shapes@spec-kitty.test")
    _git(repo, "config", "user.name", "Divergent Shapes Fixture")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    return repo


def _seed_wp_to_approved(feature_dir: Path, mission_slug: str, wp_id: str) -> None:
    """Drive *wp_id* through the legal lane path to ``approved`` (canonical emitter)."""
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane="planned",
            actor="divergent-shapes-fixture",
            force=True,
            reason="fixture: seed out of genesis",
        )
    )
    for to_lane in _APPROVE_LANES:
        gating = to_lane == "for_review"
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id=wp_id,
                to_lane=to_lane,
                actor="divergent-shapes-fixture",
                force=gating,
                reason="fixture: manufacture reviewable state" if gating else None,
            )
        )
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane="approved",
            actor="divergent-shapes-fixture",
            evidence={
                "review": {
                    "reviewer": "reviewer-renata",
                    "verdict": "approved",
                    "reference": f"review-{wp_id}",
                }
            },
            review_result=ReviewResult(
                reviewer="reviewer-renata",
                verdict="approved",
                reference=f"review-{wp_id}",
            ),
        )
    )


def _seed_wp_to_canceled(feature_dir: Path, mission_slug: str, wp_id: str) -> None:
    """Drive *wp_id* to ``canceled`` directly from ``planned`` (canceled reachable from all)."""
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane="planned",
            actor="divergent-shapes-fixture",
            force=True,
            reason="fixture: seed out of genesis",
        )
    )
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane="canceled",
            actor="divergent-shapes-fixture",
            reason="fixture: provenance-canceled survivor test",
        )
    )


def _write_meta(feature_dir: Path, *, slug: str, mission_id: str, mission_branch: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": slug,
                "mission_id": mission_id,
                "mission_type": "software-dev",
                "mission_branch": mission_branch,
                "target_branch": _TARGET_BRANCH,
            }
        ),
        encoding="utf-8",
    )


def _build_shape(
    tmp_path: Path,
    *,
    slug: str,
    mission_id: str,
    mission_branch: str,
    with_canceled_lane: bool = False,
    with_planning_lane: bool = False,
    delete_created_branch_of: str | None = None,
    canceled_lane_status: str = "canceled",
) -> DivergentMission:
    """Build one divergent-shape mission through the real allocator.

    ``canceled_lane_status`` (only meaningful with ``with_canceled_lane=True``):
    ``"canceled"`` (default) seeds lane-b's WP to an actual ``canceled`` status,
    so ``_lane_is_approved`` excludes it before the strict branch-existence
    check ever runs. ``"approved"`` instead leaves lane-b's WP genuinely ``approved``
    in the snapshot, so a caller-supplied ``excluded_canceled_wp_ids`` is the
    ONLY signal marking it provenance-canceled — the scenario that exercises
    :func:`specify_cli.merge.reconciliation._unresolvable_approved_lane_branches`'s
    ``all(wp in excluded_canceled_wp_ids ...)`` guard rather than the earlier
    ``_lane_is_approved`` short-circuit.
    """
    repo = _init_repo(tmp_path)
    feature_dir = repo / "kitty-specs" / slug
    _write_meta(feature_dir, slug=slug, mission_id=mission_id, mission_branch=mission_branch)

    lane_ids = ["lane-a"]
    if with_canceled_lane:
        lane_ids.append("lane-b")
    if with_planning_lane:
        lane_ids.append("lane-planning")
    wp_of_lane = {lane_id: f"WP{idx + 1:02d}" for idx, lane_id in enumerate(lane_ids)}

    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission_id,
        mission_branch=mission_branch,
        target_branch=_TARGET_BRANCH,
        lanes=[
            ExecutionLane(
                lane_id=lane_id,
                wp_ids=(wp_of_lane[lane_id],),
                write_scope=(f"src/{wp_of_lane[lane_id].lower()}.py",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
            for lane_id in lane_ids
        ],
        computed_at=now_utc_iso(),
        computed_from="divergent-shapes-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "bootstrap divergent mission")
    coord_base_sha = _rev(repo, "HEAD")

    lanes: dict[str, tuple[Path, str]] = {}
    for lane_id in lane_ids:
        wp_id = wp_of_lane[lane_id]
        if lane_id == "lane-planning":
            # Planning-artifact WPs live on the main checkout, never a worktree.
            lanes[lane_id] = (repo, _TARGET_BRANCH)
            _seed_wp_to_approved(feature_dir, slug, wp_id)
            continue

        worktree_path, branch = allocate_lane_worktree(repo, slug, wp_id, manifest)
        owned_rel = f"src/{wp_id.lower()}.py"
        (worktree_path / "src").mkdir(parents=True, exist_ok=True)
        (worktree_path / owned_rel).write_text(f"# {wp_id}\n", encoding="utf-8")
        _git(worktree_path, "add", owned_rel)
        _git(worktree_path, "commit", "-qm", f"feat({wp_id}): implement")
        lanes[lane_id] = (worktree_path, branch)

        if with_canceled_lane and lane_id == "lane-b" and canceled_lane_status == "canceled":
            _seed_wp_to_canceled(feature_dir, slug, wp_id)
        else:
            _seed_wp_to_approved(feature_dir, slug, wp_id)

    if delete_created_branch_of is not None:
        worktree_path, branch = lanes[delete_created_branch_of]
        _git(repo, "worktree", "remove", "--force", str(worktree_path))
        _git(repo, "branch", "-D", branch)

    return DivergentMission(
        repo_root=repo,
        feature_dir=feature_dir,
        slug=slug,
        mission_id=mission_id,
        manifest=manifest,
        lanes=lanes,
        coord_base_sha=coord_base_sha,
    )


# --------------------------------------------------------------------------- #
# The four US1 divergent shapes (the divergent-naming spec's literal table)
# --------------------------------------------------------------------------- #


def shape_backfilled_legacy(
    tmp_path: Path,
    *,
    with_canceled_lane: bool = False,
    with_planning_lane: bool = False,
    delete_created_branch_of: str | None = None,
    canceled_lane_status: str = "canceled",
) -> DivergentMission:
    """A pre-083 mission backfilled with a mid8 the original slug never embedded."""
    return _build_shape(
        tmp_path,
        slug="057-foo",
        mission_id="01KNXQS9ATWWFXS3K5ZJ9E5008",
        mission_branch="kitty/mission-foo-01KNXQS9",
        with_canceled_lane=with_canceled_lane,
        with_planning_lane=with_planning_lane,
        delete_created_branch_of=delete_created_branch_of,
        canceled_lane_status=canceled_lane_status,
    )


def shape_mismatched_mid8(
    tmp_path: Path,
    *,
    with_canceled_lane: bool = False,
    with_planning_lane: bool = False,
    delete_created_branch_of: str | None = None,
    canceled_lane_status: str = "canceled",
) -> DivergentMission:
    """A slug carrying an embedded mid8 tail that diverges from the declared mission_id."""
    return _build_shape(
        tmp_path,
        slug="foo-01KV6510",
        mission_id="01M3AAAAB6XQ7Z2K4M9N0P1R3S",
        mission_branch="kitty/mission-foo-01KV6510-01M3AAAA",
        with_canceled_lane=with_canceled_lane,
        with_planning_lane=with_planning_lane,
        delete_created_branch_of=delete_created_branch_of,
        canceled_lane_status=canceled_lane_status,
    )


def shape_invalid_identity_long(
    tmp_path: Path,
    *,
    with_canceled_lane: bool = False,
    with_planning_lane: bool = False,
    delete_created_branch_of: str | None = None,
    canceled_lane_status: str = "canceled",
) -> DivergentMission:
    """A mission_id that is >= 8 characters but not Crockford base32 (invalid ULID)."""
    return _build_shape(
        tmp_path,
        slug="057-foo",
        mission_id="not-a-valid-ulid",
        mission_branch="kitty/mission-foo-not-a-va",
        with_canceled_lane=with_canceled_lane,
        with_planning_lane=with_planning_lane,
        delete_created_branch_of=delete_created_branch_of,
        canceled_lane_status=canceled_lane_status,
    )


def shape_invalid_identity_short(
    tmp_path: Path,
    *,
    with_canceled_lane: bool = False,
    with_planning_lane: bool = False,
    delete_created_branch_of: str | None = None,
    canceled_lane_status: str = "canceled",
) -> DivergentMission:
    """A mission_id shorter than 8 characters (recorded mission_branch is legacy form)."""
    return _build_shape(
        tmp_path,
        slug="057-foo",
        mission_id="abc",
        mission_branch="kitty/mission-057-foo",
        with_canceled_lane=with_canceled_lane,
        with_planning_lane=with_planning_lane,
        delete_created_branch_of=delete_created_branch_of,
        canceled_lane_status=canceled_lane_status,
    )


DivergentShapeBuilder = Callable[..., DivergentMission]

DIVERGENT_SHAPE_BUILDERS: dict[str, DivergentShapeBuilder] = {
    "backfilled_legacy": shape_backfilled_legacy,
    "mismatched_mid8": shape_mismatched_mid8,
    "invalid_identity_long": shape_invalid_identity_long,
    "invalid_identity_short": shape_invalid_identity_short,
}


def identity_injected_lane_branch(mission_slug: str, lane_id: str, mission_id: str) -> str:
    """Reconstruct the retired identity-injected lane-branch form (negative fixture).

    Shared home for a helper duplicated byte-for-byte in
    ``tests/merge/test_executor_lane_naming.py`` and
    ``tests/merge/test_merge_divergent_end_to_end.py``. ``lane_branch_name``
    no longer takes a ``mission_id`` keyword (FR-002): it can no longer
    compose this shape. These negative-fixture tests still need the OLD
    identity form as a literal to prove it was never among the CREATED names,
    so this helper reproduces the retired formula verbatim (byte-for-byte
    identical to the removed ``mission_id`` branch) instead of routing
    through the removed parameter.
    """
    mid8 = mission_id[:8]
    human_slug = strip_numeric_prefix(mission_slug)
    suffix = f"-{mid8}"
    if human_slug.endswith(suffix):
        human_slug = human_slug[: -len(suffix)]
    return f"kitty/mission-{human_slug}-{mid8}-{lane_id}"


def all_wp_ids(mission: DivergentMission) -> list[str]:
    """Every WP id carried by *mission*'s lanes, flattened in lane order.

    Shared home for a helper duplicated in the same two test modules as
    :func:`identity_injected_lane_branch`.
    """
    return [wp for lane in mission.manifest.lanes for wp in lane.wp_ids]
