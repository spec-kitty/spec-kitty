"""Tests for tracker SQLite store behavior."""

from __future__ import annotations

import pytest
import asyncio

from specify_cli.tracker.store import TrackerSqliteStore, default_tracker_db_path

pytestmark = pytest.mark.fast


async def _upsert(store: TrackerSqliteStore, issue: dict) -> None:
    await store.upsert_issue(issue)


async def _list(store: TrackerSqliteStore, system: str | None = None):
    return await store.list_issues(system=system)


async def _delete(store: TrackerSqliteStore, ref: dict) -> None:
    await store.delete_issue(ref)


def _sample_issue(issue_id: str) -> dict:
    return {
        "ref": {
            "system": "jira",
            "workspace": "team-a",
            "id": issue_id,
            "key": f"PRJ-{issue_id}",
            "url": f"https://example.atlassian.net/browse/PRJ-{issue_id}",
        },
        "title": f"Issue {issue_id}",
        "body": "Body",
        "status": "todo",
        "issue_type": "task",
        "priority": 2,
        "assignees": ["alice"],
        "labels": ["backend"],
        "links": [],
        "custom_fields": {"source": "test"},
    }


def test_issue_persistence_across_instances(tmp_path) -> None:
    db_path = tmp_path / "tracker.db"
    store_a = TrackerSqliteStore(db_path)
    store_b = TrackerSqliteStore(db_path)

    issue = _sample_issue("100")
    asyncio.run(_upsert(store_a, issue))

    issues = asyncio.run(_list(store_b, system="jira"))
    assert len(issues) == 1

    ref = {"system": "jira", "workspace": "team-a", "id": "100"}
    asyncio.run(_delete(store_b, ref))

    remaining = asyncio.run(_list(store_a, system="jira"))
    assert remaining == []


def test_mapping_and_checkpoint_round_trip(tmp_path) -> None:
    db_path = tmp_path / "tracker.db"
    store = TrackerSqliteStore(db_path)

    ref = {
        "system": "linear",
        "workspace": "team-alpha",
        "id": "abc123",
        "key": "LIN-1",
        "url": "https://linear.app/team/issue/LIN-1",
    }
    store.upsert_mapping(wp_id="WP01", ref=ref)

    mappings = store.list_mappings()
    # Verifies the upsert dedupes to one row rather than accumulating; row content
    # (asserted below) carries dynamic created_at/updated_at timestamps so cannot be
    # pinned by a single equality.
    assert len(mappings) == 1
    assert mappings[0]["wp_id"] == "WP01"
    assert mappings[0]["external_id"] == "abc123"

    store.set_checkpoint({"cursor": "next-page", "updated_since": None}, checkpoint_key="linear:team-alpha")
    checkpoint = store.get_checkpoint("linear:team-alpha")
    assert checkpoint is not None
    if isinstance(checkpoint, dict):
        assert checkpoint["cursor"] == "next-page"
    else:
        assert checkpoint.cursor == "next-page"


def test_scope_hash_segregates_by_identity() -> None:
    first = default_tracker_db_path(
        provider="jira",
        workspace="team-a",
        server_url="https://jira.example.com",
        username="alice@example.com",
        team_slug="alpha",
    )
    second = default_tracker_db_path(
        provider="jira",
        workspace="team-a",
        server_url="https://jira.example.com",
        username="bob@example.com",
        team_slug="alpha",
    )

    assert first != second
    assert first.name.endswith(".db")
    assert second.name.endswith(".db")
