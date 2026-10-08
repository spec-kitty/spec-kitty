"""End-to-end synthesis visibility tests for compiler/context consumers.

These tests exercise the real synthesis pipeline rather than writing fake
project doctrine files by hand. That keeps FR-018 / SC-005 honest: the charter
consumers should only see project-local doctrine after a successful synthesis.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from charter.activation._project_root_candidates import resolve_project_root
from charter.activation.compiler import _default_active_charter_service
from charter.activation.context import _build_offering_service
from charter.activation.synthesizer import FixtureAdapter, SynthesisRequest, SynthesisTarget, synthesize


pytestmark = [pytest.mark.unit]

@pytest.fixture
def fixture_root() -> Path:
    return Path(__file__).parent.parent / "fixtures" / "synthesizer"


@pytest.fixture
def adapter(fixture_root: Path) -> FixtureAdapter:
    return FixtureAdapter(fixture_root=fixture_root)


@pytest.fixture
def synthesis_request() -> SynthesisRequest:
    interview_snapshot: dict[str, Any] = {
        "mission_type": "software_dev",
        "language_scope": ["python"],
        "testing_philosophy": "test-driven development with high coverage",
        "neutrality_posture": "balanced",
        "selected_directives": ["DIRECTIVE_003"],
        "risk_appetite": "moderate",
    }
    doctrine_snapshot: dict[str, Any] = {
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
    drg_snapshot: dict[str, Any] = {
        "nodes": [
            {"urn": "directive:DIRECTIVE_003", "kind": "directive"}
        ],
        "edges": [],
        "schema_version": "1",
    }
    return SynthesisRequest(
        target=SynthesisTarget(
            kind="directive",
            slug="mission-type-scope-directive",
            title="Mission Type Scope Directive",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        ),
        interview_snapshot=interview_snapshot,
        doctrine_snapshot=doctrine_snapshot,
        drg_snapshot=drg_snapshot,
        run_id="01KPE222CD1MMCYEGB3ZCY51VR",
        adapter_hints={"language": "python"},
    )


def _project_directive_ids(service: Any) -> set[str]:
    """Return PROJECT_-prefixed directive ids visible on *service*.

    *service* is either the raw ``charter.offering.service.CharterOfferingService``
    returned by ``charter.activation.context._build_offering_service`` (``.directives``
    is the repository itself, with ``.list_all()``) or, since WP03
    (charter-sole-door-bypass-closure-01KZ3WAA, FR-002/T011),
    ``charter.activation.compiler._default_active_charter_service``'s activation-aware
    ``charter.activation.resolver.ActiveCharterService`` wrapper (``.directives`` is a
    gated, filtered ``dict`` with no ``.list_all()``). The wrapper's
    ``raw_repository(kind)`` accessor (FR-002 Option A) is the sanctioned
    way to reach the raw repository either way, so this helper prefers it
    when present and falls back to plain attribute access for the raw
    (unwrapped) service.
    """
    raw_repository = getattr(service, "raw_repository", None)
    directives_repo = raw_repository("directives") if callable(raw_repository) else service.directives
    return {
        directive.id
        for directive in directives_repo.list_all()
        if directive.id.startswith("PROJECT_")
    }


def test_no_project_root_before_synthesis(tmp_path: Path) -> None:
    assert resolve_project_root(tmp_path) is None


def test_synthesis_creates_project_doctrine_root(
    tmp_path: Path,
    synthesis_request: SynthesisRequest,
    adapter: FixtureAdapter,
) -> None:
    synthesize(synthesis_request, adapter=adapter, repo_root=tmp_path)
    assert resolve_project_root(tmp_path) == tmp_path / ".kittify" / "charter-packs"


def test_compiler_service_reflects_project_directives_after_synthesis(
    tmp_path: Path,
    synthesis_request: SynthesisRequest,
    adapter: FixtureAdapter,
) -> None:
    # ``_default_active_charter_service`` routes through
    # ``build_active_charter_service``, which calls
    # ``PackContext.from_config(tmp_path)`` whenever a repo_root is supplied.
    # ``mission_type_activations`` is provisioned so that call (WP04, C-A1:
    # the provisioned charter is the sole activation authority for mission
    # types) does not hard-fail on a genuinely absent key -- unrelated to
    # this test's own subject (post-synthesis project-directive visibility).
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )

    before_ids = _project_directive_ids(_default_active_charter_service(tmp_path))
    assert before_ids == set()

    synthesize(synthesis_request, adapter=adapter, repo_root=tmp_path)

    after_ids = _project_directive_ids(_default_active_charter_service(tmp_path))
    assert after_ids - before_ids, "Expected synthesis to surface at least one project directive"


def test_context_service_reflects_project_directives_after_synthesis(
    tmp_path: Path,
    synthesis_request: SynthesisRequest,
    adapter: FixtureAdapter,
) -> None:
    before_ids = _project_directive_ids(_build_offering_service(tmp_path))
    assert before_ids == set()

    synthesize(synthesis_request, adapter=adapter, repo_root=tmp_path)

    after_ids = _project_directive_ids(_build_offering_service(tmp_path))
    assert after_ids - before_ids, "Expected context service to expose project-local doctrine after synthesis"
