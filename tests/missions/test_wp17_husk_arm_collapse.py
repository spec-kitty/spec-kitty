"""WP17 (FR-004/005/006) — topology=None husk-arm collapse + 6th predicate + load_meta.

WP06 (06a) absorbed the absent-``topology``-FIELD case into a concrete
:class:`MissionTopology` at the read-path BOUNDARY, so the downstream resolver
chain is threaded a non-optional value for any *readable* primary meta. WP17
(06b):

* deletes the **6th** coord-routing predicate ``_topology_routes_through_coord``
  (the one FR-005's WP02 collapse could not reach because it lived in this WP's
  owned file) and repoints its callers to the single canonical
  :func:`mission_runtime.routes_through_coordination`;
* universally threads the absorbed topology so the absent-field husk-arms are
  collapsed, while the **corrupt/unreadable-meta** arm (C-004) stays a distinct
  typed path;
* converts the 4 topology files' ``load_meta`` calls onto WP08's canonical
  polymorphic reader, choosing args that reproduce each site's CURRENT contract.

Discipline (#2071 CTn): assertions are over the **observable contract** — the
resolved directory, the raised typed error, or the predicate's return value —
never the internal call graph (CT4/D036). Fixtures use a production-shaped real
26-char ULID + 8-char mid8 and the canonical ``meta.json`` serializer, never a
hand-rolled writer that rots (CT3). Every "absorbs / resolves-primary" assertion
is paired with its negative control ("still-raises / wrong-topology-differs").
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology, classify_topology, routes_through_coordination
from specify_cli.core.paths import MissionMetaReadError
from specify_cli.missions._read_path_resolver import (
    CoordState,
    candidate_feature_dir_for_mission,
    classify_from_meta,
    probe_coord_state,
    resolve_feature_dir_for_slug,
    resolve_handle_to_read_path,
)

# git_repo: KEEP-set assertions drive real git worktrees via subprocess. NOT
# ``fast`` — real ``git init``/``commit`` work would poison the inner -m fast loop.
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Production-shaped identity: a real 26-char Crockford ULID + its 8-char mid8.
MISSION_ID = "01KVRJ6PQ8ZB2H7M3N4P5R6S7T"
MID8 = MISSION_ID[:8]  # "01KVRJ6P"
SLUG = "wp17-husk-collapse"
SLUG_WITH_MID8 = f"{SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{SLUG_WITH_MID8}"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_READ_PATH_RESOLVER = _REPO_ROOT / "src/specify_cli/missions/_read_path_resolver.py"


# --------------------------------------------------------------------------- #
# Production-shaped fixture helpers (canonical serializer, real git worktrees).
# --------------------------------------------------------------------------- #
def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True
    )


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "wp17@example.test")
    _git(repo_root, "config", "user.name", "WP17 Gate")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")


def _write_meta(feature_dir: Path, meta: dict[str, object]) -> None:
    """Persist meta via the canonical sorted-key serializer (NOT a rotting writer)."""
    from tests._meta_write_support import write_meta_canonical as _write_meta_canonical

    feature_dir.mkdir(parents=True, exist_ok=True)
    _write_meta_canonical(feature_dir / "meta.json", meta)


def _write_malformed_meta(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text("{ this is not valid json", encoding="utf-8")


# --------------------------------------------------------------------------- #
# (a) Corrupt/malformed-meta cell (C-004 over-collapse killer) + absent-field
#     positive control. The two are the negative/positive control PAIR.
# --------------------------------------------------------------------------- #
def test_corrupt_meta_raises_typed_error_not_classified_primary(tmp_path: Path) -> None:
    """(a-) C-004: malformed primary ``meta.json`` RAISES, never silent PRIMARY.

    The guarded read-side seam reads primary meta first; a malformed ``meta.json``
    cannot be classified, so the read path surfaces the typed corrupt-meta
    :class:`MissionMetaReadError` (the historical default ``load_meta`` contract
    was a raw ``ValueError``; ``read_primary_meta`` is routed through the ONE
    fail-closed reader ``load_meta_fail_closed`` since the #3162 pass). The
    absent-field collapse must NOT fold this arm into a silent PRIMARY
    classification — doing so is the over-collapse mutant this kills.
    """
    _init_repo(tmp_path)
    _write_malformed_meta(tmp_path / "kitty-specs" / SLUG_WITH_MID8)

    with pytest.raises(MissionMetaReadError, match="Malformed JSON"):
        resolve_handle_to_read_path(tmp_path, SLUG_WITH_MID8, require_exists=True)


def test_absent_topology_field_classifies_concrete_never_none(tmp_path: Path) -> None:
    """(a+) absent-field positive control: no ``topology`` key → concrete topology.

    A readable primary meta with NO ``topology`` field (un-backfilled / flattened)
    is ABSORBED to a concrete :class:`MissionTopology` (never ``None``). This is the
    positive control mate of the corrupt-meta negative: absent FIELD classifies;
    absent/corrupt META degrades — the two stay distinct paths (C-004).
    """
    primary = tmp_path / "kitty-specs" / SLUG_WITH_MID8
    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_slug": SLUG_WITH_MID8,
        "coordination_branch": None,
    }
    _write_meta(primary, meta)

    topology = classify_from_meta(meta, primary)
    assert topology is not None
    # #5100 FR-013 / #2602: an unstamped coord-less meta never derives
    # ``single_branch`` at runtime -- LANES (still PRIMARY routing).
    assert topology is MissionTopology.LANES
    # Negative control: a coord-declaring readable meta classifies to a DIFFERENT
    # (coord-routing) concrete topology — proving classification reads the signal,
    # not a constant.
    coord_meta = dict(meta, coordination_branch=COORD_BRANCH)
    assert classify_from_meta(coord_meta, primary) is MissionTopology.COORD


def test_corrupt_meta_lenient_primitive_degrades_not_raises(tmp_path: Path) -> None:
    """(a) C-004 lenient leg: the never-raise primitive degrades a corrupt meta.

    ``candidate_feature_dir_for_mission`` / ``resolve_feature_dir_for_slug`` keep
    their historical contract of NEVER raising on a bad ``meta.json`` — a malformed
    meta degrades the topology read to the legacy probe (returns the best-known
    primary candidate) rather than the typed raise the guarded seam emits. This pins
    that the two corrupt-meta contracts (raise vs degrade) stay DISTINCT after the
    collapse — neither is folded into the other.
    """
    _init_repo(tmp_path)
    primary = tmp_path / "kitty-specs" / SLUG_WITH_MID8
    _write_malformed_meta(primary)

    # Neither lenient primitive raises; both return the primary candidate dir.
    assert candidate_feature_dir_for_mission(tmp_path, SLUG_WITH_MID8).name == SLUG_WITH_MID8
    assert resolve_feature_dir_for_slug(tmp_path, SLUG_WITH_MID8).name == SLUG_WITH_MID8


# --------------------------------------------------------------------------- #
# (b) KEEP set as executable pins — C-001 husk short-circuit, C-003 5-hop path,
#     C-005 transient probes. Each pinned by an assertion, not a comment.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("stored_topology", "expected"),
    [
        (MissionTopology.COORD.value, True),
        (MissionTopology.LANES_WITH_COORD.value, True),
        (MissionTopology.SINGLE_BRANCH.value, False),
        (MissionTopology.LANES.value, False),
        (None, True),  # legacy (no stored) → preserve husk-consulting once
    ],
)
def test_keep_c001_husk_short_circuit_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stored_topology: str | None,
    expected: bool,
) -> None:
    """(b) KEEP C-001: the husk short-circuit gate decision is unchanged.

    Coord-routing OR no-stored (legacy) → the registered ``-coord`` husk IS the
    authoritative surface (True); a coord-less stored topology → the husk is stale
    (False). The collapse must not clip this defense (the ``df79f76f4`` data-loss
    guard). Paired coord/coord-less rows are mutual negative controls.
    """
    from specify_cli.coordination import surface_resolver

    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_slug": SLUG_WITH_MID8,
        "coordination_branch": COORD_BRANCH,
    }
    if stored_topology is not None:
        meta["topology"] = stored_topology

    monkeypatch.setattr(
        surface_resolver,
        "read_primary_meta",
        lambda _root, _slug: (meta, tmp_path / "kitty-specs" / SLUG_WITH_MID8),
    )
    result = surface_resolver._husk_is_authoritative_surface(tmp_path, SLUG_WITH_MID8)
    assert result is expected


def test_keep_c003_five_hop_feature_dir_path(tmp_path: Path) -> None:
    """(b) KEEP C-003: the 5-hop ``candidate_feature_dir_for_mission`` path resolves.

    The lenient surface/aggregate read primitive (the ticket-anchored
    #1718/#1589/#1848/#2062 hops) must still resolve a coord-routing mission to its
    materialized coord worktree dir, and a flattened mission to PRIMARY — the
    collapse keeps the 5-hop path intact. Both arms asserted with their stored
    topology as mutual negative controls.
    """
    _init_repo(tmp_path)
    # Coord-routing mission with a materialized coord worktree → coord dir.
    coord_meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "coordination_branch": COORD_BRANCH,
        "topology": MissionTopology.COORD.value,
    }
    _write_meta(tmp_path / "kitty-specs" / SLUG_WITH_MID8, coord_meta)
    coord_root = tmp_path / ".worktrees" / f"{SLUG_WITH_MID8}-coord"
    coord_dir = coord_root / "kitty-specs" / SLUG_WITH_MID8
    coord_dir.mkdir(parents=True)
    _write_meta(coord_dir, coord_meta)

    resolved = candidate_feature_dir_for_mission(tmp_path, SLUG_WITH_MID8)
    assert resolved.resolve() == coord_dir.resolve()

    # Negative control: a FLATTENED mission resolves PRIMARY, not the coord dir.
    flat_slug = f"flat-{MID8}"
    flat_primary = tmp_path / "kitty-specs" / flat_slug
    _write_meta(
        flat_primary,
        {"mission_id": MISSION_ID, "topology": MissionTopology.SINGLE_BRANCH.value},
    )
    assert (
        candidate_feature_dir_for_mission(tmp_path, flat_slug).resolve()
        == flat_primary.resolve()
    )


def test_keep_c005_probe_coord_state_empty_and_deleted(tmp_path: Path) -> None:
    """(b) KEEP C-005: the transient probes (EMPTY / DELETED) are unchanged.

    ``probe_coord_state`` discriminates MATERIALIZED / EMPTY / DELETED /
    UNMATERIALIZED — orthogonal to topology SHAPE. The collapse must leave these
    transient-state probes intact. Each state is pinned with a distinct on-disk
    fixture; the four verdicts are mutual negative controls.
    """
    _init_repo(tmp_path)
    coord_root = tmp_path / ".worktrees" / f"{SLUG_WITH_MID8}-coord"
    coord_dir = coord_root / "kitty-specs" / SLUG_WITH_MID8

    # EMPTY: coord root materialized, mission dir absent.
    coord_root.mkdir(parents=True)
    assert probe_coord_state(tmp_path, SLUG_WITH_MID8, MID8) is CoordState.EMPTY

    # MATERIALIZED: mission dir present (negative control for EMPTY).
    coord_dir.mkdir(parents=True)
    assert probe_coord_state(tmp_path, SLUG_WITH_MID8, MID8) is CoordState.MATERIALIZED

    # DELETED: a different mission whose coord root is absent AND whose declared
    # branch is gone from git → the single git rev-parse arm yields DELETED.
    other = f"deleted-{MID8}"
    assert (
        probe_coord_state(
            tmp_path, other, MID8, coordination_branch="kitty/mission-gone-deadbeef"
        )
        is CoordState.DELETED
    )
    # UNMATERIALIZED negative control: no branch signal supplied → cannot be DELETED.
    assert probe_coord_state(tmp_path, other, MID8) is CoordState.UNMATERIALIZED


def _module_called_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return names


def test_canonical_predicate_decides_read_path_routing() -> None:
    """(c) FR-005 behavioural: the canonical predicate is the read-path authority.

    The deleted local predicate was a thin call-through; its replacement
    ``routes_through_coordination`` must give the SAME 4-member truth table the read
    path now consults. Absolute per-topology assertion (CT5).
    """
    assert routes_through_coordination(MissionTopology.COORD) is True
    assert routes_through_coordination(MissionTopology.LANES_WITH_COORD) is True
    assert routes_through_coordination(MissionTopology.SINGLE_BRANCH) is False
    assert routes_through_coordination(MissionTopology.LANES) is False


# --------------------------------------------------------------------------- #
# (d) load_meta contract cells — observable RETURN per (missing, malformed)
#     contract across the 4 converted files (CT4: return value, not call args).
# --------------------------------------------------------------------------- #
def test_load_meta_canonical_default_contract(tmp_path: Path) -> None:
    """(d) FR-006: the canonical default contract — None on missing, raise on malformed.

    All 4 topology files read meta with the canonical default
    (``allow_missing=True, on_malformed="raise"``). Pin the observable RETURN of that
    contract directly: a missing file yields ``None`` (absorbed); a malformed file
    raises ``ValueError``. This is the contract every converted site reproduces.
    """
    from specify_cli.mission_metadata import load_meta

    # Missing file → None (the absent arm the resolution.py sites treat as "").
    assert load_meta(tmp_path) is None

    # Malformed file → ValueError (the raise arm status_transition / surface_resolver
    # / resolution propagate as the corrupt-meta signal).
    _write_malformed_meta(tmp_path)
    with pytest.raises(ValueError, match="Malformed JSON"):
        load_meta(tmp_path)


def test_resolution_topology_read_degrades_on_corrupt_meta(tmp_path: Path) -> None:
    """(d) FR-006: ``resolution._resolve_topology`` classifies-from-branch on corrupt meta.

    The resolution.py site wraps ``read_topology`` (which uses canonical
    ``load_meta``) in ``except (FileNotFoundError, ValueError)`` → classify from the
    coordination-branch value with no lanes. Observable RETURN: a stable
    :class:`MissionTopology` even when meta is unreadable. Paired coord/flat controls.
    """
    from mission_runtime import resolution

    primary = tmp_path / "kitty-specs" / SLUG_WITH_MID8
    _write_malformed_meta(primary)
    # No coordination_branch resolvable on disk → flat classification.
    result = resolution._resolve_topology(tmp_path, SLUG_WITH_MID8)
    assert result is classify_topology(None, has_lanes=False)
    assert result is MissionTopology.SINGLE_BRANCH


def test_status_transition_meta_exists_false_on_missing(tmp_path: Path) -> None:
    """(d) FR-006: status_transition treats a missing meta as not-exists (not raise).

    The status_transition.py site reads ``load_meta(feature_dir)`` and derives
    ``meta_exists = isinstance(meta, dict)``. A missing meta yields ``None`` →
    ``meta_exists`` False (the bootstrap window). Observable: the canonical reader
    returns ``None`` for the missing-file arm this site depends on.
    """
    from specify_cli.mission_metadata import load_meta

    feature_dir = tmp_path / "kitty-specs" / SLUG_WITH_MID8
    feature_dir.mkdir(parents=True)
    meta = load_meta(feature_dir)
    assert meta is None
    assert not isinstance(meta, dict)


def test_no_hand_rolled_meta_json_reader_in_owned_file() -> None:
    """(d) FR-006 campsite: no hand-rolled ``json.loads(... meta.json ...)`` reader.

    The dead local ``_declares_coordination_branch`` JSON reader is converted onto
    the canonical ``load_meta`` seam. Assert by AST that the owned read-path resolver
    contains no direct ``json.loads`` call (the canonical reader is the single meta
    decode authority — NFR-004).
    """
    called = _module_called_names(_READ_PATH_RESOLVER)
    # ``json.loads`` is an attribute call (ast.Attribute), captured separately:
    tree = ast.parse(_READ_PATH_RESOLVER.read_text(encoding="utf-8"))
    json_loads = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "loads"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "json"
        for node in ast.walk(tree)
    )
    assert not json_loads, (
        "the owned read-path resolver must read meta via the canonical load_meta "
        "seam, not a hand-rolled json.loads (NFR-004)"
    )
    assert "load_meta" in called
