"""#4887: the shared locked acceptance-matrix write seam, the row-ownership
splice, and the locked pre-stamp verdict guard.

Covers:

* Lock-spy: :func:`~specify_cli.acceptance.matrix.locked_reread_splice_and_write`
  re-reads and writes strictly while the lock is held, keyed on
  ``matrix_dir.name``; a lock timeout never reaches the write.
* :func:`~specify_cli.acceptance.matrix.splice_owned_rows` table: the
  row-ownership rule for both ``criteria`` and ``negative_invariants``.
* :func:`~specify_cli.acceptance.matrix.locked_acceptance_verdict_guard`:
  yields under the lock on ``pass``/``pass_pending_consolidation``, raises
  :class:`~specify_cli.acceptance.matrix.AcceptanceVerdictNotReadyError`
  otherwise.
* Wiring control: patching the shared seam to raise makes the real
  ``acceptance-verdict`` CLI exit non-zero -- proving the command is wired
  through the seam, not a private copy.
"""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn, cast

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    AcceptanceVerdictNotReadyError,
    NegativeInvariant,
    VERDICT_PASS_PENDING_CONSOLIDATION,
    locked_acceptance_verdict_guard,
    locked_reread_splice_and_write,
    read_acceptance_matrix,
    write_acceptance_matrix,
)
from specify_cli.status.locking import (
    BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS,
    FeatureStatusLockTimeoutError,
    feature_status_lock,
    feature_status_lock_path,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WORK_BRANCH = "matrix-write-seam-work"


# ---------------------------------------------------------------------------
# Shared flat-repo git helpers (mirrors test_acceptance_verdict_command.py)
# ---------------------------------------------------------------------------


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _head(repo_root: Path) -> str:
    return _git(repo_root, "rev-parse", "HEAD").stdout.strip()


def _mission_id_for(slug: str) -> str:
    digest = f"{slug:0<26}".upper()[:26]
    allowed = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    return "".join(c if c in allowed else "0" for c in digest)


def _init_flat_mission(tmp_path: Path, slug: str) -> tuple[Path, Path]:
    repo_root = tmp_path
    _git(repo_root, "init", "-q")
    _git(repo_root, "checkout", "-q", "-b", _WORK_BRANCH)
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")

    kittify_dir = repo_root / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    (kittify_dir / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")

    feature_dir = repo_root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    mission_id = _mission_id_for(slug)
    meta = {
        "mission_slug": slug,
        "slug": slug,
        "mission_id": mission_id,
        "mid8": mission_id[:8],
        "friendly_name": "Matrix Write Seam Test",
        "mission_type": "software-dev",
        "target_branch": _WORK_BRANCH,
        "created_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "init")
    return repo_root, feature_dir


def _seed_matrix(feature_dir: Path, matrix: AcceptanceMatrix) -> None:
    write_acceptance_matrix(feature_dir, matrix)


class _OrderTrackingContext:
    """Wrap a context manager, appending ``"lock_exit"`` to *order* on exit."""

    def __init__(self, inner: object, order: list[str]) -> None:
        self._inner = inner
        self._order = order

    def __enter__(self) -> object:
        return self._inner.__enter__()  # type: ignore[attr-defined]

    def __exit__(self, *exc_info: object) -> object:
        result = self._inner.__exit__(*exc_info)  # type: ignore[attr-defined]
        self._order.append("lock_exit")
        return result


# ===========================================================================
# Lock-spy: locked_reread_splice_and_write
# ===========================================================================


class TestLockedRereadSpliceAndWrite:
    def test_reread_and_write_happen_strictly_inside_the_lock(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Strict order ``lock enter -> read -> write -> lock exit``, and the
        lock key is ``matrix_dir.name``."""
        slug = "seam-strict-order"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(feature_dir, AcceptanceMatrix(mission_slug=slug))
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")

        order: list[str] = []
        lock_calls: list[tuple[Path, str, float]] = []

        import specify_cli.acceptance.matrix as matrix_module

        def _spy_lock(repo_root_arg: Path, lock_key: str, *, timeout: float = -1) -> _OrderTrackingContext:
            lock_calls.append((repo_root_arg, lock_key, timeout))
            order.append("enter")
            cm = feature_status_lock(repo_root_arg, lock_key, timeout=timeout)
            return _OrderTrackingContext(cm, order)

        def _spy_read(feature_dir_arg: Path) -> AcceptanceMatrix | None:
            order.append("read")
            return read_acceptance_matrix(feature_dir_arg)

        def _spy_write(feature_dir_arg: Path, matrix: AcceptanceMatrix) -> Path:
            order.append("write")
            return cast(Path, write_acceptance_matrix(feature_dir_arg, matrix))

        monkeypatch.setattr("specify_cli.status.mission_write.feature_status_lock", _spy_lock)
        monkeypatch.setattr(matrix_module, "read_acceptance_matrix", _spy_read)
        monkeypatch.setattr(matrix_module, "write_acceptance_matrix", _spy_write)

        fresh, result = locked_reread_splice_and_write(
            repo_root=repo_root,
            mission_slug=slug,
            matrix_dir=feature_dir,
            splice=lambda m: None,
            commit=False,
        )

        assert order == ["enter", "read", "write", "lock_exit"], order
        assert len(lock_calls) == 1
        called_repo_root, lock_key, timeout = lock_calls[0]
        assert lock_key == feature_dir.name
        assert timeout == BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS
        lock_path = feature_status_lock_path(called_repo_root, lock_key)
        assert lock_path.is_relative_to(_git_common_dir(repo_root))
        assert isinstance(result, Path)
        assert fresh.mission_slug == slug

    def test_splice_is_applied_to_the_freshly_reread_matrix(self, tmp_path: Path) -> None:
        """The ``splice`` callable receives the RE-READ matrix, not the
        caller's own pre-lock snapshot."""
        slug = "seam-splice-fresh"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        on_disk = AcceptanceMatrix(
            mission_slug=slug,
            criteria=[AcceptanceCriterion(criterion_id="FR-001", description="d", proof_type="automated_test", pass_fail="pending")],
        )
        _seed_matrix(feature_dir, on_disk)
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")

        def _splice(fresh: AcceptanceMatrix) -> None:
            fresh.criteria[0] = AcceptanceCriterion(criterion_id="FR-001", description="d", proof_type="automated_test", pass_fail="pass")

        fresh, result = locked_reread_splice_and_write(repo_root=repo_root, mission_slug=slug, matrix_dir=feature_dir, splice=_splice, commit=False)
        assert isinstance(result, Path)
        assert fresh.criteria[0].pass_fail == "pass"
        reloaded = read_acceptance_matrix(feature_dir)
        assert reloaded is not None
        assert reloaded.criteria[0].pass_fail == "pass"

    def test_matrix_vanished_between_precheck_and_relock_starts_empty(self, tmp_path: Path) -> None:
        """The matrix file is absent at re-read time -- the seam starts from
        an empty, schema-valid matrix rather than crashing."""
        slug = "seam-vanished"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        # Deliberately no acceptance-matrix.json on disk.

        seen_slugs: list[str] = []
        seen_criteria_before_splice: list[list[AcceptanceCriterion]] = []

        def _splice(fresh: AcceptanceMatrix) -> None:
            seen_slugs.append(fresh.mission_slug)
            seen_criteria_before_splice.append(list(fresh.criteria))
            fresh.criteria.append(AcceptanceCriterion(criterion_id="FR-001", description="d", proof_type="automated_test", pass_fail="pass"))

        fresh, result = locked_reread_splice_and_write(repo_root=repo_root, mission_slug=slug, matrix_dir=feature_dir, splice=_splice, commit=False)
        assert isinstance(result, Path)
        assert seen_slugs == [slug]
        assert seen_criteria_before_splice == [[]]
        assert fresh.criteria[0].criterion_id == "FR-001"

    def test_commit_true_routes_through_write_and_commit(self, tmp_path: Path) -> None:
        """``commit=True`` creates a real commit via the shared write seam."""
        slug = "seam-commit-true"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(feature_dir, AcceptanceMatrix(mission_slug=slug))
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")
        head_before = _head(repo_root)

        fresh, result = locked_reread_splice_and_write(
            repo_root=repo_root,
            mission_slug=slug,
            matrix_dir=feature_dir,
            splice=lambda m: None,
            commit=True,
            entry_id="AC-001",
            message="chore(test): commit-true seam call",
        )
        assert not isinstance(result, Path)
        assert result.status in ("committed", "unchanged")
        if result.status == "committed":
            assert _head(repo_root) != head_before

    def test_commit_true_without_entry_id_or_message_raises(self, tmp_path: Path) -> None:
        slug = "seam-commit-missing-args"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(feature_dir, AcceptanceMatrix(mission_slug=slug))
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")

        with pytest.raises(ValueError):
            locked_reread_splice_and_write(
                repo_root=repo_root,
                mission_slug=slug,
                matrix_dir=feature_dir,
                splice=lambda m: None,
                commit=True,
            )

    def test_lock_timeout_never_reaches_the_write(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A lock-acquisition timeout propagates with NO write."""
        slug = "seam-fail-closed"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(feature_dir, AcceptanceMatrix(mission_slug=slug))
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")
        head_before = _head(repo_root)

        import specify_cli.acceptance.matrix as matrix_module

        def _timeout_lock(repo_root_arg: Path, lock_key: str, *, timeout: float = -1) -> NoReturn:
            raise FeatureStatusLockTimeoutError("simulated timeout", lock_path=Path("/nonexistent/fake.status.lock"), timeout=timeout)

        write_calls: list[object] = []

        def _spy_write(*args: Any, **kwargs: Any) -> Path:
            write_calls.append(args)
            return cast(Path, write_acceptance_matrix(*args, **kwargs))

        monkeypatch.setattr("specify_cli.status.mission_write.feature_status_lock", _timeout_lock)
        monkeypatch.setattr(matrix_module, "write_acceptance_matrix", _spy_write)

        with pytest.raises(FeatureStatusLockTimeoutError):
            locked_reread_splice_and_write(
                repo_root=repo_root,
                mission_slug=slug,
                matrix_dir=feature_dir,
                splice=lambda m: None,
                commit=False,
                timeout=0.01,
            )
        assert not write_calls, "a lock-acquisition timeout must never reach the write"
        assert _head(repo_root) == head_before


def _git_common_dir(repo_root: Path) -> Path:
    from kernel.git_topology import git_common_dir

    return git_common_dir(repo_root)


# ===========================================================================
# splice_owned_rows: row ownership table
# ===========================================================================


def _criterion(criterion_id: str, *, pass_fail: str, proof_type: str = "automated_test", description: str = "d") -> AcceptanceCriterion:
    return AcceptanceCriterion(criterion_id=criterion_id, description=description, proof_type=proof_type, pass_fail=pass_fail)


def _ni(
    invariant_id: str,
    *,
    result: str,
    verification_method: str = "grep_absence",
    verification_command: str | None = "pattern",
    scope: str | None = None,
) -> NegativeInvariant:
    return NegativeInvariant(
        invariant_id=invariant_id,
        description="d",
        verification_method=verification_method,
        verification_command=verification_command,
        result=result,
        scope=scope,
    )


class TestSpliceOwnedRowsCriteria:
    def test_owned_transition_applied(self) -> None:
        """Snapshot pending, judged pass, fresh still pending, definition
        unchanged -> the fresh row is REPLACED by accept's judged row."""
        snapshot = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-001", pass_fail="pending")])
        judged = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-001", pass_fail="pass")])
        fresh = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-001", pass_fail="pending")])

        from specify_cli.acceptance.matrix import splice_owned_rows

        splice_owned_rows(fresh, snapshot, judged)
        assert fresh.criteria[0].pass_fail == "pass"

    def test_fresh_terminal_wins(self) -> None:
        """A concurrently committed non-pending fresh row is NEVER overwritten,
        even by accept's own (also non-pending) judged value."""
        snapshot = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-001", pass_fail="pending")])
        judged = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-001", pass_fail="pass")])
        fresh = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-001", pass_fail="fail")])

        from specify_cli.acceptance.matrix import splice_owned_rows

        splice_owned_rows(fresh, snapshot, judged)
        assert fresh.criteria[0].pass_fail == "fail"

    def test_fresh_only_row_kept(self) -> None:
        """A row that exists only in ``fresh`` (added concurrently) is left
        untouched."""
        snapshot = AcceptanceMatrix(mission_slug="m", criteria=[])
        judged = AcceptanceMatrix(mission_slug="m", criteria=[])
        fresh = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-002", pass_fail="pending")])

        from specify_cli.acceptance.matrix import splice_owned_rows

        splice_owned_rows(fresh, snapshot, judged)
        assert len(fresh.criteria) == 1
        assert fresh.criteria[0].criterion_id == "FR-002"

    def test_snapshot_only_row_not_readded(self) -> None:
        """A row present only in ``snapshot``/``judged`` (removed concurrently
        from ``fresh``) is never re-added. ``fresh`` carries an UNRELATED
        pending row so ``_splice_owned_rows_for_spec``'s `if not fresh_rows:
        return` early exit cannot mask this: an implementation that appended
        missing judged rows would still fail this."""
        snapshot = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-003", pass_fail="pending")])
        judged = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-003", pass_fail="pass")])
        fresh = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-999", pass_fail="pending")])

        from specify_cli.acceptance.matrix import splice_owned_rows

        splice_owned_rows(fresh, snapshot, judged)
        assert [c.criterion_id for c in fresh.criteria] == ["FR-999"]
        assert fresh.criteria[0].pass_fail == "pending"

    def test_snapshot_not_pending_never_reapplied_even_if_fresh_resets_to_pending(self) -> None:
        """Row-ownership rule condition 1: R must have been ``pending`` in accept's
        SNAPSHOT. When the snapshot already carried a TERMINAL value (e.g.
        ``pass``) and a concurrent writer resets the row to ``pending`` in
        ``fresh`` (e.g. ``acceptance-verdict --criterion ... --result
        pending``), accept's stale judgement of the OLD (already-decided) row
        must NOT be stamped back over the deliberately reset ``pending`` row.
        Mutation coverage: deleting the snapshot-pending guard in
        ``_row_is_owned`` turns this red."""
        snapshot = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-005", pass_fail="pass")])
        judged = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-005", pass_fail="pass")])
        fresh = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-005", pass_fail="pending")])

        from specify_cli.acceptance.matrix import splice_owned_rows

        splice_owned_rows(fresh, snapshot, judged)
        assert fresh.criteria[0].pass_fail == "pending"

    def test_criterion_variant_reauthored_definition_keeps_fresh_pending(self) -> None:
        """A criterion re-authored with a different ``proof_type`` between
        snapshot and fresh is a NEW row -- accept's stale judgement of the
        OLD definition must not apply."""
        snapshot = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-004", pass_fail="pending", proof_type="automated_test")])
        judged = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-004", pass_fail="pass", proof_type="automated_test")])
        fresh = AcceptanceMatrix(mission_slug="m", criteria=[_criterion("FR-004", pass_fail="pending", proof_type="manual_qa")])

        from specify_cli.acceptance.matrix import splice_owned_rows

        splice_owned_rows(fresh, snapshot, judged)
        assert fresh.criteria[0].pass_fail == "pending"
        assert fresh.criteria[0].proof_type == "manual_qa"


class TestSpliceOwnedRowsNegativeInvariants:
    def test_owned_transition_applied(self) -> None:
        snapshot = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-1", result="pending")])
        judged = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-1", result="confirmed_absent")])
        fresh = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-1", result="pending")])

        from specify_cli.acceptance.matrix import splice_owned_rows

        splice_owned_rows(fresh, snapshot, judged)
        assert fresh.negative_invariants[0].result == "confirmed_absent"

    def test_fresh_terminal_wins(self) -> None:
        snapshot = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-1", result="pending")])
        judged = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-1", result="confirmed_absent")])
        fresh = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-1", result="still_present")])

        from specify_cli.acceptance.matrix import splice_owned_rows

        splice_owned_rows(fresh, snapshot, judged)
        assert fresh.negative_invariants[0].result == "still_present"

    def test_fresh_only_row_kept(self) -> None:
        snapshot = AcceptanceMatrix(mission_slug="m", negative_invariants=[])
        judged = AcceptanceMatrix(mission_slug="m", negative_invariants=[])
        fresh = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-2", result="pending")])

        from specify_cli.acceptance.matrix import splice_owned_rows

        splice_owned_rows(fresh, snapshot, judged)
        assert len(fresh.negative_invariants) == 1

    def test_snapshot_only_row_not_readded(self) -> None:
        """``fresh`` carries an UNRELATED pending row so the early exit for an
        empty ``fresh`` section cannot mask a bug that would re-add the
        snapshot-only row."""
        snapshot = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-3", result="pending")])
        judged = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-3", result="confirmed_absent")])
        fresh = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-999", result="pending")])

        from specify_cli.acceptance.matrix import splice_owned_rows

        splice_owned_rows(fresh, snapshot, judged)
        assert [ni.invariant_id for ni in fresh.negative_invariants] == ["NI-999"]
        assert fresh.negative_invariants[0].result == "pending"

    def test_snapshot_not_pending_never_reapplied_even_if_fresh_resets_to_pending(self) -> None:
        """Row-ownership rule condition 1 for negative invariants: a snapshot that already
        carried a TERMINAL result (e.g. ``confirmed_absent``) must never be
        re-applied even though ``judged`` agrees, when ``fresh`` has been
        reset to ``pending`` by a concurrent re-registration. Mutation
        coverage: deleting the snapshot-pending guard in ``_row_is_owned``
        turns this red."""
        snapshot = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-5", result="confirmed_absent")])
        judged = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-5", result="confirmed_absent")])
        fresh = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-5", result="pending")])

        from specify_cli.acceptance.matrix import splice_owned_rows

        splice_owned_rows(fresh, snapshot, judged)
        assert fresh.negative_invariants[0].result == "pending"

    def test_reregistered_invariant_with_changed_command_keeps_fresh_pending(self) -> None:
        """A negative invariant re-registered (``acceptance-verdict
        --negative-invariant``) with a DIFFERENT ``verification_command``
        between snapshot and fresh is a NEW definition -- accept's result,
        judged against the OLD command, is discarded and the fresh
        ``pending`` row stays (accept refuses)."""
        snapshot = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-4", result="pending", verification_command="old-pattern")])
        judged = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-4", result="confirmed_absent", verification_command="old-pattern")])
        fresh = AcceptanceMatrix(mission_slug="m", negative_invariants=[_ni("NI-4", result="pending", verification_command="new-pattern")])

        from specify_cli.acceptance.matrix import splice_owned_rows

        splice_owned_rows(fresh, snapshot, judged)
        assert fresh.negative_invariants[0].result == "pending"
        assert fresh.negative_invariants[0].verification_command == "new-pattern"

    def test_tolerates_matrix_double_without_criteria_or_negative_invariants_attribute(self) -> None:
        """A unit-test double lacking ``criteria``/``negative_invariants``
        entirely is treated as empty rather than raising."""
        from specify_cli.acceptance.matrix import splice_owned_rows

        fresh = SimpleNamespace(mission_slug="m")
        snapshot = SimpleNamespace(mission_slug="m")
        judged = SimpleNamespace(mission_slug="m")

        splice_owned_rows(fresh, snapshot, judged)  # must not raise


# ===========================================================================
# locked_acceptance_verdict_guard
# ===========================================================================


class TestLockedAcceptanceVerdictGuard:
    def test_pass_verdict_yields(self, tmp_path: Path) -> None:
        slug = "guard-pass"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(
            feature_dir,
            AcceptanceMatrix(mission_slug=slug, criteria=[_criterion("FR-001", pass_fail="pass")]),
        )
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")

        with locked_acceptance_verdict_guard(repo_root, feature_dir) as matrix:
            assert matrix.overall_verdict == "pass"

    def test_pass_pending_consolidation_verdict_yields(self, tmp_path: Path) -> None:
        slug = "guard-pass-pending-consolidation"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(
            feature_dir,
            AcceptanceMatrix(
                mission_slug=slug,
                negative_invariants=[_ni("NI-1", result="deferred_to_consolidation")],
            ),
        )
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")

        with locked_acceptance_verdict_guard(repo_root, feature_dir) as matrix:
            assert matrix.overall_verdict == VERDICT_PASS_PENDING_CONSOLIDATION

    def test_pending_verdict_raises(self, tmp_path: Path) -> None:
        slug = "guard-pending"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(
            feature_dir,
            AcceptanceMatrix(mission_slug=slug, criteria=[_criterion("FR-001", pass_fail="pending")]),
        )
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")

        with pytest.raises(AcceptanceVerdictNotReadyError) as exc_info, locked_acceptance_verdict_guard(repo_root, feature_dir):
            raise AssertionError("must not yield on a pending verdict")
        assert exc_info.value.verdict == "pending"

    def test_missing_matrix_raises_as_pending_via_explicit_branch(self, tmp_path: Path) -> None:
        """A missing ``acceptance-matrix.json`` is treated as ``"pending"``
        through an EXPLICIT ``if fresh_matrix is None: raise ...`` branch
        (not a bare ``assert`` further down that ``python -O`` could strip)."""
        slug = "guard-missing-matrix"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        # Deliberately no acceptance-matrix.json on disk.

        with pytest.raises(AcceptanceVerdictNotReadyError) as exc_info, locked_acceptance_verdict_guard(repo_root, feature_dir):
            raise AssertionError("must not yield when the matrix is missing")
        assert exc_info.value.verdict == "pending"

    def test_fail_verdict_raises(self, tmp_path: Path) -> None:
        slug = "guard-fail"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(
            feature_dir,
            AcceptanceMatrix(mission_slug=slug, criteria=[_criterion("FR-001", pass_fail="fail")]),
        )
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")

        with pytest.raises(AcceptanceVerdictNotReadyError) as exc_info, locked_acceptance_verdict_guard(repo_root, feature_dir):
            raise AssertionError("must not yield on a fail verdict")
        assert exc_info.value.verdict == "fail"

    def test_lock_is_held_during_the_body(self, tmp_path: Path) -> None:
        """The guard yields while STILL HOLDING the lock -- a concurrent
        acquisition attempt from ANOTHER thread (short timeout) fails. A
        same-thread reacquisition is deliberately not used here: the
        underlying lock is re-entrant per thread (by design, so a larger
        transaction can safely wrap helpers that also take the lock), so it
        would prove nothing about whether the lock is actually held."""
        slug = "guard-lock-held"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(
            feature_dir,
            AcceptanceMatrix(mission_slug=slug, criteria=[_criterion("FR-001", pass_fail="pass")]),
        )
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")

        import threading

        other_thread_result: list[BaseException | None] = []

        def _contend() -> None:
            try:
                with feature_status_lock(repo_root, feature_dir.name, timeout=0.2):
                    other_thread_result.append(None)
            except FeatureStatusLockTimeoutError as exc:
                other_thread_result.append(exc)

        with locked_acceptance_verdict_guard(repo_root, feature_dir):
            thread = threading.Thread(target=_contend)
            thread.start()
            thread.join(timeout=5)

        assert len(other_thread_result) == 1
        assert isinstance(other_thread_result[0], FeatureStatusLockTimeoutError), "a concurrent thread must fail to acquire the lock while the guard holds it"

    def test_lock_timeout_raises_before_any_read(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        slug = "guard-lock-timeout"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(
            feature_dir,
            AcceptanceMatrix(mission_slug=slug, criteria=[_criterion("FR-001", pass_fail="pass")]),
        )
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")

        import specify_cli.acceptance.matrix as matrix_module

        read_calls: list[object] = []

        def _timeout_lock(repo_root_arg: Path, lock_key: str, *, timeout: float = -1) -> NoReturn:
            raise FeatureStatusLockTimeoutError("simulated timeout", lock_path=Path("/nonexistent/fake.status.lock"), timeout=timeout)

        def _spy_read(feature_dir_arg: Path) -> AcceptanceMatrix | None:
            read_calls.append(feature_dir_arg)
            return read_acceptance_matrix(feature_dir_arg)

        monkeypatch.setattr("specify_cli.status.mission_write.feature_status_lock", _timeout_lock)
        monkeypatch.setattr(matrix_module, "read_acceptance_matrix", _spy_read)

        with pytest.raises(FeatureStatusLockTimeoutError), locked_acceptance_verdict_guard(repo_root, feature_dir, timeout=0.01):
            raise AssertionError("must not yield on a lock timeout")
        assert not read_calls


# ===========================================================================
# Wiring control: patching the shared seam breaks the CLI
# ===========================================================================


class TestVerdictCommandWiredThroughTheSharedSeam:
    def test_seam_raising_makes_the_cli_exit_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Positive control: monkeypatching the shared seam
        to raise makes the real ``acceptance-verdict`` CLI fail -- proving the
        command routes through it rather than a private copy."""
        slug = "wiring-control"
        repo_root, feature_dir = _init_flat_mission(tmp_path, slug)
        _seed_matrix(
            feature_dir,
            AcceptanceMatrix(mission_slug=slug, criteria=[_criterion("FR-001", pass_fail="pending")]),
        )
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed")
        monkeypatch.chdir(repo_root)

        # ``specify_cli.cli.commands.agent``'s ``__init__.py`` does
        # ``from .acceptance_verdict import acceptance_verdict`` -- the
        # FUNCTION is re-exported under the SAME name as its own SUBMODULE,
        # which shadows the submodule on a plain attribute access.
        # ``importlib.import_module`` reads straight from ``sys.modules``
        # instead, giving the real submodule object to patch.
        av_command = importlib.import_module("specify_cli.cli.commands.agent.acceptance_verdict")

        def _boom(*args: object, **kwargs: object) -> NoReturn:
            raise RuntimeError("seam exploded")

        monkeypatch.setattr(av_command, "locked_reread_splice_and_write", _boom)

        result = CliRunner().invoke(
            cli_app,
            [
                "agent",
                "mission",
                "acceptance-verdict",
                "--mission",
                slug,
                "--criterion",
                "FR-001",
                "--result",
                "pass",
                "--verification-method",
                "automated_test",
                "--json",
            ],
        )
        assert result.exit_code != 0

    def test_private_helper_is_gone(self) -> None:
        """The command-local
        ``_locked_reread_splice_and_write`` copy no longer exists -- the
        command has exactly one write path, the shared seam."""
        import specify_cli.cli.commands.agent.acceptance_verdict as av_command

        assert not hasattr(av_command, "_locked_reread_splice_and_write")
