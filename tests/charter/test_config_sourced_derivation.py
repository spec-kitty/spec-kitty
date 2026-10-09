"""Unit tests for the config-sourced doctrine derivation switch (WP02, FR-001/FR-002).

Covers both derivation paths the mission's IC-01 slice repoints from
``answers.selected_*`` to ``config.activated_*``:

- ``charter.activation.compiler.compile_charter`` / ``_build_references_from_service``
  -- the compiled reference set (``references.yaml``) path.
- ``specify_cli.cli.commands.charter._synthesis._build_synthesis_request``
  -- the project-graph (``interview_snapshot``/``drg_snapshot``) path.

Plus the two squad LAND-BLOCKER requirements pinned as regression tests:

- **T026 direct roots**: a kind activated directly in
  ``config.activated_styleguides``/``activated_toolguides`` (and the
  remaining directly-activatable kinds -- tactics, procedures, agent
  profiles) resolves in the compiled set even when no selected directive's
  transitive closure reaches it (the real #2524 baseline danglers
  ``aggregate-design-rules`` / ``contextive`` are exercised directly).
- **Reject-not-drop**: an unresolvable ``config.activated_*`` stem raises
  (via WP01's ``resolve_artifact_urn``), closing the C-006 silent-drop
  vector that ``_sanitize_catalog_selection`` left open for the retired
  answers-sourced path.

This module is UNIT-level per the WP02 prompt: it does not regenerate or
assert against the committed ``references.yaml``/``graph.yaml`` artefacts
(that is WP03's IC-01-consequence slice).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.catalog import load_offering_catalog
from charter.activation.compiler import (
    ConfigActivatedRoots,
    compile_charter,
    resolve_config_activated_roots,
)
from charter.activation.interview import (
    CharterInterview,
    apply_answer_overrides,
    default_interview,
    write_interview_answers,
)
from charter.activation.catalog import resolve_offering_root
from charter.activation.kind_vocabulary import UnknownArtifactIdError
from charter.activation.pack_context import PackContext

pytestmark = [pytest.mark.fast, pytest.mark.unit]


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #

_ALL_ACTIVATED_KINDS = frozenset(
    {
        "directives",
        "tactics",
        "styleguides",
        "toolguides",
        "paradigms",
        "procedures",
        "agent_profiles",
        "mission_step_contracts",
    }
)


def _base_pack_context(tmp_path: Path) -> PackContext:
    """A ``PackContext`` with every per-kind activation left at the default (``None``)."""
    return PackContext(
        activated_kinds=_ALL_ACTIVATED_KINDS,
        activated_mission_types=frozenset({"software-dev"}),
        pack_roots=(),
        org_pack_names=(),
        repo_root=tmp_path,
    )


def _interview_with(**overrides: object) -> CharterInterview:
    interview = default_interview(mission="software-dev", profile="minimal")
    return dataclasses.replace(interview, **overrides)


def _write_yaml(path: Path, data: dict[str, object]) -> None:
    """Write *data* as YAML to *path*, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)


# --------------------------------------------------------------------------- #
# compile_charter: config is the source, interview.selected_* is inert
# --------------------------------------------------------------------------- #


def test_compiled_directives_come_from_config_not_interview() -> None:
    """FR-001/FR-002: compiled directives are config.activated_directives, not answers."""
    interview = _interview_with(selected_directives=["DIRECTIVE_003"], selected_paradigms=[])
    pack_context = dataclasses.replace(
        _base_pack_context(Path(".")),
        activated_directives=frozenset({"010-specification-fidelity-requirement"}),
    )

    compiled = compile_charter(mission="software-dev", interview=interview, pack_context=pack_context)

    assert compiled.selected_directives == ["DIRECTIVE_010"]
    assert "DIRECTIVE_003" not in compiled.selected_directives
    assert "Specification Fidelity Requirement (`DIRECTIVE_010`)" in compiled.markdown
    # The interview's own selection never appears in the rendered directive body.
    assert "Decision Documentation Requirement (`DIRECTIVE_003`)" not in compiled.markdown


def test_compiled_paradigms_come_from_config_not_interview() -> None:
    """Editing answers.selected_paradigms without a config change has no effect (SC-004 precursor)."""
    interview = _interview_with(selected_paradigms=["deep-module-design"], selected_directives=[])
    pack_context = dataclasses.replace(
        _base_pack_context(Path(".")),
        activated_directives=frozenset(),
        activated_paradigms=frozenset({"domain-driven-design"}),
    )

    compiled = compile_charter(mission="software-dev", interview=interview, pack_context=pack_context)

    assert compiled.selected_paradigms == ["domain-driven-design"]
    assert "deep-module-design" not in compiled.selected_paradigms
    assert any(ref.id == "PARADIGM:domain-driven-design" for ref in compiled.references)


def test_no_pack_context_and_no_repo_root_defaults_to_all_builtins_active() -> None:
    """Absent-key semantics: no project config at all -> every built-in directive is active.

    Mirrors the three-state default already documented on
    :class:`~charter.activation.pack_context.PackContext` (``None`` -> "all built-ins
    available"), which is also what ``charter.activation.resolver`` already applies when
    filtering paradigms/procedures/agent profiles.
    """
    interview = _interview_with(selected_directives=["DIRECTIVE_003"], selected_paradigms=[])
    catalog = load_offering_catalog()

    compiled = compile_charter(mission="software-dev", interview=interview)

    assert sorted(compiled.selected_directives) == sorted(catalog.directives)
    assert "DIRECTIVE_010" in compiled.selected_directives


# --------------------------------------------------------------------------- #
# Reject-not-drop: an unresolvable config stem raises (closes the C-006 seam)
# --------------------------------------------------------------------------- #


def test_unresolvable_config_directive_stem_raises() -> None:
    interview = _interview_with(selected_directives=[], selected_paradigms=[])
    pack_context = dataclasses.replace(
        _base_pack_context(Path(".")),
        activated_directives=frozenset({"999-does-not-exist"}),
    )

    with pytest.raises(UnknownArtifactIdError):
        compile_charter(mission="software-dev", interview=interview, pack_context=pack_context)


def test_unresolvable_config_styleguide_stem_raises_not_silently_dropped() -> None:
    """The direct-root path routes through the raising resolver too, not the lenient sanitizer."""
    interview = _interview_with(selected_directives=[], selected_paradigms=[])
    pack_context = dataclasses.replace(
        _base_pack_context(Path(".")),
        activated_directives=frozenset(),
        activated_styleguides=frozenset({"no-such-styleguide"}),
    )

    with pytest.raises(UnknownArtifactIdError):
        compile_charter(mission="software-dev", interview=interview, pack_context=pack_context)


# --------------------------------------------------------------------------- #
# T026: direct roots -- a directly-activated kind resolves with no directive edge
# --------------------------------------------------------------------------- #


def test_direct_root_styleguide_resolves_with_no_directive_selected() -> None:
    """The real #2524 baseline dangler: `aggregate-design-rules` has no directive edge."""
    interview = _interview_with(selected_directives=[], selected_paradigms=[])
    pack_context = dataclasses.replace(
        _base_pack_context(Path(".")),
        activated_directives=frozenset(),
        activated_styleguides=frozenset({"aggregate-design-rules"}),
    )

    compiled = compile_charter(mission="software-dev", interview=interview, pack_context=pack_context)

    assert compiled.selected_directives == []
    assert any(ref.id == "STYLEGUIDE:aggregate-design-rules" for ref in compiled.references)


def test_direct_root_toolguide_resolves_with_no_directive_selected() -> None:
    """The real #2524 baseline dangler: `contextive` has no directive edge."""
    interview = _interview_with(selected_directives=[], selected_paradigms=[])
    pack_context = dataclasses.replace(
        _base_pack_context(Path(".")),
        activated_directives=frozenset(),
        activated_toolguides=frozenset({"contextive"}),
    )

    compiled = compile_charter(mission="software-dev", interview=interview, pack_context=pack_context)

    assert compiled.selected_directives == []
    assert any(ref.id == "TOOLGUIDE:contextive" for ref in compiled.references)


def test_direct_root_tactic_procedure_and_agent_profile_resolve_with_no_directive_selected() -> None:
    """T026's "remaining directly-activatable kinds" -- tactics, procedures, agent profiles."""
    interview = _interview_with(selected_directives=[], selected_paradigms=[])
    pack_context = dataclasses.replace(
        _base_pack_context(Path(".")),
        activated_directives=frozenset(),
        activated_tactics=frozenset({"acceptance-test-first"}),
        activated_procedures=frozenset({"refactoring"}),
        activated_agent_profiles=frozenset({"paula-patterns"}),
    )

    compiled = compile_charter(mission="software-dev", interview=interview, pack_context=pack_context)

    reference_ids = {ref.id for ref in compiled.references}
    assert "TACTIC:acceptance-test-first" in reference_ids
    assert "PROCEDURE:refactoring" in reference_ids
    assert "AGENT_PROFILE:paula-patterns" in reference_ids


def test_direct_root_is_additive_to_directive_closure_not_a_replacement() -> None:
    """Selecting a directive AND a direct-root styleguide keeps both -- union, not either/or."""
    interview = _interview_with(selected_directives=[], selected_paradigms=[])
    pack_context = dataclasses.replace(
        _base_pack_context(Path(".")),
        activated_directives=frozenset({"010-specification-fidelity-requirement"}),
        activated_styleguides=frozenset({"aggregate-design-rules"}),
    )

    compiled = compile_charter(mission="software-dev", interview=interview, pack_context=pack_context)

    reference_ids = {ref.id for ref in compiled.references}
    assert "DIRECTIVE:DIRECTIVE_010" in reference_ids
    assert "STYLEGUIDE:aggregate-design-rules" in reference_ids


# --------------------------------------------------------------------------- #
# resolve_config_activated_roots: the shared charter-layer seam, from real disk config
# --------------------------------------------------------------------------- #


def test_resolve_config_activated_roots_reads_kittify_config_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "activated_directives:\n"
        "  - 010-specification-fidelity-requirement\n"
        "activated_styleguides:\n"
        "  - aggregate-design-rules\n"
        "mission_type_activations:\n"
        "  - software-dev\n",
        encoding="utf-8",
    )

    roots = resolve_config_activated_roots(repo_root=tmp_path)

    assert isinstance(roots, ConfigActivatedRoots)
    assert roots.directives == ["DIRECTIVE_010"]
    assert roots.styleguides == ["aggregate-design-rules"]
    # FR-018 (WP07/T038): a present project that OMITS `activated_paradigms`
    # delivers NOTHING for that kind at this delivery boundary -- absence is no
    # longer "all built-ins". (Retired: the pre-FR-018 assertion expected every
    # built-in paradigm here.)
    assert roots.paradigms == []


def test_resolve_config_activated_roots_raises_on_unresolvable_stem(tmp_path: Path) -> None:
    config_path = tmp_path / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "activated_directives:\n  - not-a-real-directive-stem\n"
        "mission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )

    with pytest.raises(UnknownArtifactIdError):
        resolve_config_activated_roots(repo_root=tmp_path)


# --------------------------------------------------------------------------- #
# _synthesis.py: the project-graph derivation path also reads config, not answers
# --------------------------------------------------------------------------- #


def test_build_synthesis_request_sources_selections_from_config_not_answers(tmp_path: Path) -> None:
    from specify_cli.cli.commands.charter._synthesis import _build_synthesis_request

    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    write_interview_answers(
        answers_path,
        _interview_with(selected_directives=["DIRECTIVE_003"], selected_paradigms=["deep-module-design"]),
    )

    config_path = tmp_path / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "activated_directives:\n  - 010-specification-fidelity-requirement\n"
        "activated_paradigms:\n  - domain-driven-design\n"
        "mission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )

    request, _adapter = _build_synthesis_request(tmp_path, "fixture")

    assert request.interview_snapshot["selected_directives"] == ["DIRECTIVE_010"]
    assert request.interview_snapshot["selected_paradigms"] == ["domain-driven-design"]
    assert "DIRECTIVE_003" not in request.interview_snapshot["selected_directives"]
    assert "deep-module-design" not in request.interview_snapshot["selected_paradigms"]
    assert request.drg_snapshot["nodes"] == [
        {"urn": "directive:DIRECTIVE_010", "kind": "directive"}
    ]


def test_build_synthesis_request_first_run_empty_config_selects_zero_directives(tmp_path: Path) -> None:
    """#2577: No ``.kittify/config.yaml`` at all -- first-run / empty-config parity.

    ``PackContext.activated_directives is None`` (absent key) is the shared
    three-state signal for "no explicit activation yet". ``compile_charter``
    (the ``references.yaml`` consumer) legitimately treats that as "all
    built-ins active" -- see
    ``test_no_pack_context_and_no_repo_root_defaults_to_all_builtins_active``
    above, a *different, still-correct* consumer of the same fallback.

    ``_build_synthesis_request`` must NOT inherit that fallback for
    ``interview_snapshot["selected_directives"]``: that field drives
    ``resolve_sections()``'s ``how-we-apply-<directive>`` companion-tactic
    expansion (one target per selected directive), so feeding it "all ~25
    built-in directives" on a project that has activated nothing yet demands
    ~25 companion tactics nobody asked for and fails ``charter synthesize``
    closed on the first missing YAML (the #2526 regression of pre-#2526
    parity, where this field was sourced from ``answers.selected_directives``
    and defaulted to ``[]`` on a fresh interview). First run must demand
    ZERO companion tactics, matching pre-#2526 behavior.
    """
    from specify_cli.cli.commands.charter._synthesis import _build_synthesis_request

    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    write_interview_answers(answers_path, _interview_with(selected_directives=["DIRECTIVE_003"]))
    # Deliberately no activated_directives key at all -- the genuine first-run
    # signal this test pins. mission_type_activations is provisioned as a
    # minimal, orthogonal key (WP04, C-A1: absence of THAT key alone is now a
    # hard construction precondition, independent of the activated_directives
    # three-state fallback this test exercises).
    config_path = tmp_path / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")

    request, _adapter = _build_synthesis_request(tmp_path, "fixture")

    assert request.interview_snapshot["selected_directives"] == []
    assert request.drg_snapshot["nodes"] == []


def test_build_synthesis_request_first_run_demands_zero_companion_tactics(tmp_path: Path) -> None:
    """#2577 RED-FIRST: first-run request resolves to ZERO companion-tactic targets.

    Exercises the real downstream consumer (``resolve_sections()``) rather
    than only inspecting the snapshot, so the assertion is pinned to the
    actual fail-closed surface the bug report described.
    """
    from charter.activation.synthesizer.interview_mapping import normalize_interview_snapshot, resolve_sections

    from specify_cli.cli.commands.charter._synthesis import _build_synthesis_request

    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    write_interview_answers(answers_path, _interview_with(selected_directives=["DIRECTIVE_003"]))
    # Deliberately no activated_directives key at all -- the genuine first-run
    # signal this test pins. mission_type_activations is provisioned as a
    # minimal, orthogonal key (WP04, C-A1: absence of THAT key alone is now a
    # hard construction precondition, independent of the activated_directives
    # three-state fallback this test exercises).
    config_path = tmp_path / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")

    request, _adapter = _build_synthesis_request(tmp_path, "fixture")
    snapshot = normalize_interview_snapshot(dict(request.interview_snapshot))
    sections = resolve_sections(snapshot)

    companion_tactic_sections = [label for label, _ctx in sections if label == "selected_directives"]
    assert companion_tactic_sections == []


def test_build_synthesis_request_explicit_activation_still_demands_companion_tactics(tmp_path: Path) -> None:
    """Regression guard: an EXPLICIT ``config.activated_directives`` selection
    still expands into one ``how-we-apply-<directive>`` companion-tactic
    target per activated directive -- the #2577 fix must not silence the
    intended (non-empty) expansion, only the first-run/absent-key case."""
    from charter.activation.synthesizer.interview_mapping import normalize_interview_snapshot, resolve_sections

    from specify_cli.cli.commands.charter._synthesis import _build_synthesis_request

    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    write_interview_answers(answers_path, _interview_with(selected_directives=[]))

    config_path = tmp_path / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "activated_directives:\n"
        "  - 010-specification-fidelity-requirement\n"
        "  - 024-locality-of-change\n"
        "mission_type_activations:\n"
        "  - software-dev\n",
        encoding="utf-8",
    )

    request, _adapter = _build_synthesis_request(tmp_path, "fixture")

    assert sorted(request.interview_snapshot["selected_directives"]) == ["DIRECTIVE_010", "DIRECTIVE_024"]

    snapshot = normalize_interview_snapshot(dict(request.interview_snapshot))
    sections = resolve_sections(snapshot)
    demanded_directive_ids = sorted(
        ctx["directive_id"] for label, ctx in sections if label == "selected_directives"
    )
    assert demanded_directive_ids == ["DIRECTIVE_010", "DIRECTIVE_024"]


# --------------------------------------------------------------------------- #
# #2529: org/project-overlay artefacts must resolve, not crash `charter
# generate`. `_resolve_config_activated_ids` previously called
# `resolve_artifact_urn` with no `org_roots`, so a config-activated ORG
# artefact raised `UnknownArtifactIdError`. The fix threads
# `list(pack_context.pack_roots[1:])` (PackContext.pack_roots is
# `(builtin_root, *org_pack_roots)`) down to the resolver.
# --------------------------------------------------------------------------- #


def test_org_only_paradigm_activated_in_config_resolves_via_org_roots(tmp_path: Path) -> None:
    """An org-pack-only paradigm activated in config.activated_paradigms
    resolves in the compiled reference set instead of raising
    ``UnknownArtifactIdError`` (the real #2524-class dangler/crash for org
    projects)."""
    org_root = tmp_path / "org-pack"
    _write_yaml(
        org_root / "paradigms" / "built-in" / "org-only-paradigm.paradigm.yaml",
        {
            "schema_version": "1.0",
            "id": "org-only-paradigm",
            "title": "Org-Only Paradigm",
            "summary": "An org-pack-only paradigm with no built-in counterpart.",
        },
    )

    interview = _interview_with(selected_directives=[], selected_paradigms=[])
    pack_context = dataclasses.replace(
        _base_pack_context(tmp_path),
        pack_roots=(resolve_offering_root(), org_root),
        activated_directives=frozenset(),
        activated_paradigms=frozenset({"org-only-paradigm"}),
    )

    compiled = compile_charter(mission="software-dev", interview=interview, pack_context=pack_context)

    assert compiled.selected_paradigms == ["org-only-paradigm"]
    assert any(ref.id == "PARADIGM:org-only-paradigm" for ref in compiled.references)


def test_org_only_paradigm_without_org_roots_would_have_raised(tmp_path: Path) -> None:
    """Regression guard for the pre-fix crash: with `pack_roots` collapsed to
    just the built-in root (no org root threaded), the same org-only stem is
    genuinely unresolvable and must still raise -- this is what closed the
    C-006 silent-drop vector, not a free pass for any unknown stem."""
    org_root = tmp_path / "org-pack"
    _write_yaml(
        org_root / "paradigms" / "built-in" / "org-only-paradigm.paradigm.yaml",
        {"schema_version": "1.0", "id": "org-only-paradigm", "title": "Org-Only Paradigm", "summary": "x"},
    )

    interview = _interview_with(selected_directives=[], selected_paradigms=[])
    pack_context = dataclasses.replace(
        _base_pack_context(tmp_path),
        pack_roots=(resolve_offering_root(),),  # no org root -- stem stays unresolvable
        activated_directives=frozenset(),
        activated_paradigms=frozenset({"org-only-paradigm"}),
    )

    with pytest.raises(UnknownArtifactIdError):
        compile_charter(mission="software-dev", interview=interview, pack_context=pack_context)


# --------------------------------------------------------------------------- #
# #2530: "Lynn Cole" free-text doctrine-intent alias. `apply_doctrine_intent_
# aliases` fires at interview *construction* time (`default_interview` /
# `CharterInterview.from_dict` / `apply_answer_overrides`, charter.activation.interview)
# and WP07's promotion wiring carries the aliased selection into
# `config.activated_*` -- the sole activation source `compile_charter` reads.
# `compile_charter` itself no longer re-applies the alias (removed as a
# dead-effect no-op, see its docstring); this pins that the end-to-end
# feature (free text -> compiled activation) is unaffected by that removal.
# --------------------------------------------------------------------------- #


def test_lynn_cole_free_text_intent_activates_end_to_end_via_config_promotion(tmp_path: Path) -> None:
    from specify_cli.cli.commands.charter.interview import _promote_interview_selections

    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"project_intent": "Our agents write too much code and it bloats the repo."},
    )
    # Construction-time aliasing already fired on the interview object itself.
    assert "DIRECTIVE_039" in interview.selected_directives
    assert "deep-module-design" in interview.selected_paradigms

    # Preseed ONLY `mission_type_activations` (unrelated to the directive/
    # paradigm promotion this test pins) so the `PackContext.from_config`
    # round-trip below doesn't hard-fail (WP04, C-A1). `_promote_interview_
    # selections` never writes this key itself, and `activated_directives`/
    # `activated_paradigms` are still genuinely absent here, so the
    # "absent-key parity" promotion warnings asserted below are unaffected.
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )

    warnings = _promote_interview_selections(tmp_path, interview)
    # No promotion FAILURE (e.g. an unresolvable id) -- the "absent-key
    # parity" notices below are expected, informational bookkeeping for a
    # project with no pre-existing config.yaml, not an error:
    #   "Key 'activated_directives' had no explicit activation set. Preserved
    #    19 built-in entries before promotion (absent-key parity)."
    assert not any("Could not resolve" in warning for warning in warnings)
    assert (tmp_path / ".kittify" / "config.yaml").exists()

    pack_context = PackContext.from_config(tmp_path)
    assert pack_context.activated_directives is not None
    assert pack_context.activated_paradigms is not None

    # A FRESH, non-aliased interview (no Lynn Cole text in its answers) --
    # proves activation flows through config, not interview mutation.
    plain_interview = default_interview(mission="software-dev", profile="minimal")
    assert "DIRECTIVE_039" not in plain_interview.selected_directives

    compiled = compile_charter(mission="software-dev", interview=plain_interview, pack_context=pack_context)

    assert "DIRECTIVE_039" in compiled.selected_directives
    assert "deep-module-design" in compiled.selected_paradigms
    assert "Lynn Cole Engineering Culture (`DIRECTIVE_039`)" in compiled.markdown
