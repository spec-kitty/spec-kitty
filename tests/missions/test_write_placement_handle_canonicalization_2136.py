"""#2136 / #2164 — universal handle-canonicalization on the WRITE/placement side.

FR-011 was completed read-side via ``resolve_planning_read_dir`` (the PRIMARY-kind
read leg folds a handle through ``_canonicalize_primary_read_handle`` before the
topology-blind ``primary_feature_dir_for_mission`` primitive). The WRITE/placement
seams were latent-buggy: they composed a primary dir from the RAW handle, so a
non-composed handle (bare ``mid8`` / full ULID / numeric, OR a bare human slug
whose on-disk dir carries the composed ``<slug>-<mid8>`` name) landed on a WRONG
dir on the write leg while the read leg resolved the real one (the #2136
read/write DIVERGENCE).

This module pins the convergence cure across the four swept seams:

* ``retrospective.writer.resolve_retrospective_home`` (site 1 — the write seam)
* ``review.cycle.resolve_review_cycle_pointer`` (site 2 — pointer read leg vs the
  ``create_rejected_review_cycle`` write leg)
* ``resolve_planning_read_dir`` for ``WORK_PACKAGE_TASK`` (the seam orchestrator
  ``append-history`` — site 3 — now routes through)
* ``cli.commands.mission_type._resolve_mission_handle`` (site 4 — the
  ``MissionNotFoundError`` bare-human-slug fallback leg)

Red-first (DIRECTIVE_034): the convergence assertions FAIL on the pre-fix seams
(the bare-``mid8`` / ULID / bare-human-slug legs diverge from the read seam),
proven by reverting the seam edits and witnessing the divergence. Post-fix every
handle form resolves the one on-disk ``<slug>-<mid8>`` dir.

No-silent-fallback (C-009 / WP07): an ambiguous handle raises
``MissionSelectorAmbiguous`` — never a silent pick of a wrong-but-plausible dir.

Fixtures use a production-shaped real 26-char Crockford ULID + its 8-char mid8 and
the canonical ``meta.json`` serializer (#2071 realistic-data discipline).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind
from specify_cli.missions._read_path_resolver import (
    MissionSelectorAmbiguous,
    candidate_feature_dir_for_mission,
    resolve_planning_read_dir,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Production-shaped identity: a real 26-char Crockford ULID + its 8-char mid8.
MISSION_ID = "01KVTVZS9C4D5E6F7G8H9J0K1M"
MID8 = MISSION_ID[:8]  # "01KVTVZS"
SLUG = "cure-2136-placement"
SLUG_WITH_MID8 = f"{SLUG}-{MID8}"

# The four handle forms an operator may type for the SAME mission. Every one must
# fold to ``SLUG_WITH_MID8`` on BOTH the write and read legs (the convergence).
ALL_HANDLE_FORMS = (SLUG_WITH_MID8, SLUG, MID8, MISSION_ID)


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True
    )


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "cure2136@example.test")
    _git(repo_root, "config", "user.name", "Cure 2136 Gate")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")


def _write_meta(feature_dir: Path, meta: dict[str, object]) -> None:
    """Persist meta via the canonical sorted-key serializer (NOT a rotting writer)."""
    from tests._meta_write_support import write_meta_canonical as _write_meta_canonical

    feature_dir.mkdir(parents=True, exist_ok=True)
    _write_meta_canonical(feature_dir / "meta.json", meta)


def _seed_composed_mission(repo_root: Path) -> Path:
    """Seed a single-branch mission whose on-disk dir carries ``<slug>-<mid8>``.

    Returns the primary feature dir. The mission is addressable by every handle
    form (composed dir name, bare human slug, bare mid8, full ULID) — exactly the
    #2136 divergence surface.
    """
    _init_repo(repo_root)
    primary_dir = repo_root / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(
        primary_dir,
        {
            "mission_id": MISSION_ID,
            "mid8": MID8,
            "mission_slug": SLUG_WITH_MID8,
        },
    )
    return primary_dir


def _seed_two_mid8_colliding_missions(repo_root: Path) -> str:
    """Seed two missions sharing the same mid8 prefix → an AMBIGUOUS handle.

    Returns the shared 8-char ambiguous handle. Resolving it MUST raise
    ``MissionSelectorAmbiguous`` (no silent pick) at every placement seam.
    """
    _init_repo(repo_root)
    ambig_mid8 = "01KVAMBG"
    id_a = ambig_mid8 + "0AAAAAAAAAAAAAAAAA"  # 26-char ULID-shaped
    id_b = ambig_mid8 + "0BBBBBBBBBBBBBBBBB"
    for mission_id, slug in ((id_a, "ambig-alpha"), (id_b, "ambig-beta")):
        composed = f"{slug}-{ambig_mid8}"
        _write_meta(
            repo_root / "kitty-specs" / composed,
            {"mission_id": mission_id, "mid8": ambig_mid8, "mission_slug": composed},
        )
    return ambig_mid8


# ---------------------------------------------------------------------------
# The convergence/equivalence test — write seam == read seam for ALL handle forms
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("handle", ALL_HANDLE_FORMS)
def test_retrospective_home_converges_with_read_seam(tmp_path: Path, handle: str) -> None:
    """SITE 1: ``resolve_retrospective_home`` (write) == read seam for every handle.

    The headline #2136 convergence: a mission with a composed dir
    ``<slug>-<mid8>`` resolves the SAME primary dir through the retrospective WRITE
    seam and through the canonical READ seam for EVERY handle form. Pre-fix the
    write seam only folded the bare-human-slug, so the bare-``mid8`` / ULID legs
    diverged onto a wrong literal dir (RED).
    """
    from specify_cli.retrospective.writer import resolve_retrospective_home

    repo_root = tmp_path
    _seed_composed_mission(repo_root)

    write_dir = resolve_retrospective_home(repo_root, handle).resolve()
    read_dir = candidate_feature_dir_for_mission(repo_root, handle).resolve()

    assert write_dir == read_dir, (
        f"write seam resolved {write_dir} but read seam resolved {read_dir} "
        f"for handle {handle!r} — #2136 write/read divergence"
    )
    assert write_dir.name == SLUG_WITH_MID8, (
        f"handle {handle!r} resolved {write_dir.name!r}, expected {SLUG_WITH_MID8!r}"
    )


def test_retrospective_home_raises_on_ambiguous_handle(tmp_path: Path) -> None:
    """SITE 1: an ambiguous handle propagates MissionSelectorAmbiguous (no silent pick)."""
    from specify_cli.retrospective.writer import resolve_retrospective_home

    ambig = _seed_two_mid8_colliding_missions(tmp_path)
    with pytest.raises(MissionSelectorAmbiguous):
        resolve_retrospective_home(tmp_path, ambig)


@pytest.mark.parametrize("handle", ALL_HANDLE_FORMS)
def test_review_cycle_pointer_read_converges_with_write_dir(
    tmp_path: Path, handle: str
) -> None:
    """SITE 2: the ``review-cycle://`` pointer read resolves the WRITTEN artifact.

    The write seam (``create_rejected_review_cycle`` →
    ``candidate_feature_dir_for_mission``) lands the artifact in the canonical
    ``<slug>-<mid8>`` dir, but emits a pointer carrying the RAW handle. Pre-fix the
    read leg joined ``kitty-specs/<raw-handle>`` verbatim, so a bare-``mid8`` /
    ULID pointer resolved a non-existent path → the written artifact was
    unreadable (RED). Post-fix the read leg folds through the SAME resolver and
    finds the file.

    Realistic data (#2071): the artifact is produced by the REAL writer
    (``create_rejected_review_cycle``), which emits both the canonical on-disk
    file AND the pointer — so the write/read divergence is exercised end-to-end,
    not hand-mocked.
    """
    from specify_cli.review.cycle import (
        create_rejected_review_cycle,
        resolve_review_cycle_pointer,
    )

    repo_root = tmp_path
    _seed_composed_mission(repo_root)

    feedback = repo_root / "feedback.md"
    feedback.write_text("Please fix the off-by-one in the loop bound.\n", encoding="utf-8")

    created = create_rejected_review_cycle(
        main_repo_root=repo_root,
        mission_slug=handle,
        wp_id="WP01",
        wp_slug="wp01-do-the-thing",
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
    )

    # The writer's pointer carries the RAW handle; resolving it must locate the
    # file the writer actually wrote (the canonical ``<slug>-<mid8>`` dir).
    resolved = resolve_review_cycle_pointer(repo_root, created.pointer)

    assert resolved.path is not None, (
        f"pointer {created.pointer!r} resolved to no path — the read leg composed "
        f"a divergent dir from the write location (#2136)"
    )
    assert resolved.path.resolve() == created.artifact_path.resolve()
    assert resolved.path.parent.parent.parent.name == SLUG_WITH_MID8


@pytest.mark.parametrize("handle", ALL_HANDLE_FORMS)
def test_planning_read_dir_work_package_converges(tmp_path: Path, handle: str) -> None:
    """SITE 3 seam: ``resolve_planning_read_dir(WORK_PACKAGE_TASK)`` folds every form.

    The orchestrator ``append-history`` placement now routes the WP-prompt path
    through this PRIMARY-kind seam (instead of a raw ``primary_feature_dir_for_mission``
    call). It MUST fold a bare-``mid8`` / ULID / human-slug handle onto the one
    on-disk ``<slug>-<mid8>`` dir.
    """
    repo_root = tmp_path
    _seed_composed_mission(repo_root)

    resolved = resolve_planning_read_dir(
        repo_root, handle, kind=MissionArtifactKind.WORK_PACKAGE_TASK
    ).resolve()
    assert resolved.name == SLUG_WITH_MID8, (
        f"WORK_PACKAGE_TASK read of handle {handle!r} resolved {resolved.name!r}, "
        f"expected {SLUG_WITH_MID8!r} (#2136 placement divergence)"
    )


def test_planning_read_dir_work_package_raises_on_ambiguous(tmp_path: Path) -> None:
    """SITE 3 seam: an ambiguous handle propagates MissionSelectorAmbiguous."""
    ambig = _seed_two_mid8_colliding_missions(tmp_path)
    with pytest.raises(MissionSelectorAmbiguous):
        resolve_planning_read_dir(
            tmp_path, ambig, kind=MissionArtifactKind.WORK_PACKAGE_TASK
        )


def test_mission_handle_bare_human_slug_folds_to_composed_dir(tmp_path: Path) -> None:
    """SITE 4: the ``MissionNotFoundError`` leg folds a bare human slug.

    A bare human slug whose on-disk dir carries the composed ``<slug>-<mid8>`` name
    is NOT matched by the identity resolver (it keys on the dir NAME), so it falls
    to the ``MissionNotFoundError`` leg. Pre-fix that leg composed the literal
    ``kitty-specs/<bare-slug>`` (a non-existent dir, RED); post-fix it folds onto
    the real composed dir.
    """
    from specify_cli.cli.commands.mission_type import _resolve_mission_handle

    repo_root = tmp_path
    _seed_composed_mission(repo_root)

    resolved = _resolve_mission_handle(repo_root, SLUG)
    assert resolved.feature_dir.name == SLUG_WITH_MID8, (
        f"bare human slug {SLUG!r} resolved {resolved.feature_dir.name!r}, "
        f"expected {SLUG_WITH_MID8!r} (#2136 fallback-leg divergence)"
    )
    # Identity is parsed from the real on-disk meta, not re-derived.
    assert resolved.mission_id == MISSION_ID


@pytest.mark.parametrize("handle", ALL_HANDLE_FORMS)
def test_mission_handle_converges_for_all_forms(tmp_path: Path, handle: str) -> None:
    """SITE 4: every handle form resolves the one composed dir (read-seam parity)."""
    from specify_cli.cli.commands.mission_type import _resolve_mission_handle

    repo_root = tmp_path
    _seed_composed_mission(repo_root)

    resolved = _resolve_mission_handle(repo_root, handle)
    read_dir = candidate_feature_dir_for_mission(repo_root, handle).resolve()
    assert resolved.feature_dir.resolve() == read_dir
    assert resolved.feature_dir.name == SLUG_WITH_MID8


def test_mission_handle_raises_on_ambiguous(tmp_path: Path) -> None:
    """SITE 4: an ambiguous mid8 raises MissionSelectorAmbiguous (no silent pick)."""
    from specify_cli.cli.commands.mission_type import _resolve_mission_handle

    ambig = _seed_two_mid8_colliding_missions(tmp_path)
    with pytest.raises(MissionSelectorAmbiguous):
        _resolve_mission_handle(tmp_path, ambig)
