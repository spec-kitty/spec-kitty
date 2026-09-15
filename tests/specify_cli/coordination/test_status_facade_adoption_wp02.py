"""WP02 — Status-facade adoption regression tests.

Two binding regressions are covered here (execution-context-unification-01KTPKST):

* **F-007 / #1737** — ``status_transition._identity_for_request`` must consume
  the canonical status surface (``resolve_status_surface`` /
  ``candidate_feature_dir_for_mission``) instead of re-deriving where status
  lives from a CWD-dependent path. A sparse lane worktree must therefore resolve
  the *same* WP lane state as the primary checkout — no ``genesis`` misread.

* **#1357** — ``CoordinationWorkspace.resolve`` must be lock-serialized so that
  two concurrent resolves of the same coordination worktree cannot both pass the
  ``not path.exists()`` guard and race ``git worktree add`` into divergent
  surfaces.
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

import pytest

from specify_cli.coordination.status_transition import (
    _identity_for_request,
    read_current_wp_state_transactional,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.status.models import Lane, TransitionRequest

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_MISSION_SLUG = "facade-adoption"
_MISSION_ID = "01KTFACADE0000000000000001"
_MID8 = _MISSION_ID[:8]
# Flattened mission: meta declares NO coordination_branch (mirrors the real
# execution-context-unification mission topology where F-007 was dogfooded).
_META = json.dumps(
    {
        "mission_slug": _MISSION_SLUG,
        "mission_id": _MISSION_ID,
        "mission_number": None,
        "mission_type": "software-dev",
        "friendly_name": "Facade adoption fixture",
    },
    indent=2,
)

_WP01_MD = (
    "---\n"
    "work_package_id: WP01\n"
    "title: Facade WP01\n"
    "dependencies: []\n"
    "subtasks: []\n"
    "owned_files:\n"
    "- src/x/\n"
    "execution_mode: code_change\n"
    "history: []\n"
    "---\n"
    "# WP01\n"
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _status_event(wp_id: str, from_lane: str, to_lane: str, event_id: str, at: str) -> str:
    return json.dumps(
        {
            "actor": "fixture",
            "at": at,
            "event_id": event_id,
            "evidence": None,
            "execution_mode": "worktree",
            "force": True,
            "from_lane": from_lane,
            "mission_id": _MISSION_ID,
            "mission_slug": _MISSION_SLUG,
            "policy_metadata": None,
            "reason": "fixture",
            "review_ref": None,
            "to_lane": to_lane,
            "wp_id": wp_id,
        },
        sort_keys=True,
    )


@pytest.fixture
def sparse_lane_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Build a flattened mission with a sparse-checkout lane worktree.

    The lane worktree's copy of ``kitty-specs/<slug>/status.events.jsonl`` and
    ``status.json`` is removed (mirroring the lane sparse policy), so reading
    status from the lane filesystem is physically impossible. This is the F-007
    condition: a transaction-identity derivation that anchors on the lane CWD
    would read the (absent) lane surface instead of the canonical authority.

    Returns ``(repo_root, lane_worktree)``.
    """
    repo = tmp_path / "main"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(_META, encoding="utf-8")
    (feature_dir / "tasks" / "WP01.md").write_text(_WP01_MD, encoding="utf-8")
    events = "\n".join(
        [
            _status_event("WP01", "genesis", "planned", "01KTFACADE000000000000P01", "2026-06-09T10:00:00+00:00"),
            _status_event("WP01", "planned", "claimed", "01KTFACADE000000000000C01", "2026-06-09T10:00:01+00:00"),
            _status_event("WP01", "claimed", "in_progress", "01KTFACADE000000000000I01", "2026-06-09T10:00:02+00:00"),
        ]
    )
    (feature_dir / "status.events.jsonl").write_text(events + "\n", encoding="utf-8")
    (feature_dir / "status.json").write_text(json.dumps({"event_count": 0, "work_packages": {}}), encoding="utf-8")

    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed flattened mission")

    lane_branch = f"kitty/mission-{_MISSION_SLUG}-lane-a"
    _git(repo, "branch", lane_branch)
    lane = repo / ".worktrees" / f"{_MISSION_SLUG}-lane-a"
    lane.parent.mkdir(exist_ok=True)
    _git(repo, "worktree", "add", "-q", str(lane), lane_branch)

    # Simulate the lane sparse-checkout policy: the event log and snapshot are
    # physically absent from the lane filesystem (this is the condition under
    # which the old derivation misread ``genesis``). We remove them directly
    # rather than via ``register_lane_sparse_checkout`` because that helper keys
    # its exclusion patterns on the ``<slug>-<mid8>`` directory name, whereas
    # this flattened fixture uses a bare-slug mission dir (matching the real
    # execution-context-unification mission layout).
    lane_feature_dir = lane / "kitty-specs" / _MISSION_SLUG
    (lane_feature_dir / "status.events.jsonl").unlink()
    (lane_feature_dir / "status.json").unlink()
    assert not (lane_feature_dir / "status.events.jsonl").exists()

    return repo, lane


def test_identity_anchor_is_cwd_invariant(sparse_lane_repo: tuple[Path, Path]) -> None:
    """#1737: the resolved transaction anchor is identical from primary and lane.

    Both invocations must resolve the SAME canonical primary ``feature_dir``
    anchor regardless of which root the request was built from.
    """
    repo, lane = sparse_lane_repo
    canonical_feature_dir = repo / "kitty-specs" / _MISSION_SLUG

    primary_ident = _identity_for_request(
        TransitionRequest(
            feature_dir=canonical_feature_dir,
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            to_lane=Lane.PLANNED,
            actor="status-read",
            repo_root=repo,
        )
    )
    # The bug condition: a caller builds feature_dir / repo_root from the lane root.
    lane_ident = _identity_for_request(
        TransitionRequest(
            feature_dir=lane / "kitty-specs" / _MISSION_SLUG,
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            to_lane=Lane.PLANNED,
            actor="status-read",
            repo_root=lane,
        )
    )

    assert primary_ident.feature_dir == canonical_feature_dir
    assert lane_ident.feature_dir == canonical_feature_dir, (
        "F-007: the transaction anchor was re-derived from the lane CWD instead of the canonical status surface."
    )


def test_f007_lane_state_parity_no_genesis_misread(sparse_lane_repo: tuple[Path, Path]) -> None:
    """F-007: lane state read from a sparse lane CWD matches the primary checkout.

    The transactional read driven from the sparse lane worktree (whose event log
    is absent) and from the primary checkout must resolve the SAME ``in_progress``
    lane — no ``genesis`` misread. This is the regression F-007 documents:
    move-task/mark-status must produce identical results from either CWD.
    """
    repo, lane = sparse_lane_repo

    _primary = read_current_wp_state_transactional(
        feature_dir=repo / "kitty-specs" / _MISSION_SLUG,
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        repo_root=repo,
    )
    primary_lane, primary_actor = _primary.lane, _primary.actor
    _lane = read_current_wp_state_transactional(
        feature_dir=lane / "kitty-specs" / _MISSION_SLUG,
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        repo_root=lane,
    )
    lane_lane, lane_actor = _lane.lane, _lane.actor

    assert primary_lane == Lane.IN_PROGRESS
    assert lane_lane == primary_lane, (
        f"F-007 regression: lane worktree CWD read {lane_lane!r} but primary read "
        f"{primary_lane!r}. The sparse lane must not misroute the status surface "
        "and misread an in-progress WP as genesis."
    )
    assert lane_actor == primary_actor


def test_identity_consumes_canonical_surface_resolver(sparse_lane_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """#1737 / #1821: the anchor is resolved through the canonical surface authority.

    Proves ``_identity_for_request`` no longer maintains a parallel derivation:
    it consults ``surface_resolver.resolve_status_surface_with_anchor`` (the
    single single-pass authority that carries both the surface path and the
    canonical primary anchor — the same authority ``MissionStatus`` is built
    on). If a future change reintroduced an independent derivation that skipped
    the resolver (the second hand-rolled composition Debby flagged at 01KTPKST
    closeout), this guard would fail.
    """
    repo, _lane = sparse_lane_repo
    import specify_cli.coordination.surface_resolver as surface_resolver

    calls: list[tuple[Path, str, bool]] = []
    real = surface_resolver.resolve_status_surface_with_anchor

    def _spy(
        repo_root: Path,
        mission_slug: str,
        topology: surface_resolver.MissionTopology | None = None,
        *,
        for_write: bool = False,
    ) -> surface_resolver.ResolvedStatusSurface:
        calls.append((repo_root, mission_slug, for_write))
        return real(repo_root, mission_slug, topology, for_write=for_write)

    monkeypatch.setattr(surface_resolver, "resolve_status_surface_with_anchor", _spy)

    _identity_for_request(
        TransitionRequest(
            feature_dir=repo / "kitty-specs" / _MISSION_SLUG,
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            to_lane=Lane.PLANNED,
            actor="status-read",
            repo_root=repo,
        )
    )

    assert calls, (
        "_identity_for_request must consume resolve_status_surface_with_anchor "
        "(the canonical authority), not re-derive the status surface "
        "independently (#1737 / #1821)."
    )
    assert calls[0][1] == _MISSION_SLUG
    assert {call[2] for call in calls} == {False, True}, "read identity and write placement must retain their distinct purposes"


# ---------------------------------------------------------------------------
# #1357 — CoordinationWorkspace.resolve lock serialization
# ---------------------------------------------------------------------------


@pytest.fixture
def coord_repo(tmp_path: Path) -> tuple[Path, str]:
    """Build a repo with a coordination branch but no coord worktree yet.

    Returns ``(repo_root, mid8)``.
    """
    repo = tmp_path / "coord-main"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    branch = CoordinationWorkspace.branch_name(_MISSION_SLUG, _MID8)
    _git(repo, "branch", branch)
    return repo, _MID8


def test_resolve_is_lock_serialized_under_concurrency(coord_repo: tuple[Path, str]) -> None:
    """#1357: concurrent resolves serialize and converge on ONE worktree.

    Many threads race ``resolve`` for the same coordination worktree. With the
    check-then-create serialized, exactly one ``git worktree add`` succeeds and
    every caller returns the identical path with no exception.
    """
    repo, mid8 = coord_repo
    expected_path = CoordinationWorkspace.worktree_path(repo, _MISSION_SLUG, mid8)

    barrier = threading.Barrier(8)
    results: list[Path] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def _worker() -> None:
        try:
            barrier.wait(timeout=10)
            path = CoordinationWorkspace.resolve(repo, _MISSION_SLUG, mid8)
            with lock:
                results.append(path)
        except BaseException as exc:  # noqa: BLE001 — capture for assertion
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
        assert not t.is_alive(), "resolve worker deadlocked (#1357 lock must be deadlock-free)"

    assert errors == [], f"concurrent resolve raised: {errors!r}"
    assert len(results) == 8
    assert all(p == expected_path for p in results)
    assert expected_path.exists()

    # Exactly one worktree registration for the coordination path.
    listing = _git(repo, "worktree", "list", "--porcelain").stdout
    resolved = str(expected_path.resolve())
    count = sum(1 for line in listing.splitlines() if line.startswith("worktree ") and Path(line.removeprefix("worktree ")).resolve() == Path(resolved))
    assert count == 1, f"expected exactly one coord worktree registration, got {count}"


def test_distinct_missions_do_not_contend(coord_repo: tuple[Path, str]) -> None:
    """#1357: the lock is path-keyed — distinct missions resolve independently."""
    repo, mid8 = coord_repo
    other_slug = "facade-adoption-other"
    other_mid8 = "01KTOTHER"
    _git(repo, "branch", CoordinationWorkspace.branch_name(other_slug, other_mid8))

    path_a = CoordinationWorkspace.resolve(repo, _MISSION_SLUG, mid8)
    path_b = CoordinationWorkspace.resolve(repo, other_slug, other_mid8)

    assert path_a != path_b
    assert path_a.exists()
    assert path_b.exists()


# ---------------------------------------------------------------------------
# WP01 (verdict-seam-boundary-hardening-01KZG179, FR-001/FR-006) — the full
# verdict_vocab bridge + review_result_from_state must be promoted onto the
# status facade so WP02's consumer migration can resolve every symbol WITHOUT
# a direct ``specify_cli.status.verdict_vocab`` / ``.reducer`` import.
# ---------------------------------------------------------------------------

# The 8 verdict_vocab functions, the EventVerdict type alias, and the 3
# constants (T001) plus review_result_from_state (T002). The 2 functions
# already promoted before this WP (is_changes_requested, to_artifact_verdict)
# are included so the assertion covers the FULL intended facade surface.
_WP01_PROMOTED_VERDICT_VOCAB_SYMBOLS = (
    "artifact_verdicts",
    "event_verdicts",
    "emission_artifact_verdicts",
    "to_event_verdict",
    "to_artifact_verdict",
    "emission_event_verdict",
    "is_changes_requested",
    "is_approved",
    "EventVerdict",
    "APPROVED",
    "REJECTED",
    "CHANGES_REQUESTED",
)
_WP01_PROMOTED_REDUCER_SYMBOL = "review_result_from_state"


def test_wp01_verdict_vocab_symbols_are_importable_and_exported() -> None:
    """Every verdict_vocab symbol WP02 needs is importable from the facade
    and listed in ``__all__`` — not reachable only via the submodule object
    (the bypass WP02's dedup closes)."""
    import specify_cli.status as status_facade

    for name in _WP01_PROMOTED_VERDICT_VOCAB_SYMBOLS:
        assert hasattr(status_facade, name), f"{name!r} must be importable from specify_cli.status (WP01 facade promotion)."
        assert name in status_facade.__all__, f"{name!r} must be listed in specify_cli.status.__all__ (WP01 facade promotion)."


def test_wp01_review_result_from_state_is_importable_and_exported() -> None:
    """``review_result_from_state`` sits beside its sibling
    ``event_sourced_review_result`` on the facade (C-002) so
    ``post_merge/review_artifact_consistency.py`` need not re-implement the
    snapshot-state decode locally."""
    import specify_cli.status as status_facade

    assert hasattr(status_facade, _WP01_PROMOTED_REDUCER_SYMBOL), (
        f"{_WP01_PROMOTED_REDUCER_SYMBOL!r} must be importable from specify_cli.status (WP01 facade promotion)."
    )
    assert _WP01_PROMOTED_REDUCER_SYMBOL in status_facade.__all__, (
        f"{_WP01_PROMOTED_REDUCER_SYMBOL!r} must be listed in specify_cli.status.__all__ (WP01 facade promotion)."
    )
