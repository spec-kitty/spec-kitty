"""Acceptance tests for the ledger execution-state projection.

Covers (spec.md User Story 3 / FR-008, FR-009, FR-010, NFR-004):

* **(a)** The single-writer campsite fix (F-4): the projection path
  (``materialize_if_stale`` / ``refresh_execution_projection``) must never
  rewrite the tracked ``kitty-specs/<mission>/status.json`` a second time —
  ``write_derived_views`` (``views.py``) and ``generate_progress_json``
  (``progress.py``) must not call the *writing* ``materialize()``, which
  would rewrite a stale tracked file (it only skips identical bytes --
  ``reducer.py:414``).
* **(b)** Ledger on -> the automatic refresh matches
  ``materialize_snapshot(...)`` on both the flat and transactional paths.
* **(b2)** Parity with the CLI command backing ``spec-kitty materialize``
  (C1) -- the regression a ``reduce(read_events())``-based projection would
  fail.
* **(c)** Ledger off -> no automatic refresh; the on-demand materialize path
  still works (the flag gates only the automatic hook, FR-009/FR-010).
* **(d)** A git operation in progress -> the refresh is skipped, and the
  transition itself still succeeds.
* **(e)** The coordination transactional path refreshes post-commit (as a
  deferred outbound, not before commit).
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer

from specify_cli.core import hosted_posture
from specify_cli.status import views as views_module
from specify_cli.status.emit import emit_status_transition, emit_status_transition_batch
from specify_cli.status.models import TransitionRequest
from specify_cli.status.reducer import materialize_snapshot

pytestmark = pytest.mark.fast

_SLUG = "wp05-execution-projection"


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    fd = tmp_path / "kitty-specs" / _SLUG
    (fd / "tasks").mkdir(parents=True)
    return fd


def _derived_status_path(repo_root: Path, slug: str = _SLUG) -> Path:
    return repo_root / ".kittify" / "derived" / slug / "status.json"


def _derived_dir_files(repo_root: Path, slug: str = _SLUG) -> Path:
    return repo_root / ".kittify" / "derived" / slug


# ---------------------------------------------------------------------------
# (a) Single-writer regression -- genuinely RED against `main` today.
# ---------------------------------------------------------------------------


class TestSingleWriterRegression:
    def test_materialize_if_stale_never_rewrites_stale_tracked_status(self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable) -> None:
        """The projection path must not rewrite tracked status.json (F-4).

        Seeds a STALE tracked ``status.json`` (bytes differ from what
        ``materialize_snapshot`` would produce for the current event log) and
        drives the projection path with the derived views stale (nothing
        under ``.kittify/derived/`` yet, so ``materialize_if_stale`` always
        regenerates). ``materialize()`` only skips a rewrite when the
        serialized bytes are IDENTICAL to what is on disk (``reducer.py``),
        so a fresh/up-to-date tracked file would pass vacuously on `main` --
        the seeded staleness is what makes this a genuine regression probe.
        """
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)

        tracked_status_path = feature_dir / "status.json"
        stale_payload = json.dumps({"work_packages": {}, "sentinel": "stale-pre-transition"}, sort_keys=True)
        tracked_status_path.write_text(stale_payload, encoding="utf-8")
        stale_bytes = tracked_status_path.read_bytes()

        # Sanity: the seeded bytes genuinely differ from a correct snapshot.
        correct_bytes = json.dumps(materialize_snapshot(feature_dir).to_dict(), sort_keys=True).encode("utf-8")
        assert stale_bytes != correct_bytes, "seed must differ from a correct materialize() to be a real regression probe"

        views_module.materialize_if_stale(feature_dir, tmp_path)

        assert tracked_status_path.read_bytes() == stale_bytes, (
            "materialize_if_stale must never rewrite tracked status.json (F-4: the projection path is write-free w.r.t. tracked state)"
        )

        views_module.refresh_execution_projection(feature_dir, tmp_path)
        assert tracked_status_path.read_bytes() == stale_bytes, "refresh_execution_projection must never rewrite tracked status.json"


# ---------------------------------------------------------------------------
# (b) Ledger on => refresh matches materialize_snapshot; (b2) parity with
# `spec-kitty materialize`.
# ---------------------------------------------------------------------------


class TestLedgerOnRefresh:
    def test_flat_path_refresh_matches_snapshot(self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable) -> None:
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
                repo_root=tmp_path,
            )
        )

        derived = _derived_dir_files(tmp_path)
        for name in ("status.json", "board-summary.json", "progress.json", "lifecycle.json"):
            assert (derived / name).exists(), f"missing {name} under {derived}"

        expected = materialize_snapshot(feature_dir).to_dict()
        actual = json.loads((derived / "status.json").read_text())
        assert actual == expected

    def test_batch_path_refreshes_once(self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable) -> None:
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)
        emit_status_transition_batch(
            [
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug=_SLUG,
                    wp_id="WP01",
                    to_lane="claimed",
                    actor="agent-1",
                    repo_root=tmp_path,
                ),
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug=_SLUG,
                    wp_id="WP01",
                    to_lane="in_progress",
                    actor="agent-1",
                    repo_root=tmp_path,
                    workspace_context="worktree:test-batch",
                ),
            ]
        )

        derived = _derived_dir_files(tmp_path)
        assert (derived / "status.json").exists()
        expected = materialize_snapshot(feature_dir).to_dict()
        actual = json.loads((derived / "status.json").read_text())
        assert actual["work_packages"]["WP01"]["lane"] == expected["work_packages"]["WP01"]["lane"] == "in_progress"


class TestParityWithMaterializeCommand:
    def test_refresh_matches_cli_materialize_output(self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable) -> None:
        """(b2/C1): the refresh's derived status.json is byte-identical (modulo
        ``materialized_at``) to the output of the CLI command backing
        ``spec-kitty materialize`` -- the regression a
        ``reduce(read_events())``-based projection would fail.
        """
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
            )
        )

        repo_a = tmp_path / "repo_a"
        repo_b = tmp_path / "repo_b"
        fd_a = repo_a / "kitty-specs" / _SLUG
        fd_b = repo_b / "kitty-specs" / _SLUG
        shutil.copytree(feature_dir, fd_a, dirs_exist_ok=True)
        shutil.copytree(feature_dir, fd_b, dirs_exist_ok=True)

        views_module.refresh_execution_projection(fd_a, repo_a)

        from specify_cli.cli.commands.materialize import materialize as materialize_cli

        with patch("specify_cli.cli.commands.materialize.locate_project_root", return_value=repo_b):
            with pytest.raises(typer.Exit) as exc_info:
                materialize_cli(mission=_SLUG, json_output=False)
            assert exc_info.value.exit_code == 0

        data_a = json.loads(_derived_status_path(repo_a).read_text())
        data_b = json.loads(_derived_status_path(repo_b).read_text())
        # `materialized_at` is a per-run timestamp; excluded from the comparison.
        data_a.pop("materialized_at", None)
        data_b.pop("materialized_at", None)
        assert data_a == data_b


# ---------------------------------------------------------------------------
# (c) Ledger off => no automatic refresh; the on-demand path still works.
# ---------------------------------------------------------------------------


class TestLedgerOffGate:
    def test_ledger_off_skips_automatic_refresh(self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            hosted_posture,
            "ledger_posture",
            lambda *a, **k: hosted_posture.LedgerPosture(enabled=False, source="test"),
        )
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
                repo_root=tmp_path,
            )
        )

        assert not _derived_dir_files(tmp_path).exists(), "ledger off must not produce an automatic .kittify/derived/ refresh"

    def test_ledger_off_on_demand_materialize_still_works(
        self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            hosted_posture,
            "ledger_posture",
            lambda *a, **k: hosted_posture.LedgerPosture(enabled=False, source="test"),
        )
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
                repo_root=tmp_path,
            )
        )

        result = views_module.materialize_if_stale(feature_dir, tmp_path)
        assert result.mission_slug == _SLUG
        assert _derived_status_path(tmp_path).exists(), "the on-demand materialize_if_stale path must still work with ledger off"


# ---------------------------------------------------------------------------
# (d) Git-op-in-progress => skipped, transition still succeeds.
# ---------------------------------------------------------------------------


class TestGitOperationInProgress:
    def test_refresh_skipped_during_git_operation(self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(views_module, "git_operation_in_progress", lambda _repo_root: True)
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)

        event = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
                repo_root=tmp_path,
            )
        )

        assert str(event.to_lane) == "claimed"
        assert not _derived_dir_files(tmp_path).exists(), "no file under .kittify/derived/ may be created while a git op is in progress"

    def test_refresh_execution_projection_returns_false_during_git_operation(
        self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)
        monkeypatch.setattr(views_module, "git_operation_in_progress", lambda _repo_root: True)

        result = views_module.refresh_execution_projection(feature_dir, tmp_path)
        assert result is False
        assert not _derived_dir_files(tmp_path).exists()


class TestRefreshExecutionProjectionUnit:
    """Direct unit coverage of ``refresh_execution_projection``: success,
    failure, and no-op returns."""

    def test_success_writes_four_files(self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable) -> None:
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)

        ok = views_module.refresh_execution_projection(feature_dir, tmp_path)
        assert ok is True
        derived = _derived_dir_files(tmp_path)
        for name in ("status.json", "board-summary.json", "progress.json", "lifecycle.json"):
            assert (derived / name).exists()
        expected = materialize_snapshot(feature_dir).to_dict()
        actual = json.loads((derived / "status.json").read_text())
        assert actual == expected

    def test_injected_failure_returns_false_and_does_not_raise(
        self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)

        def _boom(*_a: object, **_k: object) -> None:
            raise RuntimeError("injected failure")

        monkeypatch.setattr(views_module, "write_derived_views", _boom)

        result = views_module.refresh_execution_projection(feature_dir, tmp_path)
        assert result is False


# ---------------------------------------------------------------------------
# (e) Coordination transactional path refreshes post-commit.
# ---------------------------------------------------------------------------

_COORD_MISSION_SLUG = "wp05-coord-projection"
_COORD_MID8 = "01WP05COO"
_COORD_MISSION_DIRNAME = f"{_COORD_MISSION_SLUG}-{_COORD_MID8}"
_COORD_BRANCH = f"kitty/mission-{_COORD_MISSION_DIRNAME}"
_COORD_MISSION_ID = "01WP05COO000000000000000000"


def _git(repo: Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def coord_repo(tmp_path: Path) -> Path:
    """A coord-topology mission repo with WP01 seeded genesis -> planned on
    the coord branch (mirrors ``tests/specify_cli/coordination/
    test_status_transition.py``'s ``repo`` fixture + ``_seed_planned_on_coord``).
    Returns the repo root.
    """
    from specify_cli.coordination.status_service import EventLogWriteContract, append_event_log
    from specify_cli.status.models import Lane, StatusEvent

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "wp05@example.invalid")
    _git(repo, "config", "user.name", "WP05 Test")
    _git(repo, "config", "commit.gpgsign", "false")
    feature_dir = repo / "kitty-specs" / _COORD_MISSION_DIRNAME
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _COORD_MISSION_SLUG,
                "mission_id": _COORD_MISSION_ID,
                "mid8": _COORD_MID8,
                "coordination_branch": _COORD_BRANCH,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission")
    _git(repo, "branch", _COORD_BRANCH)

    seed_event = StatusEvent(
        event_id="01SEEDGENESIS0000000000WP5",
        mission_slug=_COORD_MISSION_SLUG,
        mission_id=_COORD_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-05-31T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )
    worktree = repo / ".worktrees" / "seed-genesis"
    _git(repo, "worktree", "add", "-q", str(worktree), _COORD_BRANCH)
    coord_feature_dir = worktree / "kitty-specs" / _COORD_MISSION_DIRNAME
    append_event_log(
        EventLogWriteContract.coordination_transaction_append(coord_feature_dir),
        seed_event,
    )
    _git(worktree, "add", "kitty-specs")
    _git(worktree, "commit", "-q", "-m", "seed genesis->planned")
    _git(repo, "worktree", "remove", "-f", str(worktree))
    return repo


def _coord_request(repo: Path, **overrides: Any) -> TransitionRequest:
    # ``fields`` is typed ``dict[str, Any]`` (not ``object``) specifically so
    # ``TransitionRequest(**fields)`` type-checks without a suppression:
    # ``TransitionRequest``'s fields have heterogeneous types (``Path | None``,
    # ``str | None``, ``bool``, ...), and a homogeneous ``object`` value type
    # is not assignable to any of them, while ``Any`` is.
    fields: dict[str, Any] = {
        "feature_dir": repo / "kitty-specs" / _COORD_MISSION_DIRNAME,
        "mission_slug": _COORD_MISSION_SLUG,
        "wp_id": "WP01",
        "to_lane": "claimed",
        "actor": "wp05-test",
        "repo_root": repo,
    }
    fields.update(overrides)
    return TransitionRequest(**fields)


class TestCoordinationTransactionalRefresh:
    def test_transactional_emit_refreshes_projection_post_commit(self, coord_repo: Path) -> None:
        """Drives ``emit_status_transition_transactional`` on a coord-topology
        mission and asserts the projection under ``.kittify/derived/<slug>/``
        reflects the post-commit state (deferred outbound, not pre-commit),
        and that it lands under the MAIN repo root, never the coord worktree.
        """
        from specify_cli.coordination.status_transition import emit_status_transition_transactional

        event = emit_status_transition_transactional(_coord_request(coord_repo))
        assert str(event.to_lane) == "claimed"

        derived_status = _derived_status_path(coord_repo, _COORD_MISSION_SLUG)
        assert derived_status.exists(), "coord transactional path must refresh the projection post-commit"
        assert ".worktrees" not in str(derived_status), "the projection must land under the repo root, not a coord worktree"
        data = json.loads(derived_status.read_text())
        assert data["work_packages"]["WP01"]["lane"] == "claimed"

    def test_transactional_refresh_runs_after_commit_not_before(self, coord_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """B2/(e) ordering: an injected commit failure inside the
        ``BookkeepingTransaction`` must leave no derived file behind. Mutation
        M3b (review cycle 1) made the ``_defer_fan_out`` refresh synchronous
        INSIDE the transaction; this test would stay green under that
        mutation only if the refresh ran regardless of commit outcome -- it
        does not, because the refresh is a ``txn.defer_outbound`` callback
        that never runs when ``commit`` raises.
        """
        from specify_cli.coordination import status_transition as st
        from specify_cli.coordination.transaction import BookkeepingTransaction

        def failing_commit(self: BookkeepingTransaction, *args: object, **kwargs: object) -> object:
            raise RuntimeError("injected transactional commit failure")

        monkeypatch.setattr(BookkeepingTransaction, "commit", failing_commit)
        derived_status = _derived_status_path(coord_repo, _COORD_MISSION_SLUG)
        with pytest.raises(RuntimeError, match="injected transactional commit failure"):
            st.emit_status_transition_transactional(_coord_request(coord_repo))
        assert not derived_status.exists(), "a failed commit must never leave a projection behind (no synchronous pre-commit refresh)"


class TestInnerStateAnnotationDoorRefresh:
    def test_inner_state_door_refreshes_projection_post_commit(self, coord_repo: Path) -> None:
        """B2: the inner-state annotation door
        (``emit_inner_state_changed_transactional``) is one of the three
        T024 hook sites and had no behavioural test before review cycle 1 --
        mutation M5 removed its hook and nothing caught it."""
        from specify_cli.coordination.status_transition import emit_inner_state_changed_transactional
        from specify_cli.status.models import WPInnerStateDelta

        annotation = emit_inner_state_changed_transactional(
            coord_repo / "kitty-specs" / _COORD_MISSION_DIRNAME,
            "WP01",
            WPInnerStateDelta(note="wp05 inner-state hook test"),
            actor="wp05-test",
            mission_slug=_COORD_MISSION_SLUG,
            repo_root=coord_repo,
        )
        assert annotation.wp_id == "WP01"

        derived_status = _derived_status_path(coord_repo, _COORD_MISSION_SLUG)
        assert derived_status.exists(), "the inner-state annotation door must refresh the projection post-commit"

    def test_inner_state_door_refresh_runs_after_commit_not_before(self, coord_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mirrors ``TestCoordinationTransactionalRefresh::test_transactional_
        refresh_runs_after_commit_not_before`` for the inner-state annotation
        door: an injected commit failure inside the ``BookkeepingTransaction``
        must leave no derived projection behind. The refresh is a
        ``txn.defer_outbound`` callback registered inside the transaction
        (``emit_inner_state_changed_transactional``), so it must never run
        when ``commit`` raises -- a synchronous, pre-commit refresh would
        stay green under this same assertion only if it ran unconditionally.
        """
        from specify_cli.coordination import status_transition as st
        from specify_cli.coordination.transaction import BookkeepingTransaction
        from specify_cli.status.models import WPInnerStateDelta

        def failing_commit(self: BookkeepingTransaction, *args: object, **kwargs: object) -> object:
            raise RuntimeError("injected transactional commit failure")

        monkeypatch.setattr(BookkeepingTransaction, "commit", failing_commit)
        derived_status = _derived_status_path(coord_repo, _COORD_MISSION_SLUG)
        with pytest.raises(RuntimeError, match="injected transactional commit failure"):
            st.emit_inner_state_changed_transactional(
                coord_repo / "kitty-specs" / _COORD_MISSION_DIRNAME,
                "WP01",
                WPInnerStateDelta(note="wp05 inner-state hook after-commit test"),
                actor="wp05-test",
                mission_slug=_COORD_MISSION_SLUG,
                repo_root=coord_repo,
            )
        assert not derived_status.exists(), "a failed commit must never leave a projection behind (no synchronous pre-commit refresh)"


class TestTransactionalBatchRefresh:
    def test_transactional_batch_refreshes_projection_post_commit(self, coord_repo: Path) -> None:
        """B2: nothing exercised ``emit_status_transition_batch_transactional``
        before review cycle 1."""
        from specify_cli.coordination.status_transition import emit_status_transition_batch_transactional

        events = emit_status_transition_batch_transactional(
            [
                _coord_request(coord_repo, to_lane="claimed"),
                _coord_request(
                    coord_repo,
                    to_lane="in_progress",
                    workspace_context="worktree:wp05-batch-test",
                ),
            ]
        )
        assert [str(event.to_lane) for event in events] == ["claimed", "in_progress"]

        derived_status = _derived_status_path(coord_repo, _COORD_MISSION_SLUG)
        assert derived_status.exists(), "the transactional batch door must refresh the projection post-commit"
        data = json.loads(derived_status.read_text())
        assert data["work_packages"]["WP01"]["lane"] == "in_progress"
