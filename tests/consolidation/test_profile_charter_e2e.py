"""End-to-end integration for profile-aware charter compilation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from ruamel.yaml import YAML
from typer.testing import CliRunner

import pytest

from charter.offering.service import DoctrineService
from specify_cli.cli.commands.charter import app
from charter.activation.catalog import DoctrineCatalog
from charter.activation.compiler import compile_charter, write_compiled_charter

from charter.activation.interview import (
    LocalSupportDeclaration,
    apply_answer_overrides,
    default_interview,
)
from charter.activation.resolver import resolve_governance_for_profile

runner = CliRunner()
pytestmark = [pytest.mark.non_sandbox, pytest.mark.integration, pytest.mark.git_repo]
def _write_yaml(path: Path, data: dict[object, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)


def test_profile_aware_charter_compilation_resolves_transitive_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ``built_in_root`` still simulates the doctrine root ``resolve_doctrine_root``
    # is patched to return below (missions/ and the synthetic graph.yaml -- both
    # unrelated to the WP04 DoctrineService seam). The directive/tactic/
    # styleguide/agent_profile content DoctrineService itself resolves lives in
    # a SEPARATE flat ``packs/built-in/<kind>/`` tree, injected via
    # SPEC_KITTY_PACKS_ROOT (the removed built_in_root= param's replacement).
    built_in_root = tmp_path / "doctrine"
    packs_root = tmp_path / "packs"
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
    output_dir = tmp_path / "repo" / ".kittify" / "charter"

    _write_yaml(
        packs_root / "built-in" / "directives" / "001-review.directive.yaml",
        {
            "schema_version": "1.0",
            "id": "REVIEW_FIRST",
            "title": "Review First",
            "intent": "Review code thoroughly.",
            "enforcement": "required",
            # Post-WP02: inline `tactic_refs` removed; WP03 promoted the
            # former inline chains to DRG edges (see the graph.yaml
            # fixture below).
        },
    )
    _write_yaml(
        packs_root / "built-in" / "tactics" / "review-tactic.tactic.yaml",
        {
            "schema_version": "1.0",
            "id": "review-tactic",
            "name": "Review Tactic",
            "purpose": "Drive review workflows.",
            "steps": [
                {
                    "title": "Review the change",
                    "description": "Inspect the implementation carefully.",
                    "references": [
                        {
                            "name": "Review Style",
                            "type": "styleguide",
                            "id": "review-style",
                            "when": "Always",
                        }
                    ],
                }
            ],
            "references": [],
        },
    )
    _write_yaml(
        packs_root / "built-in" / "styleguides" / "review-style.styleguide.yaml",
        {
            "schema_version": "1.0",
            "id": "review-style",
            "title": "Review Style",
            "scope": "code",
            "principles": ["Be precise"],
        },
    )
    _write_yaml(
        packs_root / "built-in" / "directives" / "002-interview.directive.yaml",
        {
            "schema_version": "1.0",
            "id": "INTERVIEW_ONLY",
            "title": "Interview Directive",
            "intent": "Interview-selected directive.",
            "enforcement": "advisory",
            # Post-WP02: inline `tactic_refs` removed from the Directive model.
        },
    )
    _write_yaml(
        packs_root / "built-in" / "agent_profiles" / "reviewer.agent.yaml",
        {
            "profile-id": "reviewer",
            "name": "Reviewer",
            "role": "reviewer",
            "purpose": "Review changes.",
            "specialization": {
                "primary-focus": "review",
                "secondary-awareness": "code quality",
                "avoidance-boundary": "implementation",
                "success-definition": "find issues before merge",
            },
            "directive-references": [
                {"code": "REVIEW_FIRST", "name": "Review First", "rationale": "Review every change."}
            ],
        },
    )
    _write_yaml(
        built_in_root / "missions" / "software-dev" / "mission.yaml",
        {
            "name": "software-dev",
            "description": "Software development mission.",
        },
    )
    # Post `resolution-activation-foundation` (unified single-PACKS_ROOT read):
    # ``MissionTemplateRepository.default_missions_root()`` now resolves the
    # ``missions`` leaf from ``SPEC_KITTY_PACKS_ROOT`` (``packs/built-in/missions``),
    # not the patched ``resolve_doctrine_root``. ``default_interview`` below reads
    # it before the ``resolve_doctrine_root`` patch is even applied, so mirror the
    # mission template under the packs root or it fails closed with
    # ``MissionsRootNotFound``.
    _write_yaml(
        packs_root / "built-in" / "missions" / "software-dev" / "mission.yaml",
        {
            "name": "software-dev",
            "description": "Software development mission.",
        },
    )
    # Post-WP03: the DRG graph is the sole authority for transitive
    # reference chains. Materialize a synthetic graph.yaml that mirrors the
    # pre-WP02 inline topology (REVIEW_FIRST -> review-tactic; review-tactic
    # -> review-style).
    _write_yaml(
        built_in_root / "graph.yaml",
        {
            "schema_version": "1.0",
            "generated_at": "2026-04-14T00:00:00Z",
            "generated_by": "test",
            # Post-#2526: config-activated agent_profiles are DRG BFS roots
            # (reject-not-drop, #2530), so the profile MUST be a first-class
            # graph node like production's generated graph.yaml emits — with a
            # `requires` edge to each directive it references. A fixture that
            # omits the node makes the profile an unknown start URN, which the
            # resolver correctly records as unresolved.
            "nodes": [
                {"urn": "directive:REVIEW_FIRST", "kind": "directive"},
                {"urn": "directive:INTERVIEW_ONLY", "kind": "directive"},
                {"urn": "tactic:review-tactic", "kind": "tactic"},
                {"urn": "styleguide:review-style", "kind": "styleguide"},
                {"urn": "agent_profile:reviewer", "kind": "agent_profile"},
            ],
            "edges": [
                {
                    "source": "directive:REVIEW_FIRST",
                    "target": "tactic:review-tactic",
                    "relation": "requires",
                },
                {
                    "source": "tactic:review-tactic",
                    "target": "styleguide:review-style",
                    "relation": "requires",
                },
                {
                    "source": "agent_profile:reviewer",
                    "target": "directive:REVIEW_FIRST",
                    "relation": "requires",
                },
            ],
        },
    )

    doctrine_service = DoctrineService()
    doctrine_catalog = DoctrineCatalog(
        paradigms=frozenset(),
        directives=frozenset({"REVIEW_FIRST", "INTERVIEW_ONLY"}),
        template_sets=frozenset({"software-dev-default"}),
        tactics=frozenset({"review-tactic"}),
        styleguides=frozenset({"review-style"}),
        toolguides=frozenset(),
        procedures=frozenset(),
        agent_profiles=frozenset({"reviewer"}),
    )
    interview = default_interview(mission="software-dev", profile="minimal")
    interview = apply_answer_overrides(
        interview,
        selected_paradigms=[],
        selected_directives=["INTERVIEW_ONLY"],
    )

    # Load the fixture graph explicitly so resolve_governance_for_profile
    # does not attempt to read the installed doctrine package.
    from charter.offering.drg.loader import load_graph, merge_layers
    from charter.offering.drg.validator import assert_valid

    drg = merge_layers(load_graph(built_in_root / "graph.yaml"), None)
    assert_valid(drg)

    resolution = resolve_governance_for_profile(
        "reviewer",
        "reviewer",
        doctrine_service,
        interview,
        graph=drg,
    )
    # Monkey-patch resolve_doctrine_root so the compiler's DRG lookup
    # targets the same synthetic built_in_root as the resolver. The
    # compiler imports the function into its own namespace, so we patch
    # the binding there.
    #
    # The compiler resolves the *built-in DRG graph* through a SECOND,
    # deliberately-separate seam: ``charter.offering.drg.loader.load_built_in_graph``
    # (via ``built_in_graph_source`` -> ``files("charter.offering")``). That seam does
    # NOT consult ``resolve_doctrine_root`` -- doctrine sits below charter in
    # the dependency graph (C-004) and must not import upward. Without patching
    # it, the compiler's transitive walk loads the *installed* package graph,
    # where none of the synthetic fixture URNs exist, and every start URN is
    # recorded as an unresolved reference. Patch it to the same synthetic graph
    # the resolver used so both seams agree.
    with patch(
        "charter.activation.compiler.resolve_doctrine_root",
        return_value=built_in_root,
    ), patch(
        "charter.offering.drg.loader.load_built_in_graph",
        return_value=drg,
    ):
        compiled = compile_charter(
            mission="software-dev",
            interview=apply_answer_overrides(
                interview,
                selected_directives=resolution.directives,
                agent_profile=resolution.profile_id,
                agent_role=resolution.role,
            ),
            doctrine_catalog=doctrine_catalog,
            doctrine_service=doctrine_service,
        )
    result = write_compiled_charter(output_dir, compiled, force=True)

    assert resolution.directives == ["REVIEW_FIRST", "INTERVIEW_ONLY"]
    assert resolution.tactics == ["review-tactic"]
    assert resolution.styleguides == ["review-style"]
    assert compiled.diagnostics == []
    assert "charter.yaml" in result.files_written  # consolidate-charter-bundle: write_compiled_charter no longer emits charter.md (INV-3)
    assert "agent_profile: reviewer" in compiled.markdown
    assert any(ref.kind == "tactic" and ref.title == "Review Tactic" for ref in compiled.references)
    assert any(ref.kind == "styleguide" and ref.title == "Review Style" for ref in compiled.references)


# ---------------------------------------------------------------------------
# T037: End-to-end scenario — explicit local support declarations
# ---------------------------------------------------------------------------


def _make_interview_yaml(path: Path, local_files: list[dict[str, str]]) -> None:
    """Write a minimal answers.yaml with optional local_supporting_files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {
        "schema_version": "1.0.0",
        "mission": "software-dev",
        "profile": "minimal",
        "answers": {
            "project_intent": "Demonstrate local support declarations.",
            "languages_frameworks": "Python 3.11+",
            "testing_requirements": "pytest",
            "quality_gates": "tests pass",
            "review_policy": "1 reviewer",
            "performance_targets": "N/A",
            "deployment_constraints": "Linux",
        },
        "selected_paradigms": [],
        "selected_directives": ["DIRECTIVE_003"],
        "available_tools": ["git"],
    }
    if local_files:
        data["local_supporting_files"] = local_files

    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)


def test_local_support_declarations_end_to_end(tmp_path: Path) -> None:
    """Full scenario: interview with local support → generate → context (2x) → additive warning."""
    import subprocess

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # Charter bundle chokepoint (PR #634) now resolves the project root via
    # `git rev-parse --git-common-dir` — initialise a minimal git repo so the
    # canonical-root resolver doesn't raise NotInsideRepositoryError.
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    interview_dir = charter_dir / "interview"

    # ── Step 1: write answers.yaml with an explicit local support declaration ──
    _make_interview_yaml(
        interview_dir / "answers.yaml",
        local_files=[{"path": "docs/team-guide.md"}],
    )

    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_root:
        mock_root.return_value = repo_root

        # ── Step 2: generate charter from interview answers ──
        gen_result = runner.invoke(app, ["generate", "--json"])
        assert gen_result.exit_code == 0, gen_result.stdout
        payload = json.loads(gen_result.stdout)
        assert payload["result"] == "success"

        # ── Step 3: library_files lists declared paths, NOT a library/ directory ──
        assert "docs/team-guide.md" in payload["library_files"]
        assert not (charter_dir / "library").exists(), "library/ directory must NOT be materialised on disk"

        # ── Step 4: agents.yaml must NOT be generated ──
        assert not (charter_dir / "agents.yaml").exists(), "agents.yaml must NOT be generated"

        # consolidate-charter-bundle (data-model.md Landmine 3, T028c):
        # ``generate`` writes charter.yaml ONLY -- charter.md is a curated,
        # hand-authored companion, NEVER produced by a generate/compile path
        # (INV-3). ``build_charter_context``'s bootstrap/compact caching
        # keys on charter.md's existence, so exercising that caching
        # end-to-end (this test's actual subject, per its docstring) now
        # requires the curated companion to exist -- exactly as a real
        # operator would author it once, post-generate.
        (charter_dir / "charter.md").write_text(
            "# Project Charter\n\n## Policy Summary\n\n- Curated companion authored post-generate.\n",
            encoding="utf-8",
        )

        # ── Step 5: first context call → bootstrap mode ──
        ctx1 = runner.invoke(app, ["context", "--action", "specify", "--json"])
        assert ctx1.exit_code == 0, ctx1.stdout
        ctx1_data = json.loads(ctx1.stdout)
        assert ctx1_data["mode"] == "bootstrap"
        assert ctx1_data["first_load"] is True
        assert "context" in ctx1_data
        assert ctx1_data["context"]  # non-empty

        # ── Step 6: second context call → compact mode (cached) ──
        ctx2 = runner.invoke(app, ["context", "--action", "specify", "--json"])
        assert ctx2.exit_code == 0, ctx2.stdout
        ctx2_data = json.loads(ctx2.stdout)
        assert ctx2_data["mode"] == "compact"
        assert ctx2_data["first_load"] is False
        assert "context" in ctx2_data
        assert ctx2_data["context"]  # non-empty


def test_local_support_additive_warning_when_overlapping_built_in_concept(tmp_path: Path) -> None:
    """Local file targeting a shipped concept produces an additive warning diagnostic."""
    output_dir = tmp_path / ".kittify" / "charter"

    interview = default_interview(mission="software-dev", profile="minimal")
    # Select DIRECTIVE_003 so it appears in shipped references; declare a local
    # file that explicitly targets it to trigger the overlap check.
    interview = apply_answer_overrides(
        interview,
        selected_directives=["DIRECTIVE_003"],
        local_supporting_files=[
            LocalSupportDeclaration(
                path="docs/directive-003-notes.md",
                action=None,
                target_kind="directive",
                target_id="DIRECTIVE_003",
            )
        ],
    )

    compiled = compile_charter(mission="software-dev", interview=interview)

    # Must have exactly one additive warning diagnostic
    overlap_warnings = [d for d in compiled.diagnostics if "overlaps built-in" in d]
    assert overlap_warnings, "Expected an additive-overlap diagnostic when local file targets a shipped directive"
    assert "DIRECTIVE_003" in overlap_warnings[0]

    # Local support reference must still appear in the bundle
    local_refs = [r for r in compiled.references if r.kind == "local_support"]
    assert local_refs, "Local support reference must be included despite overlap warning"
    assert any("directive-003-notes.md" in r.source_path for r in local_refs)

    # Verify the reference carries the additive relationship label
    local_ref_content = local_refs[0].content
    assert "additive" in local_ref_content.lower()

    # Write to disk and confirm no library/ directory is created
    result = write_compiled_charter(output_dir, compiled, force=True)
    assert "charter.yaml" in result.files_written  # consolidate-charter-bundle: write_compiled_charter no longer emits charter.md (INV-3)
    assert not (output_dir / "library").exists(), (
        "library/ directory must NOT be created even when local support files are declared"
    )
