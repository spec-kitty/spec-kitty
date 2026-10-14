"""Tests for ``tracker_egress_verdict`` after the hosted destination was removed (#6164).

Channel 1 (hosted-sync consent) retired earlier (#5); the hosted destination itself
(``HOSTED_SERVICE``) was then removed from open-core with the hosted tracker surface (#6164),
leaving one destination. This file pins the surviving channel: Channel 2 (the project's own
committed ``tracker.egress`` key) is two-way at ``LOCAL_SUBPROCESS`` -- ``refused`` refuses,
``permitted`` grants, and absence/illegal/unreadable all refuse (inability to determine consent
is never consent).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.tracker.config import TrackerProjectConfig, save_tracker_config
from specify_cli.tracker.egress_verdict import (
    CHANNEL_2,
    EgressDestination,
    tracker_egress_verdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_egress(root: Path, value: str) -> None:
    save_tracker_config(root, TrackerProjectConfig(provider="beads", egress=value))


class TestLocalSubprocessIsTwoWay:
    def test_refused_key_refuses(self, tmp_path: Path) -> None:
        _write_egress(tmp_path, "refused")
        verdict = tracker_egress_verdict(tmp_path, destination=EgressDestination.LOCAL_SUBPROCESS, identifiers="issue-1")
        assert verdict.refused is True
        assert verdict.refusing_channels == frozenset({CHANNEL_2})

    def test_permitted_key_permits(self, tmp_path: Path) -> None:
        _write_egress(tmp_path, "permitted")
        verdict = tracker_egress_verdict(tmp_path, destination=EgressDestination.LOCAL_SUBPROCESS, identifiers="issue-1")
        assert verdict.refused is False
        assert verdict.refusing_channels == frozenset()

    def test_absent_key_refuses_with_grant_remedy(self, tmp_path: Path) -> None:
        verdict = tracker_egress_verdict(tmp_path, destination=EgressDestination.LOCAL_SUBPROCESS, identifiers="issue-1")
        assert verdict.refused is True
        assert verdict.remedies

    def test_illegal_value_refuses_as_fault(self, tmp_path: Path) -> None:
        _write_egress(tmp_path, "sometimes")
        verdict = tracker_egress_verdict(tmp_path, destination=EgressDestination.LOCAL_SUBPROCESS, identifiers="issue-1")
        assert verdict.refused is True

    def test_no_root_refuses(self) -> None:
        verdict = tracker_egress_verdict(None, destination=EgressDestination.LOCAL_SUBPROCESS, identifiers="issue-1")
        assert verdict.refused is True


def test_never_raises_on_unreadable_config(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("not: [valid: yaml", encoding="utf-8")
    for destination in EgressDestination:
        verdict = tracker_egress_verdict(tmp_path, destination=destination, identifiers="issue-1")
        assert isinstance(verdict.refused, bool)
