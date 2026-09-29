"""Unit tests for the status-owned transition pipeline (WP02, FR-005).

``status/transition_pipeline.py::prepare_transition`` is the single
validation/build authority (decision Q4). These tests pin its behavioural
contract (``contracts/emit-pipeline.md`` §1) with in-memory mission dirs and
injected fakes, the NFR-004 cost pin (§6) through the flat shells, and the
purity/layering invariants (P-1, P-3) via an AST scan of the module source.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import specify_cli.status.emit as emit_module
import specify_cli.status.transition_pipeline as pipeline_module
from kernel.clock import now_utc_iso
from specify_cli.core.dependency_graph import DependencyReadiness
from specify_cli.status.emit import (
    TransitionError,
    emit_status_transition,
    emit_status_transition_batch,
)
from specify_cli.status.models import (
    DoneEvidence,
    InnerStateChanged,
    Lane,
    ReviewResult,
    StatusEvent,
    TransitionRequest,
    WPInnerStateDelta,
)
from specify_cli.status.transition_pipeline import PreparedTransition, prepare_transition
from tests.status.conftest import seed_wp_to_planned as _seed_planned

pytestmark = pytest.mark.fast

_SLUG = "034-test-mission"
_MISSION_ID = "01ABCDEFGHJKMNPQRSTVWXYZ12"


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    fd = tmp_path / "kitty-specs" / _SLUG
    fd.mkdir(parents=True)
    return fd


def _request(**overrides: Any) -> TransitionRequest:
    base: dict[str, Any] = {
        "feature_dir": None,
        "mission_slug": _SLUG,
        "wp_id": "WP01",
        "to_lane": "claimed",
        "actor": "agent-1",
    }
    base.update(overrides)
    return TransitionRequest(**base)


class _Fakes:
    """Injected I/O fakes with call counters (contract §1 seams)."""

    def __init__(self, *, subtasks_complete: bool = True, evidence_present: bool = True) -> None:
        self.resolver_calls: list[dict[str, Any]] = []
        self.subtasks_calls: list[tuple[Any, ...]] = []
        self.evidence_calls: list[tuple[Any, ...]] = []
        self._subtasks_complete = subtasks_complete
        self._evidence_present = evidence_present

    def resolve_subtasks_dir(self, feature_dir: Path, repo_root: Path | None, mission_slug: str, *, effective_root: Path | None = None) -> Path:
        self.resolver_calls.append({"feature_dir": feature_dir, "repo_root": repo_root, "mission_slug": mission_slug, "effective_root": effective_root})
        return feature_dir

    def infer_subtasks_complete(self, subtasks_dir: Path, wp_id: str, *, status_dir: Path | None = None) -> bool:
        self.subtasks_calls.append((subtasks_dir, wp_id, status_dir))
        return self._subtasks_complete

    def infer_implementation_evidence(self, feature_dir: Path, wp_id: str) -> bool:
        self.evidence_calls.append((feature_dir, wp_id))
        return self._evidence_present

    def kwargs(self) -> dict[str, Any]:
        return {
            "resolve_subtasks_dir": self.resolve_subtasks_dir,
            "infer_subtasks_complete": self.infer_subtasks_complete,
            "infer_implementation_evidence": self.infer_implementation_evidence,
        }


def _prepare(feature_dir: Path, request: TransitionRequest, from_lane: str, **extra: Any) -> PreparedTransition:
    return prepare_transition(
        request=request,
        feature_dir=feature_dir,
        mission_slug=_SLUG,
        mission_id=_MISSION_ID,
        from_lane=from_lane,
        **extra,
    )


# ── T010: behavioural contract ───────────────────────────────────────────────


class TestAliasHandling:
    def test_doing_alias_resolves_to_in_progress(self, feature_dir: Path) -> None:
        prepared = _prepare(feature_dir, _request(to_lane="doing", workspace_context="worktree:/x"), Lane.CLAIMED)
        assert prepared.event is not None
        assert prepared.event.to_lane == Lane.IN_PROGRESS
        assert prepared.resolved_lane == Lane.IN_PROGRESS

    def test_alias_collapse_is_a_mirror_only_no_op(self, feature_dir: Path) -> None:
        prepared = _prepare(feature_dir, _request(to_lane="doing"), Lane.IN_PROGRESS)
        assert prepared == PreparedTransition(
            event=None,
            resolved_lane=Lane.IN_PROGRESS,
            annotation=None,
            mirror_frontmatter_lane=True,
        )

    def test_missing_wp_id_raises_type_error(self, feature_dir: Path) -> None:
        with pytest.raises(TypeError, match="requires wp_id, to_lane, and actor"):
            _prepare(feature_dir, _request(wp_id=None), Lane.PLANNED)


class TestReviewGateInference:
    def test_gates_inferred_only_for_review_handoff_without_force(self, feature_dir: Path) -> None:
        fakes = _Fakes()
        prepared = _prepare(feature_dir, _request(to_lane="for_review", repo_root=feature_dir.parent.parent), Lane.IN_PROGRESS, **fakes.kwargs())
        assert prepared.event is not None
        assert prepared.event.to_lane == Lane.FOR_REVIEW
        assert len(fakes.resolver_calls) == 1
        assert fakes.resolver_calls[0]["mission_slug"] == _SLUG
        assert fakes.resolver_calls[0]["repo_root"] == feature_dir.parent.parent
        assert fakes.subtasks_calls == [(feature_dir, "WP01", feature_dir)]
        assert fakes.evidence_calls == [(feature_dir, "WP01")]

    def test_forced_review_handoff_skips_subtask_gate_but_still_infers_evidence(self, feature_dir: Path) -> None:
        fakes = _Fakes()
        _prepare(feature_dir, _request(to_lane="for_review", force=True, reason="forced"), Lane.IN_PROGRESS, **fakes.kwargs())
        assert fakes.resolver_calls == []
        assert fakes.subtasks_calls == []
        assert len(fakes.evidence_calls) == 1

    def test_non_review_edges_never_touch_the_gate_readers(self, feature_dir: Path) -> None:
        fakes = _Fakes()
        _prepare(feature_dir, _request(to_lane="claimed"), Lane.PLANNED, **fakes.kwargs())
        assert fakes.resolver_calls == []
        assert fakes.subtasks_calls == []
        assert fakes.evidence_calls == []

    def test_implementation_evidence_inferred_only_when_caller_left_it_none(self, feature_dir: Path) -> None:
        fakes = _Fakes()
        _prepare(
            feature_dir,
            _request(to_lane="for_review", implementation_evidence_present=True),
            Lane.IN_PROGRESS,
            **fakes.kwargs(),
        )
        assert fakes.evidence_calls == []
        assert len(fakes.subtasks_calls) == 1

    def test_incomplete_subtasks_refuse_the_handoff(self, feature_dir: Path) -> None:
        fakes = _Fakes(subtasks_complete=False)
        with pytest.raises(TransitionError):
            _prepare(feature_dir, _request(to_lane="for_review"), Lane.IN_PROGRESS, **fakes.kwargs())

    def test_effective_root_is_threaded_to_the_resolver(self, feature_dir: Path, tmp_path: Path) -> None:
        fakes = _Fakes()
        owned = tmp_path / "owned"
        _prepare(feature_dir, _request(to_lane="for_review", effective_root=owned), Lane.IN_PROGRESS, **fakes.kwargs())
        assert fakes.resolver_calls[0]["effective_root"] == owned


class TestEventConstruction:
    def test_evidence_dict_becomes_done_evidence(self, feature_dir: Path) -> None:
        evidence = {"review": {"reviewer": "rev", "verdict": "approved", "reference": "PR#1"}}
        prepared = _prepare(feature_dir, _request(to_lane="done", actor="rev", evidence=evidence), Lane.APPROVED)
        assert prepared.event is not None
        assert isinstance(prepared.event.evidence, DoneEvidence)
        assert prepared.event.evidence.review.reviewer == "rev"

    def test_malformed_evidence_is_refused_before_validation(self, feature_dir: Path) -> None:
        with pytest.raises(TransitionError, match="review.reviewer"):
            _prepare(feature_dir, _request(to_lane="done", evidence={"review": {}}), Lane.APPROVED)

    def test_build_receives_provenance_policy_review_result_and_identity(self, feature_dir: Path) -> None:
        review_result = ReviewResult(reviewer="rev", verdict="approved", reference="review-1")
        prepared = _prepare(
            feature_dir,
            _request(
                to_lane="approved",
                actor="rev",
                review_result=review_result,
                policy_metadata={"agent": "rev"},
                reason="looks good",
                reason_source="operator",
                review_ref="review-1",
            ),
            Lane.IN_REVIEW,
        )
        event = prepared.event
        assert event is not None
        assert event.mission_id == _MISSION_ID
        assert event.mission_slug == _SLUG
        assert event.review_result == review_result
        assert event.policy_metadata == {"agent": "rev"}
        assert event.reason_source == "operator"
        assert event.review_ref == "review-1"
        assert event.from_lane == Lane.IN_REVIEW

    def test_at_is_stamped_on_event_and_annotation(self, feature_dir: Path) -> None:
        stamp = now_utc_iso()
        prepared = _prepare(
            feature_dir,
            _request(annotation_delta=WPInnerStateDelta(role="implementer", agent_profile="python-pedro")),
            Lane.PLANNED,
            at=stamp,
        )
        assert prepared.event is not None
        assert prepared.event.at == stamp
        assert isinstance(prepared.annotation, InnerStateChanged)
        assert prepared.annotation.at == stamp
        assert prepared.annotation.delta.role == "implementer"
        # Distinct ULIDs; no sort order is claimed (python-ulid is not monotonic
        # within a millisecond, and the reducer folds annotations post-transition).
        assert prepared.annotation.event_id != prepared.event.event_id

    def test_no_annotation_without_delta(self, feature_dir: Path) -> None:
        prepared = _prepare(feature_dir, _request(), Lane.PLANNED)
        assert prepared.annotation is None
        assert prepared.mirror_frontmatter_lane is True

    def test_workspace_context_defaults_to_execution_mode_and_root(self, feature_dir: Path, tmp_path: Path) -> None:
        # claimed -> in_progress REQUIRES a workspace context; the default
        # ``<execution_mode>:<repo_root or feature_dir>`` satisfies the guard.
        prepared = _prepare(feature_dir, _request(to_lane="in_progress", repo_root=tmp_path), Lane.CLAIMED)
        assert prepared.event is not None
        assert prepared.event.to_lane == Lane.IN_PROGRESS


class TestDefaultWorkspaceContextKnob:
    """``prepare_transition(default_workspace_context=...)`` (#946, D-2, DRIFT-3).

    The pipeline is the single validation authority, so the plain batch
    door's deliberate #946 fail-closed skip lives here as an explicit policy
    knob rather than as shell-side logic. ``True`` (the default every other
    door relies on) synthesises ``<execution_mode>:<repo_root or feature_dir>``
    when the request omits ``workspace_context``; ``False`` leaves it ``None``
    so the ``claimed -> in_progress`` guard refuses with the historical
    message. Operator decision 2026-09-07 reverted WP02's parity change.
    """

    def test_true_synthesises_the_default_for_claimed_to_in_progress(self, feature_dir: Path, tmp_path: Path) -> None:
        prepared = _prepare(
            feature_dir,
            _request(to_lane="in_progress", repo_root=tmp_path),
            Lane.CLAIMED,
            default_workspace_context=True,
        )
        assert prepared.event is not None
        assert prepared.event.to_lane == Lane.IN_PROGRESS

    def test_false_refuses_claimed_to_in_progress_without_a_context(self, feature_dir: Path, tmp_path: Path) -> None:
        with pytest.raises(TransitionError, match="requires workspace context"):
            _prepare(
                feature_dir,
                _request(to_lane="in_progress", repo_root=tmp_path),
                Lane.CLAIMED,
                default_workspace_context=False,
            )

    def test_false_honours_an_explicit_context(self, feature_dir: Path) -> None:
        prepared = _prepare(
            feature_dir,
            _request(to_lane="in_progress", workspace_context="worktree:/nonexistent/wp01"),
            Lane.CLAIMED,
            default_workspace_context=False,
        )
        assert prepared.event is not None
        assert prepared.event.to_lane == Lane.IN_PROGRESS

    def test_false_leaves_edges_without_a_context_guard_untouched(self, feature_dir: Path) -> None:
        # Only the claimed -> in_progress guard reads workspace_context
        # (``wp_state.py``); every other edge is unaffected by the knob.
        prepared = _prepare(feature_dir, _request(to_lane="claimed"), Lane.PLANNED, default_workspace_context=False)
        assert prepared.event is not None
        assert prepared.event.to_lane == Lane.CLAIMED


class TestValidation:
    def test_validate_transition_called_exactly_once(self, feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[Any, ...]] = []
        real = pipeline_module.validate_transition

        def counting(*args: Any, **kwargs: Any) -> Any:
            calls.append(args)
            return real(*args, **kwargs)

        monkeypatch.setattr(pipeline_module, "validate_transition", counting)
        _prepare(feature_dir, _request(), Lane.PLANNED)
        assert len(calls) == 1
        assert calls[0][:2] == (Lane.PLANNED, Lane.CLAIMED)

    def test_refusal_raises_transition_error(self, feature_dir: Path) -> None:
        with pytest.raises(TransitionError, match="Illegal transition"):
            _prepare(feature_dir, _request(to_lane="done"), Lane.PLANNED)

    @pytest.mark.parametrize(
        "readiness",
        [None, DependencyReadiness(wp_id="WP01", dependencies=("WP00",), unsatisfied=())],
        ids=["none", "satisfied"],
    )
    def test_readiness_passes_through(self, feature_dir: Path, readiness: DependencyReadiness | None) -> None:
        # WP04 wires the guard; until then both verdicts are accepted and inert.
        prepared = _prepare(feature_dir, _request(), Lane.PLANNED, readiness=readiness)
        assert prepared.event is not None
        assert prepared.event.to_lane == Lane.CLAIMED


class TestPurity:
    def test_no_writes_no_lock_against_in_memory_mission_dir(self, feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def forbidden_lock(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("the pipeline must never take feature_status_lock")

        monkeypatch.setattr(emit_module, "feature_status_lock", forbidden_lock)
        before = sorted(p.relative_to(feature_dir) for p in feature_dir.rglob("*"))
        prepared = _prepare(feature_dir, _request(), Lane.PLANNED, **_Fakes().kwargs())
        after = sorted(p.relative_to(feature_dir) for p in feature_dir.rglob("*"))
        assert prepared.event is not None
        assert before == after == []


# ── T014: layering + purity pins (AST) ───────────────────────────────────────


def _pipeline_tree() -> ast.Module:
    source = Path(pipeline_module.__file__).read_text(encoding="utf-8")
    return ast.parse(source)


def _imported_modules(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def _called_names(tree: ast.Module) -> set[str]:
    called: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            called.add(func.id)
        elif isinstance(func, ast.Attribute):
            called.add(func.attr)
    return called


def test_pipeline_never_imports_coordination() -> None:
    imported = _imported_modules(_pipeline_tree())
    assert not any(name.startswith("specify_cli.coordination") for name in imported), imported
    assert not any(name.startswith("subprocess") for name in imported), imported


def test_pipeline_performs_no_writes_locks_or_git() -> None:
    called = _called_names(_pipeline_tree())
    forbidden = {"open", "feature_status_lock", "write_frontmatter", "run", "materialize"}
    assert not (called & forbidden), called & forbidden
    assert not any(name.startswith("append_") for name in called), called


def test_ast_pins_are_non_vacuous() -> None:
    """Mutation check: the scanners flag the shapes they claim to forbid."""
    poisoned = ast.parse("from specify_cli.coordination import x\nimport subprocess\ndef f(p):\n    open(p, 'a')\n    _store.append_events_atomic(p, [])\n")
    imported = _imported_modules(poisoned)
    assert any(name.startswith("specify_cli.coordination") for name in imported)
    assert "subprocess" in imported
    called = _called_names(poisoned)
    assert "open" in called
    assert any(name.startswith("append_") for name in called)


# ── T013: NFR-004 cost pin through the flat shells (contract §6) ─────────────


class _ReadCounters:
    """Count ``_derive_from_lane`` and full-log ``read_events`` calls on the emit path.

    ``reads_before_append`` snapshots the read count at the moment of the
    atomic append: that is the emit path's own cost. Reads AFTER the append
    are the pre-existing durability read-back (``store.verify_event_readback``,
    one per appended event) and the materialize step -- not pipeline cost, and
    not what NFR-004 governs.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.derive = 0
        self.read_events = 0
        self.reads_before_append: int | None = None
        self.appends = 0
        real_derive = emit_module._derive_from_lane
        real_read = emit_module._store.read_events
        real_append = emit_module._store.append_event_stream_atomic_verified

        def counting_derive(*args: Any, **kwargs: Any) -> Any:
            self.derive += 1
            return real_derive(*args, **kwargs)

        def counting_read(*args: Any, **kwargs: Any) -> Any:
            self.read_events += 1
            return real_read(*args, **kwargs)

        def observing_append(*args: Any, **kwargs: Any) -> Any:
            self.appends += 1
            self.reads_before_append = self.read_events
            return real_append(*args, **kwargs)

        monkeypatch.setattr(emit_module, "_derive_from_lane", counting_derive)
        monkeypatch.setattr(emit_module._store, "read_events", counting_read)
        monkeypatch.setattr(emit_module._store, "append_event_stream_atomic_verified", observing_append)


def test_emit_reads_log_once(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One flat-shell emit: ``_derive_from_lane`` == 1, one full-log read before the write."""
    _seed_planned(feature_dir, "WP01", slug=_SLUG)
    counters = _ReadCounters(monkeypatch)
    with patch.object(emit_module, "_saas_fan_out"):
        event = emit_status_transition(_request(feature_dir=feature_dir))
    assert isinstance(event, StatusEvent)
    assert counters.appends == 1
    assert counters.derive == 1
    assert counters.reads_before_append == 1


def test_batch_emit_reads_log_once_for_the_whole_batch(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A batch of N: one derive, one full read before the single write -- from_lane chains in memory."""
    _seed_planned(feature_dir, "WP01", slug=_SLUG)
    counters = _ReadCounters(monkeypatch)
    with patch.object(emit_module, "_saas_fan_out"):
        events = emit_status_transition_batch(
            [
                _request(feature_dir=feature_dir, to_lane="claimed"),
                _request(feature_dir=feature_dir, to_lane="in_progress", workspace_context="worktree:/nonexistent/wp01"),
                _request(feature_dir=feature_dir, to_lane="for_review", force=True, reason="ready"),
            ]
        )
    assert [event.to_lane for event in events] == [Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW]
    assert counters.appends == 1
    assert counters.derive == 1
    assert counters.reads_before_append == 1


# ── WP03 (mixed-lane-authorship-soundness-01M3M7Y0, FR-001/T015): lane-head
#    stamping through prepare_transition itself (pure -- no git, no I/O). ──


class TestLaneHeadStamping:
    def test_none_probe_means_no_stamp(self, feature_dir: Path) -> None:
        """``lane_head_probe`` defaults to ``None`` -- P-1 (the pipeline never defaults to a real probe)."""
        prepared = _prepare(feature_dir, _request(feature_dir=feature_dir, policy_metadata={"agent": "claude"}), Lane.PLANNED)
        assert prepared.event is not None
        assert prepared.event.policy_metadata == {"agent": "claude"}

    def test_probe_called_once_with_expected_args_and_stamps_the_event(self, feature_dir: Path) -> None:
        calls: list[dict[str, Any]] = []

        def fake_probe(*, repo_root: Path, mission_slug: str, wp_id: str) -> str | None:
            calls.append({"repo_root": repo_root, "mission_slug": mission_slug, "wp_id": wp_id})
            return "deadbeef" * 5

        repo_root = feature_dir.parent.parent
        prepared = _prepare(
            feature_dir,
            _request(feature_dir=feature_dir, policy_metadata={"agent": "claude"}, repo_root=repo_root),
            Lane.PLANNED,
            lane_head_probe=fake_probe,
        )
        assert prepared.event is not None
        assert prepared.event.policy_metadata == {"agent": "claude", "lane_head": "deadbeef" * 5}
        assert calls == [{"repo_root": repo_root, "mission_slug": _SLUG, "wp_id": "WP01"}]

    def test_probe_returning_none_leaves_policy_metadata_untouched(self, feature_dir: Path) -> None:
        prepared = _prepare(
            feature_dir,
            _request(feature_dir=feature_dir, policy_metadata={"agent": "claude"}, repo_root=feature_dir),
            Lane.PLANNED,
            lane_head_probe=lambda **_: None,
        )
        assert prepared.event is not None
        assert prepared.event.policy_metadata == {"agent": "claude"}

    def test_no_stamp_persists_byte_identically_to_no_probe_injected(self, feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No stamp (``None`` probe vs. a probe that finds nothing) must build the identical event."""
        monkeypatch.setattr(emit_module, "_generate_ulid", lambda: "01FIXEDULIDFORCOMPARISON1")
        request_kwargs: dict[str, Any] = {"feature_dir": feature_dir, "policy_metadata": {"agent": "claude"}, "repo_root": feature_dir}

        baseline = _prepare(feature_dir, _request(**request_kwargs), Lane.PLANNED, at="2026-01-01T00:00:00+00:00")
        with_probe_finding_nothing = _prepare(
            feature_dir,
            _request(**request_kwargs),
            Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            lane_head_probe=lambda **_: None,
        )
        assert baseline.event is not None
        assert with_probe_finding_nothing.event is not None
        assert baseline.event.to_dict() == with_probe_finding_nothing.event.to_dict()

    def test_request_repo_root_is_preferred_over_the_repo_root_kwarg(self, feature_dir: Path) -> None:
        calls: list[Path] = []

        def fake_probe(*, repo_root: Path, mission_slug: str, wp_id: str) -> str | None:
            calls.append(repo_root)
            return None

        request_root = feature_dir / "request-root"
        kwarg_root = feature_dir / "kwarg-root"
        _prepare(
            feature_dir,
            _request(feature_dir=feature_dir, repo_root=request_root),
            Lane.PLANNED,
            lane_head_probe=fake_probe,
            repo_root=kwarg_root,
        )
        assert calls == [request_root]

    def test_repo_root_kwarg_is_the_fallback_when_request_repo_root_is_none(self, feature_dir: Path) -> None:
        calls: list[Path | None] = []

        def fake_probe(*, repo_root: Path, mission_slug: str, wp_id: str) -> str | None:
            calls.append(repo_root)
            return None

        kwarg_root = feature_dir / "kwarg-root"
        _prepare(
            feature_dir,
            _request(feature_dir=feature_dir, repo_root=None),
            Lane.PLANNED,
            lane_head_probe=fake_probe,
            repo_root=kwarg_root,
        )
        assert calls == [kwarg_root]

    def test_probe_not_called_when_no_repo_root_is_available(self, feature_dir: Path) -> None:
        calls: list[Path] = []

        def fake_probe(*, repo_root: Path, mission_slug: str, wp_id: str) -> str | None:
            calls.append(repo_root)
            return "deadbeef" * 5

        prepared = _prepare(
            feature_dir,
            _request(feature_dir=feature_dir, repo_root=None, policy_metadata={"agent": "claude"}),
            Lane.PLANNED,
            lane_head_probe=fake_probe,
            repo_root=None,
        )
        assert calls == []
        assert prepared.event is not None
        assert prepared.event.policy_metadata == {"agent": "claude"}
