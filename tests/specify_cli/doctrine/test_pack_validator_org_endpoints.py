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

GREEN evidence: functional commit 788eba0e42b9a697f2187031b5868ced2d5b6415.
The same three-file validator surface (this module, test_pack_validator.py,
and test_pack_validator_fragment_finding.py)
ran with -n 2 --dist loadfile -q and focused --cov instrumentation:
123 passed, including all twelve public-command defects and two controls.
Provenance/public-authority enabler da5b882cbf3008f8d1df3525fad53ba7134a9377
preceded the functional commit and retained 12 failed, 2 passed acceptance.
The touched baseline strict-type failure was reported as #5971 and repaired
without suppression. This is executable contract evidence, not review approval.

Final bounded evidence (same clone tools, two workers, loadfile):
- Combined sixteen named WP test files with focused source --cov: 332 passed;
  direct default-catalog helper follow-up: 1 passed. Every added helper branch
  executed. Against the planning SHA, XML line hits intersected with added
  executable git-diff lines: 140/140 covered (100%), including all five sources.
- Owning fast tiers, marker expression '(fast or unit) and not slow and not e2e
  and not stress and not timing and not performance': tests/charter 3320 passed;
  tests/doctrine 3900 passed, 9 skipped; tests/specify_cli/doctrine 530 passed.
- Named facade identity/kind vocabulary/terminology/no-dead-symbol gates:
  270 passed. No allowlist/config change or private adapter resolver import.
- Both real public commands on packs/internal: exit 0, 0 errors, 0 advisories.
- Ruff check, format --check --force-exclude and mypy --strict on all eight
  changed Python files plus reconciliation typing: passed; no new suppression.
- PATH clone .venv/bin plus UV_NO_SYNC=1 PYTEST_XDIST_AUTO_NUM_WORKERS=2
  make test-fast: exit 0, 2451 passed, 5 skipped. The gate itself was not skipped
  or altered. Canonical review transition independently reruns its real gate.
No full architectural/e2e/performance/stress/test-full sweep was run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from charter.drg import DRGGraph, DRGNode, NodeKind, OrgDRGFragment, load_org_pack
from pydantic import BaseModel
from specify_cli.doctrine import pack_validator as pv
from specify_cli.cli.commands._doctrine_collect import _collect_org_layer_data
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
def test_requires_endpoint_contract(
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


def _write_fragment(root: Path, nodes: list[dict[str, str]], edges: list[dict[str, str]]) -> Path:
    file = root / "drg" / "fragment.yaml"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(yaml.safe_dump({"nodes": nodes, "edges": edges}), encoding="utf-8")
    return file


def _write_artifact(root: Path, plural: str, suffix: str, data: dict[str, Any]) -> Path:
    file = root / plural / f"local.{suffix}.yaml"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(yaml.safe_dump(data), encoding="utf-8")
    return file


def _local_node() -> dict[str, str]:
    return {"id": "local", "kind": "directives"}


def _edge(source: str, target: str, relation: str = "requires") -> dict[str, str]:
    return {"source": source, "target": target, "relation": relation}


def _dangling(result: pv.ValidationResult) -> list[pv.ValidationIssue]:
    return [issue for issue in result.errors if issue.category == "drg_dangling_edge"]


@pytest.mark.parametrize(
    "kind,plural,suffix,data",
    [
        ("asset", "assets", "asset", {"id": "file-only", "title": "Logo", "mime": "image/png", "path": "logo.png"}),
        (
            "directive",
            "directives",
            "directive",
            {"schema_version": "1.0", "id": "FILE_ONLY", "title": "Policy", "intent": "Local policy", "enforcement": "advisory"},
        ),
        (
            "agent_profile",
            "agent_profiles",
            "agent",
            {
                "profile-id": "file-only",
                "name": "Local",
                "roles": ["implementer"],
                "purpose": "Implement local policy",
                "specialization": {"primary_focus": "Implementation"},
            },
        ),
        (
            "agent_profile",
            "agent_profiles",
            "agent",
            {
                "profile_id": "file-only",
                "name": "Local",
                "roles": ["implementer"],
                "purpose": "Implement local policy",
                "specialization": {"primary_focus": "Implementation"},
            },
        ),
    ],
)
@pytest.mark.parametrize("valid", [True, False])
@pytest.mark.parametrize("qualified", [True, False])
def test_same_scan_file_trust_twins(tmp_path: Path, kind: str, plural: str, suffix: str, data: dict[str, Any], valid: bool, qualified: bool) -> None:
    artifact = dict(data)
    if not valid:
        artifact["unexpected_schema_key"] = True
        # Asset contracts are loose: make an actual required field invalid.
        if kind == "asset":
            artifact["mime"] = ""
    file = _write_artifact(tmp_path, plural, suffix, artifact)
    identity = str(data.get("id", data.get("profile-id", data.get("profile_id"))))
    token = f"{kind}:{identity}" if qualified else identity
    fragment = _write_fragment(tmp_path, [_local_node()], [_edge("local", token)])
    result = pv.validate_pack(tmp_path)
    if valid:
        assert _dangling(result) == [], result.errors
        assert result.ok, result.errors
    else:
        assert any(issue.file == str(file) and issue.category == "schema_invalid" for issue in result.errors), result.errors
        assert [(issue.file, issue.artifact_id) for issue in _dangling(result)] == [(str(fragment), token)]


def test_declaration_independent_of_invalid_asset_and_skill_schema(tmp_path: Path) -> None:
    _write_artifact(tmp_path, "assets", "asset", {"id": "logo", "mime": "", "path": "logo.png"})
    _write_fragment(tmp_path, [{"id": "logo", "kind": "assets"}, {"id": "workflow", "kind": "skills"}], [_edge("workflow", "asset:logo")])
    result = pv.validate_pack(tmp_path)
    assert any(issue.category == "schema_invalid" for issue in result.errors)
    assert _dangling(result) == []


def test_both_intent_shortcut_preserved_but_not_schema_trusted(tmp_path: Path) -> None:
    _write_artifact(tmp_path, "paradigms", "paradigm", {"id": "shortcut", "enhances": "missing", "overrides": "missing"})
    _write_fragment(tmp_path, [_local_node()], [_edge("local", "shortcut")])
    result = pv.validate_pack(tmp_path)
    assert any(issue.category == "intent_conflict" for issue in result.errors)
    assert not any(issue.category == "schema_invalid" for issue in result.errors)
    assert [issue.artifact_id for issue in _dangling(result)] == ["shortcut"]


@pytest.mark.parametrize("relation", ["requires", "unknown-label"])
def test_both_sides_and_unknown_prefix_order(tmp_path: Path, relation: str) -> None:
    _write_fragment(tmp_path, [], [_edge("missing-source", "directve:missing", relation)])
    result = pv.validate_pack(tmp_path)
    assert [issue.artifact_id for issue in _dangling(result)] == ["missing-source", "directve:missing"]
    assert "source" in result.errors[0].message and "target" in result.errors[1].message
    assert all("unresolved_edge_endpoint" in issue.message for issue in _dangling(result))


def test_unknown_label_and_local_last_assignment_do_not_validate_relation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pv, "_load_endpoint_catalog", lambda: pv._EndpointCatalog({"directive:shared", "tactic:shared"}, {}))
    _write_fragment(tmp_path, [{"id": "shared", "kind": "directives"}, {"id": "shared", "kind": "assets"}], [_edge("shared", "asset:shared", "unknown-label")])
    assert pv.validate_pack(tmp_path).ok
    loaded = load_org_pack("test", tmp_path, 1)
    assert pv._org_local_registry(loaded, set())["shared"] == "asset:shared"


def test_builtin_bare_and_qualified_controls_and_deterministic_json(tmp_path: Path) -> None:
    _write_fragment(
        tmp_path, [_local_node()], [_edge("local", "acceptance-test-first"), _edge("local", "tactic:acceptance-test-first"), _edge("local", "directive:missing")]
    )
    results = [CliRunner().invoke(doctrine_app, ["pack", "validate", str(tmp_path), "--json"]) for _ in range(2)]
    assert all(result.exit_code == 1 for result in results)
    assert results[0].stdout == results[1].stdout
    payload = json.loads(results[0].stdout)
    assert [row["artifact_id"] for row in payload["errors"]] == ["directive:missing"]


def test_all_three_consumers_load_once_and_sanctions_keep_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_artifact(
        tmp_path, "directives", "directive", {"schema_version": "1.0", "id": "ORG_POLICY", "title": "Policy", "intent": "Policy", "enforcement": "advisory"}
    )
    # Invalid schema, yet loader discovery still contributes this built-in node
    # to sanction analysis, which is deliberately not the trust projection.
    (tmp_path / "directives" / "invalid.directive.yaml").write_text("id: DIRECTIVE_003\n", encoding="utf-8")
    _write_fragment(tmp_path, [_local_node()], [_edge("local", "ORG_POLICY"), _edge("local", "directive:missing", "enhances")])
    (tmp_path / "replaceable-builtins.yaml").write_text(
        "replaceable_builtins:\n  - {urn: 'directive:DIRECTIVE_003', reason: Explicit replacement}\n", encoding="utf-8"
    )
    calls: list[str] = []

    def counted(pack_name: str, pack_root: Path, layer_index: int) -> OrgDRGFragment:
        calls.append(pack_name)
        return load_org_pack(pack_name, pack_root, layer_index)

    monkeypatch.setattr(pv, "load_org_pack", counted)
    result = pv.validate_pack(tmp_path)
    assert len(calls) == 1
    assert [issue.artifact_id for issue in _dangling(result)] == ["directive:missing"]
    assert any(issue.category == "unknown_target" for issue in result.errors)
    assert not any(issue.category == "pack_sanction" for issue in result.advisories + result.errors)


@pytest.mark.parametrize("content,category", [("nodes: [", "parse_error"), ("nodes: [{id: x, kind: wrong}]", "schema_invalid")])
def test_failed_load_one_attempt_without_derived_noise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str, category: str) -> None:
    file = _write_fragment(tmp_path, [], [])
    file.write_text(content, encoding="utf-8")
    (tmp_path / "replaceable-builtins.yaml").write_text("replaceable_builtins: [{urn: 'tactic:missing'}]\n", encoding="utf-8")
    calls: list[str] = []

    def counted(pack_name: str, pack_root: Path, layer_index: int) -> OrgDRGFragment:
        calls.append(pack_name)
        return load_org_pack(pack_name, pack_root, layer_index)

    monkeypatch.setattr(pv, "load_org_pack", counted)
    result = pv.validate_pack(tmp_path)
    assert len(calls) == 1
    assert [(issue.file, issue.category) for issue in result.errors] == [(str(file), category)]
    assert result.advisories == []


@pytest.mark.parametrize("valid", [False, True])
def test_governance_fault_attributes_sibling_and_valid_twin_runs_endpoints(tmp_path: Path, valid: bool) -> None:
    fragment = _write_fragment(tmp_path, [_local_node()], [_edge("local", "asset:missing")])
    profile = tmp_path / "mission_types" / "software-dev" / "governance-profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text("selected_directives: " + ("[DIRECTIVE_003]" if valid else "not-a-list"), encoding="utf-8")
    result = pv.validate_pack(tmp_path)
    if valid:
        assert [(issue.file, issue.category) for issue in result.errors] == [(str(fragment), "drg_dangling_edge")]
    else:
        assert [(issue.file, issue.category) for issue in result.errors] == [(str(profile), "schema_invalid")]
        assert _dangling(result) == []


def test_io_fault_and_no_fragment_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file = _write_fragment(tmp_path, [], [])

    def failing(pack_name: str, pack_root: Path, layer_index: int) -> OrgDRGFragment:
        raise PermissionError(13, "not readable", str(file))

    monkeypatch.setattr(pv, "load_org_pack", failing)
    result = pv.validate_pack(tmp_path)
    assert [(issue.file, issue.category) for issue in result.errors] == [(str(file), "unreadable_file")]
    assert pv._collect_fragment_edge_intent(file.parent) == {}
    assert pv._pack_node_urns(tmp_path) is None
    file.unlink()
    assert pv.validate_pack(tmp_path).ok
    assert pv._collect_fragment_edge_intent(file.parent) == {}
    assert pv._pack_node_urns(tmp_path) is None


def test_omitted_default_differs_from_explicit_absent_helper_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file = _write_fragment(tmp_path, [_local_node()], [_edge("local", "missing", "enhances")])
    assert pv._collect_fragment_edge_intent(file.parent)["directives"]["local"][0] == {"enhances": "missing"}
    assert pv._pack_node_urns(tmp_path) == frozenset({"directive:local"})

    def forbidden(pack_name: str, pack_root: Path, layer_index: int) -> OrgDRGFragment:
        pytest.fail("explicit load outcome must not reload")

    monkeypatch.setattr(pv, "load_org_pack", forbidden)
    assert pv._collect_fragment_edge_intent(file.parent, None) == {}
    assert pv._pack_node_urns(tmp_path, None) is None


def test_unavailable_builtins_still_checks_local_closure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.offering.drg import loader

    def unavailable() -> DRGGraph:
        raise loader.DRGLoadError("unavailable")

    monkeypatch.setattr(loader, "load_built_in_graph", unavailable)
    _write_fragment(tmp_path, [_local_node()], [_edge("local", "directive:local"), _edge("local", "directive:missing")])
    assert [issue.artifact_id for issue in _dangling(pv.validate_pack(tmp_path))] == ["directive:missing"]


def test_identity_helper_defensive_branches() -> None:
    class Identity(BaseModel):
        id: str

    assert pv._validated_artifact_urn("directives", Identity(id="example")) == "directive:example"
    assert pv._validated_artifact_urn("not-a-kind", Identity(id="example")) is None
    assert pv._validated_artifact_urn("directives", Identity(id="")) is None

    class NoIdentity(BaseModel):
        pass

    assert pv._validated_artifact_urn("directives", NoIdentity()) is None


def test_alias_trusted_identity_without_loader_discovery_is_added_deterministically(tmp_path: Path) -> None:
    _write_fragment(tmp_path, [_local_node()], [])
    fragment = load_org_pack("test", tmp_path, 1)
    assert pv._org_local_registry(fragment, {"agent_profile:alias"}) == {"local": "directive:local", "alias": "agent_profile:alias"}


def test_intentional_sibling_standalone_red_complete_runtime_resolves(tmp_path: Path) -> None:
    pack = tmp_path / "primary-pack"
    sibling = tmp_path / "sibling-pack"
    _write_fragment(pack, [_local_node()], [_edge("directive:local", "asset:sibling-logo")])
    _write_fragment(sibling, [{"id": "sibling-logo", "kind": "assets"}], [])
    standalone = pv.validate_pack(pack)
    assert [issue.artifact_id for issue in _dangling(standalone)] == ["asset:sibling-logo"]
    repo = tmp_path / "consumer"
    config = repo / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        yaml.safe_dump(
            {
                "charter_packs": {
                    "org": {
                        "packs": [
                            {"name": "primary", "local_path": str(pack)},
                            {"name": "sibling", "local_path": str(sibling)},
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    runtime = _collect_org_layer_data(repo)
    assert runtime["errors"] == [], runtime
    assert runtime["dangling_endpoints"] == []
    assert len(runtime["configured_packs"]) == 2


def _write_graph(file: Path, nodes: list[dict[str, str]], edges: list[dict[str, str]]) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "generated_at": "2026-10-09T00:00:00Z",
                "generated_by": "test",
                "nodes": nodes,
                "edges": edges,
            }
        ),
        encoding="utf-8",
    )


def test_coexisting_shapes_cannot_cross_rescue_and_share_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fragment = _write_fragment(tmp_path, [{"id": "org-only", "kind": "assets"}], [_edge("asset:org-only", "asset:graph-only")])
    graph = tmp_path / "drg" / "a.graph.yaml"
    _write_graph(graph, [{"urn": "asset:graph-only", "kind": "asset"}], [_edge("asset:graph-only", "asset:org-only")])
    calls: list[bool] = []
    actual = pv._load_endpoint_catalog

    def catalog() -> pv._EndpointCatalog:
        calls.append(True)
        return actual()

    monkeypatch.setattr(pv, "_load_endpoint_catalog", catalog)
    result = pv.validate_pack(tmp_path)
    assert len(calls) == 1
    assert [(issue.file, issue.artifact_id) for issue in _dangling(result)] == [
        (str(fragment), "asset:graph-only"),
        (str(graph), "asset:org-only"),
    ]
    assert any(issue.category == "drg_root_graph_missing" for issue in result.errors)
    assert _dangling(result)[1].message == "dangling DRG edge — target URN 'asset:org-only' not in built-in or pack artifact set"


def test_sharded_snapshot_order_duplicate_and_kind_drift_unchanged(tmp_path: Path) -> None:
    first = tmp_path / "drg" / "a.graph.yaml"
    second = tmp_path / "drg" / "b.graph.yaml"
    edge = _edge("directive:A", "directive:B")
    _write_graph(first, [{"urn": "directive:A", "kind": "directive"}, {"urn": "directive:DIRECTIVE_003", "kind": "directive"}], [edge])
    _write_graph(second, [{"urn": "directive:B", "kind": "directive"}], [edge])
    # Valid document, inconsistent catalog kind isolates the existing drift
    # branch without bypassing graph model validation.
    catalog = pv._EndpointCatalog({"directive:DIRECTIVE_003"}, {"directive:DIRECTIVE_003": "tactic"})
    errors, advisories = pv._validate_drg(first.parent, set(), catalog)
    assert [(issue.category, issue.file, issue.artifact_id) for issue in errors] == [
        ("drg_kind_drift", str(first), "directive:DIRECTIVE_003"),
        ("drg_dangling_edge", str(first), "directive:B"),
    ]
    assert errors[1].message == "dangling DRG edge — target URN 'directive:B' not in built-in or pack artifact set"
    assert [(issue.category, issue.file) for issue in advisories] == [("duplicate_drg_edge", str(second))]
    assert advisories[0].message == "duplicate edge (directive:A -[requires]-> directive:B) already present in a.graph.yaml"


def test_generated_augmentation_edges_never_acquire_fragment_findings(tmp_path: Path) -> None:
    _write_fragment(tmp_path, [], [])
    _write_artifact(tmp_path, "paradigms", "paradigm", {"id": "projection", "enhances": "missing"})
    loaded = load_org_pack("test", tmp_path, 1)
    assert len(loaded.edges) == 1 and loaded.authored_edges == []
    result = pv.validate_pack(tmp_path)
    assert _dangling(result) == []
    assert any(issue.category == "unknown_target" for issue in result.errors)


@pytest.mark.parametrize("qualified", [False, True])
def test_authored_augmentation_preserves_unknown_target_fallback(tmp_path: Path, qualified: bool) -> None:
    _write_fragment(tmp_path, [_local_node()], [_edge("local", "directive:missing" if qualified else "missing", "enhances")])
    result = pv.validate_pack(tmp_path)
    assert [issue.category for issue in result.errors] == ["drg_dangling_edge", "unknown_target"]
    assert "unresolved_edge_endpoint" in result.errors[0].message if not qualified else "directive:missing" in result.errors[0].message


def test_direct_graph_helper_omission_loads_default_catalog(tmp_path: Path) -> None:
    file = tmp_path / "drg" / "only.graph.yaml"
    _write_graph(file, [{"urn": "directive:A", "kind": "directive"}], [_edge("directive:A", "directive:A")])
    assert pv._validate_drg(file.parent, set()) == ([], [])


def test_empty_pack_and_empty_fragment(tmp_path: Path) -> None:
    assert pv.validate_pack(tmp_path).ok
    _write_fragment(tmp_path, [], [])
    assert pv.validate_pack(tmp_path).ok
