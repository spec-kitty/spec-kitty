"""WP01 (gate-read-surface-completion / FR-004 / FR-009) — the single kind-aware
planning-read chokepoint, plus the retirement of the bespoke primary-anchor helper
pair onto it.

The seam (:func:`resolve_planning_read_dir`) already exists; WP01 is *adoption*:
``_planning_read_dir`` is the ONE locus every gate planning-read consumes, and the
former bespoke helpers (``_primary_anchored_feature_dir`` /
``_resolve_mission_dir_name_primary_anchored``) now route through it — no parallel
primary-anchor planning-read path survives (C-001 / FR-009).

Discipline (standing memory + reviewer-renata post-tasks):

* Tests run through the **pre-existing entry points** — ``_planning_read_dir`` and the
  retired helper ``_primary_anchored_feature_dir`` — never ``resolve_planning_read_dir``
  directly (that would test the seam, not the adoption).
* The RED proof is **non-vacuous and not an ImportError**: the helper EXISTS; it is its
  BODY that is proven. ``test_red_first_body_revert_*`` substitutes the chokepoint's
  routing with the pre-consolidation **topology-routed** body (the coord-aware
  ``candidate_feature_dir_for_mission``) and asserts the behavioral assertion goes RED
  (resolves the coord husk), then GREEN with the real seam routing (resolves PRIMARY).
* Fixtures are production-shaped: a real 26-char Crockford ULID + its real 8-char mid8,
  a composed ``<slug>-<mid8>`` primary dir (a bare-slug dir is canonicalized and masks
  the coord/primary divergence — a false green, NFR-002), and the canonical meta
  serializer.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands.agent import mission as mission_mod
from specify_cli.cli.commands.agent.mission import (
    _planning_read_dir,
    _primary_anchored_feature_dir,
)
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# Production-shaped identity: a real 26-char Crockford ULID + its 8-char mid8.
MISSION_ID = "01KVW9B0XFXPKTBE77QT3KRSW8"
MID8 = MISSION_ID[:8]  # "01KVW9B0"
SLUG = "gate-read-surface-completion"
SLUG_WITH_MID8 = f"{SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{SLUG_WITH_MID8}"

PRIMARY_TRUTH = "# spec.md — PRIMARY TRUTH (authored on primary)\n"
STALE_HUSK = "# spec.md — STALE pre-mission coord husk copy\n"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True
    )


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "wp01@example.test")
    _git(repo_root, "config", "user.name", "WP01 Gate")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")


def _write_meta(feature_dir: Path, meta: dict[str, object]) -> None:
    """Persist meta via the canonical sorted-key serializer (not a rotting writer)."""
    from tests._meta_write_support import write_meta_canonical as _write_meta_canonical

    feature_dir.mkdir(parents=True, exist_ok=True)
    _write_meta_canonical(feature_dir / "meta.json", meta)


def _seed_coord_topology(repo_root: Path) -> tuple[Path, Path]:
    """Seed a COORD-topology mission: PRIMARY truth + a materialized STALE coord husk.

    Returns ``(primary_dir, coord_husk_dir)`` — the composed ``<slug>-<mid8>`` primary
    dir carries the truth, the materialized ``-coord`` husk carries the stale copy.
    """
    from mission_runtime import MissionTopology

    _init_repo(repo_root)
    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_slug": SLUG_WITH_MID8,
        "coordination_branch": COORD_BRANCH,
        "topology": MissionTopology.COORD.value,
    }
    primary_dir = repo_root / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(primary_dir, meta)
    (primary_dir / "spec.md").write_text(PRIMARY_TRUTH, encoding="utf-8")

    coord_husk_dir = (
        repo_root / ".worktrees" / f"{SLUG_WITH_MID8}-coord" / "kitty-specs" / SLUG_WITH_MID8
    )
    _write_meta(coord_husk_dir, meta)
    (coord_husk_dir / "spec.md").write_text(STALE_HUSK, encoding="utf-8")
    return primary_dir, coord_husk_dir


def _seed_flattened(repo_root: Path) -> Path:
    """Seed a FLATTENED (single-branch) mission — every read resolves PRIMARY (NFR-001)."""
    from mission_runtime import MissionTopology

    _init_repo(repo_root)
    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_slug": SLUG_WITH_MID8,
        "topology": MissionTopology.SINGLE_BRANCH.value,
    }
    primary_dir = repo_root / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(primary_dir, meta)
    (primary_dir / "spec.md").write_text(PRIMARY_TRUTH, encoding="utf-8")
    return primary_dir


# --------------------------------------------------------------------------- #
# T005.1 — the chokepoint resolves PRIMARY for a coord-topology planning kind.
# --------------------------------------------------------------------------- #
def test_chokepoint_resolves_primary_for_coord_topology_planning_kind(
    tmp_path: Path,
) -> None:
    """``_planning_read_dir`` resolves the PRIMARY dir for a coord-topology mission.

    A coord-topology mission's planning artifact lives on the PRIMARY surface; the
    chokepoint must resolve it there (NOT the materialized stale coord husk). All three
    mapped planning kinds (spec/plan/tasks) are PRIMARY-partition, so each resolves the
    same primary dir.
    """
    primary_dir, coord_husk_dir = _seed_coord_topology(tmp_path)

    for artifact_type in ("spec", "plan", "tasks"):
        resolved = _planning_read_dir(tmp_path, SLUG_WITH_MID8, artifact_type=artifact_type)
        assert resolved.resolve() == primary_dir.resolve()
        assert resolved.resolve() != coord_husk_dir.resolve()
    # Observable content contract: the planning read is the PRIMARY truth, not the husk.
    spec = _planning_read_dir(tmp_path, SLUG_WITH_MID8, artifact_type="spec") / "spec.md"
    assert spec.read_text(encoding="utf-8") == PRIMARY_TRUTH


def test_chokepoint_flattened_mission_resolves_primary(tmp_path: Path) -> None:
    """A flattened mission's planning read resolves PRIMARY — unchanged (NFR-001)."""
    primary_dir = _seed_flattened(tmp_path)
    resolved = _planning_read_dir(tmp_path, SLUG_WITH_MID8, artifact_type="spec")
    assert resolved.resolve() == primary_dir.resolve()
    assert (resolved / "spec.md").read_text(encoding="utf-8") == PRIMARY_TRUTH


def test_chokepoint_unmapped_artifact_type_raises_no_silent_default(
    tmp_path: Path,
) -> None:
    """An unmapped ``artifact_type`` raises loudly — no silent kind default (DECISION 1).

    The chokepoint names the kind via ``_kind_for_artifact``; an unknown type cannot
    silently mis-route to a default kind/surface.
    """
    _seed_coord_topology(tmp_path)
    with pytest.raises(KeyError):
        _planning_read_dir(tmp_path, SLUG_WITH_MID8, artifact_type="not-a-planning-kind")


# --------------------------------------------------------------------------- #
# T005.2 — behavioral assertion through an EXISTING caller of the retired helper.
# --------------------------------------------------------------------------- #
def test_retired_caller_resolves_same_primary_dir(tmp_path: Path) -> None:
    """``_primary_anchored_feature_dir`` (existing caller) resolves the SAME primary dir.

    Proves the retirement preserved behavior at a real call site: the helper that
    finalize-tasks / check-prerequisites consume still anchors to PRIMARY for a
    coord-topology mission (not the stale coord husk).
    """
    primary_dir, coord_husk_dir = _seed_coord_topology(tmp_path)

    resolved = _primary_anchored_feature_dir(tmp_path, SLUG_WITH_MID8)

    assert resolved is not None
    assert resolved.resolve() == primary_dir.resolve()
    assert resolved.resolve() != coord_husk_dir.resolve()


def test_retired_caller_returns_none_on_no_handle(tmp_path: Path) -> None:
    """``None``-on-no-handle fallback preserved (caller falls back to the coord-aware
    resolver) — a load-bearing contract of the retired helper."""
    _seed_coord_topology(tmp_path)
    assert _primary_anchored_feature_dir(tmp_path, None) is None
    assert _primary_anchored_feature_dir(tmp_path, "   ") is None


def test_retired_caller_propagates_ambiguous_selector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ambiguity propagation preserved: an ambiguous handle is never silently resolved.

    The retired helper surfaces the structured ``ActionContextError`` (mapped from
    ``MissionSelectorAmbiguous``) rather than picking a wrong-but-plausible dir
    (C-CTX-4 / C-009).
    """
    from mission_runtime import ActionContextError

    _seed_coord_topology(tmp_path)

    def _raise_ambiguous(*_args: object, **_kwargs: object) -> str | None:
        raise MissionSelectorAmbiguous(
            handle="gate", candidates=[f"{SLUG_WITH_MID8}", "gate-other-01ABCDEF"]
        )

    # Force the canonicalization step the workhorse runs to report ambiguity.
    # #2056 decomposition: ``_primary_anchored_feature_dir`` and its sibling
    # ``_resolve_mission_dir_name_primary_anchored`` both live in the
    # ``mission_feature_resolution`` seam, and the (same-module) sibling call
    # resolves in THAT namespace — so patch the helper on the seam module, not the
    # ``mission`` shim re-export.
    from specify_cli.cli.commands.agent import mission_feature_resolution as _seam

    monkeypatch.setattr(
        _seam,
        "_resolve_mission_dir_name_primary_anchored",
        _raise_ambiguous,
    )
    with pytest.raises(ActionContextError):
        _primary_anchored_feature_dir(tmp_path, "gate")


# --------------------------------------------------------------------------- #
# T005.3 — RED proof by reverting the chokepoint's BODY to the pre-consolidation
#          topology-routed path (NOT an ImportError). The helper EXISTS; its body
#          is what is proven. With the seam routing → PRIMARY (GREEN); reverted to
#          the coord-aware ``candidate_feature_dir_for_mission`` → coord husk (RED).
# --------------------------------------------------------------------------- #
def test_red_first_body_revert_makes_caller_resolve_coord_husk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-vacuous RED: reverting the chokepoint body to the topology-routed resolver
    makes the existing caller resolve the COORD husk; the real seam routing resolves
    PRIMARY. This proves the consolidation's body (seam vs bespoke topology routing) is
    load-bearing — not an ImportError on a missing symbol.
    """
    primary_dir, coord_husk_dir = _seed_coord_topology(tmp_path)

    # GREEN baseline: the live chokepoint routes through the seam → PRIMARY.
    green = _primary_anchored_feature_dir(tmp_path, SLUG_WITH_MID8)
    assert green is not None
    assert green.resolve() == primary_dir.resolve()

    # Revert the chokepoint BODY to the pre-consolidation topology-routed path (the
    # coord-aware ``candidate_feature_dir_for_mission`` the bespoke helpers must NOT
    # use). The symbol still EXISTS — only its body changes.
    from specify_cli.missions._read_path_resolver import candidate_feature_dir_for_mission

    def _reverted_body(repo_root: Path, mission_slug: str, *, artifact_type: str) -> Path:
        husk: Path = candidate_feature_dir_for_mission(repo_root, mission_slug)
        return husk

    monkeypatch.setattr(mission_mod, "_planning_read_dir", _reverted_body)

    # RED under the reverted body: the existing caller now resolves the coord husk.
    reverted = _primary_anchored_feature_dir(tmp_path, SLUG_WITH_MID8)
    assert reverted is not None
    assert reverted.resolve() == coord_husk_dir.resolve()
    assert reverted.resolve() != primary_dir.resolve()
