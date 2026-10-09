"""Outside-in acceptance for canonical org-fragment endpoints (#5833).

Portable RED evidence (before any source edit):
Planning boundary: 2912dfcb54923787374afa0e52f80a964d588dc5.
Witness HEAD: 09ec001dbf1827aae4b138b58dce84e98c232ff8; differences from
planning boundary were lifecycle status/baseline records only, no source changes.
Command: .venv/bin/python -m pytest
  tests/specify_cli/doctrine/test_pack_validator_org_endpoints.py
  -n 2 --dist loadfile -q
Result: 12 failed, 2 passed, exit 1. All six doctrine cases returned
{\"advisories\": [], \"errors\": [], \"ok\": true}, missing the correlated finding;
all six charter cases rendered 'Pack validation: 0 errors, 0 advisories'.
Declared-node controls passed. Requires, not augmentation, isolates the gap.
Earlier fixture-development runs corrected missing catalog metadata and stderr
mixing; those runs are NOT the authoritative RED witness. No validator/resolver
was mocked; only the ambiguity catalog was isolated with real graph models.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from charter.drg import DRGGraph, DRGNode, NodeKind
from specify_cli.cli.commands.charter import app as charter_app
from specify_cli.cli.commands.doctrine import app as doctrine_app

pytestmark = [pytest.mark.fast, pytest.mark.unit]


def _pack(root: Path, source: str, target: str) -> Path:
    fragment = root / "drg" / "fragment.yaml"
    fragment.parent.mkdir(parents=True)
    fragment.write_text(
        yaml.safe_dump(
            {
                "nodes": [{"id": "local", "kind": "directives", "title": "Local policy"}],
                "edges": [{"source": source, "target": target, "relation": "requires"}],
            }
        ),
        encoding="utf-8",
    )
    return fragment


@pytest.mark.parametrize("command", ["doctrine", "charter"])
@pytest.mark.parametrize(
    "source,target,token,role,cause",
    [
        ("directive:missing", "local", "directive:missing", "source", None),
        ("local", "asset:missing", "asset:missing", "target", None),
        ("missing", "local", "missing", "source", "unresolved_edge_endpoint"),
        ("local", "missing", "missing", "target", "unresolved_edge_endpoint"),
        ("local", "directive:", "directive:", "target", "malformed_urn"),
        ("local", "shared", "shared", "target", "ambiguous_edge_endpoint"),
    ],
)
def test_issue_5833_requires_endpoint_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    source: str,
    target: str,
    token: str,
    role: str,
    cause: str | None,
) -> None:
    """Both existing commands must identify the same offending requires endpoint."""
    if cause == "ambiguous_edge_endpoint":
        # Isolate only catalog content, not validation or the real resolver.
        graph = DRGGraph(
            schema_version="1.0",
            generated_at="2026-10-09T00:00:00Z",
            generated_by="acceptance-test",
            nodes=[
                DRGNode(urn="directive:shared", kind=NodeKind.DIRECTIVE),
                DRGNode(urn="tactic:shared", kind=NodeKind.TACTIC),
            ],
            edges=[],
        )
        monkeypatch.setattr("charter.offering.drg.loader.load_built_in_graph", lambda: graph)
    fragment = _pack(tmp_path, source, target)
    runner = CliRunner()
    if command == "doctrine":
        result = runner.invoke(doctrine_app, ["pack", "validate", str(tmp_path), "--json"])
        assert result.stdout.startswith("{"), (result.stdout, result.exception)
        payload = json.loads(result.stdout)
        assert not any(row.get("category") in {"schema_invalid", "unknown_target"} for row in payload["errors"])
        matches = [
            row
            for row in payload["errors"]
            if row.get("category") == "drg_dangling_edge"
            and row["severity"] == "error"
            and row["artifact_type"] == "drg"
            and row["file"] == str(fragment)
            and row["artifact_id"] == token
            and role in row["message"]
            and token in row["message"]
        ]
        assert len(matches) == 1, payload
        if cause is not None:
            assert cause in matches[0]["message"]
    else:
        result = runner.invoke(charter_app, ["org", "validate", str(tmp_path)])
        assert "dangling DRG edge" in result.output, result.output
        assert "fragment.yaml" in result.output and token in result.output and role in result.output
        if cause is not None:
            assert cause in result.output
    assert result.exit_code == 1, result.output


@pytest.mark.parametrize("command", ["doctrine", "charter"])
def test_declared_requires_control(tmp_path: Path, command: str) -> None:
    _pack(tmp_path, "directive:local", "local")
    app = doctrine_app if command == "doctrine" else charter_app
    args = ["pack", "validate", str(tmp_path), "--json"] if command == "doctrine" else ["org", "validate", str(tmp_path)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
