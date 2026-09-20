"""WP03 -- CLI preserve/prune/dry-run + narrow refusal (charter-synthesize-reconciliation-01KZJQN6).

Covers the T016 test list from ``kitty-specs/charter-synthesize-reconciliation-
01KZJQN6/tasks/WP03-cli-preserve-prune-dryrun.md`` plus the post-tasks squad
amendments:

1. ``--prune`` removes divergent content and lists each deletion (exit 0),
   asserting node+edges are dropped TOGETHER (amendment #1 atomicity).
2. ``--prune`` with nothing to prune -> no-op, empty deletions (exit 0).
3. ``--dry-run`` on a superset overlay -> non-empty ``planned_deletes``,
   no file written (exit 0).
4. ``--dry-run`` with no divergence -> empty ``planned_deletes`` (exit 0).
5. Orphaned removal without ``--prune`` -> exit 1, lists the orphan +
   remediation, and the orphan node's edges are retained WITH it (amendment
   #1's refusal-path counterpart) -- preserve mode never deletes anything
   (orphaned or not), so the underlying write is non-destructive; refusal
   means "flagged for operator decision", not "graph.yaml untouched".
6. Unparseable ``graph.yaml`` -> exit 1, no write.
7. Backed divergence (plain run) -> exit 0, content preserved, warning
   surfaced.
8. The amendment #3 sentinel-coercion unit test for ``_coerce_cli_bool``.

Real behavior throughout: every scenario drives the actual
``charter.activation.synthesizer.synthesize`` / ``reconcile_synthesis`` machinery
against a real ``tmp_path`` repo with the canonical ``FixtureAdapter``
(inputs-hash-keyed against ``tests/charter/fixtures/synthesizer/``). Only
the interview-answers -> ``SynthesisRequest`` derivation
(``_build_synthesis_request``) and evidence collection are mocked -- the
same narrow mocking convention already established by
``tests/agent/cli/commands/test_charter_synthesize_cli.py`` and
``tests/charter/test_reject_not_drop_cli.py`` -- so the CLI's OWN
reconciliation policy (preview, orphan classification, refusal, prune/
preserve reporting) is exercised for real, not stubbed out.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.synthesizer import FixtureAdapter, SynthesisRequest, SynthesisTarget, synthesize
from charter.activation.synthesizer.manifest import (
    MANIFEST_PATH,
    ManifestArtifactEntry,
    finalize_manifest,
    load_yaml as load_manifest,
)
from charter.activation.synthesizer.provenance import load_yaml as load_provenance
from charter.activation.synthesizer.reconcile import SynthesizeMode
from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml
from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.charter.synthesize import _coerce_cli_bool

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_LEGACY_URN = "tactic:legacy-preference-order-3270"
_LEGACY_EDGE_TARGET = "directive:DIRECTIVE_003"
_ORPHAN_URN = "tactic:orphaned-no-backing-artifact"
_ORPHAN_EDGE_TARGET = "directive:DIRECTIVE_003"


# ---------------------------------------------------------------------------
# Shared setup helpers (mirrors tests/charter/synthesizer/test_synthesize_reconcile.py)
# ---------------------------------------------------------------------------


def _minimal_interview_snapshot() -> dict[str, Any]:
    return {
        "mission_type": "software_dev",
        "language_scope": ["python"],
        "testing_philosophy": "test-driven development with high coverage",
        "neutrality_posture": "balanced",
        "selected_directives": ["DIRECTIVE_003"],
        "risk_appetite": "moderate",
    }


def _minimal_doctrine_snapshot() -> dict[str, Any]:
    return {
        "directives": {
            "DIRECTIVE_003": {
                "id": "DIRECTIVE_003",
                "title": "Decision Documentation",
                "body": "Document significant architectural decisions via ADRs.",
            }
        },
        "tactics": {},
        "styleguides": {},
    }


def _minimal_drg_snapshot() -> dict[str, Any]:
    return {
        "nodes": [{"urn": "directive:DIRECTIVE_003", "kind": "directive"}],
        "edges": [],
        "schema_version": "1",
    }


def _request(run_id: str) -> SynthesisRequest:
    target = SynthesisTarget(
        kind="directive",
        slug="mission-type-scope-directive",
        title="Mission Type Scope Directive",
        artifact_id="PROJECT_001",
        source_section="mission_type",
    )
    return SynthesisRequest(
        target=target,
        interview_snapshot=_minimal_interview_snapshot(),
        doctrine_snapshot=_minimal_doctrine_snapshot(),
        drg_snapshot=_minimal_drg_snapshot(),
        run_id=run_id,
        adapter_hints={"language": "python"},
    )


def _fixture_adapter() -> FixtureAdapter:
    # FixtureAdapter() with no explicit fixture_root resolves the canonical
    # tests/charter/fixtures/synthesizer/ root relative to its own module
    # location -- the same root tests/charter/synthesizer/conftest.py's
    # `fixture_adapter` fixture points at.
    return FixtureAdapter()


def _seed_complete_bundle(repo_root: Path) -> None:
    """Materialize ``charter.yaml`` so the #2773 fail-closed preflight passes."""
    charter_yaml = repo_root / ".kittify" / "charter" / "charter.yaml"
    charter_yaml.parent.mkdir(parents=True, exist_ok=True)
    charter_yaml.write_text(
        "schema_version: '2.0.0'\ngovernance: {}\ndirectives: {}\n",
        encoding="utf-8",
    )


def _graph_yaml() -> YAML:
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    return yaml


def _load_graph(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", _graph_yaml().load(path.read_text()))


def _dump_graph(path: Path, data: dict[str, Any]) -> None:
    buffer = io.StringIO()
    _graph_yaml().dump(data, buffer)
    path.write_text(buffer.getvalue())


def _graph_path(repo_root: Path) -> Path:
    return repo_root / ".kittify" / "doctrine" / "graph.yaml"


def _inject_backed_legacy_content(tmp_path: Path) -> None:
    """Append a backed (artifact file present) on-disk-only node+edge.

    Mirrors ``test_synthesize_reconcile.py``'s injection helper: this node is
    a genuine "preserved-but-untargeted" case with a real backing artifact
    file, so it is never orphaned.
    """
    doctrine_dir = tmp_path / ".kittify" / "doctrine"
    graph_path = _graph_path(tmp_path)
    graph = _load_graph(graph_path)
    graph["nodes"].append({"urn": _LEGACY_URN, "kind": "tactic", "label": "Legacy Preference Order Tactic (3270)"})
    graph.setdefault("edges", []).append(
        {
            "source": _LEGACY_URN,
            "target": _LEGACY_EDGE_TARGET,
            "relation": "applies",
            "reason": "Derived from synthesis target 'legacy-preference-order-3270'",
        }
    )
    _dump_graph(graph_path, graph)

    existing_artifact = doctrine_dir / "tactic" / "how-we-apply-directive-003.tactic.yaml"
    legacy_artifact = doctrine_dir / "tactic" / "legacy-preference-order-3270.tactic.yaml"
    legacy_artifact.write_bytes(existing_artifact.read_bytes())

    # Register a manifest + provenance entry so the backing-artifact probe
    # (reconcile._backing_path_by_urn) resolves this URN as BACKED, not
    # orphaned -- mirroring what a real prior synthesis run would have
    # written for it (probing is manifest+provenance-driven, not a raw
    # filename guess; a bare content-file copy alone reads as orphaned).
    rel_content = ".kittify/doctrine/tactic/legacy-preference-order-3270.tactic.yaml"
    rel_prov = ".kittify/charter/provenance/tactic-legacy-preference-order-3270.yaml"
    content_hash = hashlib.sha256(legacy_artifact.read_bytes()).hexdigest()  # noqa: TID251 -- test-only fixture hash, not a production owner

    manifest_path = tmp_path / MANIFEST_PATH
    manifest = load_manifest(manifest_path)
    new_entry = ManifestArtifactEntry(
        kind="tactic",
        slug="legacy-preference-order-3270",
        path=rel_content,
        provenance_path=rel_prov,
        content_hash=content_hash,
    )
    updated_manifest = finalize_manifest(manifest.model_copy(update={"artifacts": [*manifest.artifacts, new_entry]}))
    manifest_path.write_text(canonical_yaml(updated_manifest.model_dump(mode="python")).decode("utf-8"), encoding="utf-8")

    existing_prov_path = tmp_path / ".kittify" / "charter" / "provenance" / "tactic-how-we-apply-directive-003.yaml"
    existing_prov_entry = load_provenance(existing_prov_path)
    legacy_prov_entry = existing_prov_entry.model_copy(
        update={
            "artifact_slug": "legacy-preference-order-3270",
            "artifact_urn": _LEGACY_URN,
            "artifact_content_hash": content_hash,
        }
    )
    (tmp_path / rel_prov).write_bytes(canonical_yaml(legacy_prov_entry.model_dump(mode="python")))


def _inject_orphaned_node(tmp_path: Path) -> None:
    """Append a node+edge with NO backing manifest/provenance/artifact entry.

    Simulates a backing artifact having been deleted: the node survives in
    ``graph.yaml`` but no manifest entry's provenance sidecar resolves to
    its URN, so ``_backing_path_by_urn`` (reconcile.py) reports it unbacked
    (``backing_artifact=None``) -- the narrow FR-014 refusal case.
    """
    graph_path = _graph_path(tmp_path)
    graph = _load_graph(graph_path)
    graph["nodes"].append({"urn": _ORPHAN_URN, "kind": "tactic", "label": "Orphaned Tactic"})
    graph.setdefault("edges", []).append(
        {
            "source": _ORPHAN_URN,
            "target": _ORPHAN_EDGE_TARGET,
            "relation": "applies",
            "reason": "No backing artifact on disk (orphan test fixture)",
        }
    )
    _dump_graph(graph_path, graph)


def _invoke_synthesize(
    tmp_path: Path,
    request: SynthesisRequest,
    syn_adapter: Any,
    extra_args: list[str],
) -> Any:
    """Invoke ``charter synthesize --adapter fixture --json <extra_args>``.

    Mocks only ``find_repo_root``/``_collect_evidence_result``/
    ``_build_synthesis_request`` -- the SAME narrow-mocking convention
    ``tests/charter/test_reject_not_drop_cli.py`` and
    ``tests/agent/cli/commands/test_charter_synthesize_cli.py`` already use
    -- so every WP03-owned reconciliation/reporting code path in
    ``synthesize.py``/``_synthesis.py`` runs for real against *tmp_path*.

    #4785 Finding 3 / WP04 reconciliation: ``synthesize.py`` now also fails
    closed via the WP02 write-root guard (``resolve_charter_write_root``),
    which is probed against the REAL process cwd -- deliberately NOT
    patchable through the ``find_repo_root`` mock above, since the whole
    point of the guard is to catch the case where a real invocation's cwd
    diverges from whatever ``find_repo_root`` resolves to. Without isolating
    cwd here, this helper would spuriously trip the guard whenever the test
    process happens to be running from inside an actual linked git worktree
    (e.g. a spec-kitty lane worktree) -- unrelated to anything this test
    suite exercises. ``tmp_path`` is a plain (non-git) directory, so
    chdir'ing into it makes the guard's kernel ``git_topology`` probe
    degrade safely (not-a-repo -> not-a-linked-worktree, no raise) exactly
    like a real, ordinary checkout would.
    """
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        with (
            patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
            patch(
                "specify_cli.cli.commands.charter._collect_evidence_result",
                return_value=SimpleNamespace(warnings=[], bundle=SimpleNamespace()),
            ),
            patch(
                "specify_cli.cli.commands.charter._build_synthesis_request",
                return_value=(request, syn_adapter),
            ),
        ):
            return runner.invoke(
                charter_app,
                ["synthesize", "--adapter", "fixture", "--json", *extra_args],
                catch_exceptions=False,
            )
    finally:
        os.chdir(old_cwd)


# ---------------------------------------------------------------------------
# 1. --prune removes and lists (with edge atomicity)
# ---------------------------------------------------------------------------


def test_prune_removes_divergent_content_and_lists_each_deletion(tmp_path: Path) -> None:
    adapter = _fixture_adapter()
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=adapter, repo_root=tmp_path)
    _inject_backed_legacy_content(tmp_path)
    _seed_complete_bundle(tmp_path)

    result = _invoke_synthesize(tmp_path, _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"), adapter, ["--prune"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["result"] == "success"
    deletions = payload["deletions"]
    assert any(d["urn"] == _LEGACY_URN and d["ref_kind"] == "node" for d in deletions)
    assert any(d["urn"].startswith(_LEGACY_URN) and d["ref_kind"] == "edge" for d in deletions), (
        "amendment #1: a --prune that removes a node must also list its edges as removed"
    )

    graph = _load_graph(_graph_path(tmp_path))
    node_urns = {n["urn"] for n in graph["nodes"]}
    assert _LEGACY_URN not in node_urns, "--prune must excise the divergent node"
    assert all(e["source"] != _LEGACY_URN for e in graph.get("edges", [])), "amendment #1: --prune must drop the node's edges TOGETHER with the node"


# ---------------------------------------------------------------------------
# 2. --prune no-op (nothing to prune)
# ---------------------------------------------------------------------------


def test_prune_with_nothing_to_prune_is_a_noop(tmp_path: Path) -> None:
    adapter = _fixture_adapter()
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=adapter, repo_root=tmp_path)
    _seed_complete_bundle(tmp_path)

    result = _invoke_synthesize(tmp_path, _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"), adapter, ["--prune"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["result"] == "success"
    assert payload["deletions"] == []


# ---------------------------------------------------------------------------
# 3. --dry-run on a superset overlay -> non-empty planned_deletes, no write
# ---------------------------------------------------------------------------


def test_dry_run_reports_nonempty_planned_deletes_and_writes_nothing(tmp_path: Path) -> None:
    adapter = _fixture_adapter()
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=adapter, repo_root=tmp_path)
    _inject_backed_legacy_content(tmp_path)
    _seed_complete_bundle(tmp_path)

    graph_before = _graph_path(tmp_path).read_bytes()
    manifest_before = (tmp_path / MANIFEST_PATH).read_bytes()

    result = _invoke_synthesize(tmp_path, _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"), adapter, ["--dry-run"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["result"] == "dry_run"
    planned = payload["planned_deletes"]
    assert any(d["urn"] == _LEGACY_URN for d in planned), planned

    assert _graph_path(tmp_path).read_bytes() == graph_before, "--dry-run must not write graph.yaml"
    assert (tmp_path / MANIFEST_PATH).read_bytes() == manifest_before, "--dry-run must not write the manifest"


# ---------------------------------------------------------------------------
# 4. --dry-run with no divergence -> empty planned_deletes
# ---------------------------------------------------------------------------


def test_dry_run_reports_empty_planned_deletes_when_no_divergence(tmp_path: Path) -> None:
    adapter = _fixture_adapter()
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=adapter, repo_root=tmp_path)
    _seed_complete_bundle(tmp_path)

    result = _invoke_synthesize(tmp_path, _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"), adapter, ["--dry-run"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["result"] == "dry_run"
    assert payload["planned_deletes"] == []


# ---------------------------------------------------------------------------
# 5. Orphaned removal without --prune refuses (with edge-retention atomicity)
# ---------------------------------------------------------------------------


def test_orphaned_removal_without_prune_refuses_with_remediation(tmp_path: Path) -> None:
    adapter = _fixture_adapter()
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=adapter, repo_root=tmp_path)
    _inject_orphaned_node(tmp_path)
    _seed_complete_bundle(tmp_path)

    result = _invoke_synthesize(tmp_path, _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"), adapter, [])

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["result"] == "failure"
    warnings = " ".join(payload["warnings"])
    assert _ORPHAN_URN in warnings
    assert "--prune" in warnings, "refusal must name the remediation (--prune)"
    assert "orphaned" in warnings.lower()

    # Refusal path: the orphan node AND its edge are retained TOGETHER
    # (amendment #1's counterpart to the prune-path atomicity assertion).
    # Preserve mode never deletes anything (orphaned or not, see
    # reconcile.merge_project_overlay), so the underlying write this run
    # performed is non-destructive -- "refused" means the operator is
    # flagged to decide (--prune or restore the artifact), not that
    # graph.yaml is byte-identical to before the run.
    graph = _load_graph(_graph_path(tmp_path))
    node_urns = {n["urn"] for n in graph["nodes"]}
    assert _ORPHAN_URN in node_urns
    assert any(e["source"] == _ORPHAN_URN for e in graph.get("edges", [])), "the orphan node's edge must still be present alongside the node"


# ---------------------------------------------------------------------------
# 6. Unparseable graph.yaml refuses (exit 1, no write)
# ---------------------------------------------------------------------------


def test_corrupt_overlay_refuses_with_actionable_message_and_no_write(tmp_path: Path) -> None:
    adapter = _fixture_adapter()
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=adapter, repo_root=tmp_path)
    _seed_complete_bundle(tmp_path)

    manifest_before = (tmp_path / MANIFEST_PATH).read_bytes()
    _graph_path(tmp_path).write_text("schema_version: '1.0'\nnodes: [\n  {urn: broken\n", encoding="utf-8")

    result = _invoke_synthesize(tmp_path, _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"), adapter, [])

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["result"] == "failure"
    warnings = " ".join(payload["warnings"])
    assert "Refused" in warnings
    assert "No write was made" in warnings

    assert (tmp_path / MANIFEST_PATH).read_bytes() == manifest_before, "a corrupt-overlay refusal must not rewrite the manifest"


# ---------------------------------------------------------------------------
# 7. Backed divergence (plain run) -> exit 0, preserved, warning surfaced
# ---------------------------------------------------------------------------


def test_backed_divergence_plain_run_preserves_and_warns(tmp_path: Path) -> None:
    adapter = _fixture_adapter()
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=adapter, repo_root=tmp_path)
    _inject_backed_legacy_content(tmp_path)
    _seed_complete_bundle(tmp_path)

    result = _invoke_synthesize(tmp_path, _request("01BBBBBBBBBBBBBBBBBBBBBBBBB"), adapter, [])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["result"] == "success"
    retained = payload["retained"]
    assert any(r["urn"] == _LEGACY_URN for r in retained), retained

    graph = _load_graph(_graph_path(tmp_path))
    node_urns = {n["urn"] for n in graph["nodes"]}
    assert _LEGACY_URN in node_urns, "backed divergence must be preserved, never dropped, on a plain run"


# ---------------------------------------------------------------------------
# 8. Amendment #3 -- sentinel coercion
# ---------------------------------------------------------------------------


class _FakeOptionInfoSentinel:
    """Stand-in for the ``typer.OptionInfo`` object an in-process caller that
    omits ``prune``/``dry_run`` would receive as the Python-level default
    (see ``_coerce_cli_bool``'s docstring)."""


def test_coerce_cli_bool_passes_through_real_booleans() -> None:
    assert _coerce_cli_bool(True) is True
    assert _coerce_cli_bool(False) is False


def test_coerce_cli_bool_coerces_non_bool_sentinel_to_false() -> None:
    sentinel = _FakeOptionInfoSentinel()
    assert _coerce_cli_bool(cast("bool", sentinel)) is False
    assert _coerce_cli_bool(cast("bool", None)) is False
    assert _coerce_cli_bool(cast("bool", "truthy-string")) is False


# ---------------------------------------------------------------------------
# SynthesizeMode import sanity (guards against a stale re-export drifting
# out from under this test module's own imports).
# ---------------------------------------------------------------------------


def test_synthesize_mode_import_is_the_canonical_enum() -> None:
    assert {m.value for m in SynthesizeMode} == {"preserve", "prune", "dry_run"}
