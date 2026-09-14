"""Red-first partition-mapping tests for the artifacts port (WP02).

Mission ``coord-write-placement-closure-01KYCF83`` WP02 (FR-002, FR-003,
FR-006; DIRECTIVE_041 red-first). Pins, via BEHAVIORAL assertions on the
resolver (never literal dict snapshots -- an unrelated future addition to
either SSOT dict must not red this file), that:

- ``PRIMARY_METADATA`` now resolves a non-None, partition-aware
  ``commit_target`` (T006) instead of the old read-anchored ``None`` sentinel;
- ``decisions.events.jsonl`` and ``traces/`` classify to a COORD-partition kind
  via the SINGLE classifier ``kind_for_mission_file`` (T007/T008);
- ``assert_partition_invariant()`` stays exhaustive + disjoint after the two
  new classifications land (T009);
- ``write_meta`` -- driven the way a real caller derives its target from the
  port -- lands ``meta.json`` on the resolved PRIMARY surface, never an
  ambient decoy directory (T054), closing FR-002 at the foundation rather than
  deferring the first observation to WP09's birth-cutover seam.

Authored BEFORE the T006-T008 edits land: every assertion below reds against
the pre-edit classifier (``PRIMARY_METADATA.commit_target is None``;
``decisions.events.jsonl`` / ``traces/`` classify to ``None``) and goes green
only once T006-T008 are applied.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.fast]

import mission_runtime.artifacts as artifacts_mod
from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    TopologySurface,
    is_primary_artifact_kind,
    kind_for_mission_file,
)
from mission_runtime.artifacts import MissionArtifactHome, artifact_home_for
from specify_cli.coordination.coherence import is_coord_residue_churn, is_status_state_path
from specify_cli.mission_metadata import write_meta

_MISSION_SLUG = "coord-write-placement-closure-01KYCF83"
_COORD_BRANCH_REF = CommitTarget(ref=f"kitty/mission-{_MISSION_SLUG}/coord")


# ---------------------------------------------------------------------------
# T006 -- PRIMARY_METADATA.commit_target is partition-aware, not a
# read-anchored ``None`` sentinel.
# ---------------------------------------------------------------------------


def test_primary_metadata_commit_target_is_partition_aware() -> None:
    """T006: the sentinel flip -- PRIMARY_METADATA now carries a routed target.

    Pre-edit this resolves ``commit_target=None`` (the special-case arm at
    ``artifacts.py:218-224``); post-edit it falls through to the generic
    PRIMARY arm and carries the resolved ``placement_ref`` -- required for
    ``write_meta`` / ``_flip_phase`` / ``_bake_mission_number`` to route meta
    writes through the port (T054 below drives this end-to-end).
    """
    home = artifact_home_for(MissionArtifactKind.PRIMARY_METADATA, _COORD_BRANCH_REF)

    assert home.write_surface is TopologySurface.PRIMARY
    assert home.read_surface is TopologySurface.PRIMARY
    assert home.commit_target is not None, (
        "PRIMARY_METADATA.commit_target must be partition-aware (T006), not "
        "the port-blind None sentinel"
    )
    assert home.commit_target == _COORD_BRANCH_REF


# ---------------------------------------------------------------------------
# T007 -- decisions.events.jsonl classifies to a COORD-partition kind.
# ---------------------------------------------------------------------------


def test_decisions_events_jsonl_classifies_to_coord() -> None:
    """T007: decisions.events.jsonl -> a COORD-homed kind via the ONE classifier.

    Behavioral, not a literal-kind-name snapshot: this stays green under any
    future kind rename as long as the basename classifies to SOME kind and
    that kind is COORD-partition.
    """
    path = f"kitty-specs/{_MISSION_SLUG}/decisions.events.jsonl"

    kind = kind_for_mission_file(path)

    assert kind is not None, (
        "decisions.events.jsonl must classify to a MissionArtifactKind "
        "(FR-003), not fall through the unrecognized-path None"
    )
    assert not is_primary_artifact_kind(kind), (
        f"decisions.events.jsonl classified to {kind!r}, a PRIMARY-partition "
        "kind -- FR-003 requires COORD"
    )


# ---------------------------------------------------------------------------
# T008 -- traces/ classifies to a COORD-partition kind.
# ---------------------------------------------------------------------------


def test_traces_dir_classifies_to_coord() -> None:
    """T008: traces/<file> -> a COORD-homed kind via the residue-dirs SSOT."""
    path = f"kitty-specs/{_MISSION_SLUG}/traces/design-decisions.md"

    kind = kind_for_mission_file(path)

    assert kind is not None, (
        "traces/ must classify to a MissionArtifactKind (FR-006), not fall "
        "through the unrecognized-path None"
    )
    assert not is_primary_artifact_kind(kind), (
        f"traces/ classified to {kind!r}, a PRIMARY-partition kind -- FR-006 "
        "requires COORD"
    )


def test_decisions_and_traces_kinds_are_distinct_from_each_other() -> None:
    """Disjointness edge case (T008 risk): traces/ and decisions.events.jsonl
    must not collapse onto the same kind AND neither may double-home onto an
    existing PRIMARY entry (checked positively above); this pins that the two
    new classifications are independently addressable kinds."""
    decisions_kind = kind_for_mission_file(f"kitty-specs/{_MISSION_SLUG}/decisions.events.jsonl")
    traces_kind = kind_for_mission_file(f"kitty-specs/{_MISSION_SLUG}/traces/notes.md")

    assert decisions_kind is not None
    assert traces_kind is not None
    assert decisions_kind is not traces_kind


# ---------------------------------------------------------------------------
# #3928 -- the decisions/ LEDGER (index.json + DM-<ulid>.md) classifies to a
# COORD-partition kind, so the churn classifier agrees with the write side.
# ---------------------------------------------------------------------------

# The two (and only two) ledger shapes ``decisions/store.py`` writes
# (``index_path`` / ``artifact_path``); the DM id is a ULID.
_LEDGER_PATHS = (
    f"kitty-specs/{_MISSION_SLUG}/decisions/index.json",
    f"kitty-specs/{_MISSION_SLUG}/decisions/DM-01M1VRA2ABCDEFGHJKMNPQRS.md",
)


@pytest.mark.parametrize("path", _LEDGER_PATHS)
def test_decisions_ledger_classifies_to_coord(path: str) -> None:
    """#3928: decisions/<ledger file> -> a COORD-homed kind via the ONE classifier.

    Pre-fix both shapes classify to ``None`` (fall through the
    unrecognized-path leg), so ``is_coord_residue_churn`` returns False and
    ``agent mission record-analysis`` refuses with ``DIRTY_WORKTREE`` the
    moment a Decision Moment is opened -- even though
    ``decisions/service.py`` documents the ledger as coord-authority-owned
    STATUS-partition state. Behavioral like T007/T008: any COORD-partition
    kind keeps this green.
    """
    kind = kind_for_mission_file(path)

    assert kind is not None, (
        f"{path} must classify to a MissionArtifactKind (#3928), not fall "
        "through the unrecognized-path None"
    )
    assert not is_primary_artifact_kind(kind), (
        f"{path} classified to {kind!r}, a PRIMARY-partition kind -- the "
        "ledger is coord-authority-owned state, so #3928 requires COORD"
    )


@pytest.mark.parametrize("path", _LEDGER_PATHS)
def test_decisions_ledger_is_coord_residue_churn(path: str) -> None:
    """#3928 symptom level: the churn predicate the recorder consults.

    ``is_coord_residue_churn`` is the exact predicate
    ``cli/commands/agent/mission_record_analysis.py`` filters dirty paths
    through; pre-fix it returned False for both ledger shapes. Also pins the
    mission-slug scoping (another mission's ledger is not this mission's
    residue) and that the ledger did NOT borrow STATUS_STATE -- the WP13
    ``is_status_state_path`` predicate must keep matching exactly
    ``status.events.jsonl`` / ``status.json`` (its coord-commit consumers
    stage on that narrow set).
    """
    assert is_coord_residue_churn(path, mission_slug=_MISSION_SLUG) is True, (
        f"{path} must classify as coordination residue churn (#3928)"
    )
    assert is_coord_residue_churn(path, mission_slug="another-mission-01") is False, (
        "a ledger under another mission's directory is not this mission's residue"
    )
    assert is_status_state_path(path) is False, (
        f"{path} must not classify as STATUS_STATE -- is_status_state_path is "
        "deliberately narrow (WP13) and must not widen to the ledger"
    )


def test_decisions_ledger_kind_is_distinct_from_neighbor_kinds() -> None:
    """Disjointness edge case (the T008-risk pattern): the ledger's kind must
    be independently addressable from DECISION_LOG (the mission-root
    ``decisions.events.jsonl`` event stream) and STATUS_STATE, so neither
    narrow consumer set silently widens when the ledger gains a kind."""
    ledger_kind = kind_for_mission_file(_LEDGER_PATHS[0])
    log_kind = kind_for_mission_file(f"kitty-specs/{_MISSION_SLUG}/decisions.events.jsonl")
    status_kind = kind_for_mission_file(f"kitty-specs/{_MISSION_SLUG}/status.events.jsonl")

    assert ledger_kind is not None
    assert ledger_kind is not log_kind
    assert ledger_kind is not status_kind


# ---------------------------------------------------------------------------
# T009 -- assert_partition_invariant() stays exhaustive + disjoint.
# ---------------------------------------------------------------------------


def test_partition_invariant_stays_exhaustive_and_disjoint() -> None:
    """P-1 (data-model.md): the two SSOT frozensets never overlap and jointly
    cover every MissionArtifactKind member -- including the two new
    classifications this WP adds."""
    artifacts_mod.assert_partition_invariant()  # must not raise


# ---------------------------------------------------------------------------
# T054 -- behavioral proof: write_meta lands meta on the PRIMARY surface via
# the port, not an ambient feature_dir.
# ---------------------------------------------------------------------------


def _route_meta_write_dir(
    *, primary_dir: Path, ambient_dir: Path, placement_ref: CommitTarget
) -> Path:
    """Mimic a real meta-write caller deriving its target from the port.

    A caller that consumes ``PRIMARY_METADATA``'s resolved home routes the
    write through the port's ``commit_target`` when it is non-None (T006);
    pre-fix the sentinel is always ``None``, so a caller has nothing to route
    on and falls back to whatever ambient directory it happened to hold --
    exactly the regression FR-002 closes.

    Calls ``artifacts_mod.artifact_home_for`` (attribute access, not the
    module-level import) so the anti-mutant test below can monkeypatch the
    module attribute and have this helper observe the patch.
    """
    home = artifacts_mod.artifact_home_for(MissionArtifactKind.PRIMARY_METADATA, placement_ref)
    if home.commit_target is None:
        return ambient_dir
    return primary_dir


def test_write_meta_lands_on_primary_surface_via_the_port(tmp_path: Path) -> None:
    """T054: write_meta, routed via the port's commit_target, lands on PRIMARY.

    Reds pre-T006 (commit_target is None -> the helper falls back to the
    ambient decoy dir, so meta.json never appears in primary_dir); greens
    once T006 flips the sentinel.
    """
    primary_dir = tmp_path / "primary-surface"
    primary_dir.mkdir()
    ambient_dir = tmp_path / "ambient-decoy-surface"
    ambient_dir.mkdir()

    target_dir = _route_meta_write_dir(
        primary_dir=primary_dir, ambient_dir=ambient_dir, placement_ref=_COORD_BRANCH_REF
    )
    write_meta(target_dir, {"slug": "x"}, validate=False)

    assert (primary_dir / "meta.json").exists(), (
        "write_meta must land meta.json on the PRIMARY surface resolved via "
        "the port's commit_target, not an ambient fallback"
    )
    assert not (ambient_dir / "meta.json").exists(), (
        "meta.json leaked onto the ambient decoy directory -- the port's "
        "commit_target was not consulted"
    )


def test_write_meta_routing_anti_mutant_catches_reverted_sentinel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anti-mutant: forcing the OLD PRIMARY_METADATA commit_target=None arm back
    makes the routing helper -- and therefore write_meta's landing surface --
    fall back to the ambient decoy, proving the positive T054 test above is
    not vacuous (it would catch a regression that reintroduces the None
    sentinel)."""
    primary_dir = tmp_path / "primary-surface"
    primary_dir.mkdir()
    ambient_dir = tmp_path / "ambient-decoy-surface"
    ambient_dir.mkdir()

    original_artifact_home_for = artifacts_mod.artifact_home_for

    def _forced_none_commit_target(
        kind: MissionArtifactKind, placement_ref: CommitTarget
    ) -> MissionArtifactHome:
        home = original_artifact_home_for(kind, placement_ref)
        if kind is MissionArtifactKind.PRIMARY_METADATA:
            return MissionArtifactHome(
                kind=kind,
                read_surface=home.read_surface,
                write_surface=home.write_surface,
                commit_target=None,
            )
        return home

    monkeypatch.setattr(artifacts_mod, "artifact_home_for", _forced_none_commit_target)

    target_dir = _route_meta_write_dir(
        primary_dir=primary_dir, ambient_dir=ambient_dir, placement_ref=_COORD_BRANCH_REF
    )
    write_meta(target_dir, {"slug": "x"}, validate=False)

    assert (ambient_dir / "meta.json").exists(), (
        "mutant did not reproduce the pre-fix routing -- this test would be "
        "vacuous against a regression that reintroduces commit_target=None"
    )
    assert not (primary_dir / "meta.json").exists()
