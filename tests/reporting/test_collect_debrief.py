"""Starter tests for the deterministic debrief collector (Stage A).

Every gh call is stubbed through the single `_run_gh` seam, so these run with
no network and no GitHub token. They pin the JSON contract the synthesis stage
depends on — especially `valid_refs` (the hallucination guard) and the
generated Method provenance.

NOTE (scaffold): when this graduates to a PR, join the test-completeness
baselines the repo enforces for new test files (see the maintainer runbook).
"""

from __future__ import annotations

import json

import pytest

from scripts.reporting import collect_debrief as cd

pytestmark = pytest.mark.unit


def _fake_gh(responses: dict[str, object]):
    """Return a `_run_gh` replacement that matches on a substring of the args."""

    def _run(args: list[str]) -> str:
        joined = " ".join(args)
        for needle, payload in responses.items():
            if needle in joined:
                return payload if isinstance(payload, str) else json.dumps(payload)
        return "[]"

    return _run


def test_window_contract_shape_and_ref_guard(monkeypatch):
    prs = [
        {
            "number": 5266,
            "title": "Ship Op-vs-Mission doctrine",
            "author": {"login": "stijn-dejongh"},
            "mergedAt": "2026-09-28T09:14:29Z",
            "labels": [],
            "url": "u/5266",
        },
    ]
    closed = [
        {
            "number": 5050,
            "title": "Upgrade deletes template",
            "author": {"login": "a"},
            "closedAt": "2026-09-27T00:00:00Z",
            "createdAt": "2026-09-20T00:00:00Z",
            "labels": [{"name": "priority:P0"}],
            "url": "u/5050",
            "stateReason": "completed",
        },
        {
            "number": 1193,
            "title": "Dropped epic",
            "author": {"login": "b"},
            "closedAt": "2026-09-27T00:00:00Z",
            "createdAt": "2026-09-01T00:00:00Z",
            "labels": [],
            "url": "u/1193",
            "stateReason": "not_planned",
        },
    ]
    monkeypatch.setattr(
        cd,
        "_run_gh",
        _fake_gh(
            {
                "pr list": prs,
                "issue list --repo spec-kitty/spec-kitty --state closed": closed,
                "commits/main": "dc06afb962abc",
                "search/issues": {"total": 169},
            }
        ),
    )

    out = cd.collect_window(["spec-kitty/spec-kitty"], "2026-09-26T06:00:00Z", "2026-09-28T05:50:00Z")

    assert out["meta"]["mode"] == "window"
    assert out["meta"]["filters"] == {"since": "2026-09-26T06:00:00Z", "until": "2026-09-28T05:50:00Z"}
    assert out["meta"]["main_shas"]["spec-kitty/spec-kitty"] == "dc06afb962"
    assert "queried, not estimated" in out["meta"]["method"]

    assert out["metrics"]["prs_merged"] == 1
    assert out["metrics"]["issues_closed"] == 2
    assert out["metrics"]["issues_closed_by_reason"] == {"fixed": 1, "not_planned": 1}
    assert out["metrics"]["p0_closed"] == 1

    # The hallucination guard: exactly the refs the collector saw, sorted.
    assert out["valid_refs"] == ["#1193", "#5050", "#5266"]
    assert out["authors"] == {"stijn-dejongh": 1}


def test_scope_buckets_priority_and_epics(monkeypatch):
    issues = [
        {
            "number": 5045,
            "title": "Nightly red",
            "author": {"login": "a"},
            "closedAt": None,
            "createdAt": "2026-09-25T00:00:00Z",
            "labels": [{"name": "priority:P0"}],
            "url": "u",
            "stateReason": None,
            "milestone": {"title": "11"},
        },
        {
            "number": 1619,
            "title": "Epic",
            "author": {"login": "b"},
            "closedAt": None,
            "createdAt": "2026-09-01T00:00:00Z",
            "labels": [{"name": "priority:P1"}, {"name": "epic"}],
            "url": "u",
            "stateReason": None,
            "milestone": {"title": "11"},
        },
    ]
    monkeypatch.setattr(
        cd,
        "_run_gh",
        _fake_gh(
            {
                "issue list": issues,
                "commits/main": "b7ada76012",
            }
        ),
    )

    out = cd.collect_scope(["spec-kitty/spec-kitty"], milestone="11", label=None, query=None)

    assert out["meta"]["mode"] == "scope"
    assert out["metrics"]["open_issues"] == 2
    assert out["metrics"]["by_priority"]["priority:P0"] == 1
    assert out["metrics"]["by_priority"]["priority:P1"] == 1
    assert out["metrics"]["epics"] == 1
    assert out["valid_refs"] == ["#1619", "#5045"]


def test_duplicate_label_overrides_close_reason(monkeypatch):
    closed = [
        {
            "number": 42,
            "title": "Dup",
            "author": {"login": "a"},
            "closedAt": "2026-09-27T00:00:00Z",
            "createdAt": "2026-09-26T00:00:00Z",
            "labels": [{"name": "duplicate"}],
            "url": "u",
            "stateReason": "not_planned",
            "milestone": None,
        },
    ]
    monkeypatch.setattr(
        cd,
        "_run_gh",
        _fake_gh(
            {
                "issue list": closed,
                "pr list": [],
                "commits/main": "abc123",
                "search/issues": {"total": 0},
            }
        ),
    )
    out = cd.collect_window(["spec-kitty/spec-kitty"], "2026-09-26T00:00:00Z", "2026-09-28T00:00:00Z")
    assert out["metrics"]["issues_closed_by_reason"] == {"duplicate": 1}


def test_collector_fails_closed_on_gh_error(monkeypatch):
    def _boom(args):
        raise cd.CollectorError("gh exploded")

    monkeypatch.setattr(cd, "_run_gh", _boom)
    with pytest.raises(cd.CollectorError):
        cd.collect_scope(["spec-kitty/spec-kitty"], milestone="11", label=None, query=None)
