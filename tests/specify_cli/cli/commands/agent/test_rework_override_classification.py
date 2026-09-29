"""Rework-vs-override classification through the real ``move-task`` CLI (#5196).

Mission ``rework-is-not-an-override``. A forced move out of ``planned`` is an
arbiter override only when it targets ``approved``/``done`` after a rejection
(``for_review`` or ``in_review`` source). A forced *rework* resubmission
(``claimed``/``for_review``) is not an override and must light no probe.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.specify_cli.cli.commands.agent import _rework_loop_harness as h

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.mark.parametrize("target", ["for_review", "claimed"])
def test_forced_rework_after_rejection_is_not_an_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    """FR-004: the legacy ``--force`` habit on a rework move records no override."""
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    h.reject(m, "for_review_to_planned", allow_force=True)

    result = h.move(m, h.WP, target, h.IMPLEMENTER, "--force")

    assert result.exit_code == 0, result.output
    probes = h.override_probes(m, move_output=result.output)
    assert probes["cli_marker"] is False, f"forced rework announced an override: {result.output}"
    assert not any(probes.values()), probes


@pytest.mark.parametrize("route", ["for_review_to_planned", "in_review_to_planned"])
def test_forced_approve_after_rejection_is_an_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, route: str) -> None:
    """FR-005: a genuine forced ``planned -> approved`` lights all five probes for BOTH rejection sources.

    The approved-cycle write is suppressed for a genuine override, so the only
    review-cycle artifact is the rejection's ``review-cycle-1.md`` (the base
    writes a spurious ``review-cycle-2.md`` for the ``in_review`` source).
    """
    m = h.build_mission(tmp_path, monkeypatch)
    h.drive_to_for_review(m)
    h.reject(m, route, allow_force=True)

    result = h.move(m, h.WP, "approved", h.REVIEWER, "--force", "--note", h.ARBITER_NOTE)

    assert result.exit_code == 0, result.output
    probes = h.override_probes(m, move_output=result.output)
    assert probes == dict.fromkeys(probes, True), f"not all probes lit: {probes}"
    assert h.review_cycle_files(m) == ["review-cycle-1.md"]
