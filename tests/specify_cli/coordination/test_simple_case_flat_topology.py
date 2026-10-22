"""WP08 keystone — the NFR-006 "simple case still works" flat-topology test.

This is the **operator's binding requirement** (NFR-006 / SC-007 / SC-008 /
C-SIMPLECASE): when every diff-type target resolves to the **base** branch — a
real single-branch repo with a full 26-char ULID ``mission_id``, **no**
``coordination_branch`` declared, **no** lane worktree — spec-kitty MUST run
**exactly as it did before lanes/coordination existed**. Every adopted fragment
resolves to the base; **zero** ``.worktrees/``/coordination paths are read or
written; the write-target is ``target_branch`` (the base), not git HEAD; and the
emitted status event shape matches the pre-lane flat baseline.

Why this is the keystone (not a weaker assertion)
--------------------------------------------------
The WP05 review surfaced a binding subtlety: the NFR-006 simple case is the
**same topology** ``BookkeepingTransaction`` classifies as *legacy* (full ULID,
``meta.json`` present, no ``coordination_branch``). On that path
``MissionStatus.save`` → ``BookkeepingTransaction.acquire`` routes the
write-target through ``_resolve_legacy_lane_destination``, which reads
``git symbolic-ref HEAD`` of the operator's worktree — a seam that **BYPASSES**
the ``_identity_for_request`` write-target resolver WP05 fixed
(``coordination/status_transition.py::_resolve_write_target`` →
``resolve_placement_only(...).ref``).

Therefore this keystone drives the **full** ``MissionStatus.save`` end-to-end
path (not just the resolvers), so it observes the value spec-kitty *actually
commits*. In the genuine flat case ``git HEAD == target_branch == base`` (the
repo is on ``main``, which IS ``target_branch``), so the legacy-override reading
HEAD yields ``target_branch`` — **benign, because it equals base**. This matches
NFR-006's "byte-identical to pre-lane behaviour": the historical flat path always
committed to HEAD, and here HEAD == base. We assert the commit receipt's
``destination_ref`` resolves to ``target_branch`` (== base) via the full save
path, and that NO coord/lane surface is touched.

#1716 residual note (deferred, does NOT bite the genuine simple case)
---------------------------------------------------------------------
The ``BookkeepingTransaction`` legacy-override on ``git symbolic-ref HEAD`` is a
**deferred #1716 residual** (the topology-authority root, C-003 / out of scope).
It only diverges from ``target_branch`` under **topology divergence** —
``git HEAD != target_branch`` — i.e. an operator standing on an off-target lane
branch while running a flat-topology mission (witnessed by
``tests/unit/status/test_mission_status_aggregate.py::
test_save_supports_identity_bearing_legacy_mission``, which parks HEAD on
``legacy-lane``). It does **NOT** bite the NFR-006 simple case, where HEAD == base
by construction — so NFR-006 holds. The CWD-invariant write-target fix WP05
landed lives in ``_resolve_write_target`` (asserted directly below as the
fragment-level proof), separate from the transaction's HEAD-based legacy override.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionArtifactKind
from mission_runtime.resolution import resolve_placement_only
from specify_cli.coordination.status_transition import (
    _resolve_write_target,
)
from specify_cli.coordination.surface_resolver import (
    WorktreeTopology,
    classify_worktree_topology,
    resolve_status_surface,
)
from specify_cli.core.paths import get_main_repo_root, resolve_canonical_root
from specify_cli.lanes.persistence import resolve_lanes_dir
from specify_cli.status.aggregate import MissionStatus
from specify_cli.status import lifecycle_events
from specify_cli.status.store import _SlugResolver
from specify_cli.workspace.root_resolver import resolve_status_lock_root

from tests.specify_cli.write_side.topology_fixtures import (
    KITTY_SPECS,
    TARGET_BRANCH,
    PrimaryTopology,
    _init_repo,
    _run_git,
    build_primary,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: The single canonical event we stage so ``MissionStatus.save`` has a real
#: artifact to commit through ``BookkeepingTransaction``. Pre-lane-shaped:
#: ``feature_slug``/``mission_slug``, no coord/lane fields.
_KEYSTONE_EVENT_ID = "01KV9W0XKEYSTONE0FLAT00001"

# ---------------------------------------------------------------------------
# Production-shaped flat-save fixture (NFR-002): a full 26-char ULID mission
# whose on-disk dir is ``kitty-specs/<slug>-<mid8>/`` — the REAL Identity-Model
# (083+) dir shape the ``BookkeepingTransaction`` save path resolves via
# ``coord_mission_dir_name(slug, mid8)``. The genuine simple case carries the
# mid8-suffixed dir (it is NOT a bare-slug stand-in); the slug therefore embeds
# the exact-case mid8 so ``coord_mission_dir_name`` is idempotent on it (matching
# the witnessing legacy aggregate test, which embeds ``01LEGACY``). No coord
# branch, no lanes — the flat collapse the save path must run.
_FLAT_SAVE_MISSION_ID = "01KV9W0XKEYSTONEFLATSAVE01"
_FLAT_SAVE_MID8 = _FLAT_SAVE_MISSION_ID[:8]  # "01KV9W0X"
_FLAT_SAVE_SLUG = f"write-side-keystone-flat-{_FLAT_SAVE_MID8}"

#: The flat mission's base branch IS its own working branch — NOT ``main``.
#: This is the production truth of the pre-lane flat path: status bookkeeping was
#: committed to the operator's working branch (HEAD), and ``main``/``master`` are
#: PROTECTED — Spec Kitty has always refused status commits onto them
#: (``git.commit_helpers._DEFAULT_PROTECTED_BRANCHES``), a guard orthogonal to and
#: older than lanes/coordination. The genuine simple case therefore has
#: ``target_branch`` == the (non-protected) working branch, so HEAD == base ==
#: target_branch all coincide and the commit is permitted (the byte-identical
#: pre-lane flat behaviour). Using ``main`` here would not model the flat case —
#: it would model the (rejected) "commit status to the protected default" path.
_FLAT_SAVE_BASE_BRANCH = "kitty/mission-write-side-keystone-flat-01kv9w0x"


def _build_flat_save_mission(tmp_path: Path) -> PrimaryTopology:
    """Build a real single-branch repo whose mission dir is ``<slug>-<mid8>``.

    This is the production-true simple case for the FULL ``MissionStatus.save``
    path: full ULID ``mission_id``, NO ``coordination_branch``, NO lane worktree,
    HEAD on the (non-protected) base branch where base == ``target_branch``. The
    dir name matches ``_mission_specs_dir_name`` so the save path classifies it as
    a legacy (== flat) mission and resolves its meta.json (the bare-slug WP01
    builder is for resolver-level fragments, which do not go through that dir-name
    grammar). The single working branch IS ``target_branch`` (flat: no separate
    lane/coord branch), so HEAD == base == target_branch — the flat collapse.
    """
    repo = tmp_path / "flat-save-checkout"
    _init_repo(repo)  # default branch ``main`` with an initial commit
    # Rename the single branch to the mission's working branch so the flat
    # base == target_branch == HEAD, and it is NOT a protected branch.
    _run_git(repo, "branch", "-m", TARGET_BRANCH, _FLAT_SAVE_BASE_BRANCH)
    feature_dir = repo / KITTY_SPECS / _FLAT_SAVE_SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    (repo / ".kittify").mkdir(parents=True, exist_ok=True)
    (repo / ".kittify" / "config.yaml").write_text("agents: {}\n", encoding="utf-8")
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _FLAT_SAVE_MISSION_ID,
                "mid8": _FLAT_SAVE_MID8,
                "mission_slug": _FLAT_SAVE_SLUG,
                "target_branch": _FLAT_SAVE_BASE_BRANCH,
            }
        ),
        encoding="utf-8",
    )
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "kittify + flat mission")
    return PrimaryTopology(
        repo_root=repo,
        feature_dir=feature_dir,
        mission_id=_FLAT_SAVE_MISSION_ID,
        mission_slug=_FLAT_SAVE_SLUG,
        target_branch=_FLAT_SAVE_BASE_BRANCH,
    )


def _stage_flat_status_event(primary: PrimaryTopology) -> Path:
    """Write a single pre-lane-shaped status event into the flat mission dir.

    Returns the ``status.events.jsonl`` path so the caller can assert the
    on-disk event shape against the historical flat baseline.
    """
    event = {
        "event_id": _KEYSTONE_EVENT_ID,
        "mission_slug": primary.mission_slug,
        "feature_slug": primary.mission_slug,
        "wp_id": "WP01",
        "from_lane": "planned",
        "to_lane": "claimed",
        "at": "2026-06-17T12:00:00+00:00",
        "actor": "keystone",
        "force": False,
        "execution_mode": "worktree",
        "evidence": None,
        "reason": None,
        "review_ref": None,
    }
    events_path = primary.feature_dir / "status.events.jsonl"
    events_path.write_text(json.dumps(event) + "\n", encoding="utf-8")
    return events_path


# ---------------------------------------------------------------------------
# The keystone: full MissionStatus.save end-to-end path on the flat topology
# ---------------------------------------------------------------------------


def test_flat_save_writes_target_branch_via_full_save_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """KEYSTONE (NFR-006 / SC-008): the full save path commits to base == target_branch.

    Drives ``MissionStatus.load(...).save(...)`` end-to-end on a real
    single-branch repo (full ULID, no coord, no lanes), from the repo root with
    HEAD on ``main`` (the base) — i.e. ``git HEAD == target_branch == base``.

    This is the test that reveals whether the simple case genuinely writes
    ``target_branch``: it observes the value spec-kitty actually commits via the
    ``BookkeepingTransaction`` legacy path (the seam that bypasses
    ``_identity_for_request``). In the pure flat case the legacy-override reading
    HEAD SHOULD yield ``target_branch`` because HEAD == base — and we assert it
    does, plus that the committed artifact lands on ``target_branch`` itself.

    If the receipt's ``destination_ref`` were to DIVERGE from ``target_branch``
    here, that would be a real NFR-006 failure (the flat case is the one place it
    must NOT diverge) — this assertion is the binding guard for that.
    """
    primary = _build_flat_save_mission(tmp_path)
    # The flat invariant: the single working branch IS the base; HEAD == base ==
    # target_branch (no separate lane/coord branch — the flat collapse).
    _stage_flat_status_event(primary)
    # Drive WITHOUT cd-ing anywhere off-target and WITHOUT an explicit repo_root
    # threading (paula's trap): the operator stands in the flat checkout on base.
    monkeypatch.chdir(primary.repo_root)

    ms = MissionStatus.load(repo_root=primary.repo_root, mission_slug=primary.mission_slug)
    # The flat mission is legacy-topology (no coordination_branch) — the same
    # topology that exercises the BookkeepingTransaction HEAD-reading override.
    assert ms.topology == "legacy"
    assert ms.coordination_branch is None
    assert ms.mission_id == primary.mission_id  # full 26-char ULID, no fabrication

    receipt = ms.save(operation="keystone-flat-save")

    # The write/merge-target == target_branch (the base) — NOT a coord/lane ref.
    # In the flat case HEAD == base, so the legacy-override (which reads
    # ``git symbolic-ref HEAD``) yields the base too: byte-identical to the
    # historical pre-lane flat path (NFR-006/SC-008). It is NOT a coord branch.
    assert receipt.destination_ref == primary.target_branch
    assert "-coord" not in receipt.destination_ref
    assert "-lane-" not in receipt.destination_ref
    # The artifact really committed onto target_branch (observable, not a vibe):
    committed = subprocess.run(
        [
            "git",
            "-C",
            str(primary.repo_root),
            "show",
            f"{primary.target_branch}:{KITTY_SPECS}/{primary.mission_slug}/status.events.jsonl",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    # The committed event carries the pre-lane flat shape (the observable baseline).
    persisted = json.loads(committed.strip())
    assert persisted["event_id"] == _KEYSTONE_EVENT_ID
    assert persisted["to_lane"] == "claimed"
    # Pre-lane flat event shape: no coordination/lane routing fields leaked in.
    assert "coordination_branch" not in persisted
    assert "lane" not in persisted

    # The write landed in the primary checkout worktree — NOT a coord worktree.
    assert receipt.worktree_root.resolve() == primary.repo_root.resolve()
    assert ".worktrees" not in receipt.worktree_root.resolve().parts


def test_flat_save_touches_zero_worktree_or_coord_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """KEYSTONE (NFR-006 / SC-007): the captured path-set has ZERO coord/lane entries.

    Renata S-1 — "byte-identical to pre-lane" needs an OBSERVABLE baseline, not a
    spot-check. We capture the SET of filesystem paths the full save path opens
    for writing (via ``pathlib.Path.open`` interception) and assert NONE is under
    ``.worktrees/`` or any coordination surface. The flat topology must touch
    only the primary checkout.
    """
    primary = _build_flat_save_mission(tmp_path)
    _stage_flat_status_event(primary)
    monkeypatch.chdir(primary.repo_root)

    opened_for_write: list[Path] = []
    # ``Path.open`` is heavily overloaded; capture it as a plain callable so the
    # pass-through wrapper does not have to satisfy every typed overload.
    real_open: Callable[..., Any] = Path.open

    def _tracking_open(self: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            opened_for_write.append(self.resolve())
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", _tracking_open)

    ms = MissionStatus.load(repo_root=primary.repo_root, mission_slug=primary.mission_slug)
    ms.save(operation="keystone-flat-pathset")

    # Assert on the captured path-SET (not a spot-check): zero coord/lane writes.
    worktree_writes = [p for p in opened_for_write if ".worktrees" in p.parts]
    assert worktree_writes == [], (
        "flat-topology save must touch ZERO .worktrees/coord paths; got: "
        f"{worktree_writes}"
    )
    # And every write that DID happen lives under the primary checkout root.
    repo_root = primary.repo_root.resolve()
    stray = [p for p in opened_for_write if repo_root not in p.parents and p != repo_root]
    assert stray == [], f"flat-topology save wrote outside the primary checkout: {stray}"


# ---------------------------------------------------------------------------
# Fragment-level proof: every adopted fragment resolves to base (== the WP01
# frozen oracle value), and the CWD-invariant write-target fix is base too.
# ---------------------------------------------------------------------------


def test_flat_every_adopted_fragment_resolves_to_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """KEYSTONE (NFR-006 / SC-007): every adopted fragment == base, zero coord paths.

    The full-save path above proves the committed behaviour; this pins the
    *fragment* values the adoption routes through (root, placement, status
    surface, lanes, write-target). On the flat topology each MUST equal the base
    (the WP01 frozen ``expected_primary_root`` oracle) and NONE may resolve under
    ``.worktrees/``. Driven WITHOUT explicit ``repo_root`` (paula's trap).
    """
    primary = build_primary(tmp_path)
    monkeypatch.chdir(primary.repo_root)
    fd = primary.feature_dir
    base = primary.expected_primary_root  # the WP01 frozen oracle value

    # --- root fragment (workspace.primary_root surrogate resolvers, FR-001) ---
    assert resolve_canonical_root(fd) == base
    assert get_main_repo_root(primary.repo_root) == base
    assert resolve_status_lock_root(fd, None) == base
    assert lifecycle_events._repo_root_for_lifecycle_log(fd / "status.events.jsonl") == base
    # store.py slug resolver anchors on the flat specs root (no ancestor escape).
    assert _SlugResolver(fd)._mission_specs_root == fd.parent

    # --- placement / write-target fragment (branch_ref.destination_ref, FR-004) ---
    # STATUS_STATE (coord-preserving) kind: flat topology → target_branch
    # (write-surface-coherence WP02 / T031).
    placement = resolve_placement_only(
        primary.repo_root, primary.mission_slug, kind=MissionArtifactKind.STATUS_STATE
    )
    assert placement.ref == primary.target_branch  # flat arm → target_branch
    # The adopted write-target resolver agrees and is CWD-invariant base, NOT HEAD.
    assert _resolve_write_target(primary.repo_root, primary.mission_slug, None) == (
        primary.target_branch
    )

    # --- status surface fragment (status_surface.status_write_dir, FR-003) ---
    surface = resolve_status_surface(primary.repo_root, primary.mission_slug)
    assert surface == fd / "status.events.jsonl"
    assert ".worktrees" not in surface.parts
    # The flat mission is NOT classified as a coord worktree.
    assert classify_worktree_topology(fd) is not WorktreeTopology.COORD_WORKTREE

    # --- lanes fragment (resolve_lanes_dir, FR-008) ---
    lanes = resolve_lanes_dir(fd)
    assert lanes == fd / "lanes.json"
    assert ".worktrees" not in lanes.parts

    # The whole-object invariant (C-SIMPLECASE): the union of every fragment path
    # touches ZERO .worktrees/coord surfaces — the flat collapse.
    every_fragment_path = [
        base,
        placement.ref,
        surface,
        lanes,
        fd,
    ]
    for value in every_fragment_path:
        assert ".worktrees" not in str(value), f"fragment leaked a coord path: {value}"


def test_flat_write_target_is_cwd_invariant_base_not_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-008 flat arm: the adopted write-target stays base even off-target.

    This isolates the WP05 fragment-level fix from the BookkeepingTransaction
    legacy override (the deferred #1716 residual). The adopted
    ``_resolve_write_target`` is CWD-invariant: parking HEAD on an off-target lane
    branch does NOT move it off ``target_branch`` (the latent bug it supersedes).
    The transaction-level HEAD override is what would diverge here — which is why
    the keystone save-path test above asserts the GENUINE simple case (HEAD == base).
    """
    primary = build_primary(tmp_path)
    monkeypatch.chdir(primary.repo_root)

    on_base = _resolve_write_target(primary.repo_root, primary.mission_slug, None)
    assert on_base == primary.target_branch

    off_target = "kitty/mission-write-side-primary-01kv9w0x-lane-z"
    _run_git(primary.repo_root, "checkout", "-q", "-b", off_target)
    # HEAD now diverges from base, but the adopted resolver stays on base.
    off = _resolve_write_target(primary.repo_root, primary.mission_slug, None)
    assert off == primary.target_branch
    assert off != off_target
