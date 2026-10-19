"""Golden snapshot: what a synthesized Kotlin and TypeScript project has in force.

The golden (``fixtures/synthesized_in_force_snapshot.json``) freezes the combined
delivery change of the charter-synthesis-graph-and-languages Mission for a
project whose charter was synthesized from testing, quality-gate and
documentation answers:

* the in-force sets and the per-action styleguides delivered to software-dev
  ``implement`` and ``review`` (synthesized styleguides are reach-only, so they
  arrive through the directive that elaborates them);
* the label of the always-synthesized project-intent directive;
* the multi-language evidence ``languages`` of a Kotlin and TypeScript repository.

``tests/charter/test_default_in_force_snapshot.py`` stays the guard of the bare,
unsynthesized default. Regenerate this golden only for a deliberate change, with
``UPDATE_SNAPSHOT=1``, and review the diff.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest
import yaml

from charter.activation.action_governance_bundle import _load_action_governance_bundle
from charter.activation.evidence.code_reader import CodeReadingCollector
from charter.activation.pack_context import PackContext
from charter.activation.resolver import resolve_project_governance
from charter.activation.synthesizer import SynthesisRequest, SynthesisTarget, synthesize
from charter.activation.synthesizer.adapter import AdapterOutput
from kernel.clock import UTC, datetime

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_GOLDEN = Path(__file__).parent / "fixtures" / "synthesized_in_force_snapshot.json"
_ACTIONS = ("implement", "review")
_DEPTHS = (1, 2)
_SLOTS = ("directive_ids", "tactic_ids", "styleguide_ids")
_GENERATED_AT = datetime(2026, 10, 19, 0, 0, 0, tzinfo=UTC)

_INTERVIEW: dict[str, Any] = {
    "mission_type": "software_dev",
    "language_scope": ["kotlin", "typescript"],
    "testing_philosophy": "test-first with mutation testing on the domain core",
    "quality_gates": "ktlint, detekt and eslint clean before review",
    "documentation_policy": "every public API documented with examples",
}
_STYLEGUIDE_SCOPES = {
    "testing-style-guide": "testing",
    "documentation-policy-style-guide": "docs",
}
_SOURCE_DIRECTIVES = ("DIRECTIVE_030", "DIRECTIVE_034", "DIRECTIVE_037")


class _DeterministicAdapter:
    """Offline adapter producing a schema-valid body per target kind, from the slug alone."""

    id = "snapshot-fixture"
    version = "1.0.0"

    def generate(self, request: SynthesisRequest) -> AdapterOutput:
        target = request.target
        title = target.title or target.slug
        body: dict[str, Any]
        if target.kind == "directive":
            body = {
                "id": target.artifact_id,
                "schema_version": "1.0",
                "title": title,
                "intent": f"Intent of {target.slug}.",
                "enforcement": "required",
                "scope": "All project work.",
                "procedures": [f"Follow {target.slug}."],
            }
        elif target.kind == "tactic":
            body = {
                "id": target.slug,
                "schema_version": "1.0",
                "name": title,
                "purpose": f"Purpose of {target.slug}.",
                "steps": [{"title": "Apply", "description": f"Apply {target.slug}."}],
            }
        else:
            body = {
                "id": target.slug,
                "schema_version": "1.0",
                "title": title,
                "scope": _STYLEGUIDE_SCOPES.get(target.slug, "code"),
                "principles": [f"Principle of {target.slug}."],
            }
        return AdapterOutput(body=body, generated_at=_GENERATED_AT)


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("synthesized-project")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _write(root / ".kittify" / "config.yaml", "mission_type_activations:\n  - software-dev\n")
    _write(root / "build.gradle.kts", 'plugins { kotlin("jvm") }\n')
    for name in ("Domain", "Service", "Repository"):
        _write(root / "src" / "main" / "kotlin" / f"{name}.kt", f"class {name}\n")
    _write(root / "web" / "package.json", "{}\n")
    for name in ("app", "client"):
        _write(root / "web" / "src" / f"{name}.ts", f"export const {name} = 1;\n")
    request = SynthesisRequest(
        target=SynthesisTarget(
            kind="directive",
            slug="project-intent-directive",
            title="Project Intent Directive",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        ),
        interview_snapshot=_INTERVIEW,
        doctrine_snapshot={"directives": {}, "tactics": {}, "styleguides": {}},
        drg_snapshot={
            "schema_version": "1",
            "nodes": [{"urn": f"directive:{directive}", "kind": "directive"} for directive in _SOURCE_DIRECTIVES],
            "edges": [],
        },
        run_id="01KYSNAPSHOT0000000000000A",
        adapter_hints={"language": "kotlin"},
    )
    synthesize(request, adapter=_DeterministicAdapter(), repo_root=root)
    return root


def _delivered(root: Path, action: str, depth: int) -> dict[str, list[str]]:
    bundle = _load_action_governance_bundle(
        repo_root=root,
        action=action,
        effective_depth=depth,
        pack_context=PackContext.from_config(root),
        mission_type="software-dev",
    )
    return {slot.removesuffix("_ids"): sorted(getattr(bundle, slot)) for slot in _SLOTS}


def _synthesized_ids(root: Path) -> dict[str, list[str]]:
    manifest = yaml.safe_load((root / ".kittify" / "charter" / "synthesis-manifest.yaml").read_text(encoding="utf-8"))
    by_kind: dict[str, list[str]] = {}
    for artifact in manifest["artifacts"]:
        by_kind.setdefault(artifact["kind"], []).append(artifact["slug"])
    return {kind: sorted(slugs) for kind, slugs in sorted(by_kind.items())}


def _project_intent_label(root: Path) -> list[Mapping[str, Any]]:
    graph = yaml.safe_load((root / ".kittify" / "charter-packs" / "graph.yaml").read_text(encoding="utf-8"))
    return [node for node in graph["nodes"] if "intent" in str(node.get("urn", "")).lower() or "PROJECT_001" in str(node.get("urn", ""))]


def _snapshot(root: Path) -> dict[str, Any]:
    governance = json.loads(json.dumps(asdict(resolve_project_governance(root)), sort_keys=True, default=sorted))
    return {
        "synthesized": _synthesized_ids(root),
        "project_intent_nodes": _project_intent_label(root),
        "governance": governance,
        "bundles": {action: {str(depth): _delivered(root, action, depth) for depth in _DEPTHS} for action in _ACTIONS},
        "evidence_languages": list(CodeReadingCollector(root).collect().languages),
    }


def _dump(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def test_synthesized_in_force_matches_golden(project: Path) -> None:
    actual = json.loads(_dump(_snapshot(project)))
    if os.environ.get("UPDATE_SNAPSHOT") == "1":
        _GOLDEN.write_text(_dump(actual), encoding="utf-8")
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    assert actual == golden
