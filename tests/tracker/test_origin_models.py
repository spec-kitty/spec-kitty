"""Tests for specify_cli.tracker.origin_models dataclasses."""

from __future__ import annotations

import dataclasses

import pytest

from specify_cli.tracker.origin_models import OriginCandidate


# ---------------------------------------------------------------------------
# OriginCandidate
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


class TestOriginCandidate:
    """Tests for the OriginCandidate frozen dataclass."""

    def test_construct_with_valid_fields(self) -> None:
        candidate = OriginCandidate(
            external_issue_id="issue-123",
            external_issue_key="PROJ-42",
            title="Fix login page",
            status="In Progress",
            url="https://tracker.example.com/PROJ-42",
            match_type="exact",
        )
        assert candidate.external_issue_id == "issue-123"
        assert candidate.external_issue_key == "PROJ-42"
        assert candidate.title == "Fix login page"
        assert candidate.status == "In Progress"
        assert candidate.url == "https://tracker.example.com/PROJ-42"
        assert candidate.match_type == "exact"

    def test_frozen_raises_on_attribute_assignment(self) -> None:
        candidate = OriginCandidate(
            external_issue_id="id-1",
            external_issue_key="KEY-1",
            title="Title",
            status="Open",
            url="https://example.com",
            match_type="text",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            candidate.title = "Changed"  # type: ignore[misc]

    def test_equality(self) -> None:
        kwargs = {
            "external_issue_id": "id-1",
            "external_issue_key": "KEY-1",
            "title": "Title",
            "status": "Open",
            "url": "https://example.com",
            "match_type": "exact",
        }
        first = OriginCandidate(**kwargs)
        second = OriginCandidate(**kwargs)
        assert first == second
        assert first is not second

    def test_text_match_type(self) -> None:
        candidate = OriginCandidate(
            external_issue_id="id-2",
            external_issue_key="KEY-2",
            title="Fuzzy match",
            status="Done",
            url="https://example.com/2",
            match_type="text",
        )
        assert candidate.match_type == "text"
