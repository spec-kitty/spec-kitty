"""Status read matrix: topology x coordination state x owned x cwd (Mission lane-worktree-model-hardening, WP04).

A characterization of the directory every root-taking status entry point resolves today, per
cell, on real git fixtures (no resolver is patched). The entry points are
``resolve_status_surface_with_anchor``, ``candidate_feature_dir_for_mission``,
``MissionStatus.load``, ``resolve_surface_dir_or_typed_error`` and
``committed_authority.primary_surface_dir``, plus the one read door
``resolve_status_read`` (WP05).

Each Mission carries a registered lane worktree (for ``lanes`` / ``lanes_with_coord``) whose
``kitty-specs/<mission>/`` copy is the fork-time shadow (``planned``) while the authority has
moved on (``in_progress``):

* ``single_branch`` / ``lanes``: the authority is the repository root checkout's working tree
  (the write checkout);
* ``lanes_with_coord``: the authority is the coordination branch, and the repository root
  checkout carries a stale decoy log:
  - ``materialized``: the coordination worktree is checked out and holds the log;
  - ``empty``: the coordination worktree is checked out with no Mission directory;
  - ``unmaterialized``: the coordination branch holds the log, no worktree is checked out.

No lane-checkout cell resolves the lane copy (``LANE``) since WP04 (FR-002).

Labels: ``ROOT`` (the repository root checkout's Mission dir), ``LANE`` (the lane worktree's
copy), ``COORD`` (the coordination worktree's Mission dir), ``NESTED`` (a coordination path
composed under the coordination worktree itself), a ``(missing)`` suffix when the path does not
exist, or ``!<ExceptionName>``. Cells that a later work package changes carry a comment naming it.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.coordination.status_service import (
    EventLogWriteContract,
    append_event_stream_log,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.models import Lane, StatusEvent

MID8 = "01KXMATR"
MISSION_ID = f"{MID8}000000000000000001"
SLUG = f"matrix-{MID8}"
MISSION_BRANCH = f"kitty/mission-{SLUG}"
COORD_BRANCH = MISSION_BRANCH
LANE_BRANCH = f"{MISSION_BRANCH}-lane-a"
KITTY_SPECS = "kitty-specs"

SINGLE_BRANCH = "single_branch"
LANES = "lanes"
LANES_WITH_COORD = "lanes_with_coord"

MATERIALIZED = "materialized"
EMPTY = "empty"
UNMATERIALIZED = "unmaterialized"
NOT_APPLICABLE = "n/a"

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WP_FILE = "---\nwork_package_id: WP01\ntitle: Matrix WP01\ndependencies: []\nsubtasks: []\n---\n\n# WP01\n"


@dataclass(frozen=True)
class MatrixMission:
    """Paths of one materialized matrix Mission."""

    repo: Path
    topology: str
    coord_state: str
    lane_worktree: Path | None
    coord_worktree: Path | None

    @property
    def root_mission_dir(self) -> Path:
        return self.repo / KITTY_SPECS / SLUG

    @property
    def lane_mission_dir(self) -> Path | None:
        return None if self.lane_worktree is None else self.lane_worktree / KITTY_SPECS / SLUG

    @property
    def coord_mission_dir(self) -> Path:
        return self.repo / ".worktrees" / f"{SLUG}-coord" / KITTY_SPECS / SLUG


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _event(event_id: str, from_lane: Lane, to_lane: Lane, at: str) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=SLUG,
        mission_id=MISSION_ID,
        wp_id="WP01",
        from_lane=from_lane,
        to_lane=to_lane,
        at=at,
        actor="matrix",
        force=False,
        reason="matrix",
        execution_mode="worktree",
    )


PLANNED = _event("01KXMATR0SEED00000000000001", Lane.GENESIS, Lane.PLANNED, "2026-11-06T00:00:00+00:00")
CLAIMED = _event("01KXMATR0SEED00000000000002", Lane.PLANNED, Lane.CLAIMED, "2026-11-06T00:01:00+00:00")
IN_PROGRESS = _event("01KXMATR0SEED00000000000003", Lane.CLAIMED, Lane.IN_PROGRESS, "2026-11-06T00:02:00+00:00")


def _append_root(mission_dir: Path, events: list[StatusEvent]) -> None:
    append_event_stream_log(EventLogWriteContract.primary_checkout_append(mission_dir), list(events))


def _append_coord(mission_dir: Path, events: list[StatusEvent]) -> None:
    append_event_stream_log(EventLogWriteContract.coordination_transaction_append(mission_dir), list(events))


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "matrix@example.invalid")
    git(repo, "config", "user.name", "Matrix")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / "README.md").write_text("matrix fixture\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "root commit")


def _write_planning(repo: Path, topology: str) -> Path:
    mission_dir = repo / KITTY_SPECS / SLUG
    (mission_dir / "tasks").mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mission_slug": SLUG,
        "slug": SLUG,
        "mid8": MID8,
        "mission_type": "software-dev",
        "target_branch": "main",
        "mission_branch": MISSION_BRANCH,
        "vcs": "git",
        "topology": topology,
    }
    if topology == LANES_WITH_COORD:
        meta["coordination_branch"] = COORD_BRANCH
    (mission_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (mission_dir / "tasks" / "WP01.md").write_text(_WP_FILE, encoding="utf-8")
    write_lanes_json(
        mission_dir,
        LanesManifest(
            version=1,
            mission_slug=SLUG,
            mission_id=MISSION_ID,
            mission_branch=MISSION_BRANCH,
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=(),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-11-06T00:00:00+00:00",
            computed_from="matrix",
        ),
    )
    return mission_dir


def _add_lane_worktree(repo: Path) -> Path:
    lane = repo / ".worktrees" / f"{SLUG}-lane-a"
    git(repo, "worktree", "add", "-q", "-b", LANE_BRANCH, str(lane))
    return lane


def _build_coord_branch(repo: Path, *, with_log: bool) -> None:
    """Create the coordination branch (from the root commit) and commit the log on it."""
    root_commit = git(repo, "rev-list", "--max-parents=0", "main")
    git(repo, "branch", COORD_BRANCH, root_commit)
    if not with_log:
        return
    scratch = repo / ".worktrees" / "matrix-coord-seed"
    git(repo, "worktree", "add", "-q", str(scratch), COORD_BRANCH)
    _append_coord(scratch / KITTY_SPECS / SLUG, [PLANNED, CLAIMED, IN_PROGRESS])
    git(scratch, "add", "-A")
    git(scratch, "commit", "-q", "-m", "coordination log")
    git(repo, "worktree", "remove", "-f", str(scratch))


def build_matrix_mission(base: Path, topology: str, coord_state: str = NOT_APPLICABLE) -> MatrixMission:
    """Materialize one matrix Mission under ``base``."""
    repo = base / "repo"
    _init_repo(repo)
    mission_dir = _write_planning(repo, topology)
    # The repository root checkout's log: the authority for single_branch/lanes, a stale
    # decoy for lanes_with_coord. Either way the lane worktree forks from ``planned``.
    _append_root(mission_dir, [PLANNED])
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "planning")

    lane_worktree = None if topology == SINGLE_BRANCH else _add_lane_worktree(repo)
    coord_worktree: Path | None = None
    if topology == LANES_WITH_COORD:
        _build_coord_branch(repo, with_log=coord_state != EMPTY)
        if coord_state in (MATERIALIZED, EMPTY):
            coord_worktree = repo / ".worktrees" / f"{SLUG}-coord"
            git(repo, "worktree", "add", "-q", str(coord_worktree), COORD_BRANCH)
    else:
        # The write checkout moves on after the lane worktree forked.
        _append_root(mission_dir, [CLAIMED, IN_PROGRESS])
    return MatrixMission(
        repo=repo,
        topology=topology,
        coord_state=coord_state,
        lane_worktree=lane_worktree,
        coord_worktree=coord_worktree,
    )


# ---------------------------------------------------------------------------
# Entry points and labels
# ---------------------------------------------------------------------------

ROOT = "ROOT"
LANE_COPY = "LANE"
COORD = "COORD"
NESTED_MISSING = "NESTED(missing)"
COORD_MISSING = "COORD(missing)"
_SENTINEL = Path("/on-missing-meta-sentinel")

ANCHOR = "resolve_status_surface_with_anchor"
CANDIDATE = "candidate_feature_dir_for_mission"
LOAD = "MissionStatus.load"
TYPED = "resolve_surface_dir_or_typed_error"
COMMITTED = "primary_surface_dir"
DOOR = "resolve_status_read"
REF = "REF"
"""The door's label for a ref-sourced surface (``COORD_BRANCH_REF``): no path, the committed branch."""


def _anchor(root: Path) -> Path:
    from specify_cli.coordination.surface_resolver import resolve_status_surface_with_anchor

    return resolve_status_surface_with_anchor(root, SLUG).read_dir


def _candidate(root: Path) -> Path:
    from specify_cli.missions._read_path_resolver import candidate_feature_dir_for_mission

    return candidate_feature_dir_for_mission(root, SLUG)


def _load(root: Path) -> Path:
    from specify_cli.status.aggregate import MissionStatus

    return MissionStatus.load(root, SLUG).read_dir


def _typed(root: Path) -> Path:
    from specify_cli.missions._read_path_resolver import resolve_surface_dir_or_typed_error

    return resolve_surface_dir_or_typed_error(root, SLUG, on_missing_meta=_SENTINEL)


def _committed(root: Path) -> Path:
    from runtime.next.committed_authority import primary_surface_dir

    return primary_surface_dir(root, SLUG)


_REF_SENTINEL = Path("/status-read-door/ref-sourced")


def _door(root: Path) -> Path:
    """The one read door (WP05): its path, or a sentinel the label maps to ``REF``."""
    from specify_cli.status.read_surface import resolve_status_read

    surface = resolve_status_read(root, SLUG)
    return surface.path if surface.path is not None else _REF_SENTINEL


ENTRY_POINTS: dict[str, Callable[[Path], Path]] = {
    ANCHOR: _anchor,
    CANDIDATE: _candidate,
    LOAD: _load,
    TYPED: _typed,
    COMMITTED: _committed,
    DOOR: _door,
}


def label(mission: MatrixMission, path: Path) -> str:
    """Name the surface ``path`` points at, with a ``(missing)`` suffix when it does not exist."""
    if path == _REF_SENTINEL:
        return REF
    candidates = {
        ROOT: mission.root_mission_dir,
        LANE_COPY: mission.lane_mission_dir,
        COORD: mission.coord_mission_dir,
    }
    resolved = path.resolve(strict=False)
    for name, candidate in candidates.items():
        if candidate is not None and resolved == candidate.resolve(strict=False):
            return name if path.exists() else f"{name}(missing)"
    if resolved.parts.count(".worktrees") > 1:
        return NESTED_MISSING if not path.exists() else "NESTED"
    return str(path)


def resolve_label(mission: MatrixMission, entry: str, root: Path) -> str:
    try:
        return label(mission, ENTRY_POINTS[entry](root))
    except Exception as exc:  # the matrix pins typed refusals as cell values
        return f"!{type(exc).__name__}"


# ---------------------------------------------------------------------------
# The matrix: (topology, coordination state, cwd) -> entry point -> label
# ---------------------------------------------------------------------------

CWD_ROOT = "repository_root_checkout"
CWD_LANE = "lane_checkout"
CWD_COORD = "coordination_worktree"


def _all(value: str) -> dict[str, str]:
    return dict.fromkeys(ENTRY_POINTS, value)


def _cell(door: str, **others: str) -> dict[str, str]:
    """A cell whose five legacy entry points read ``others`` and whose door reads ``door``."""
    return {**others, DOOR: door}


# The DOOR column is the one read door (WP05, FR-001/FR-003): one declared source per
# (topology, coordination state), the same from every cwd. The five legacy entry points keep
# their characterized values until WP06/WP07 move their callers onto the door.
MATRIX: dict[tuple[str, str, str], dict[str, str]] = {
    (SINGLE_BRANCH, NOT_APPLICABLE, CWD_ROOT): _all(ROOT),
    (LANES, NOT_APPLICABLE, CWD_ROOT): _all(ROOT),
    # A lane root re-anchors to the repository root (WP04, FR-002, #6884): every lane-checkout
    # cell reads exactly what its repository-root cell reads.
    (LANES, NOT_APPLICABLE, CWD_LANE): _all(ROOT),
    (LANES_WITH_COORD, MATERIALIZED, CWD_ROOT): {**_all(COORD), COMMITTED: ROOT},
    (LANES_WITH_COORD, MATERIALIZED, CWD_LANE): {**_all(COORD), COMMITTED: ROOT},
    # A coordination worktree root composes a nested coordination path in the legacy entry
    # points. The door (and the anchor, which delegates to it) re-anchors it (WP05).
    # changes in WP06 (cross-cwd parity) for the others.
    (LANES_WITH_COORD, MATERIALIZED, CWD_COORD): _cell(
        COORD,
        **{ANCHOR: COORD, CANDIDATE: COORD, LOAD: ROOT, TYPED: NESTED_MISSING, COMMITTED: ROOT},
    ),
    # Empty coordination worktree whose branch holds no log yet: the declared pre-seed
    # WRITE_CHECKOUT fallback (WP05, FR-003; the surface carries ``fallback_reason``).
    (LANES_WITH_COORD, EMPTY, CWD_ROOT): _all(ROOT),
    (LANES_WITH_COORD, EMPTY, CWD_LANE): _all(ROOT),
    # changes in WP06 (cross-cwd parity) for the legacy entry points
    (LANES_WITH_COORD, EMPTY, CWD_COORD): _cell(
        ROOT,
        **{ANCHOR: ROOT, CANDIDATE: COORD_MISSING, LOAD: ROOT, TYPED: NESTED_MISSING, COMMITTED: ROOT},
    ),
    # Unmaterialized coordination worktree: the door reads the committed branch (WP05, FR-003);
    # the legacy entry points still compose a missing path or read the root's stale copy
    # until WP06/WP07 migrate their callers.
    (LANES_WITH_COORD, UNMATERIALIZED, CWD_ROOT): _cell(
        REF,
        **{ANCHOR: COORD_MISSING, CANDIDATE: ROOT, LOAD: ROOT, TYPED: COORD_MISSING, COMMITTED: ROOT},
    ),
    (LANES_WITH_COORD, UNMATERIALIZED, CWD_LANE): _cell(
        REF,
        **{ANCHOR: COORD_MISSING, CANDIDATE: ROOT, LOAD: ROOT, TYPED: COORD_MISSING, COMMITTED: ROOT},
    ),
}

_MISSIONS: dict[tuple[str, str], MatrixMission] = {}


@pytest.fixture(scope="module")
def matrix_missions(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[tuple[str, str], MatrixMission]]:
    """Build each (topology, coordination state) Mission once per module; cells only read."""
    _MISSIONS.clear()
    yield _MISSIONS
    _MISSIONS.clear()


def _mission_for(
    cache: dict[tuple[str, str], MatrixMission],
    factory: pytest.TempPathFactory,
    topology: str,
    coord_state: str,
) -> MatrixMission:
    key = (topology, coord_state)
    if key not in cache:
        cache[key] = build_matrix_mission(factory.mktemp(f"{topology}-{coord_state}".replace("/", "-")), topology, coord_state)
    return cache[key]


def _cwd_root(mission: MatrixMission, cwd: str) -> Path:
    if cwd == CWD_LANE:
        assert mission.lane_worktree is not None
        return mission.lane_worktree
    if cwd == CWD_COORD:
        assert mission.coord_worktree is not None
        return mission.coord_worktree
    return mission.repo


@pytest.mark.parametrize(("topology", "coord_state", "cwd"), sorted(MATRIX))
def test_status_read_matrix_cell(
    topology: str,
    coord_state: str,
    cwd: str,
    matrix_missions: dict[tuple[str, str], MatrixMission],
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every entry point resolves the pinned surface for its cell, from the cell's cwd."""
    mission = _mission_for(matrix_missions, tmp_path_factory, topology, coord_state)
    root = _cwd_root(mission, cwd)
    monkeypatch.chdir(root)

    observed = {entry: resolve_label(mission, entry, root) for entry in ENTRY_POINTS}

    assert observed == MATRIX[(topology, coord_state, cwd)]


def test_owned_single_branch_reads_the_owned_mission_dir(tmp_path: Path) -> None:
    """Owned cell: a validated owned checkout's committed-authority anchor is the fact's own dir."""
    from mission_runtime import OwnedCheckout
    from runtime.next.committed_authority import primary_surface_dir
    from mission_runtime.context import MissionTopology

    mission = build_matrix_mission(tmp_path, SINGLE_BRANCH)
    owned_root = tmp_path / "owned-checkout"
    git(mission.repo, "worktree", "add", "-q", "-b", "owned-write", str(owned_root))
    fact = OwnedCheckout._mint(
        repository_root=mission.repo,
        owned_root=owned_root,
        mission_dir=owned_root / KITTY_SPECS / SLUG,
        mission_slug=SLUG,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="owned-write",
    )

    assert primary_surface_dir(mission.repo, SLUG, owned=fact) == owned_root / KITTY_SPECS / SLUG


# ---------------------------------------------------------------------------
# Acceptance (FR-002): a lane root re-anchors to the repository root
# ---------------------------------------------------------------------------


def _wp01_lane(mission_dir: Path) -> str | None:
    from specify_cli.status import wp_snapshot_state

    state = wp_snapshot_state(mission_dir, "WP01") or {}
    lane = state.get("lane")
    return None if lane is None else str(lane)


@pytest.mark.parametrize(
    ("topology", "coord_state", "authority"),
    [(LANES, NOT_APPLICABLE, ROOT), (LANES_WITH_COORD, MATERIALIZED, COORD)],
)
def test_lane_root_reads_write_checkout_state(
    topology: str,
    coord_state: str,
    authority: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User Story 1, scenario 2: from inside a lane checkout every entry point reads the authority.

    The lane copy says ``planned``; the authority (the write checkout, or the coordination worktree
    on a coordination Mission) says ``in_progress``.
    """
    mission = build_matrix_mission(tmp_path, topology, coord_state)
    assert mission.lane_worktree is not None
    assert mission.lane_mission_dir is not None
    assert _wp01_lane(mission.lane_mission_dir) == "planned"
    monkeypatch.chdir(mission.lane_worktree)

    for entry in (ANCHOR, CANDIDATE, LOAD, TYPED):
        resolved = ENTRY_POINTS[entry](mission.lane_worktree)
        assert label(mission, resolved) == authority, entry
        assert _wp01_lane(resolved) == "in_progress", entry


def test_repository_root_input_unchanged(tmp_path: Path) -> None:
    """Positive control (FR-002): a repository-root input is returned unchanged, and so is the read."""
    from specify_cli.missions._read_path_resolver import canonical_status_read_root

    mission = build_matrix_mission(tmp_path, LANES)

    assert canonical_status_read_root(mission.repo) == mission.repo
    for entry in ENTRY_POINTS:
        assert label(mission, ENTRY_POINTS[entry](mission.repo)) == ROOT, entry


def test_lane_root_normalizes_to_the_repository_root(tmp_path: Path) -> None:
    """The one normalization helper re-anchors a lane root, never returning a lane path."""
    from specify_cli.missions._read_path_resolver import canonical_status_read_root

    mission = build_matrix_mission(tmp_path, LANES)
    assert mission.lane_worktree is not None

    assert canonical_status_read_root(mission.lane_worktree).resolve() == mission.repo.resolve()


def test_root_outside_any_repository_is_unchanged(tmp_path: Path) -> None:
    """A directory in no git repository has no worktree registry and no lane: it stays as given."""
    from specify_cli.missions._read_path_resolver import canonical_status_read_root

    plain = tmp_path / "not-a-repository"
    plain.mkdir()

    assert canonical_status_read_root(plain) == plain


def test_root_with_a_headless_git_directory_is_unchanged(tmp_path: Path) -> None:
    """A ``.git`` directory without ``HEAD`` is no repository to git either: no registry to read."""
    from specify_cli.missions._read_path_resolver import canonical_status_read_root

    fake = tmp_path / "fake-repository"
    (fake / ".git").mkdir(parents=True)

    assert canonical_status_read_root(fake) == fake
