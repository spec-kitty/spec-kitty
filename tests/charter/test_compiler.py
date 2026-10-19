"""Scope: mock-boundary tests for charter compiler bundle generation -- no real git."""

import dataclasses
from pathlib import Path

import pytest

from charter.activation.catalog import OfferingCatalog, load_offering_catalog
from charter.activation.compiler import (
    _resolve_template_set,
    _sanitize_catalog_selection,
    _unregistered_tool_message,
    compile_charter,
    write_compiled_charter,
)
from charter.activation.interview import (
    CharterInterview,
    LocalSupportDeclaration,
    apply_answer_overrides,
    default_interview,
    validate_local_support_declarations,
)
from charter.activation.pack_context import PackContext

pytestmark = pytest.mark.fast


def test_compile_charter_contains_governance_activation_block() -> None:
    """Compiled charter includes mission metadata and governance activation section."""
    # Arrange
    interview = default_interview(mission="software-dev", profile="minimal")

    # Assumption check
    assert interview.mission == "software-dev", "interview must be for software-dev"

    # Act
    compiled = compile_charter(mission="software-dev", interview=interview)

    # Assert
    assert compiled.mission == "software-dev"
    assert compiled.template_set == "software-dev-default"
    assert "## Governance Activation" in compiled.markdown
    assert "selected_directives" in compiled.markdown
    assert "available_tools: [git, spec-kitty]" in compiled.markdown


def test_resolve_template_set_uses_smallest_available_fallback() -> None:
    catalog = OfferingCatalog(
        template_sets={"zeta-default", "alpha-default"},
        paradigms=[],
        directives=[],
        tactics=[],
        styleguides=[],
        toolguides=[],
        procedures=[],
        agent_profiles=[],
    )

    assert (
        _resolve_template_set(
            mission="software-dev",
            requested_template_set=None,
            catalog=catalog,
        )
        == "alpha-default"
    )


# NOTE (WP03 T028, unify-charter-activation-surfaces): two tests used to live
# here --
# ``test_compile_charter_preserves_explicit_empty_selections`` and
# ``test_compile_charter_renders_lynn_cole_rules_verbatim`` -- both DELETED,
# not re-pinned, because they exercised the answers-sourced activation path
# WP02 (FR-001/FR-002) retired outright:
#
# - ``test_compile_charter_preserves_explicit_empty_selections`` asserted
#   that an interview's explicit ``selected_paradigms=[]``/
#   ``selected_directives=[]`` suppressed compiled activation. Activation is
#   now sourced exclusively from ``config.activated_*``; ``interview.
#   selected_*`` is inert for this purpose (see ``compile_charter``'s own
#   docstring). The equivalent, CURRENT invariant -- config absent -> every
#   built-in active, config present -> config wins over any interview value
#   -- is already covered by
#   ``tests/charter/test_config_sourced_derivation.py::test_no_pack_context_and_no_repo_root_defaults_to_all_builtins_active``
#   and ``::test_compiled_paradigms_come_from_config_not_interview``, so
#   deleting here is not a coverage loss.
# - ``test_compile_charter_renders_lynn_cole_rules_verbatim`` asserted that a
#   "Lynn Cole" trigger phrase in ``project_intent``
#   (``apply_doctrine_intent_aliases``, ``charter/interview.py``) auto-adds
#   ``DIRECTIVE_039``/``deep-module-design`` to the COMPILED charter. That
#   alias function still runs (it mutates the in-memory
#   ``CharterInterview.selected_directives``/``selected_paradigms``) but its
#   output is now silently discarded -- compiled activation reads
#   ``config.activated_*``, never the mutated interview object -- so the
#   feature this test pinned is presently dead code with no product-visible
#   effect. Fixing ``apply_doctrine_intent_aliases`` to target
#   ``config.yaml`` instead is a product decision outside WP03's explicit
#   scope (regenerate artefacts + re-pin/delete these 6 named tests); it is
#   reported as a gap for a follow-up mission rather than silently patched
#   here.


def test_compile_charter_renders_selected_directive_content() -> None:
    interview = default_interview(mission="software-dev", profile="minimal")
    interview = apply_answer_overrides(
        interview,
        selected_directives=["DIRECTIVE_003"],
    )

    compiled = compile_charter(mission="software-dev", interview=interview)

    # The directive renders its real definition (title + id), not the generic placeholder line.
    assert "Apply doctrine directive `DIRECTIVE_003`" not in compiled.markdown
    assert "(`DIRECTIVE_003`)" in compiled.markdown


def test_compile_charter_renders_agent_profile_metadata_when_present() -> None:
    interview = default_interview(mission="software-dev", profile="minimal")
    interview = apply_answer_overrides(interview, agent_profile="reviewer", agent_role="reviewer")

    compiled = compile_charter(mission="software-dev", interview=interview)

    assert "agent_profile: reviewer" in compiled.markdown
    assert "agent_role: reviewer" in compiled.markdown


def test_write_compiled_charter_writes_bundle(tmp_path: Path) -> None:
    """write_compiled_charter creates ONLY charter.yaml (WP03/T011-T012: the
    charter.md clobber is removed and references.yaml is retired -- see
    data-model.md Landmine 3); a repeat write without ``force`` succeeds."""
    # Arrange
    interview = default_interview(mission="software-dev", profile="minimal")
    compiled = compile_charter(mission="software-dev", interview=interview)

    # Assumption check
    assert not (tmp_path / "charter.yaml").exists(), "target directory must be empty"

    # Act
    result = write_compiled_charter(tmp_path, compiled, force=True)

    # Assert
    assert result.files_written == ["charter.yaml"]
    assert (tmp_path / "charter.yaml").exists()
    assert not (tmp_path / "charter.md").exists()
    assert not (tmp_path / "references.yaml").exists()

    # library/ materialization has been removed; no files should exist there.
    assert not (tmp_path / "library").exists()

    # ``force`` no longer gates a destructive overwrite (there is none left to
    # gate): a second write with force=False refreshes charter.yaml in place.
    rewritten = write_compiled_charter(tmp_path, compiled, force=False)
    assert rewritten.files_written == ["charter.yaml"]
    assert (tmp_path / "charter.yaml").exists()


def test_write_compiled_charter_persists_structured_languages_for_round_trip(tmp_path: Path) -> None:
    """WP02/T008+T009 (re-pinned for WP03): compiled charter's languages
    field is persisted to charter.yaml's ``catalog.languages`` on disk.

    ``references.yaml`` is retired (WP03/T012); the structured field's new
    home is charter.yaml's DERIVED ``catalog`` section. Repointing
    ``infer_repo_languages``'s tier-1 read at ``catalog.languages`` is
    WP08's job (language tier-3 fallback migration, dependent on WP03) --
    this test only pins WP03's write side of the contract.
    """
    from ruamel.yaml import YAML

    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": "Rust services with cargo and rustc tooling"},
    )
    compiled = compile_charter(mission="software-dev", interview=interview)

    assert compiled.active_languages == ["rust"], "compile_charter must compute the structured field"

    charter_dir = tmp_path / ".kittify" / "charter"
    write_compiled_charter(charter_dir, compiled, force=True)

    yaml = YAML()
    document = yaml.load((charter_dir / "charter.yaml").read_text(encoding="utf-8"))
    assert document["catalog"]["languages"] == ["rust"], (
        "languages field must be persisted to charter.yaml's catalog section on disk"
    )


def test_compile_with_doctrine_service_none_uses_drg_backed_path() -> None:
    """Calling compile_charter without ActiveCharterService must NOT emit a YAML
    fallback diagnostic.

    Per C-001 of the excise-doctrine-curation-and-inline-references-01KP54J6
    mission there is no YAML-scanning fallback: the compiler constructs a
    default :class:`ActiveCharterService` internally and always takes the
    DRG-backed path. The compiled result includes tactics / procedures /
    toolguides resolved via the graph, not just paradigms + directives.
    """
    interview = default_interview(mission="software-dev", profile="minimal")
    interview = apply_answer_overrides(
        interview,
        selected_directives=["DIRECTIVE_003"],
    )

    compiled = compile_charter(mission="software-dev", interview=interview, charter_service=None)

    fallback_msg = (
        "ActiveCharterService unavailable; using YAML scanning fallback. "
        "Profile-aware compilation requires ActiveCharterService."
    )
    assert not any(fallback_msg in d for d in compiled.diagnostics), (
        f"Unexpected legacy fallback diagnostic: {compiled.diagnostics}"
    )
    # The DRG-backed path resolves transitive artifacts. With an explicit shipped
    # directive selection the bundled graph should yield at least one tactic.
    kinds = {reference.kind for reference in compiled.references}
    assert "tactic" in kinds, (
        "DRG-backed path should have resolved transitive tactics; "
        f"got kinds {sorted(kinds)}"
    )
    # Regression: directives stored under the built-in/ subdirectory must resolve
    # to a real definition, not the "unavailable" placeholder summary.
    directive_refs = [r for r in compiled.references if r.kind == "directive"]
    assert directive_refs, "Expected at least one directive reference in the compiled bundle"
    unresolved = [r.id for r in directive_refs if r.summary == "Definition unavailable in bundled doctrine."]
    assert not unresolved, f"Directive(s) not found in built-in doctrine: {unresolved}"


def test_compile_with_repo_root_uses_project_drg_overlay(tmp_path: Path) -> None:
    """When repo_root is passed, the project DRG overlay at
    <repo_root>/.kittify/doctrine/graph.yaml participates in transitive
    resolution (exercises the repo_root branch of _build_references and
    _default_active_charter_service).

    Post-merge fix per P2 of the excise-doctrine-curation-and-inline-references-01KP54J6
    mission review.
    """
    interview = default_interview(mission="software-dev", profile="minimal")
    interview = apply_answer_overrides(
        interview,
        selected_directives=["DIRECTIVE_003"],
    )

    # charter_service=None below makes compile_charter build its own
    # default doctrine service via PackContext.from_config(tmp_path), which
    # now hard-fails (WP04, C-A1) without a provisioned
    # mission_type_activations key -- unrelated to the repo_root/DRG-overlay
    # behavior this test exercises.
    kittify_dir = tmp_path / ".kittify"
    kittify_dir.mkdir(parents=True)
    (kittify_dir / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )

    # An empty project overlay at .kittify/doctrine/graph.yaml is enough
    # to prove the repo_root branch executes load_validated_graph. We use
    # an empty edges/nodes overlay so shipped edges dominate and the
    # compilation still succeeds end-to-end.
    overlay_dir = tmp_path / ".kittify" / "doctrine"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "graph.yaml").write_text(
        "schema_version: '1.0'\n"
        "generated_at: '2026-04-14T00:00:00+00:00'\n"
        "generated_by: test-compile-with-repo-root\n"
        "nodes: []\n"
        "edges: []\n"
    )

    # Also create a project doctrine overlay dir so _default_active_charter_service
    # exercises the project-root branch (compiler.py lines 267-269).
    (tmp_path / "src" / "charter" / "offering").mkdir(parents=True)

    compiled = compile_charter(
        mission="software-dev",
        interview=interview,
        charter_service=None,
        repo_root=tmp_path,
    )
    kinds = {reference.kind for reference in compiled.references}
    # Shipped graph still supplies tactics even with empty project overlay.
    assert "tactic" in kinds, (
        f"repo_root branch should still resolve shipped tactics; got {sorted(kinds)}"
    )


def _empty_pack_context(repo_root: Path, **overrides: object) -> PackContext:
    """A ``PackContext`` with every per-kind activation explicitly empty.

    Unlike the ``None`` (absent-key) three-state default -- which falls back
    to "every built-in active" and would mask the graph-load-failure
    scenario below -- an explicit empty ``frozenset()`` per kind means
    nothing is config-activated unless *overrides* says otherwise.
    """
    base = PackContext(
        activated_kinds=frozenset(
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
        ),
        activated_mission_types=frozenset({"software-dev"}),
        pack_roots=(),
        org_pack_names=(),
        repo_root=repo_root,
        activated_directives=frozenset(),
        activated_tactics=frozenset(),
        activated_styleguides=frozenset(),
        activated_toolguides=frozenset(),
        activated_paradigms=frozenset(),
        activated_procedures=frozenset(),
        activated_agent_profiles=frozenset(),
    )
    return dataclasses.replace(base, **overrides)  # type: ignore[arg-type]


def test_compile_with_repo_root_handles_missing_shipped_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WP03 re-pin (T028): when the shipped graph cannot be loaded, tactics
    reachable ONLY via directive-closure transitive resolution do not
    resolve -- but a tactic activated DIRECTLY in ``config.activated_*``
    still surfaces via the documented graph-load-failure fallback bucket
    (``_resolve_transitive_reference_graph``'s ``FileNotFoundError`` branch
    in ``charter/compiler.py``: "the direct roots must still surface...
    rather than silently vanishing"). This is WP02 T026's intentional
    behavior change, not a regression: the original assertion here ("no
    tactics ever resolve on graph failure") is unconditionally false now
    that direct-root activation exists, so it is re-pinned rather than
    merely deleted.
    """
    from charter.activation import _drg_helpers as drg_helpers_module
    interview = default_interview(mission="software-dev", profile="minimal")

    # charter_service=None below makes compile_charter build its own
    # default doctrine service via PackContext.from_config(tmp_path), which
    # now hard-fails (WP04, C-A1) without a provisioned
    # mission_type_activations key -- unrelated to the graph-load-failure
    # fallback behavior this test exercises (the explicit ``pack_context``
    # passed to compile_charter itself is unaffected -- see
    # ``_empty_pack_context``'s direct dataclass construction below).
    kittify_dir = tmp_path / ".kittify"
    kittify_dir.mkdir(parents=True)
    (kittify_dir / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )

    def _raise_fnf(_repo_root: Path) -> object:
        raise FileNotFoundError("synthetic: shipped graph missing")

    monkeypatch.setattr(drg_helpers_module, "load_validated_graph", _raise_fnf)

    # No tactic is config-activated directly -- the only way "tactic" could
    # appear is via directive transitive closure, which the broken graph
    # makes unreachable.
    no_tactics = _empty_pack_context(tmp_path)
    compiled = compile_charter(
        mission="software-dev",
        interview=interview,
        charter_service=None,
        repo_root=tmp_path,
        pack_context=no_tactics,
    )
    kinds = {reference.kind for reference in compiled.references}
    assert "tactic" not in kinds, (
        f"graph-load failure must not resolve transitive-only tactics when none is "
        f"config-activated directly; got {sorted(kinds)}"
    )

    # A tactic activated DIRECTLY still surfaces via the fallback bucket,
    # even though the graph failed to load (WP02 T026).
    with_direct_tactic = _empty_pack_context(tmp_path, activated_tactics=frozenset({"zombies-tdd"}))
    compiled_with_direct_tactic = compile_charter(
        mission="software-dev",
        interview=interview,
        charter_service=None,
        repo_root=tmp_path,
        pack_context=with_direct_tactic,
    )
    direct_kinds = {reference.kind for reference in compiled_with_direct_tactic.references}
    assert "tactic" in direct_kinds, (
        "a directly config-activated tactic must still surface via the graph-load-failure "
        f"fallback bucket; got {sorted(direct_kinds)}"
    )


# NOTE (WP03 T028, unify-charter-activation-surfaces): DELETED (not
# re-pinned) ``test_compile_with_doctrine_service_unknown_directive_in_diagnostics``.
# It set ``interview_with_directive.selected_directives = ["DIRECTIVE_MISSING"]``
# and asserted the bogus id produced a diagnostic. Since ``interview.
# selected_*`` is no longer read for activation (WP02, FR-001/FR-002),
# "DIRECTIVE_MISSING" now never enters any code path -- the assertion can
# never be satisfied again by construction, not merely by an implementation
# detail moving. The config-sourced replacement for "an invalid activation
# id is surfaced, not silently dropped" is a STRONGER, fail-closed contract
# (raise, not degrade-with-diagnostic) already pinned by
# ``tests/charter/test_config_sourced_derivation.py::test_unresolvable_config_directive_stem_raises``
# (and its styleguide sibling), so deleting here is not a coverage loss.


# ---------------------------------------------------------------------------
# T006: LocalSupportDeclaration + CharterInterview.local_supporting_files
# ---------------------------------------------------------------------------


def test_charter_interview_from_dict_parses_local_supporting_files() -> None:
    data = {
        "mission": "software-dev",
        "profile": "minimal",
        "answers": {},
        "selected_paradigms": [],
        "selected_directives": [],
        "available_tools": [],
        "local_supporting_files": [
            {
                "path": "docs/governance/project-planning.md",
                "action": "plan",
                "target_kind": "directive",
                "target_id": "003-decision-documentation-requirement",
            }
        ],
    }
    interview = CharterInterview.from_dict(data)
    assert {d.path for d in interview.local_supporting_files} == {
        "docs/governance/project-planning.md"
    }
    decl = interview.local_supporting_files[0]
    assert decl.path == "docs/governance/project-planning.md"
    assert decl.action == "plan"
    assert decl.target_kind == "directive"
    assert decl.target_id == "003-decision-documentation-requirement"


def test_charter_interview_from_dict_ignores_missing_local_supporting_files() -> None:
    data: dict[str, object] = {
        "mission": "software-dev",
        "profile": "minimal",
        "answers": {},
        "selected_paradigms": [],
        "selected_directives": [],
        "available_tools": [],
    }
    interview = CharterInterview.from_dict(data)
    assert interview.local_supporting_files == []


def test_charter_interview_to_dict_omits_local_supporting_files_when_empty() -> None:
    interview = default_interview(mission="software-dev", profile="minimal")
    d = interview.to_dict()
    assert "local_supporting_files" not in d


def test_charter_interview_to_dict_includes_local_supporting_files_when_present() -> None:
    interview = default_interview(mission="software-dev", profile="minimal")
    decl = LocalSupportDeclaration(path="docs/my-guide.md", action="implement")
    interview = apply_answer_overrides(interview, local_supporting_files=[decl])
    d = interview.to_dict()
    assert "local_supporting_files" in d
    assert d["local_supporting_files"] == [{"path": "docs/my-guide.md", "action": "implement"}]


def test_local_support_declaration_from_dict_valid() -> None:
    raw = {"path": "docs/guide.md", "action": "review", "target_kind": "tactic", "target_id": "some-tactic"}
    decl = LocalSupportDeclaration.from_dict(raw)
    assert decl is not None
    assert decl.path == "docs/guide.md"
    assert decl.action == "review"
    assert decl.target_kind == "tactic"
    assert decl.target_id == "some-tactic"


def test_local_support_declaration_from_dict_missing_path_returns_none() -> None:
    raw: dict[str, object] = {"action": "plan"}
    assert LocalSupportDeclaration.from_dict(raw) is None


def test_local_support_declaration_from_dict_non_dict_returns_none() -> None:
    assert LocalSupportDeclaration.from_dict("not-a-dict") is None
    assert LocalSupportDeclaration.from_dict(None) is None


# ---------------------------------------------------------------------------
# T007: validate_local_support_declarations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("docs/*.md", "glob"),
        ("docs/file?.md", "glob"),
        ("docs/[abc].md", "glob"),
        ("docs/governance/", "directory"),
    ],
)
def test_validate_rejects_glob_and_directory_paths(path: str, reason: str) -> None:
    valid, errors = validate_local_support_declarations([LocalSupportDeclaration(path=path)])
    assert valid == []
    assert any(reason in e for e in errors)


def test_validate_accepts_valid_explicit_path() -> None:
    decls = [LocalSupportDeclaration(path="docs/governance/project-planning.md")]
    valid, errors = validate_local_support_declarations(decls)
    assert {v.path for v in valid} == {"docs/governance/project-planning.md"}
    assert errors == []


def test_validate_normalizes_unknown_action_to_none() -> None:
    decls = [LocalSupportDeclaration(path="docs/guide.md", action="deploy")]
    valid, errors = validate_local_support_declarations(decls)
    assert {v.path for v in valid} == {"docs/guide.md"}
    assert valid[0].action is None
    # An error/warning message should describe the unknown action
    assert any("deploy" in e for e in errors)


def test_validate_accepts_known_actions() -> None:
    for action in ("specify", "plan", "implement", "review"):
        decls = [LocalSupportDeclaration(path="docs/guide.md", action=action)]
        valid, errors = validate_local_support_declarations(decls)
        assert {v.path for v in valid} == {"docs/guide.md"}
        assert valid[0].action == action
        assert errors == []


def test_validate_mixed_valid_and_invalid() -> None:
    decls = [
        LocalSupportDeclaration(path="docs/guide.md"),
        LocalSupportDeclaration(path="docs/**"),
    ]
    valid, errors = validate_local_support_declarations(decls)
    assert {v.path for v in valid} == {"docs/guide.md"}
    assert len(errors) == 1


# ---------------------------------------------------------------------------
# T008: Compiler builds additive references with overlap warnings
# ---------------------------------------------------------------------------


def test_compile_with_local_support_file_creates_local_reference() -> None:
    interview = default_interview(mission="software-dev", profile="minimal")
    decl = LocalSupportDeclaration(path="docs/governance/project-planning.md")
    interview = apply_answer_overrides(interview, local_supporting_files=[decl])

    compiled = compile_charter(mission="software-dev", interview=interview)

    local_refs = [r for r in compiled.references if r.kind == "local_support"]
    assert {r.id for r in local_refs} == {"LOCAL:docs/governance/project-planning.md"}
    ref = local_refs[0]
    assert ref.id == "LOCAL:docs/governance/project-planning.md"
    assert ref.source_path == "docs/governance/project-planning.md"


def test_compile_local_support_reference_is_additive_not_replacement() -> None:
    """Local support reference must not replace the shipped directive reference,
    and overlapping a shipped directive emits a warning diagnostic."""
    interview = default_interview(mission="software-dev", profile="minimal")
    directive_id = sorted(load_offering_catalog().directives)[0]
    decl = LocalSupportDeclaration(
        path="docs/custom-directive.md",
        target_kind="directive",
        target_id=directive_id,
    )
    interview = apply_answer_overrides(
        interview,
        selected_directives=[directive_id],
        local_supporting_files=[decl],
    )

    compiled = compile_charter(mission="software-dev", interview=interview)

    local_refs = [r for r in compiled.references if r.kind == "local_support"]
    shipped_refs = [r for r in compiled.references if r.kind != "local_support"]
    assert {r.id for r in local_refs} == {"LOCAL:docs/custom-directive.md"}
    # Shipped refs must still be present
    assert len(shipped_refs) > 0
    # Targeting a shipped directive also emits the overlap warning diagnostic.
    assert any("built-in content remains primary" in d for d in compiled.diagnostics), (
        f"Expected overlap warning; diagnostics: {compiled.diagnostics}"
    )


def test_compile_local_support_no_warning_when_no_overlap() -> None:
    """No overlap warning when local file does not target any shipped artifact."""
    interview = default_interview(mission="software-dev", profile="minimal")
    decl = LocalSupportDeclaration(path="docs/custom-note.md")
    interview = apply_answer_overrides(interview, local_supporting_files=[decl])

    compiled = compile_charter(mission="software-dev", interview=interview)

    assert not any("built-in content remains primary" in d for d in compiled.diagnostics)


def test_compile_invalid_local_support_paths_emit_diagnostics() -> None:
    """Glob/dir paths rejected during compilation with diagnostics."""
    interview = default_interview(mission="software-dev", profile="minimal")
    bad_decl = LocalSupportDeclaration(path="docs/**/*.md")
    interview = apply_answer_overrides(interview, local_supporting_files=[bad_decl])

    compiled = compile_charter(mission="software-dev", interview=interview)

    # Invalid declaration must not produce a local_support reference
    local_refs = [r for r in compiled.references if r.kind == "local_support"]
    assert local_refs == []
    # A diagnostic must record the rejection
    assert any("glob" in d for d in compiled.diagnostics)


# ---------------------------------------------------------------------------
# T010: write_compiled_charter does NOT produce library/ directory
# ---------------------------------------------------------------------------


def test_tracked_kinds_table_matches_the_artifact_kind_vocabulary() -> None:
    """Each tracked kind is a real ``ArtifactKind`` whose plural is the graph
    bucket / raw-repository key the table records (and the table is not empty)."""
    import charter.activation.compiler as compiler_module
    from charter.activation.kind_vocabulary import ArtifactKind

    assert compiler_module._TRACKED_KINDS
    for kind, tracked in compiler_module._TRACKED_KINDS.items():
        assert ArtifactKind(kind).plural == tracked.plural


def test_unresolved_cause_vocabulary_is_one_closed_set() -> None:
    """The record ``cause`` vocabulary is a single ``Literal`` alias: every
    ``CatalogMissCause`` maps onto a member with the SAME string value (the
    ``--json`` output is unchanged), and the compiler-owned causes are members
    too -- adding a cause in one place without the other fails here."""
    import typing

    import charter.activation.compiler as compiler_module
    from charter.activation._catalog_miss import CatalogMissCause

    declared = set(typing.get_args(compiler_module.UnresolvedCause))
    mapping = compiler_module._CAUSE_BY_CATALOG_MISS
    compiler_owned = {
        compiler_module._MALFORMED_URN_CAUSE,
        compiler_module._UNATTRIBUTED_KIND_CAUSE,
        compiler_module._GRAPH_LOAD_FAILURE_CAUSE,
    }

    assert set(mapping) == set(CatalogMissCause)
    assert {cause: value for cause, value in mapping.items() if cause.value != value} == {}
    assert declared == set(mapping.values()) | compiler_owned


# ---------------------------------------------------------------------------
# #4614 / FR-013: label-specific diagnostic for unregistered tool ids
# ---------------------------------------------------------------------------


def test_unregistered_tool_message_lists_all_ids_sorted_in_one_message() -> None:
    assert _unregistered_tool_message(["b", "a"]) == (
        "available_tools: 'a', 'b' are not registered tool ids; ignored (tool ids are validated separately from project languages)"
    )


def test_sanitize_catalog_selection_default_message_is_unchanged_for_other_labels() -> None:
    diagnostics: list[str] = []

    _sanitize_catalog_selection(values=["nope"], allowed={"yes"}, label="widgets", diagnostics=diagnostics)

    assert diagnostics == ["Ignored unknown widgets: nope"]


def test_sanitize_catalog_selection_emits_no_message_when_nothing_is_missing() -> None:
    diagnostics: list[str] = []

    _sanitize_catalog_selection(
        values=["git"], allowed={"git"}, label="available_tools", diagnostics=diagnostics, missing_message=_unregistered_tool_message
    )

    assert diagnostics == []


def test_compile_charter_reports_unregistered_tool_as_tool_id_and_keeps_registry() -> None:
    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        available_tools=["git", "zig"],
    )

    compiled = compile_charter(mission="software-dev", interview=interview)

    assert "zig" not in compiled.available_tools
    assert any(line.startswith("available_tools: 'zig' is not a registered tool id") for line in compiled.diagnostics)
    assert not any("Ignored unknown available_tools" in line for line in compiled.diagnostics)


def test_compile_charter_rederive_languages_ignores_stale_compiled_list(tmp_path: Path) -> None:
    """``rederive_languages=True`` derives from the interview; the default stays compiled-first."""
    charter_yaml = tmp_path / ".kittify" / "charter" / "charter.yaml"
    charter_yaml.parent.mkdir(parents=True)
    charter_yaml.write_text("schema_version: '2.0.0'\ncatalog:\n  languages: [python]\n  references: []\n", encoding="utf-8")
    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": "Rust with cargo"},
    )

    kept = compile_charter(mission="software-dev", interview=interview, repo_root=tmp_path)
    rederived = compile_charter(mission="software-dev", interview=interview, repo_root=tmp_path, rederive_languages=True)

    assert kept.active_languages == ["python"]
    assert rederived.active_languages == ["rust"]
