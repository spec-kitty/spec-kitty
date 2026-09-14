from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from kernel.clock import UTC, datetime, timedelta

pytestmark = [pytest.mark.unit]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "convergence" / "census_status.py"
_MAP_PATH = _REPO_ROOT / ".kittify" / "convergence-map.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("census_status_for_tests", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_seed_map_has_complete_nonpending_dispositions() -> None:
    module = _load_module()
    census_map = module.load_map(_MAP_PATH)

    assert len(census_map.clusters) == 74
    assert sum(len(cluster.commits) for cluster in census_map.clusters) == 800
    assert all(cluster.disposition != "PENDING" for cluster in census_map.clusters)


def test_seed_map_census_counts_match_commit_lists() -> None:
    document = json.loads(_MAP_PATH.read_text(encoding="utf-8"))

    for cluster in document["clusters"]:
        assert cluster["census_commit_count"] == len(cluster["commits"]), cluster["id"]


def test_status_lines_report_pending_and_triage_age() -> None:
    module = _load_module()
    now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
    commits = [
        module.UpstreamCommit("a" * 40, now - timedelta(days=3), "port an upstream fix"),
        module.UpstreamCommit("b" * 40, now - timedelta(days=2), "new upstream commit"),
    ]
    lookup = {"a" * 40: module.Cluster("PR#1", "PORT", ("a" * 40,))}

    lines = module.status_lines(
        commits,
        lookup,
        pending_only=False,
        max_age_days=1.0,
        now=now,
    )

    assert f"PORT {'a' * 40} PR#1: port an upstream fix" in lines
    assert f"PENDING {'b' * 40} unmapped: new upstream commit [triage: older than threshold]" in lines
    assert lines[-1] == ("checked=2 FORBIDDEN=0 PENDING=1 PORT=1 SUPERSEDED=0 pending-older-than-1-day=1")


def test_status_lines_pending_only_suppresses_dispositioned_commits() -> None:
    module = _load_module()
    now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
    commits = [
        module.UpstreamCommit("a" * 40, now, "mapped"),
        module.UpstreamCommit("b" * 40, now, "pending"),
    ]
    lookup = {"a" * 40: module.Cluster("PR#1", "SUPERSEDED", ("a" * 40,))}

    lines = module.status_lines(
        commits,
        lookup,
        pending_only=True,
        max_age_days=1.0,
        now=now,
    )

    assert lines == [
        f"PENDING {'b' * 40} pending",
        "checked=2 FORBIDDEN=0 PENDING=1 PORT=0 SUPERSEDED=1 pending-older-than-1-day=0",
    ]


def test_load_map_rejects_a_commit_in_two_clusters(tmp_path: Path) -> None:
    module = _load_module()
    sha = "c" * 40
    path = tmp_path / "convergence-map.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "base_commit": sha,
                "remote": "old",
                "remote_branch": "main",
                "clusters": [
                    {"id": "one", "disposition": "PORT", "commits": [sha]},
                    {"id": "two", "disposition": "FORBIDDEN", "commits": [sha]},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(module.CensusStatusError, match="appears in more than one cluster"):
        module.load_map(path)
