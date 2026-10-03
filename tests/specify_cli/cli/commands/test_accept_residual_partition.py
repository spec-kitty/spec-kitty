"""WP02 / FR-008: accept residual routing + M2 dirty-surface reconciliation.

``accept.py::_commit_residual_acceptance_artifacts`` used a raw ``git commit``
(``run_git(["commit", ...])``) scoped to the PRIMARY checkout only. Two bugs
followed from that:

* **Misrouting (T007)** — a coordination-topology mission's residual matrix /
  issue-matrix / status-view artifacts must land on the COORDINATION branch
  (the same surface :func:`~specify_cli.acceptance.matrix.write_acceptance_matrix`
  writes to under coord topology), but a raw ``git commit`` in the PRIMARY
  checkout can only ever commit files tracked in the PRIMARY tree — it has no
  way to reach a *different* git worktree at all.
* **M2 dirty-detection gap (T008)** — ``_spec_artifact_dirty_paths`` scanned
  only ``git_status_entries(repo_root)`` (the PRIMARY tree). Under coord
  topology the matrix write lands in the coordination worktree, a completely
  separate git checkout, so its dirt was invisible to the scan and the
  residual commit step silently no-opped, leaving the coord worktree dirty.

These tests build a REAL coordination-topology mission (a genuine
``git worktree`` materialised via the canonical
:class:`~specify_cli.coordination.workspace.CoordinationWorkspace`, not a
mock) and drive ``_spec_artifact_dirty_paths`` /
``_commit_residual_acceptance_artifacts`` directly — the same function-level
seam ``test_accept_clean_tree.py``'s
``test_residual_acceptance_commit_is_scoped_to_mission_paths`` already pins
for the PRIMARY-only case.

Identity is production-shaped: a full 26-char Crockford ULID and the
canonical on-disk ``<slug>-<mid8>`` layout (NFR-002/NFR-005), matching
``test_accept_gate_read_surface.py``'s coord fixture.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.acceptance.matrix import (
    AcceptanceMatrix,
    NegativeInvariant,
    read_acceptance_matrix,
    write_acceptance_matrix,
)
from kernel.git import GitPath, StatusEntry
from specify_cli.acceptance import _filter_coordination_residue
from specify_cli.cli.commands.accept import (
    _commit_residual_acceptance_artifacts,
    _residual_commit_files,
    _run_residual_acceptance_commit,
    _spec_artifact_dirty_paths,
)
from specify_cli.task_utils import TaskCliError
from specify_cli.coordination.commit_outcome import COORD_RECORD_IN_ROOT_CHECKOUT, commit_outcome_payload
from specify_cli.coordination.commit_router import partition_for_mission_path
from specify_cli.coordination.workspace import CoordinationWorkspace

pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]

# Production-shaped identity (NFR-002/NFR-005): a full 26-char Crockford-base32
# ULID, its first-8-char mid8, and the canonical ``<slug>-<mid8>`` handle.
_MISSION_ID = "01KWZV91XFXPKTBE77QT3KRSW8"
_MID8 = _MISSION_ID[:8]  # "01KWZV91"
_SLUG = "accept-residual-partition"
_HANDLE = f"{_SLUG}-{_MID8}"
# The mission's OWN unprotected working branch (where accept "runs from").
# Deliberately distinct from the canonical coordination-branch grammar
# (``kitty/mission-<handle>``, see ``coord_reconstruct_branch``) so the two
# branches never collide when both are created in the same fixture.
_TARGET_BRANCH = f"feat/{_HANDLE}"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _porcelain(repo_root: Path) -> str:
    return _git(repo_root, "status", "--porcelain").stdout


def _head_sha(repo_root: Path) -> str:
    return _git(repo_root, "rev-parse", "HEAD").stdout.strip()


def _write_meta(feature_dir: Path, *, coordination_branch: str | None) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mid8": _MID8,
        "mission_slug": _HANDLE,
        "mission_type": "software-dev",
        "target_branch": _TARGET_BRANCH,
    }
    if coordination_branch:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _initial_matrix() -> AcceptanceMatrix:
    return AcceptanceMatrix(
        mission_slug=_HANDLE,
        criteria=[],
        negative_invariants=[
            NegativeInvariant(
                invariant_id="NI1",
                description="legacy symbol must be absent",
                verification_method="grep_absence",
                verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
            )
        ],
    )


def _build_coord_mission(repo_root: Path, *, primary_dir_name: str = _HANDLE) -> tuple[Path, Path]:
    """Build a real coord-topology mission with a materialised coord worktree.

    Returns ``(primary_feature_dir, coord_feature_dir)``. The coord worktree is
    a genuine ``git worktree`` (via the canonical
    :class:`CoordinationWorkspace`), checked out on its own coordination
    branch — mirroring production, not a stub.

    ``primary_dir_name`` is the PRIMARY ``kitty-specs/<dir>`` name; the coord
    mission dir is always the canonical ``<slug>-<mid8>``. They differ for a
    backfilled mission whose primary dir carries no ``-<mid8>``.
    """
    _git(repo_root, "init", "-q", ".")
    _git(repo_root, "config", "user.email", "t@t")
    _git(repo_root, "config", "user.name", "t")
    _git(repo_root, "branch", "-M", "main")

    primary_feature_dir = repo_root / "kitty-specs" / primary_dir_name
    coord_branch = CoordinationWorkspace.branch_name(_HANDLE, _MID8)
    _write_meta(primary_feature_dir, coordination_branch=coord_branch)

    # A minimal committed baseline so the mission's own (unprotected) branch
    # and the coordination branch both have somewhere to fork from.
    # ``.worktrees/`` is gitignored (mirrors a real spec-kitty repo) so the
    # coord worktree materialised below never shows up as primary-tree dirt
    # itself (a nested-repo pointer would otherwise pollute the porcelain
    # assertions this suite makes about the PRIMARY surface staying clean).
    # ``.kittify/sync-state.json`` is a real spec-kitty gitignore entry (a
    # sync-event side effect of ``safe_commit``'s post-commit hook); ignoring
    # it here mirrors a real project so it never pollutes the primary-tree
    # cleanliness assertions this suite makes.
    (repo_root / ".gitignore").write_text(".worktrees/\n.kittify/sync-state.json\n")
    (repo_root / ".gitkeep").write_text("")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "init")
    _git(repo_root, "checkout", "-q", "-b", _TARGET_BRANCH)
    _git(repo_root, "branch", coord_branch)

    coord_root = CoordinationWorkspace.resolve(repo_root, _HANDLE, _MID8)
    coord_feature_dir = coord_root / "kitty-specs" / _HANDLE
    _write_meta(coord_feature_dir, coordination_branch=coord_branch)

    # Commit an initial (pending) matrix on the coord branch so the later
    # rewrite registers as tracked-modified dirt, not an untracked file (the
    # dirty scan deliberately excludes ``??`` — see
    # ``_spec_artifact_dirty_paths``'s docstring).
    write_acceptance_matrix(coord_feature_dir, _initial_matrix())
    _git(coord_root, "add", "-A")
    _git(coord_root, "commit", "-q", "-m", "coord baseline")

    return primary_feature_dir, coord_feature_dir


def test_dirty_scan_detects_coord_worktree_residue(tmp_path: Path) -> None:
    """M2 (T006/T008): coord-worktree dirt is invisible to a primary-only scan.

    ``write_acceptance_matrix`` rewrites the matrix in the COORD worktree
    (mirroring what accept's readiness checks do); the PRIMARY checkout stays
    perfectly clean throughout. Pre-fix, ``_spec_artifact_dirty_paths`` only
    consulted ``git_status_entries(repo_root)`` (primary) and returned ``[]`` —
    the M2 gap this test proves RED against.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _primary_feature_dir, coord_feature_dir = _build_coord_mission(repo_root)

    # Rewrite the matrix on COORD only; primary never touched.
    resolved = AcceptanceMatrix(
        mission_slug=_HANDLE,
        criteria=[],
        negative_invariants=[
            NegativeInvariant(
                invariant_id="NI1",
                description="legacy symbol must be absent",
                verification_method="grep_absence",
                verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
                result="confirmed_absent",
            )
        ],
    )
    write_acceptance_matrix(coord_feature_dir, resolved)

    assert _porcelain(repo_root) == "", "primary must stay clean for this scenario"

    dirty = _spec_artifact_dirty_paths(repo_root, _HANDLE)

    assert f"kitty-specs/{_HANDLE}/acceptance-matrix.json" in dirty, (
        "coord-worktree dirt (where write_acceptance_matrix actually writes under coord topology) was not detected — M2 gap"
    )


def test_dirty_scan_uses_coord_mission_dir_when_primary_dir_has_no_mid8(tmp_path: Path) -> None:
    """The coord dirt prefix comes from the COORDINATION mission dir, not the primary name.

    A backfilled mission's primary directory is ``kitty-specs/<slug>`` (no
    ``-<mid8>``) while its coordination directory is ``kitty-specs/<slug>-<mid8>``.
    Pre-fix the scan filtered with ``kitty-specs/<slug>/``, matched nothing in the
    coordination worktree, and the residual commit silently committed zero files.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _primary_feature_dir, coord_feature_dir = _build_coord_mission(repo_root, primary_dir_name=_SLUG)
    assert coord_feature_dir.name == _HANDLE != _SLUG

    write_acceptance_matrix(
        coord_feature_dir,
        AcceptanceMatrix(
            mission_slug=_HANDLE,
            criteria=[],
            negative_invariants=[
                NegativeInvariant(
                    invariant_id="NI1",
                    description="legacy symbol must be absent",
                    verification_method="grep_absence",
                    verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
                    result="confirmed_absent",
                )
            ],
        ),
    )

    dirty = _spec_artifact_dirty_paths(repo_root, _SLUG)

    assert dirty == [f"kitty-specs/{_HANDLE}/acceptance-matrix.json"]


def test_residual_commit_routes_matrix_to_coord_branch(tmp_path: Path) -> None:
    """T007: the residual commit lands on the COORD branch via commit_for_mission.

    Not a raw primary-checkout ``git commit`` — the primary branch gains NO new
    commit from this call, and the coord branch does.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _primary_feature_dir, coord_feature_dir = _build_coord_mission(repo_root)
    coord_root = coord_feature_dir.parent.parent

    primary_head_before = _head_sha(repo_root)
    coord_head_before = _head_sha(coord_root)

    resolved = AcceptanceMatrix(
        mission_slug=_HANDLE,
        criteria=[],
        negative_invariants=[
            NegativeInvariant(
                invariant_id="NI1",
                description="legacy symbol must be absent",
                verification_method="grep_absence",
                verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
                result="confirmed_absent",
            )
        ],
    )
    write_acceptance_matrix(coord_feature_dir, resolved)

    created = _commit_residual_acceptance_artifacts(repo_root, _HANDLE)

    assert created is True

    # Primary gained NO commit — the router never touches the primary branch
    # for a coord-partition kind.
    assert _head_sha(repo_root) == primary_head_before
    # Coord DID gain a commit, and its tree is now clean.
    assert _head_sha(coord_root) != coord_head_before
    assert _porcelain(coord_root) == ""

    # Round-trip (T009): the committed matrix reads back with the resolved
    # invariant, not the stale pending baseline.
    read_back = read_acceptance_matrix(coord_feature_dir)
    assert read_back is not None
    assert read_back.negative_invariants[0].result == "confirmed_absent"

    show = subprocess.run(
        ["git", "-C", str(coord_root), "show", f"HEAD:kitty-specs/{_HANDLE}/acceptance-matrix.json"],
        capture_output=True,
        text=True,
    )
    assert show.returncode == 0, "acceptance-matrix.json is not committed at coord HEAD"
    assert json.loads(show.stdout)["negative_invariants"][0]["result"] == "confirmed_absent"


def test_residual_commit_keeps_primary_kind_residuals_working(tmp_path: Path) -> None:
    """DoD: PRIMARY-kind residuals (e.g. a dirty spec.md) must be unregressed.

    A flattened (no coordination_branch) mission's own primary artifact goes
    dirty; the residual commit must still land it directly on the current
    (unprotected) branch — the historical raw-git behaviour
    ``test_accept_clean_tree.py`` already pins, preserved by this WP.

    Decision ``plan.design.accept-primary-leg-ref``: meta.json's stored
    ``target_branch`` stays ``_TARGET_BRANCH`` and is never checked out.
    HEAD is the unprotected branch ``work``. The PRIMARY residual lands on
    ``work``, the same ref an unprotected acceptance-metadata commit uses.
    The earlier re-pin that set ``target_branch`` to ``work`` hid that split.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _git(repo_root, "init", "-q", ".")
    _git(repo_root, "config", "user.email", "t@t")
    _git(repo_root, "config", "user.name", "t")
    _git(repo_root, "branch", "-M", "main")
    _git(repo_root, "checkout", "-q", "-b", "work")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    _write_meta(feature_dir, coordination_branch=None)
    (feature_dir / "spec.md").write_text("# spec\nv1\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "baseline")

    (feature_dir / "spec.md").write_text("# spec\nv2\n", encoding="utf-8")

    created = _commit_residual_acceptance_artifacts(repo_root, _SLUG)

    assert created is True
    assert _porcelain(repo_root) == ""
    show = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"HEAD:kitty-specs/{_SLUG}/spec.md"],
        capture_output=True,
        text=True,
    )
    assert show.returncode == 0
    assert "v2" in show.stdout


def test_residual_commit_handles_mixed_primary_and_coord_dirt(tmp_path: Path) -> None:
    """A batch mixing PRIMARY dirt (spec.md) and COORD dirt (matrix) commits both.

    Proves the seam is not hand-classified: primary residue lands directly on
    the current branch, coord residue lands on the coord branch, in the SAME
    ``_commit_residual_acceptance_artifacts`` call.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    primary_feature_dir, coord_feature_dir = _build_coord_mission(repo_root)
    coord_root = coord_feature_dir.parent.parent

    (primary_feature_dir / "spec.md").write_text("# spec\nv1\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "add spec baseline")
    (primary_feature_dir / "spec.md").write_text("# spec\nv2\n", encoding="utf-8")

    resolved = AcceptanceMatrix(
        mission_slug=_HANDLE,
        criteria=[],
        negative_invariants=[
            NegativeInvariant(
                invariant_id="NI1",
                description="legacy symbol must be absent",
                verification_method="grep_absence",
                verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
                result="confirmed_absent",
            )
        ],
    )
    write_acceptance_matrix(coord_feature_dir, resolved)

    created = _commit_residual_acceptance_artifacts(repo_root, _HANDLE)

    assert created is True
    assert _porcelain(repo_root) == ""
    assert _porcelain(coord_root) == ""

    primary_show = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"HEAD:kitty-specs/{_HANDLE}/spec.md"],
        capture_output=True,
        text=True,
    )
    assert primary_show.returncode == 0
    assert "v2" in primary_show.stdout

    coord_show = subprocess.run(
        ["git", "-C", str(coord_root), "show", f"HEAD:kitty-specs/{_HANDLE}/acceptance-matrix.json"],
        capture_output=True,
        text=True,
    )
    assert coord_show.returncode == 0
    assert json.loads(coord_show.stdout)["negative_invariants"][0]["result"] == "confirmed_absent"


# ---------------------------------------------------------------------------
# WP16 (T085): both residual legs through the commit router.
#
# The three tests below (R7/R8/R9) and the ledger pair prove the DEFECT this
# WP removes: a raw ``git commit`` (``_commit_primary_residuals``) that
# committed EVERY primary-checkout dirty mission path onto the target branch
# regardless of its partition, and a root-join bug
# (``_commit_coord_residuals``'s ``repo_root / path`` join against a
# coordination-worktree-relative path) that silently no-opped the
# coordination leg. After the fix both legs flow through ONE
# ``commit_for_mission`` call (``_run_residual_acceptance_commit``), which
# groups by partition and reports a root-checkout COORD-record copy as
# skipped (``COORD_RECORD_IN_ROOT_CHECKOUT``) rather than committing it to
# the target.
# ---------------------------------------------------------------------------


def test_accept_never_commits_coord_record_from_root_checkout_to_target(tmp_path: Path) -> None:
    """R7: a COORD record dirty only in the root checkout never lands on target.

    At the base, ``_commit_primary_residuals`` treats every primary-checkout
    dirty mission path as real primary work -- it does not consult the file's
    partition at all -- so a stale root-checkout copy of ``status.events.jsonl``
    (a STATUS_STATE / COORD-partition kind) is committed straight onto the
    target branch. After the fix, the SAME path is classified by the router
    and, since its owning (coordination) copy is clean, is reported skipped
    with ``COORD_RECORD_IN_ROOT_CHECKOUT`` and never reaches the target.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    primary_feature_dir, coord_feature_dir = _build_coord_mission(repo_root)
    coord_root = coord_feature_dir.parent.parent

    # Committed baseline on BOTH surfaces; the coordination copy is the
    # owning one and stays clean throughout.
    (coord_feature_dir / "status.events.jsonl").write_text('{"event_id":"a"}\n', encoding="utf-8")
    _git(coord_root, "add", "-A")
    _git(coord_root, "commit", "-q", "-m", "coord status baseline")

    (primary_feature_dir / "status.events.jsonl").write_text('{"event_id":"a"}\n', encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "stale root status baseline")

    target_before = _head_sha(repo_root)

    # Dirty ONLY the root-checkout (stale) copy.
    (primary_feature_dir / "status.events.jsonl").write_text('{"event_id":"a-edited"}\n', encoding="utf-8")

    result = _run_residual_acceptance_commit(repo_root, _HANDLE)

    assert result is not None, "the root-checkout dirt must still produce a router result"

    log = _git(repo_root, "log", f"{target_before}..HEAD", "--", f"kitty-specs/{_HANDLE}/status.events.jsonl").stdout
    assert log.strip() == "", "a COORD record dirty only in the root checkout must never land on the target branch"
    assert _head_sha(repo_root) == target_before, "the target branch must gain no new commit for root-checkout COORD residue"

    payload = commit_outcome_payload(result)
    skipped_paths = {fate["path"]: fate["reason"] for surface in payload["surfaces"] for fate in surface["skipped"]}
    assert skipped_paths.get(f"kitty-specs/{_HANDLE}/status.events.jsonl") == COORD_RECORD_IN_ROOT_CHECKOUT


def test_accept_commits_coord_only_dirt_on_coordination_branch(tmp_path: Path) -> None:
    """R8: a genuine coordination-worktree edit survives, never overwritten by a stale root copy.

    A pure "coord dirty, no root copy at all" fixture turns out NOT to
    discriminate old vs. new code here: for ``acceptance-matrix.json``
    (a COPY-plan kind), the router's ``_copy_into`` already degrades
    gracefully to "nothing to copy, trust the coordination worktree's own
    content" when the (wrongly root-joined) source is simply absent -- so the
    retired L427 root-join bug is masked in that shape on BOTH
    implementations. The bug IS observable when a **stale, already-committed**
    root copy ALSO exists: at the base, ``_commit_coord_residuals`` joins the
    coordination-relative dirty path onto ``repo_root`` (L427), which resolves
    to that stale root file -- the router's COPY plan then overwrites the
    coordination worktree's genuine, uncommitted edit with the stale root
    content and commits THAT onto the coordination branch (confirmed empirically
    against the WP base: the coordination branch ends up carrying
    ``"stale-root"``, not the real edit). After the fix, the coordination path
    resolves against the coordination worktree root -- landing ``IN_PLACE``,
    never touching the stale root copy -- so the real edit survives.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    primary_feature_dir, coord_feature_dir = _build_coord_mission(repo_root)
    coord_root = coord_feature_dir.parent.parent

    # A stale, already-committed root copy (never touched again) -- the trap
    # the L427 join falls into.
    (primary_feature_dir / "acceptance-matrix.json").write_text('{"version": "stale-root"}\n', encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "stale root matrix copy")
    primary_head_before = _head_sha(repo_root)

    # The coordination worktree's OWN genuine, uncommitted edit.
    (coord_feature_dir / "acceptance-matrix.json").write_text('{"version": "coord-edited"}\n', encoding="utf-8")

    result = _run_residual_acceptance_commit(repo_root, _HANDLE)

    assert result is not None
    assert _head_sha(repo_root) == primary_head_before, "the stale root copy must stay untouched"
    assert _porcelain(coord_root) == ""

    coord_show = _git(coord_root, "show", f"HEAD:kitty-specs/{_HANDLE}/acceptance-matrix.json")
    assert json.loads(coord_show.stdout)["version"] == "coord-edited", "the real coordination-worktree edit must survive, never overwritten by the stale root copy"


def test_accept_gate_and_committer_agree_per_path(tmp_path: Path) -> None:
    """R9: the dirty gate and the committer give the SAME per-path partition verdict.

    At the base this disagrees for ``traces/*.md``: the gate
    (``_filter_coordination_residue``) treats a root-checkout copy of a
    TRACER_FILE as coordination residue (not real primary work, dropped from
    the blocking set), while the OLD committer
    (``_commit_primary_residuals``) blindly committed it onto the target
    branch anyway -- the gate said "not real work" and the committer
    disagreed by landing it on the target. After the fix, every COORD-kind
    path the gate drops as residue is also a path the unified committer never
    lands on the PRIMARY (target) surface, and every PRIMARY-kind path the
    gate keeps IS committed there.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    primary_feature_dir, coord_feature_dir = _build_coord_mission(repo_root)
    coord_root = coord_feature_dir.parent.parent

    # path -> expected partition.
    paths: dict[str, str] = {
        f"kitty-specs/{_HANDLE}/spec.md": "primary",
        f"kitty-specs/{_HANDLE}/decisions/index.json": "primary",
        f"kitty-specs/{_HANDLE}/status.events.jsonl": "coordination",
        f"kitty-specs/{_HANDLE}/traces/x.md": "coordination",
        f"kitty-specs/{_HANDLE}/acceptance-matrix.json": "coordination",
    }

    # Committed baselines for the COORD-kind paths on the OWNING (coordination)
    # copy too, so the router has something to compare the root-checkout dirt
    # against (mirrors R7/R8's fixture shape).
    for rel in ("status.events.jsonl", "traces/x.md"):
        coord_path = coord_feature_dir / rel
        coord_path.parent.mkdir(parents=True, exist_ok=True)
        coord_path.write_text("v1\n", encoding="utf-8")
    _git(coord_root, "add", "-A")
    _git(coord_root, "commit", "-q", "-m", "coord baselines for R9")

    for rel in paths:
        full = repo_root / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("v1\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "root baselines for R9")
    for rel in paths:
        (repo_root / rel).write_text("v2\n", encoding="utf-8")

    dirty_entries = [StatusEntry(xy="M ", path=GitPath.parse(rel)) for rel in paths]
    gate_kept = set(
        _filter_coordination_residue(
            dirty_entries,
            repo_root=repo_root,
            feature=_HANDLE,
            owned=None,
        )
    )

    for rel, expected_partition in paths.items():
        gate_dropped_as_residue = not any(str(kept.path) == rel for kept in gate_kept)
        assert gate_dropped_as_residue == (expected_partition == "coordination"), rel
        # Same predicate the committer's own grouping consults (R9 holds by
        # construction once the gate calls it too).
        assert partition_for_mission_path(repo_root, _HANDLE, Path(rel)) == expected_partition, rel

    result = _run_residual_acceptance_commit(repo_root, _HANDLE)
    assert result is not None
    payload = commit_outcome_payload(result)

    landed_on_primary: set[str] = set()
    for surface in payload["surfaces"]:
        if surface["surface"] == "primary":
            landed_on_primary.update(surface["committed"])

    for rel, expected_partition in paths.items():
        if expected_partition == "primary":
            assert rel in landed_on_primary, f"{rel} is PRIMARY-partition and must be committed on the target"
        else:
            assert rel not in landed_on_primary, f"{rel} is COORD-partition and must never land on the target"


def test_accept_commits_uncommitted_ledger_on_target(tmp_path: Path) -> None:
    """FR-009: an uncommitted decision ledger is committed by accept on the target branch.

    ``decisions/index.json`` + ``decisions/DM-*.md`` are PRIMARY-partition
    (WP12, DECISION_LEDGER) under EVERY topology, including a coordination-
    routed mission -- the residual commit must land them on the target
    branch, never the coordination branch.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    primary_feature_dir, _coord_feature_dir = _build_coord_mission(repo_root)

    target_before = _head_sha(repo_root)

    decisions_dir = primary_feature_dir / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    (decisions_dir / "index.json").write_text('{"entries": []}\n', encoding="utf-8")
    (decisions_dir / "DM-0001.md").write_text("# Decision\n", encoding="utf-8")
    # Stage (but do not commit) the new ledger files: the dirty scan excludes
    # fully-untracked (``??``) paths, mirroring a real uncommitted ledger an
    # operator ``git add``ed but never committed.
    _git(repo_root, "add", str(decisions_dir.relative_to(repo_root)))

    created = _commit_residual_acceptance_artifacts(repo_root, _HANDLE)

    assert created is True
    assert _head_sha(repo_root) != target_before
    index_show = _git(repo_root, "show", f"HEAD:kitty-specs/{_HANDLE}/decisions/index.json")
    assert index_show.returncode == 0
    dm_show = _git(repo_root, "show", f"HEAD:kitty-specs/{_HANDLE}/decisions/DM-0001.md")
    assert dm_show.returncode == 0
    assert _porcelain(repo_root) == ""


def test_accept_with_committed_ledger_is_clean(tmp_path: Path) -> None:
    """Positive control: an already-committed ledger produces no residual commit."""
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    primary_feature_dir, _coord_feature_dir = _build_coord_mission(repo_root)

    decisions_dir = primary_feature_dir / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    (decisions_dir / "index.json").write_text('{"entries": []}\n', encoding="utf-8")
    (decisions_dir / "DM-0001.md").write_text("# Decision\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "ledger already committed")

    created = _commit_residual_acceptance_artifacts(repo_root, _HANDLE)

    assert created is False
    assert _porcelain(repo_root) == ""


def test_run_residual_acceptance_commit_raises_on_a_refused_surface(tmp_path: Path) -> None:
    """T086 step 5 / B1 (cycle 2): a protected-target flat mission still refuses cleanly.

    A flattened mission accepted FROM its own protected target branch (the
    N3 "flattened / no-branch-strategy" shape: HEAD == ``target_branch`` ==
    ``main``) hits the router's protected-primary refusal -- B1's HEAD-leg
    bypass only applies when HEAD is UNPROTECTED, so this scenario (unlike
    the 7 regressed tests) still routes through ``commit_for_mission`` and
    still refuses. The residual commit must never silently land it, nor
    swallow the refusal.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _git(repo_root, "init", "-q", ".")
    _git(repo_root, "config", "user.email", "t@t")
    _git(repo_root, "config", "user.name", "t")
    _git(repo_root, "branch", "-M", "main")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    # HEAD == target_branch == "main" (both protected) -- a raw meta.json
    # write, not ``_write_meta`` (whose module-constant ``_TARGET_BRANCH`` is
    # deliberately NOT "main", for the OTHER fixtures in this file).
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mid8": _MID8, "mission_slug": _SLUG, "mission_type": "software-dev", "target_branch": "main"}),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("# spec\nv1\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "baseline")
    (feature_dir / "spec.md").write_text("# spec\nv2\n", encoding="utf-8")

    with pytest.raises(TaskCliError) as exc_info:
        _run_residual_acceptance_commit(repo_root, _SLUG)

    assert "PROTECTED_BRANCH_REFUSED" in str(exc_info.value)
    assert _SLUG in str(exc_info.value)


def test_run_residual_acceptance_commit_raises_when_any_surface_is_refused_even_with_a_committed_sibling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutation-sensitive: a split batch with primary ``committed`` + coordination ``refused`` must still raise.

    Pins the exact predicate T086 step 5 specifies (``any surface refused or
    error``, not "the caller-partition surface"): a mutation narrowing the
    check to only the first/caller surface would let a refused coordination
    surface slip through silently whenever the primary surface succeeded.
    """
    from specify_cli.coordination.commit_outcome import PathFate, SurfaceOutcome
    from specify_cli.coordination.commit_router import CommitRouterResult

    mixed_result = CommitRouterResult(
        status="committed",
        placement_ref="topic",
        commit_hash="abc1234",
        surfaces=(
            SurfaceOutcome(surface="primary", branch="topic", status="committed", commit_hash="abc1234", committed=("kitty-specs/m/spec.md",)),
            SurfaceOutcome(
                surface="coordination",
                branch="kitty/mission-m-01ABCDEF",
                status="refused",
                commit_hash=None,
                refused=(PathFate(path="kitty-specs/m/status.events.jsonl", reason="STATUS_LOCK_HELD"),),
                diagnostic="status lock held",
            ),
        ),
    )

    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _git(repo_root, "init", "-q", ".")
    _git(repo_root, "config", "user.email", "t@t")
    _git(repo_root, "config", "user.name", "t")
    _git(repo_root, "branch", "-M", "main")
    _git(repo_root, "checkout", "-q", "-b", "work")
    feature_dir = repo_root / "kitty-specs" / "m"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": "m", "slug": "m", "mission_type": "software-dev", "target_branch": "work"}),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("v1\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "baseline")
    (feature_dir / "spec.md").write_text("v2\n", encoding="utf-8")

    monkeypatch.setattr("specify_cli.coordination.commit_router.commit_for_mission", lambda *_a, **_k: mixed_result)

    with pytest.raises(TaskCliError) as exc_info:
        _run_residual_acceptance_commit(repo_root, "m")

    assert "STATUS_LOCK_HELD" in str(exc_info.value)


def test_residual_commit_files_defensive_guard_when_coord_worktree_root_vanishes(tmp_path: Path) -> None:
    """``_residual_commit_files`` fails closed (never drops coordination dirt) if its
    own ``_coord_worktree_root`` re-probe ever disagreed with the caller's ``coord_dirty``.

    This can never happen through ``_run_residual_acceptance_commit`` itself
    (it derives both from the SAME probe), so this is a white-box unit test of
    the defensive branch directly -- not a reachable production scenario.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _git(repo_root, "init", "-q", ".")
    _git(repo_root, "config", "user.email", "t@t")
    _git(repo_root, "config", "user.name", "t")
    _git(repo_root, "branch", "-M", "main")
    # No coordination_branch at all -- ``_coord_worktree_root`` always resolves
    # ``None`` for this mission, regardless of what ``coord_dirty`` claims.
    feature_dir = repo_root / "kitty-specs" / _SLUG
    _write_meta(feature_dir, coordination_branch=None)

    files = _residual_commit_files(
        repo_root,
        _SLUG,
        primary_dirty=[f"kitty-specs/{_SLUG}/spec.md"],
        coord_dirty=[f"kitty-specs/{_SLUG}/status.events.jsonl"],
        owned=None,
    )

    assert files == (repo_root / f"kitty-specs/{_SLUG}/spec.md",)
