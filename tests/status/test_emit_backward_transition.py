"""Regression tests for the review-rejection backward-rewind fan-out path (issue #1141).

Scenario 4 of the identity-boundary canary drives a WP through the forward
lane chain (``planned → claimed → in_progress → for_review → in_review``)
and then triggers a forced backward ``in_review → planned`` rollback. Before
this fix the canary peek found the prior forward ``for_review → in_review``
row at the head of the offline queue instead of the rollback — i.e. the
backward emission appeared to be silently dropped/replaced.

These tests pin the contract at the layer this repo owns:

1. ``emit_status_transition`` fires ``fire_status_fanout`` exactly once per
   forward transition AND exactly once for a forced backward review-rejection
   transition (``in_review → planned``, ``force=True``).
2. The backward fan-out invocation carries the correct ``from_lane`` /
   ``to_lane`` / ``force`` values and is the most recent recorded call.
3. The full forward+backward sequence on a single WP produces exactly five
   fan-out invocations and the last one is the backward rollback.

If the canary failure recurs and these tests still pass, the regression is
downstream of ``fire_status_fanout`` (in ``emit_wp_status_changed`` →
``OfflineQueue.queue_event``) — the breadcrumb log added in
``src/specify_cli/status/adapters.py`` will then surface it in operator
logs. See ``kitty-specs/investigate-canary-followups-1142-1141-01KS02TV/
research/h1-evidence-1141.md`` for the bisect plan.

NB: this file MUST opt out of the autouse SaaS-fanout disabling fixture in
``tests/status/conftest.py`` — the contract under test IS the fan-out call.
``conftest.py`` skips that fixture for ``test_emit_fanout_after_adapter.py``
by filename; we extend that allowlist by overriding the fixture locally.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.status import adapters
from specify_cli.status import emit as _emit_module
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.models import TransitionRequest

pytestmark = pytest.mark.fast

# Capture the real ``_status_fan_out`` at import time, BEFORE pytest gets a
# chance to apply the conftest's autouse no-op patch. The fixture below
# rebinds the module attribute back to this captured reference for each
# test in this file.
_REAL_STATUS_FAN_OUT = _emit_module._status_fan_out


@pytest.fixture(autouse=True)
def _enable_status_fanout_for_this_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-enable real status fan-out routing for tests in this module.

    ``tests/status/conftest.py`` autouse-patches
    ``specify_cli.status.emit._status_fan_out`` to a no-op for every test in
    this directory except a single whitelisted filename. Without this
    override our registered handler would never fire and the assertions
    would pass vacuously. We restore the original ``_status_fan_out`` (the
    one that calls ``fire_status_fanout``) for the duration of every test in
    this file.
    """
    monkeypatch.setattr(_emit_module, "_status_fan_out", _REAL_STATUS_FAN_OUT)


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    fd = tmp_path / "kitty-specs" / "test-1141-feature"
    fd.mkdir(parents=True)
    return fd


def _drive_forward_chain(
    feature_dir: Path,
    *,
    wp_id: str,
    actor: str,
) -> None:
    """Walk a WP through the canonical forward lane chain via emit_status_transition.

    Mirrors the canary scenario 4 setup: ``planned → claimed → in_progress
    → for_review → in_review``. Each hop is a separate
    ``emit_status_transition`` call so the status fan-out fires once per
    transition (the canary uses ``spec-kitty agent tasks move-task`` for
    each lane individually, which has the same effect at the emit layer).
    """
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{wp_id}.md").write_text(
        f"---\nwork_package_id: {wp_id}\nsubtasks: []\n---\n\n# {wp_id}\n",
        encoding="utf-8",
    )
    # Seed the WP out of the non-display 'genesis' state into 'planned' by
    # writing the seed event directly to the log (no emit → no fan-out call),
    # so the fan-out counts below reflect only the forward lane chain.
    seed_event = {
        "event_id": "01HXYZ0123456789ABCDEFGS01",
        "mission_slug": "test-1141-feature",
        "wp_id": wp_id,
        "from_lane": "genesis",
        "to_lane": "planned",
        "at": "2026-06-01T12:00:00+00:00",
        "actor": "seed",
        "force": True,
        "execution_mode": "worktree",
        "evidence": None,
        "reason": "seed",
        "review_ref": None,
        "feature_slug": "test-1141-feature",
    }
    events_path = feature_dir / "status.events.jsonl"
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(seed_event) + "\n")
    # planned → claimed
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug="test-1141-feature",
            wp_id=wp_id,
            to_lane="claimed",
            actor=actor,
        )
    )
    # claimed → in_progress
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug="test-1141-feature",
            wp_id=wp_id,
            to_lane="in_progress",
            actor=actor,
        )
    )
    # in_progress → for_review (empty authored roster; evidence supplied)
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug="test-1141-feature",
            wp_id=wp_id,
            to_lane="for_review",
            actor=actor,
            implementation_evidence_present=True,
        )
    )
    # for_review → in_review (reviewer claims)
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug="test-1141-feature",
            wp_id=wp_id,
            to_lane="in_review",
            actor=actor,
        )
    )


class TestBackwardTransitionFanOut:
    """Backward (force-required) rollback fan-out reaches the registered handler."""

    def test_forced_in_review_to_planned_fires_fanout_once(
        self, feature_dir: Path
    ) -> None:
        """A forced backward ``in_review → planned`` must produce one fan-out call.

        Pin: the call carries ``force=True`` and the correct lane delta.
        """
        adapters.reset_handlers()
        captured: list[dict[str, Any]] = []

        def fake_saas(**kwargs: Any) -> None:
            captured.append(dict(kwargs))

        adapters.register_status_fanout_handler(fake_saas)

        try:
            _drive_forward_chain(
                feature_dir, wp_id="WP01", actor="canary-actor"
            )
            # Sanity: forward chain produced 4 fan-out calls.
            assert len(captured) == 4, (
                f"Forward chain should fan out 4 events; got {len(captured)}: "
                f"{[(c['from_lane'], c['to_lane'], c['metadata'].force) for c in captured]}"
            )

            # Trigger the backward rollback under test.
            from specify_cli.status.models import ReviewResult

            event = emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="test-1141-feature",
                    wp_id="WP01",
                    to_lane="planned",
                    actor="canary-actor",
                    force=True,
                    reason="backward rewind: in_review -> planned: review_rejected",
                    review_result=ReviewResult(
                        reviewer="canary-actor",
                        verdict="rejected",
                        reference="review-ref-1141",
                    ),
                )
            )
            assert event is not None

            # Fan-out fired one more time.
            assert len(captured) == 5, (
                "Backward rollback must produce exactly one additional fan-out "
                f"invocation; got {len(captured)} total calls"
            )

            backward_call = captured[-1]
            assert backward_call["wp_id"] == "WP01"
            assert backward_call["from_lane"] == "in_review", (
                f"Backward call from_lane is {backward_call['from_lane']!r}; "
                "expected 'in_review' (the WP's lane at the moment of rollback)."
            )
            assert backward_call["to_lane"] == "planned", (
                f"Backward call to_lane is {backward_call['to_lane']!r}; "
                "expected 'planned' (the rollback target)."
            )
            assert backward_call["metadata"].force is True, (
                "Backward review-rejection emit must carry force=True per the "
                "events-package contract."
            )
            assert backward_call["metadata"].reason, (
                "Backward review-rejection emit must carry a non-empty reason."
            )
        finally:
            adapters.reset_handlers()

    def test_full_sequence_last_fanout_is_backward_rollback(
        self, feature_dir: Path
    ) -> None:
        """End-to-end shape: forward × 4 then backward × 1; last fan-out is the rollback.

        Mirrors the canary peek expectation: the most recent ``WPStatusChanged``
        row for ``WP01`` is the ``in_review → planned`` rollback, not the
        prior forward hop.
        """
        adapters.reset_handlers()
        captured: list[dict[str, Any]] = []

        def fake_saas(**kwargs: Any) -> None:
            captured.append(dict(kwargs))

        adapters.register_status_fanout_handler(fake_saas)

        try:
            _drive_forward_chain(
                feature_dir, wp_id="WP02", actor="canary-actor"
            )

            from specify_cli.status.models import ReviewResult

            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="test-1141-feature",
                    wp_id="WP02",
                    to_lane="planned",
                    actor="canary-actor",
                    force=True,
                    reason="backward rewind: in_review -> planned",
                    review_result=ReviewResult(
                        reviewer="canary-actor",
                        verdict="rejected",
                        reference="review-ref-1141-b",
                    ),
                )
            )

            assert len(captured) == 5
            # Build the (from, to, force) signature for each fan-out call.
            transitions = [
                (c["from_lane"], c["to_lane"], c["metadata"].force) for c in captured
            ]
            assert transitions == [
                ("planned", "claimed", False),
                ("claimed", "in_progress", False),
                ("in_progress", "for_review", False),
                ("for_review", "in_review", False),
                ("in_review", "planned", True),
            ], f"Fan-out transition sequence diverged from canary scenario 4: {transitions!r}"

            # The last fan-out (what the canary peek reads) is the rollback.
            last = captured[-1]
            assert last["from_lane"] == "in_review"
            assert last["to_lane"] == "planned"
            assert last["metadata"].force is True
        finally:
            adapters.reset_handlers()

    def test_backward_fanout_carries_mission_slug_and_wp_id(
        self, feature_dir: Path
    ) -> None:
        """The fan-out kwargs include the identity fields the SaaS materializer requires."""
        adapters.reset_handlers()
        captured: list[dict[str, Any]] = []

        def fake_saas(**kwargs: Any) -> None:
            captured.append(dict(kwargs))

        adapters.register_status_fanout_handler(fake_saas)

        try:
            _drive_forward_chain(
                feature_dir, wp_id="WP03", actor="canary-actor"
            )

            from specify_cli.status.models import ReviewResult

            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="test-1141-feature",
                    wp_id="WP03",
                    to_lane="planned",
                    actor="canary-actor",
                    force=True,
                    reason="backward rewind: in_review -> planned",
                    review_result=ReviewResult(
                        reviewer="canary-actor",
                        verdict="rejected",
                        reference="review-ref-1141-c",
                    ),
                )
            )

            backward = captured[-1]
            assert backward["mission_slug"] == "test-1141-feature"
            assert backward["wp_id"] == "WP03"
            assert backward["actor"] == "canary-actor"
        finally:
            adapters.reset_handlers()
