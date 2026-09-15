"""Dependency readiness guard inside the FSM (mission fsm-write-path-integrity, WP04).

Spec US4, FR-012..FR-014, C-004, C-005, NFR-002, NFR-004; contract
``contracts/dependency-guard.md``; data-model §6; decision Q8
(``01M1V8HVDQH36X06JDK22SZV02``, fail-OPEN on ``None``).
"""

from __future__ import annotations

import ast
import json
import logging
import subprocess
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import specify_cli.coordination.status_transition as status_transition_module
import specify_cli.status.emit as emit_module
import specify_cli.status.reducer as reducer_module
import specify_cli.status.transition_pipeline as pipeline_module
from specify_cli.coordination.status_service import EventLogWriteContract, append_event_log
from specify_cli.coordination.status_transition import (
    emit_status_transition_batch_transactional,
    emit_status_transition_transactional,
)
from specify_cli.core.dependency_graph import DependencyReadiness, parse_wp_dependencies
from specify_cli.lanes.recovery import RECOVERY_ACTOR
from specify_cli.lanes.recovery import _get_recovery_transitions
from specify_cli.status.dependency_verdict import UNRESOLVABLE_MARKER, readiness_from_snapshot, wp_lanes_from_snapshot
from specify_cli.status.emit import TransitionError, emit_status_transition, emit_status_transition_batch
from specify_cli.status.locking import feature_status_lock
from specify_cli.status.models import GuardContext, Lane, StatusEvent, StatusSnapshot, TransitionRequest
from specify_cli.status.reducer import reduce
from specify_cli.status.store import append_event, read_events
from specify_cli.status.transition_context import TransitionContext
from specify_cli.status.transition_pipeline import prepare_transition
from specify_cli.status.transitions import validate_transition
from specify_cli.status.validate import validate_transition_legality
from specify_cli.status.wp_metadata import WPMetadata
from specify_cli.status.wp_state import wp_state_for
from tests.status.conftest import seed_wp_to_planned

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "test-feature"


@pytest.fixture(autouse=True)
def _no_fan_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(emit_module, "_saas_fan_out", lambda *args, **kwargs: None)
    monkeypatch.setattr(emit_module, "_resolved_binding_fan_out", lambda *args, **kwargs: None)


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    fd = tmp_path / "kitty-specs" / _SLUG
    fd.mkdir(parents=True)
    return fd


def _write_wp(feature_dir: Path, wp_id: str, dependencies: tuple[str, ...] = ()) -> Path:
    """Author a WP prompt file on the planning surface with its declared dependencies."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    deps = "[" + ", ".join(dependencies) + "]"
    wp_file = tasks_dir / f"{wp_id}-slug.md"
    wp_file.write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\ndependencies: {deps}\nsubtasks: []\n---\n\n# {wp_id}\n",
        encoding="utf-8",
    )
    return wp_file


def _write_wp_raw(feature_dir: Path, wp_id: str, frontmatter: str) -> Path:
    """Author a WP prompt file with verbatim frontmatter (legacy / corrupt shapes)."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    wp_file = tasks_dir / f"{wp_id}-slug.md"
    wp_file.write_text(frontmatter + f"\n# {wp_id}\n", encoding="utf-8")
    return wp_file


_CORRUPT_FRONTMATTER = "---\nwork_package_id: WP02\n"  # no closing fence


_COUNTER = {"n": 0}


def _event(wp_id: str, from_lane: Lane, to_lane: Lane, **overrides: Any) -> StatusEvent:
    _COUNTER["n"] += 1
    fields: dict[str, Any] = {
        "event_id": f"01DEPGUARD{_COUNTER['n']:016d}",
        "mission_slug": _SLUG,
        "wp_id": wp_id,
        "from_lane": from_lane,
        "to_lane": to_lane,
        # Monotonic across the whole module: the reducer orders by ``(at, event_id)``
        # (reducer.py), so a wrapping seconds-only stamp would reorder a chain.
        "at": f"2026-01-01T{_COUNTER['n'] // 3600 % 24:02d}:{_COUNTER['n'] // 60 % 60:02d}:{_COUNTER['n'] % 60:02d}+00:00",
        "actor": "seed",
        "force": False,
        "execution_mode": "worktree",
    }
    fields.update(overrides)
    return StatusEvent(**fields)


def _advance(feature_dir: Path, wp_id: str, *lanes: Lane, **overrides: Any) -> None:
    """Append lane hops directly to the log (no pipeline, no guard) from ``planned``."""
    from_lane = Lane.PLANNED
    for lane in lanes:
        append_event(feature_dir, _event(wp_id, from_lane, lane, **overrides))
        from_lane = lane


def _claim_request(feature_dir: Path, wp_id: str, **overrides: Any) -> TransitionRequest:
    base: dict[str, Any] = {
        "feature_dir": feature_dir,
        "mission_slug": _SLUG,
        "wp_id": wp_id,
        "to_lane": "claimed",
        "actor": "agent-1",
    }
    base.update(overrides)
    return TransitionRequest(**base)


def _dependent_pair(feature_dir: Path, *dep_lanes: Lane, **dep_overrides: Any) -> None:
    """WP01 advanced through ``dep_lanes``; WP02 planned and declaring ``dependencies: [WP01]``."""
    _write_wp(feature_dir, "WP01")
    _write_wp(feature_dir, "WP02", dependencies=("WP01",))
    seed_wp_to_planned(feature_dir, "WP01", slug=_SLUG)
    seed_wp_to_planned(feature_dir, "WP02", slug=_SLUG)
    if dep_lanes:
        _advance(feature_dir, "WP01", *dep_lanes, **dep_overrides)


# ── T020: RED-first — a verdict-less shell claim of a dep-blocked WP ─────────


def test_flat_shell_refuses_verdictless_claim_of_dep_blocked_wp(feature_dir: Path) -> None:
    """SC-005 repro: WP01 ``in_progress``, WP02 declares ``dependencies: [WP01]``.

    A direct ``emit_status_transition`` for ``planned -> claimed`` on WP02, with
    no readiness supplied by the caller, succeeds on the base. After WP04 the
    flat shell resolves readiness in-lock (FR-013) and the claim is refused.
    """
    _dependent_pair(feature_dir, Lane.CLAIMED, Lane.IN_PROGRESS)

    with pytest.raises(TransitionError, match="unsatisfied dependencies"):
        emit_status_transition(_claim_request(feature_dir, "WP02"))


# ── T021: the tri-state field and the guard clause (FR-012, C-004) ────────────


class TestGuardPolarity:
    """Contract §2 polarity table: fail-OPEN on ``None``, refuse only on ``False``."""

    @pytest.mark.parametrize("edge", [("planned", "claimed"), ("claimed", "in_progress")])
    def test_false_refuses_both_entry_edges(self, edge: tuple[str, str]) -> None:
        ok, err = validate_transition(*edge, GuardContext(actor="a", workspace_context="worktree", dependency_ready=False))
        assert ok is False
        assert err == f"Transition {edge[0]} -> {edge[1]} blocked: unsatisfied dependencies (force with reason to override)"

    @pytest.mark.parametrize("edge", [("planned", "claimed"), ("claimed", "in_progress")])
    @pytest.mark.parametrize("verdict", [True, None])
    def test_true_and_none_pass_both_entry_edges(self, edge: tuple[str, str], verdict: bool | None) -> None:
        ok, _ = validate_transition(*edge, GuardContext(actor="a", workspace_context="worktree", dependency_ready=verdict))
        assert ok is True

    @pytest.mark.parametrize(
        ("edge", "ctx"),
        [
            (("in_progress", "for_review"), GuardContext(actor="a", subtasks_complete=True, implementation_evidence_present=True, dependency_ready=False)),
            (("for_review", "in_review"), GuardContext(actor="a", dependency_ready=False)),
            (("planned", "blocked"), GuardContext(actor="a", reason="r", dependency_ready=False)),
            (("claimed", "canceled"), GuardContext(actor="a", reason="r", dependency_ready=False)),
        ],
    )
    def test_other_edges_ignore_the_field(self, edge: tuple[str, str], ctx: GuardContext) -> None:
        ok, err = validate_transition(*edge, ctx)
        assert ok is True, err

    def test_default_is_none(self) -> None:
        assert GuardContext().dependency_ready is None
        assert TransitionContext(actor="a").dependency_ready is None

    def test_guard_never_consults_force_itself(self) -> None:
        """Force is handled once at ``check_transition``; the guard alone still refuses."""
        state = wp_state_for(Lane.PLANNED)
        ctx = GuardContext(actor="a", reason="override", force=True, dependency_ready=False)
        assert state.can_transition_to(Lane.CLAIMED, ctx) is False
        assert state.guard_for(Lane.CLAIMED, ctx)[0] is False
        assert state.check_transition(Lane.CLAIMED, ctx) == (True, None)

    def test_force_bypass_requires_actor_and_reason(self) -> None:
        ok, _ = validate_transition("planned", "claimed", GuardContext(actor="a", force=True, dependency_ready=False))
        assert ok is False
        ok, _ = validate_transition("planned", "claimed", GuardContext(actor="a", reason="r", force=True, dependency_ready=False))
        assert ok is True


# ── T024 step 1: the two probe sites keep passing with no verdict (C-004) ─────


class TestProbeSitesFailOpen:
    def test_recovery_progression_probe_shape(self) -> None:
        """``lanes/recovery.py`` builds a bare context on exactly the guarded edges."""
        for edge in (("planned", "claimed"), ("claimed", "in_progress")):
            ok, err = validate_transition(*edge, GuardContext(actor=RECOVERY_ACTOR, workspace_context="recovery"))
            assert ok is True, err

    def test_recovery_progression_function_reaches_the_ceiling(self) -> None:
        assert _get_recovery_transitions(Lane.PLANNED) == [Lane.CLAIMED, Lane.IN_PROGRESS]

    def test_backward_edge_probe_shape_unchanged(self) -> None:
        """``tasks_transition_core.py``'s force-free backward-edge probe (FR-015)."""
        ctx = GuardContext(reason="rewind", review_ref=None, review_result=None)
        assert validate_transition("in_progress", "planned", ctx) == (True, None)
        assert validate_transition("claimed", "planned", ctx)[0] is False  # no such edge: unchanged


# ── T023: the pipeline threads the verdict (FR-013 consumer) ──────────────────


def _readiness(*unsatisfied: str) -> DependencyReadiness:
    return DependencyReadiness(wp_id="WP02", dependencies=("WP01",), unsatisfied=tuple(unsatisfied))


class TestPipelineThreadsReadiness:
    def test_unsatisfied_verdict_refuses_planned_to_claimed(self, feature_dir: Path) -> None:
        with pytest.raises(TransitionError, match="unsatisfied dependencies"):
            prepare_transition(
                request=_claim_request(feature_dir, "WP02"),
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                mission_id=None,
                from_lane="planned",
                readiness=_readiness("WP01"),
            )

    def test_satisfied_verdict_builds_the_event(self, feature_dir: Path) -> None:
        prepared = prepare_transition(
            request=_claim_request(feature_dir, "WP02"),
            feature_dir=feature_dir,
            mission_slug=_SLUG,
            mission_id=None,
            from_lane="planned",
            readiness=_readiness(),
        )
        assert prepared.event is not None
        assert prepared.event.to_lane == Lane.CLAIMED

    def test_guard_context_receives_the_verdict(self, feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: list[GuardContext] = []
        real = pipeline_module.validate_transition

        def spy(from_lane: str, to_lane: str, ctx: GuardContext) -> tuple[bool, str | None]:
            seen.append(ctx)
            return real(from_lane, to_lane, ctx)

        monkeypatch.setattr(pipeline_module, "validate_transition", spy)
        kwargs: dict[str, Any] = {
            "request": _claim_request(feature_dir, "WP02"),
            "feature_dir": feature_dir,
            "mission_slug": _SLUG,
            "mission_id": None,
            "from_lane": "planned",
        }
        prepare_transition(readiness=_readiness(), **kwargs)
        prepare_transition(readiness=None, **kwargs)
        with pytest.raises(TransitionError):
            prepare_transition(readiness=_readiness("WP01"), **kwargs)
        assert [ctx.dependency_ready for ctx in seen] == [True, None, False]


# ── T022: the pure verdict helper and the shells' declared-deps read ──────────


class TestVerdictHelpers:
    def test_readiness_from_snapshot_no_declared_deps_is_a_satisfied_verdict(self, feature_dir: Path) -> None:
        _dependent_pair(feature_dir)
        snapshot = reduce(read_events(feature_dir))
        verdict = readiness_from_snapshot(snapshot, "WP01", ())
        assert verdict is not None
        assert verdict.satisfied is True
        assert verdict.dependencies == ()

    def test_wp_lanes_from_snapshot_reports_lane_less_state_as_genesis(self) -> None:
        snapshot = StatusSnapshot(
            mission_slug=_SLUG,
            materialized_at="2026-01-01T00:00:00+00:00",
            event_count=0,
            last_event_id=None,
            work_packages={"WP01": {"actor": "x"}, "WP02": {"lane": "approved"}},
            summary={},
        )
        assert wp_lanes_from_snapshot(snapshot) == {"WP01": "genesis", "WP02": "approved"}

    def test_declared_dependencies_missing_file_declares_nothing(self, feature_dir: Path) -> None:
        assert emit_module._declared_dependencies(feature_dir, "WP09") == ()

    def test_declared_dependencies_ambiguous_match_fails_closed(self, feature_dir: Path) -> None:
        """Case (b): a stale rename leftover (two files matching WP03) is NOT 'no declarations'.

        ``_find_wp_file`` returns ``None`` for both zero-match (a) and
        multi-match (b); case (a) must stay an empty tuple, but case (b) means
        the declarations are unresolvable, not absent, and must fail closed.
        """
        tasks = feature_dir / "tasks"
        tasks.mkdir()
        (tasks / "WP03.md").write_text(
            "---\nwork_package_id: WP03\ntitle: Run-state persistence\ndependencies: [WP02]\nsubtasks: []\n---\n\n# WP03\n",
            encoding="utf-8",
        )
        (tasks / "WP03-run-state.md").write_text(
            "---\nwork_package_id: WP03\ntitle: Run-state persistence (renamed)\ndependencies: [WP02]\nsubtasks: []\n---\n\n# WP03\n",
            encoding="utf-8",
        )
        with pytest.raises(TransitionError, match="ambiguous"):
            emit_module._declared_dependencies(feature_dir, "WP03")

    def test_declared_dependencies_reads_only_the_dependencies_key(self, feature_dir: Path) -> None:
        tasks = feature_dir / "tasks"
        tasks.mkdir()
        # A file whose other fields would fail whole-model validation still yields its deps.
        (tasks / "WP02-x.md").write_text("---\nwork_package_id: not-a-wp-id\ndependencies: [WP01, ' WP03 ']\nestimated_lines: 12\n---\nbody\n", encoding="utf-8")
        assert emit_module._declared_dependencies(feature_dir, "WP02") == ("WP01", "WP03")

    def test_declared_dependencies_absent_key_declares_nothing(self, feature_dir: Path) -> None:
        tasks = feature_dir / "tasks"
        tasks.mkdir()
        (tasks / "WP02.md").write_text("---\nwork_package_id: WP02\n---\nbody\n", encoding="utf-8")
        assert emit_module._declared_dependencies(feature_dir, "WP02") == ()

    def test_declared_dependencies_unparseable_frontmatter_fails_closed(self, feature_dir: Path) -> None:
        tasks = feature_dir / "tasks"
        tasks.mkdir()
        (tasks / "WP02.md").write_text("---\nwork_package_id: WP02\n", encoding="utf-8")  # no closing fence
        with pytest.raises(TransitionError, match="unreadable"):
            emit_module._declared_dependencies(feature_dir, "WP02")

    @pytest.mark.parametrize("raw", [3, [1, 2], {"a": 1}])
    def test_malformed_dependencies_value_fails_closed(self, raw: object, feature_dir: Path) -> None:
        """Only a value ``WPMetadata`` would also refuse stays fail-closed."""
        with pytest.raises(TransitionError, match="malformed"):
            emit_module._coerce_declared_dependencies(raw, wp_id="WP02", wp_file=feature_dir / "tasks" / "WP02.md")
        with pytest.raises(ValidationError):
            WPMetadata.model_validate({"work_package_id": "WP02", "dependencies": raw})

    # Review cycle 1, finding 1: the legacy string forms WPMetadata coerces.
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("[]", ()), ("WP01, WP02", ("WP01", "WP02")), ("WP01", ("WP01",)), ("  WP03 ,WP04  ", ("WP03", "WP04"))],
    )
    def test_legacy_string_dependencies_coerce_like_wpmetadata(self, raw: str, expected: tuple[str, ...], feature_dir: Path) -> None:
        assert emit_module._coerce_declared_dependencies(raw, wp_id="WP02", wp_file=feature_dir / "tasks" / "WP02.md") == expected

    @pytest.mark.parametrize(
        ("yaml_value", "expected"),
        [('"[]"', ()), ('"WP01, WP02"', ("WP01", "WP02")), ("WP01", ("WP01",))],
    )
    def test_declared_dependencies_agree_with_the_pre_flight_parser(self, yaml_value: str, expected: tuple[str, ...], feature_dir: Path) -> None:
        """Single canonical parser (FR-014): the shell reads exactly what ``parse_wp_dependencies`` reads."""
        wp_file = _write_wp_raw(feature_dir, "WP02", f"---\nwork_package_id: WP02\ntitle: WP02\ndependencies: {yaml_value}\n---\n")
        assert emit_module._declared_dependencies(feature_dir, "WP02") == expected
        assert tuple(parse_wp_dependencies(wp_file)) == expected

    # Review cycle 1, finding 2 (shape b): an unresolvable file is a verdict, not an error.
    def test_resolve_dependency_readiness_unresolvable_file_is_an_unsatisfied_verdict(self, feature_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
        _write_wp_raw(feature_dir, "WP02", _CORRUPT_FRONTMATTER)
        seed_wp_to_planned(feature_dir, "WP02", slug=_SLUG)
        snapshot = reduce(read_events(feature_dir))
        with caplog.at_level(logging.WARNING, logger=emit_module.__name__):
            verdict = emit_module._resolve_dependency_readiness(feature_dir, "WP02", snapshot)
        assert verdict.satisfied is False
        assert verdict.dependencies == ()
        assert len(verdict.unsatisfied) == 1 and verdict.unsatisfied[0].startswith(UNRESOLVABLE_MARKER)
        assert "unreadable" in verdict.unsatisfied[0]
        assert any("unresolvable" in record.getMessage() for record in caplog.records)

    def test_resolve_dependency_readiness_never_returns_none(self, feature_dir: Path) -> None:
        _dependent_pair(feature_dir, Lane.CLAIMED, Lane.IN_PROGRESS)
        snapshot = reduce(read_events(feature_dir))
        blocked = emit_module._resolve_dependency_readiness(feature_dir, "WP02", snapshot)
        free = emit_module._resolve_dependency_readiness(feature_dir, "WP01", snapshot)
        assert blocked.satisfied is False and blocked.unsatisfied == ("WP01",)
        assert free.satisfied is True

    def test_derive_from_lane_with_supplied_snapshot_does_not_read_the_log(self, feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _dependent_pair(feature_dir, Lane.CLAIMED)
        snapshot = reduce(read_events(feature_dir))
        monkeypatch.setattr(emit_module._store, "read_events", lambda *a, **k: pytest.fail("second full-log read"))
        assert emit_module._derive_from_lane(feature_dir, "WP01", snapshot=snapshot) == str(Lane.CLAIMED)
        assert emit_module._derive_from_lane(feature_dir, "WP09", snapshot=snapshot) == str(Lane.GENESIS)


# ── Review cycle 1: legacy-string and corrupt WP files through the flat shell ──


class TestLegacyAndCorruptWpFiles:
    def test_legacy_empty_string_dependencies_can_be_claimed(self, feature_dir: Path) -> None:
        """Finding 1: ``dependencies: "[]"`` (three live 062-* WP files) is claimable."""
        _write_wp_raw(feature_dir, "WP02", '---\nwork_package_id: WP02\ntitle: WP02\ndependencies: "[]"\nsubtasks: []\n---\n')
        seed_wp_to_planned(feature_dir, "WP02", slug=_SLUG)
        assert emit_status_transition(_claim_request(feature_dir, "WP02")).to_lane == Lane.CLAIMED

    def test_bare_scalar_dependency_is_honoured_when_the_dep_is_approved(self, feature_dir: Path) -> None:
        _write_wp(feature_dir, "WP01")
        _write_wp_raw(feature_dir, "WP02", "---\nwork_package_id: WP02\ntitle: WP02\ndependencies: WP01\n---\n")
        seed_wp_to_planned(feature_dir, "WP01", slug=_SLUG)
        seed_wp_to_planned(feature_dir, "WP02", slug=_SLUG)
        _advance(feature_dir, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW, Lane.APPROVED)
        assert emit_status_transition(_claim_request(feature_dir, "WP02")).to_lane == Lane.CLAIMED

    def test_bare_scalar_dependency_still_gates_when_the_dep_is_in_flight(self, feature_dir: Path) -> None:
        """The coercion is load-bearing: a bare ``WP01`` is a real dependency, not noise."""
        _write_wp(feature_dir, "WP01")
        _write_wp_raw(feature_dir, "WP02", "---\nwork_package_id: WP02\ntitle: WP02\ndependencies: WP01\n---\n")
        seed_wp_to_planned(feature_dir, "WP01", slug=_SLUG)
        seed_wp_to_planned(feature_dir, "WP02", slug=_SLUG)
        _advance(feature_dir, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS)
        with pytest.raises(TransitionError, match="planned -> claimed blocked"):
            emit_status_transition(_claim_request(feature_dir, "WP02"))

    def test_corrupt_frontmatter_refuses_the_entry_edge_without_force(self, feature_dir: Path) -> None:
        _write_wp_raw(feature_dir, "WP02", _CORRUPT_FRONTMATTER)
        seed_wp_to_planned(feature_dir, "WP02", slug=_SLUG)
        before = len(read_events(feature_dir))
        with pytest.raises(TransitionError, match="planned -> claimed blocked: unsatisfied dependencies"):
            emit_status_transition(_claim_request(feature_dir, "WP02"))
        assert len(read_events(feature_dir)) == before

    def test_corrupt_frontmatter_entry_edge_is_force_bypassable(self, feature_dir: Path) -> None:
        _write_wp_raw(feature_dir, "WP02", _CORRUPT_FRONTMATTER)
        seed_wp_to_planned(feature_dir, "WP02", slug=_SLUG)
        event = emit_status_transition(_claim_request(feature_dir, "WP02", force=True, reason="operator: WP file corrupt, claiming anyway"))
        assert event.force is True and event.to_lane == Lane.CLAIMED

    def test_corrupt_frontmatter_never_affects_non_guarded_edges(self, feature_dir: Path) -> None:
        """Finding 2: ``-> blocked`` and a forced ``-> canceled`` still work on a corrupt WP file."""
        _write_wp_raw(feature_dir, "WP02", _CORRUPT_FRONTMATTER)
        seed_wp_to_planned(feature_dir, "WP02", slug=_SLUG)
        blocked = emit_status_transition(_claim_request(feature_dir, "WP02", to_lane="blocked", reason="waiting on operator"))
        assert blocked.to_lane == Lane.BLOCKED
        canceled = emit_status_transition(_claim_request(feature_dir, "WP02", to_lane="canceled", force=True, reason="operator: abandon"))
        assert canceled.to_lane == Lane.CANCELED
        assert reduce(read_events(feature_dir)).work_packages["WP02"]["lane"] == Lane.CANCELED


# ── Ambiguous WP file: a rename leftover must fail CLOSED like the unreadable case ──


class TestAmbiguousWpFileDependencyGuard:
    """``tasks/WP03.md`` renamed to ``tasks/WP03-run-state.md`` with the old file left behind.

    Both match the ``WP03`` pattern, so ``_find_wp_file`` cannot resolve one
    canonical file (case (b), distinct from the genuinely-absent case (a) at
    :308). The declared dependencies are unresolvable, not empty, so this
    must refuse the guarded entry edges exactly like an unreadable WP file
    does (``force`` + actor + reason still bypasses; non-guarded edges are
    unaffected).
    """

    @staticmethod
    def _seed_ambiguous_wp03(feature_dir: Path) -> None:
        _write_wp(feature_dir, "WP02")
        tasks = feature_dir / "tasks"
        for name in ("WP03.md", "WP03-run-state.md"):
            (tasks / name).write_text(
                "---\nwork_package_id: WP03\ntitle: Run-state persistence\ndependencies: [WP02]\nsubtasks: []\n---\n\n# WP03\n",
                encoding="utf-8",
            )
        seed_wp_to_planned(feature_dir, "WP02", slug=_SLUG)
        seed_wp_to_planned(feature_dir, "WP03", slug=_SLUG)
        _advance(feature_dir, "WP02", Lane.CLAIMED, Lane.IN_PROGRESS)  # WP02 unfinished

    def test_ambiguous_wp_file_refuses_planned_to_claimed(self, feature_dir: Path) -> None:
        self._seed_ambiguous_wp03(feature_dir)
        before = len(read_events(feature_dir))
        with pytest.raises(TransitionError, match="planned -> claimed blocked: unsatisfied dependencies"):
            emit_status_transition(_claim_request(feature_dir, "WP03"))
        assert len(read_events(feature_dir)) == before

    def test_ambiguous_wp_file_refuses_claimed_to_in_progress(self, feature_dir: Path) -> None:
        self._seed_ambiguous_wp03(feature_dir)
        _advance(feature_dir, "WP03", Lane.CLAIMED)  # a claim that predates the rename leftover
        with pytest.raises(TransitionError, match="claimed -> in_progress blocked"):
            emit_status_transition(_claim_request(feature_dir, "WP03", to_lane="in_progress", workspace_context="worktree:/x"))

    def test_ambiguous_wp_file_entry_edge_is_force_bypassable(self, feature_dir: Path) -> None:
        self._seed_ambiguous_wp03(feature_dir)
        event = emit_status_transition(_claim_request(feature_dir, "WP03", force=True, reason="operator: rename leftover, claiming anyway"))
        assert event.force is True and event.to_lane == Lane.CLAIMED

    def test_ambiguous_wp_file_never_affects_non_guarded_edges(self, feature_dir: Path) -> None:
        self._seed_ambiguous_wp03(feature_dir)
        blocked = emit_status_transition(_claim_request(feature_dir, "WP03", to_lane="blocked", reason="waiting on operator"))
        assert blocked.to_lane == Lane.BLOCKED
        canceled = emit_status_transition(_claim_request(feature_dir, "WP03", to_lane="canceled", force=True, reason="operator: abandon"))
        assert canceled.to_lane == Lane.CANCELED

    def test_ambiguous_wp_file_verdict_carries_the_unresolvable_marker(self, feature_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
        self._seed_ambiguous_wp03(feature_dir)
        snapshot = reduce(read_events(feature_dir))
        with caplog.at_level(logging.WARNING, logger=emit_module.__name__):
            verdict = emit_module._resolve_dependency_readiness(feature_dir, "WP03", snapshot)
        assert verdict.satisfied is False
        assert verdict.dependencies == ()
        assert len(verdict.unsatisfied) == 1 and verdict.unsatisfied[0].startswith(UNRESOLVABLE_MARKER)
        assert "ambiguous" in verdict.unsatisfied[0]
        assert any("ambiguous" in record.getMessage() for record in caplog.records)

    def test_unambiguous_zero_match_case_a_stays_satisfied(self, feature_dir: Path) -> None:
        """Case (a), genuinely no file, is unaffected by the case-(b) fix (pin at :308)."""
        _write_wp(feature_dir, "WP02")
        seed_wp_to_planned(feature_dir, "WP02", slug=_SLUG)
        seed_wp_to_planned(feature_dir, "WP03", slug=_SLUG)  # WP03 has no prompt file at all
        assert emit_status_transition(_claim_request(feature_dir, "WP03")).to_lane == Lane.CLAIMED


# ── T024 step 2: the same-mission chain matrix through the flat shell ─────────


class TestChainMatrix:
    def test_dep_approved_allows_the_claim(self, feature_dir: Path) -> None:
        _dependent_pair(feature_dir, Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.APPROVED)
        event = emit_status_transition(_claim_request(feature_dir, "WP02"))
        assert event.to_lane == Lane.CLAIMED

    def test_dep_done_allows_the_claim(self, feature_dir: Path) -> None:
        _dependent_pair(feature_dir, Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.APPROVED, Lane.DONE)
        assert emit_status_transition(_claim_request(feature_dir, "WP02")).to_lane == Lane.CLAIMED

    def test_dep_canceled_with_operator_provenance_allows_the_claim(self, feature_dir: Path) -> None:
        _dependent_pair(feature_dir, Lane.CANCELED, reason="descoped by operator", reason_source="operator", actor="operator")
        assert emit_status_transition(_claim_request(feature_dir, "WP02")).to_lane == Lane.CLAIMED

    def test_dep_canceled_without_provenance_blocks_the_claim(self, feature_dir: Path) -> None:
        _dependent_pair(feature_dir, Lane.CANCELED, reason="auto", reason_source="synthetic")
        with pytest.raises(TransitionError, match="unsatisfied dependencies"):
            emit_status_transition(_claim_request(feature_dir, "WP02"))

    @pytest.mark.parametrize("dep_lanes", [(Lane.CLAIMED, Lane.IN_PROGRESS), (Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW)])
    def test_dep_in_flight_blocks_the_claim_and_persists_nothing(self, feature_dir: Path, dep_lanes: tuple[Lane, ...]) -> None:
        _dependent_pair(feature_dir, *dep_lanes)
        before = len(read_events(feature_dir))
        with pytest.raises(TransitionError, match="unsatisfied dependencies"):
            emit_status_transition(_claim_request(feature_dir, "WP02"))
        assert len(read_events(feature_dir)) == before
        assert reduce(read_events(feature_dir)).work_packages["WP02"]["lane"] == Lane.PLANNED

    def test_claimed_to_in_progress_is_gated_too(self, feature_dir: Path) -> None:
        _dependent_pair(feature_dir, Lane.CLAIMED, Lane.IN_PROGRESS)
        _advance(feature_dir, "WP02", Lane.CLAIMED)  # a claim that predates the dep's regression
        with pytest.raises(TransitionError, match="claimed -> in_progress blocked"):
            emit_status_transition(_claim_request(feature_dir, "WP02", to_lane="in_progress", workspace_context="worktree:/x"))

    def test_force_with_actor_and_reason_bypasses_and_is_recorded(self, feature_dir: Path) -> None:
        _dependent_pair(feature_dir, Lane.CLAIMED, Lane.IN_PROGRESS)
        event = emit_status_transition(_claim_request(feature_dir, "WP02", force=True, reason="operator override: parallel lane"))
        assert event.force is True
        assert event.reason == "operator override: parallel lane"
        assert reduce(read_events(feature_dir)).work_packages["WP02"]["lane"] == Lane.CLAIMED

    def test_force_without_reason_is_still_refused(self, feature_dir: Path) -> None:
        _dependent_pair(feature_dir, Lane.CLAIMED, Lane.IN_PROGRESS)
        with pytest.raises(TransitionError):
            emit_status_transition(_claim_request(feature_dir, "WP02", force=True))

    def test_wp_without_declared_deps_is_unaffected(self, feature_dir: Path) -> None:
        _dependent_pair(feature_dir, Lane.CLAIMED, Lane.IN_PROGRESS)
        _write_wp(feature_dir, "WP03")
        seed_wp_to_planned(feature_dir, "WP03", slug=_SLUG)
        assert emit_status_transition(_claim_request(feature_dir, "WP03")).to_lane == Lane.CLAIMED

    def test_batch_shell_is_gated_and_all_or_nothing(self, feature_dir: Path) -> None:
        _dependent_pair(feature_dir, Lane.CLAIMED, Lane.IN_PROGRESS)
        before = len(read_events(feature_dir))
        with pytest.raises(TransitionError, match="unsatisfied dependencies"):
            emit_status_transition_batch(
                [
                    _claim_request(feature_dir, "WP02"),
                    _claim_request(feature_dir, "WP02", to_lane="in_progress", workspace_context="worktree:/x"),
                ]
            )
        assert len(read_events(feature_dir)) == before

    def test_batch_shell_allows_the_start_sequence_when_dep_is_approved(self, feature_dir: Path) -> None:
        _dependent_pair(feature_dir, Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.APPROVED)
        events = emit_status_transition_batch(
            [
                _claim_request(feature_dir, "WP02"),
                _claim_request(feature_dir, "WP02", to_lane="in_progress", workspace_context="worktree:/x"),
            ]
        )
        assert [e.to_lane for e in events] == [Lane.CLAIMED, Lane.IN_PROGRESS]


# ── T024 step 4: pre-lock TOCTOU -- the verdict reflects the post-lock state ──


def test_verdict_reflects_state_written_by_a_writer_that_held_the_lock_first(feature_dir: Path) -> None:
    """A concurrent writer regresses the dependency while holding L1; the emitter
    that was waiting for the lock must see the regression and be refused."""
    _dependent_pair(feature_dir, Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.APPROVED)
    lock_root = emit_module._feature_status_lock_root(feature_dir, None)
    holder_has_lock = threading.Event()
    emitter_waiting = threading.Event()
    outcome: dict[str, Any] = {}

    def holder() -> None:
        with feature_status_lock(lock_root, feature_dir.name):
            holder_has_lock.set()
            assert emitter_waiting.wait(5)
            time.sleep(0.2)  # give the emitter time to block on the lock
            # The dependency regresses to in_progress while the lock is held.
            append_event(feature_dir, _event("WP01", Lane.APPROVED, Lane.IN_PROGRESS, force=True, reason="rework"))

    def emitter() -> None:
        emitter_waiting.set()
        try:
            outcome["event"] = emit_status_transition(_claim_request(feature_dir, "WP02"))
        except TransitionError as exc:
            outcome["error"] = str(exc)

    holder_thread = threading.Thread(target=holder)
    holder_thread.start()
    assert holder_has_lock.wait(5)
    emitter_thread = threading.Thread(target=emitter)
    emitter_thread.start()
    holder_thread.join(10)
    emitter_thread.join(10)
    assert not holder_thread.is_alive() and not emitter_thread.is_alive()

    assert "event" not in outcome, "pre-lock (stale) verdict was used"
    assert "unsatisfied dependencies" in outcome["error"]
    assert reduce(read_events(feature_dir)).work_packages["WP02"]["lane"] == Lane.PLANNED


# ── T024 step 5: replay purity (C-005 / NFR-002) ─────────────────────────────


class TestReplayPurity:
    def test_reducer_has_no_guard_references(self) -> None:
        tree = ast.parse(Path(reducer_module.__file__).read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                names.update(alias.name for alias in node.names)
                names.add(node.module or "")
        assert not names & {"validate_transition", "GuardContext", "dependency_ready", "dependency_readiness_for_wp", "readiness_from_snapshot"}, names
        assert not any(name.endswith(("wp_state", "transitions", "dependency_verdict", "transition_pipeline")) for name in names if "." in name), names

    def test_scan_is_non_vacuous(self) -> None:
        poisoned = ast.parse("from specify_cli.status.transitions import validate_transition\nGuardContext()\n")
        found = {n.id for n in ast.walk(poisoned) if isinstance(n, ast.Name)} | {
            a.name for n in ast.walk(poisoned) if isinstance(n, ast.ImportFrom) for a in n.names
        }
        assert {"validate_transition", "GuardContext"} <= found

    def test_now_dep_illegal_history_replays_and_audits_without_a_guard_finding(self, feature_dir: Path) -> None:
        # History: WP02 was claimed while WP01 was still in_progress (legal before WP04).
        _dependent_pair(feature_dir, Lane.CLAIMED, Lane.IN_PROGRESS)
        _advance(feature_dir, "WP02", Lane.CLAIMED, Lane.IN_PROGRESS)
        events = read_events(feature_dir)
        snapshot = reduce(events)
        assert snapshot.work_packages["WP02"]["lane"] == Lane.IN_PROGRESS
        assert snapshot.work_packages["WP01"]["lane"] == Lane.IN_PROGRESS
        findings = validate_transition_legality(
            [{"event_id": e.event_id, "from_lane": str(e.from_lane), "to_lane": str(e.to_lane), "at": e.at, "force": e.force, "wp_id": e.wp_id} for e in events]
        )
        assert findings == []
        # And the live guard would refuse the same claim today: the difference is the whole point.
        assert validate_transition("planned", "claimed", GuardContext(actor="a", dependency_ready=False))[0] is False


# ── T024 step 3: coordination topology -- the verdict follows txn.feature_dir ──


_COORD_SLUG = "dep-guard-coord"
_COORD_MID8 = "01KTDEP0"
_COORD_MISSION_ID = "01KTDEP0000000000000000000"
_COORD_DIRNAME = f"{_COORD_SLUG}-{_COORD_MID8}"
_COORD_BRANCH = f"kitty/mission-{_COORD_DIRNAME}"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _coord_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    primary = repo / "kitty-specs" / _COORD_DIRNAME
    primary.mkdir(parents=True)
    (primary / "meta.json").write_text(
        json.dumps({"mission_slug": _COORD_SLUG, "mission_id": _COORD_MISSION_ID, "mid8": _COORD_MID8, "coordination_branch": _COORD_BRANCH}) + "\n",
        encoding="utf-8",
    )
    _write_wp(primary, "WP01")
    _write_wp(primary, "WP02", dependencies=("WP01",))
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission")
    _git(repo, "branch", _COORD_BRANCH)
    return repo


def _coord_event(wp_id: str, from_lane: Lane, to_lane: Lane) -> StatusEvent:
    return _event(wp_id, from_lane, to_lane, mission_slug=_COORD_SLUG, mission_id=_COORD_MISSION_ID)


def _hops(wp_id: str, *lanes: Lane) -> list[StatusEvent]:
    events: list[StatusEvent] = []
    from_lane = Lane.GENESIS
    for lane in lanes:
        events.append(_coord_event(wp_id, from_lane, lane))
        from_lane = lane
    return events


def _seed_coord_surface(repo: Path, events: list[StatusEvent]) -> None:
    worktree = repo / ".worktrees" / "seed"
    _git(repo, "worktree", "add", "-q", str(worktree), _COORD_BRANCH)
    coord_feature_dir = worktree / "kitty-specs" / _COORD_DIRNAME
    for event in events:
        append_event_log(EventLogWriteContract.coordination_transaction_append(coord_feature_dir), event)
    _git(worktree, "add", "kitty-specs")
    _git(worktree, "commit", "-q", "-m", "seed coord status")
    _git(repo, "worktree", "remove", "-f", str(worktree))


def _seed_primary_surface(repo: Path, events: list[StatusEvent]) -> None:
    for event in events:
        append_event_log(EventLogWriteContract.primary_checkout_append(repo / "kitty-specs" / _COORD_DIRNAME), event)


def _coord_claim(repo: Path) -> TransitionRequest:
    return TransitionRequest(
        feature_dir=repo / "kitty-specs" / _COORD_DIRNAME, mission_slug=_COORD_SLUG, wp_id="WP02", to_lane="claimed", actor="agent-1", repo_root=repo
    )


_APPROVED_CHAIN = (Lane.PLANNED, Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.APPROVED)
_IN_PROGRESS_CHAIN = (Lane.PLANNED, Lane.CLAIMED, Lane.IN_PROGRESS)


@pytest.mark.git_repo
class TestCoordSurfaceResolution:
    """FR-013: the transactional shell resolves readiness against ``txn.feature_dir``
    (the coordination surface), never the stale primary planning dir."""

    def test_verdict_follows_coord_surface_when_primary_is_stale_blocked(self, tmp_path: Path) -> None:
        repo = _coord_repo(tmp_path)
        _seed_coord_surface(repo, _hops("WP01", *_APPROVED_CHAIN) + _hops("WP02", Lane.PLANNED))
        _seed_primary_surface(repo, _hops("WP01", *_IN_PROGRESS_CHAIN) + _hops("WP02", Lane.PLANNED))

        event = emit_status_transition_transactional(_coord_claim(repo))

        assert event.to_lane == Lane.CLAIMED
        assert event.wp_id == "WP02"

    def test_verdict_follows_coord_surface_when_primary_is_stale_approved(self, tmp_path: Path) -> None:
        repo = _coord_repo(tmp_path)
        _seed_coord_surface(repo, _hops("WP01", *_IN_PROGRESS_CHAIN) + _hops("WP02", Lane.PLANNED))
        _seed_primary_surface(repo, _hops("WP01", *_APPROVED_CHAIN) + _hops("WP02", Lane.PLANNED))

        with pytest.raises(TransitionError, match="unsatisfied dependencies"):
            emit_status_transition_transactional(_coord_claim(repo))

    def test_batch_door_follows_coord_surface_too(self, tmp_path: Path) -> None:
        repo = _coord_repo(tmp_path)
        _seed_coord_surface(repo, _hops("WP01", *_IN_PROGRESS_CHAIN) + _hops("WP02", Lane.PLANNED))
        _seed_primary_surface(repo, _hops("WP01", *_APPROVED_CHAIN) + _hops("WP02", Lane.PLANNED))

        with pytest.raises(TransitionError, match="unsatisfied dependencies"):
            emit_status_transition_batch_transactional([_coord_claim(repo)])

    def test_transactional_shell_resolves_readiness_inside_the_transaction(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Order pin: acquire -> reduce (one read) -> readiness -> prepare; no read before acquire."""
        repo = _coord_repo(tmp_path)
        _seed_coord_surface(repo, _hops("WP01", *_APPROVED_CHAIN) + _hops("WP02", Lane.PLANNED))
        observed: list[str] = []
        real_acquire = status_transition_module._acquire_status_transaction
        real_reduce = emit_module._reduce_write_surface
        real_readiness = emit_module._resolve_dependency_readiness
        real_read = emit_module._store.read_events
        surfaces: dict[str, Path] = {}

        @contextmanager
        def tracking_acquire(*args: Any, **kwargs: Any) -> Iterator[Any]:
            observed.append("acquire")
            with real_acquire(*args, **kwargs) as txn:
                surfaces["txn"] = txn.feature_dir
                yield txn
                observed.append("release")

        def tracking_reduce(feature_dir: Path) -> Any:
            observed.append("reduce")
            surfaces["reduced"] = feature_dir
            return real_reduce(feature_dir)

        def tracking_readiness(planning_dir: Path, wp_id: str, snapshot: Any) -> Any:
            observed.append("readiness")
            surfaces["planning"] = planning_dir
            return real_readiness(planning_dir, wp_id, snapshot)

        def counting_read(*args: Any, **kwargs: Any) -> Any:
            observed.append("read_events")
            return real_read(*args, **kwargs)

        monkeypatch.setattr(status_transition_module, "_acquire_status_transaction", tracking_acquire)
        monkeypatch.setattr(emit_module, "_reduce_write_surface", tracking_reduce)
        monkeypatch.setattr(emit_module, "_resolve_dependency_readiness", tracking_readiness)
        monkeypatch.setattr(emit_module._store, "read_events", counting_read)

        emit_status_transition_transactional(_coord_claim(repo))

        assert observed.index("acquire") < observed.index("reduce") < observed.index("readiness") < observed.index("release")
        assert observed[: observed.index("readiness")].count("read_events") == 1
        assert surfaces["reduced"] == surfaces["txn"]
        assert surfaces["txn"] != repo / "kitty-specs" / _COORD_DIRNAME  # the coord worktree, not primary
        assert surfaces["planning"] == repo / "kitty-specs" / _COORD_DIRNAME  # WP file read on primary


def test_flat_ad_hoc_directory_keeps_its_declared_dependencies(tmp_path: Path) -> None:
    """The flat door accepts an explicit mission dir outside kitty-specs in git."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    feature_dir = tmp_path / "ad-hoc"
    feature_dir.mkdir()
    _dependent_pair(feature_dir)
    with pytest.raises(TransitionError, match="unsatisfied dependencies"):
        emit_status_transition(_claim_request(feature_dir, "WP02"), ensure_sync_daemon=False)
