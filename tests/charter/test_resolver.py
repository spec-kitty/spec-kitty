"""Tests for charter-centric governance resolver."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import charter.activation.catalog as catalog_module
from charter.activation.interview import default_interview
from charter.activation.resolver import (
    ActiveCharterService,
    GovernanceResolutionError,
    collect_governance_diagnostics,
    resolve_governance_for_profile,
    resolve_project_governance,
)

pytestmark = pytest.mark.fast


_GOVERNANCE_SELECTION_KEY = "charter"


def _write_charter_files(
    root: Path,
    *,
    governance: str,
    directives: str = "directives: []\n",
) -> Path:
    """Write governance/directives bodies into charter.yaml's sections.

    consolidate-charter-bundle (IC-04 / WP04, T028c): ``resolve_project_
    governance`` reads ``charter.activation.sync.load_governance_config`` /
    ``load_directives_config``, which now source ``charter.yaml``'s
    ``governance:`` / ``directives:`` sections directly -- the retired
    ``governance.yaml`` / ``directives.yaml`` files are no longer read at
    all. Callers pass the SAME bare-YAML fixture bodies as before; this
    helper nests them under the two charter.yaml keys instead of writing
    two standalone files.

    Writes at the CANONICAL root (``charter.resolution.
    resolve_canonical_repo_root(root)``), not necessarily ``root`` itself:
    the loaders anchor every read there (FR-010 worktree transparency), and
    several callers in this file pass a *subdirectory* of the
    ``tests/charter/conftest.py`` autouse-git-initialized ``tmp_path``
    (e.g. ``tmp_path / "repo"``) -- which resolves to ``tmp_path``, not the
    subdirectory, so the fixture must write where the reader will actually
    look.
    """
    from charter.resolution import resolve_canonical_repo_root
    from ruamel.yaml import YAML

    yaml = YAML()
    # resolve_canonical_repo_root shells out with cwd=root; root must exist
    # on disk first (it may be a not-yet-created subdirectory of the
    # conftest-git-initialized tmp_path).
    root.mkdir(parents=True, exist_ok=True)
    canonical_root = resolve_canonical_repo_root(root)
    charter_dir = canonical_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    document = {
        "governance": yaml.load(governance),
        "directives": yaml.load(directives),
    }
    with (charter_dir / "charter.yaml").open("w", encoding="utf-8") as fh:
        yaml.dump(document, fh)
    # ``mission_type_activations`` is unrelated to the governance/directives
    # resolution this module pins, but WP04 (C-A1) made it a hard
    # construction precondition for ``PackContext.from_config`` -- callers of
    # ``resolve_project_governance``/``collect_governance_diagnostics``
    # construct a ``PackContext`` internally to read ``activated_directives``,
    # so every fixture built by this helper needs the key provisioned. There
    # is no ``charter:`` pointer in this fixture's config.yaml, so activation
    # is read directly from config.yaml (the legacy/un-migrated path) --
    # this key lands there, not in charter.yaml.
    #
    # Unlike ``charter.yaml`` above (deliberately written at the CANONICAL
    # root for FR-010 worktree transparency), ``PackContext.from_config``
    # reads ``.kittify/config.yaml`` from its ``repo_root`` argument
    # literally, with no canonical-root resolution of its own. Several
    # callers in this file pass ``root`` as a *subdirectory* of the
    # conftest-git-initialized ``tmp_path`` (e.g. ``tmp_path / "repo"``,
    # which resolves to a DIFFERENT canonical root than ``root`` itself) and
    # then call ``resolve_project_governance(root)`` with that same literal
    # subdirectory -- so this key must be written at ``root``, not
    # ``canonical_root``, or ``PackContext.from_config`` will not find it.
    config_path = root / ".kittify" / "config.yaml"
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    return charter_dir


def test_resolve_governance_reads_charter_selections_first(
    tmp_path: Path, monkeypatch
) -> None:
    """Charter selections (paradigms, directives, tools, template_set) are used
    when explicitly declared and all values exist in the shipped catalog."""
    # Build a minimal doctrine root so shipped paradigm validation passes.
    offering_root = tmp_path / "offering_root"
    (offering_root / "paradigms").mkdir(parents=True)
    (offering_root / "paradigms" / "test-first.paradigm.yaml").write_text(
        "id: test-first\n"
    )
    (offering_root / "directives").mkdir(parents=True)
    (offering_root / "agent_profiles").mkdir(parents=True)
    (offering_root / "missions" / "software-dev").mkdir(parents=True)
    (offering_root / "missions" / "software-dev" / "mission.yaml").write_text(
        "name: software-dev\n"
    )
    monkeypatch.setattr(catalog_module, "resolve_offering_root", lambda: offering_root)
    # Built-in pack content resolves per-kind via ``built_in_dir`` post-relocation
    # (mission doctrine-built-in-seam-consolidation-01KYW3TX, WP02); point it at
    # the synthetic root's flat per-kind directories too.
    monkeypatch.setattr(catalog_module, "built_in_dir", lambda kind: offering_root / kind.plural)

    repo_root = tmp_path / "repo"
    _write_charter_files(
        repo_root,
        governance="""
charter:
  selected_paradigms: [test-first]
  selected_directives: [TEST_FIRST]
  available_tools: [git]
  template_set: software-dev-default
""",
        directives="""
directives:
  - id: TEST_FIRST
    title: Keep tests strict
""",
    )

    result = resolve_project_governance(repo_root, tool_registry={"git", "python", "pytest"})

    assert result.paradigms == ["test-first"]
    assert result.directives == ["TEST_FIRST"]
    # Tools resolve as the union of charter declaration and runtime registry
    # (DRIFT-1 remediation): charter declares [git]; registry baseline is
    # {git, python, pytest}; resolved set is the sorted union.
    assert result.tools == ["git", "pytest", "python"]
    assert result.metadata["tools_source"] == "charter+registry"
    assert result.template_set == "software-dev-default"
    assert result.metadata["template_set_source"] == "charter"


def test_resolve_governance_missing_paradigm_hard_fails(tmp_path: Path) -> None:
    _write_charter_files(
        tmp_path,
        governance="""
charter:
  selected_paradigms: [missing-paradigm]
""",
    )

    with pytest.raises(GovernanceResolutionError) as exc:
        resolve_project_governance(tmp_path)

    assert "missing-paradigm" in str(exc.value)


def test_resolve_governance_missing_directive_hard_fails(tmp_path: Path) -> None:
    _write_charter_files(
        tmp_path,
        governance="""
charter:
  selected_directives: [NOT_A_DIRECTIVE]
""",
    )

    with pytest.raises(GovernanceResolutionError) as exc:
        resolve_project_governance(tmp_path)

    assert "NOT_A_DIRECTIVE" in str(exc.value)


def test_resolve_governance_charter_declares_tool_outside_registry_is_unioned(tmp_path: Path) -> None:
    """Charter-declared tools not in the runtime registry are added to the resolved set.

    Per the union semantic (see DRIFT-1 remediation): the runtime registry is
    a baseline of always-available tools; the charter ``available_tools`` list
    is an additional declaration. The effective resolved set is the union of
    the two — declaring ``imaginary-tool`` in the charter adds it to the
    resolved set instead of raising a GovernanceResolutionError.

    A diagnostic line records which tools came from the charter declaration so
    operators can see at a glance which tools were added beyond the baseline.
    """
    _write_charter_files(
        tmp_path,
        governance="""
charter:
  available_tools: [imaginary-tool]
""",
    )

    result = resolve_project_governance(tmp_path, tool_registry={"git", "python"})

    assert "imaginary-tool" in result.tools
    assert "git" in result.tools
    assert "python" in result.tools
    assert result.metadata["tools_source"] == "charter+registry"
    assert any(
        "imaginary-tool" in diag and "Charter declared additional tool" in diag
        for diag in result.diagnostics
    )


def test_resolve_governance_missing_template_set_hard_fails(tmp_path: Path) -> None:
    _write_charter_files(
        tmp_path,
        governance="""
charter:
  template_set: missing-template-set
""",
    )

    with pytest.raises(GovernanceResolutionError) as exc:
        resolve_project_governance(tmp_path)

    assert "missing-template-set" in str(exc.value)


def test_resolve_governance_template_set_fallback_visible(tmp_path: Path) -> None:
    _write_charter_files(
        tmp_path,
        governance="""
charter:
  available_tools: []
""",
    )

    result = resolve_project_governance(
        tmp_path,
        tool_registry={"git"},
        fallback_template_set="fallback-pack",
    )

    assert result.template_set == "fallback-pack"
    assert result.metadata["template_set_source"] == "fallback"
    assert any("fallback-pack" in line for line in result.diagnostics)


def test_resolver_does_not_read_mission_files(tmp_path: Path) -> None:
    _write_charter_files(
        tmp_path,
        governance="charter: {}\n",
    )
    mission_file = tmp_path / "src" / "charter" / "offering" / "missions" / "software-dev" / "mission.yaml"
    mission_file.parent.mkdir(parents=True)
    mission_file.write_text("::invalid-yaml::\n\tbad")

    result = resolve_project_governance(tmp_path, tool_registry={"git"})
    assert result.tools == ["git"]


def test_collect_governance_diagnostics_reports_failures(tmp_path: Path) -> None:
    _write_charter_files(
        tmp_path,
        governance="""
charter:
  selected_directives: [NOT_A_DIRECTIVE]
""",
    )

    diagnostics = collect_governance_diagnostics(tmp_path)
    assert diagnostics
    assert any("NOT_A_DIRECTIVE" in line for line in diagnostics)


def test_resolve_governance_uses_registry_local_directives_and_template_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Additive contract (C-001, #3728): a project-local directive is unioned
    onto the resolved base set, not substituted for it.

    Deliberate contract change from the pre-#3728 replace semantic (was
    ``result.directives == ["LOCAL_ONLY"]`` / ``"catalog_fallback"``). The
    catalog is monkeypatched to a known set so the union is deterministic.
    """
    monkeypatch.setattr(
        "charter.activation.resolver.load_offering_catalog",
        lambda: SimpleNamespace(
            paradigms=frozenset(),
            directives=frozenset({"DIRECTIVE_010", "DIRECTIVE_003"}),
            template_sets=frozenset({"software-dev-default"}),
            domains_present=frozenset(),
        ),
    )
    _write_charter_files(
        tmp_path,
        governance="charter: {}\n",
        directives="""
directives:
  - id: LOCAL_ONLY
    title: Local rule
""",
    )

    result = resolve_project_governance(
        tmp_path,
        tool_registry={"python", "git"},
        fallback_template_set="fallback-pack",
    )

    assert result.tools == ["git", "python"]
    assert result.directives == ["DIRECTIVE_003", "DIRECTIVE_010", "LOCAL_ONLY"]
    assert result.template_set == "fallback-pack"
    assert result.metadata == {
        "tools_source": "registry_only",
        "directives_source": "catalog_fallback+project_local",
        "template_set_source": "fallback",
    }
    assert any("runtime tool registry fallback" in line for line in result.diagnostics)
    assert any("fallback-pack" in line for line in result.diagnostics)
    assert any(
        "project-local directive" in line and "LOCAL_ONLY" in line
        for line in result.diagnostics
    ), result.diagnostics


def test_resolve_governance_uses_catalog_directives_when_no_local_declarations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_charter_files(tmp_path, governance="charter: {}\n")
    monkeypatch.setattr(
        "charter.activation.resolver.load_offering_catalog",
        lambda: SimpleNamespace(
            paradigms=frozenset(),
            directives=frozenset({"DIRECTIVE_010", "DIRECTIVE_003"}),
            template_sets=frozenset({"software-dev-default"}),
            domains_present=frozenset(),
        ),
    )

    result = resolve_project_governance(tmp_path, tool_registry={"git"})

    assert result.directives == ["DIRECTIVE_003", "DIRECTIVE_010"]
    assert result.metadata["directives_source"] == "catalog_fallback"


def test_bare_project_fallback_emits_catalog_default_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-005: the catalog-default fallback (branch 3a) is no longer silent —
    a diagnostic names the fallback and its size."""
    _write_charter_files(tmp_path, governance="charter: {}\n")
    monkeypatch.setattr(
        "charter.activation.resolver.load_offering_catalog",
        lambda: SimpleNamespace(
            paradigms=frozenset(),
            directives=frozenset({"DIRECTIVE_010", "DIRECTIVE_003"}),
            template_sets=frozenset({"software-dev-default"}),
            domains_present=frozenset(),
        ),
    )

    result = resolve_project_governance(tmp_path, tool_registry={"git"})

    assert result.metadata["directives_source"] == "catalog_fallback"
    assert any(
        "built-in catalog default" in line and "2 directives" in line
        for line in result.diagnostics
    ), result.diagnostics


def test_explicit_selection_and_local_declaration_union(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INV-3 / D2: an explicit charter selection remains authoritative (never
    narrowed) while a coexisting local declaration is additively merged with a
    diagnostic — never silently dropped."""
    monkeypatch.setattr(
        "charter.activation.resolver.load_offering_catalog",
        lambda: SimpleNamespace(
            paradigms=frozenset(),
            directives=frozenset({"DIRECTIVE_A", "DIRECTIVE_C"}),
            template_sets=frozenset({"software-dev-default"}),
            domains_present=frozenset(),
        ),
    )
    _write_charter_files(
        tmp_path,
        governance=f"{_GOVERNANCE_SELECTION_KEY}:\n  selected_directives: [DIRECTIVE_A]\n",
        directives="""
directives:
  - id: DIRECTIVE_C
    title: Local rule
""",
    )

    result = resolve_project_governance(tmp_path, tool_registry={"git"})

    assert result.directives == ["DIRECTIVE_A", "DIRECTIVE_C"]
    # WP03 (FR-012): _resolve_directive_base now ALWAYS consults the
    # activated_*-derived base first (no config.yaml activated_directives key
    # here -> catalog_fallback, which happens to already contain both A and
    # C), then unions the charter selection onto it -- so the label reflects
    # BOTH sources were consulted, not "charter" alone as it did when a
    # non-empty selected_directives fully short-circuited the base lookup.
    # The union RESULT (INV-3: DIRECTIVE_A never narrowed away) is unchanged.
    assert result.metadata["directives_source"] == "catalog_fallback+charter+project_local"
    # Selected id is never narrowed away (INV-3).
    assert "DIRECTIVE_A" in result.directives
    assert any(
        "project-local directive" in line and "charter" in line
        for line in result.diagnostics
    ), result.diagnostics


def test_local_declaration_matching_catalog_id_dedups_in_base_position(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INV-5: a local id equal to a catalog id appears once, in base position."""
    monkeypatch.setattr(
        "charter.activation.resolver.load_offering_catalog",
        lambda: SimpleNamespace(
            paradigms=frozenset(),
            directives=frozenset({"DIRECTIVE_010", "DIRECTIVE_003"}),
            template_sets=frozenset({"software-dev-default"}),
            domains_present=frozenset(),
        ),
    )
    _write_charter_files(
        tmp_path,
        governance="charter: {}\n",
        directives="""
directives:
  - id: DIRECTIVE_003
    title: Duplicate of a catalog id
""",
    )

    result = resolve_project_governance(tmp_path, tool_registry={"git"})

    assert result.directives == ["DIRECTIVE_003", "DIRECTIVE_010"]
    assert result.directives.count("DIRECTIVE_003") == 1
    assert result.metadata["directives_source"] == "catalog_fallback+project_local"
    # #3728 review-fix: the merge diagnostic must be truthful in the zero-net-add
    # case — it names the already-present id instead of claiming a merge.
    assert any(
        "already present" in line and "none added" in line
        for line in result.diagnostics
    ), result.diagnostics


def test_activation_base_and_local_declaration_union(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C-001 / #3728: a base sourced from ``activated_directives`` (a non-empty
    activation set, with no explicit ``selected_directives``) is additively
    unioned with a NEW project-local declaration, yielding
    ``sorted(activated) + [new_local]`` and source ``activation+project_local``.
    """
    monkeypatch.setattr(
        "charter.activation.resolver.load_offering_catalog",
        lambda: SimpleNamespace(
            paradigms=frozenset(),
            directives=frozenset({"DIRECTIVE_003", "DIRECTIVE_010"}),
            template_sets=frozenset({"software-dev-default"}),
            domains_present=frozenset(),
        ),
    )
    # Pre-provision config.yaml so the helper leaves it untouched: the base must
    # come from a non-empty ``activated_directives`` set (the legacy config-embedded
    # activation path — no ``charter:`` pointer in this fixture).
    config_path = tmp_path / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "mission_type_activations:\n"
        "  - software-dev\n"
        "activated_directives:\n"
        "  - DIRECTIVE_010\n"
        "  - DIRECTIVE_003\n",
        encoding="utf-8",
    )
    _write_charter_files(
        tmp_path,
        governance="charter: {}\n",
        directives="""
directives:
  - id: LOCAL_NEW
    title: New local rule
""",
    )

    result = resolve_project_governance(tmp_path, tool_registry={"git"})

    assert result.directives == ["DIRECTIVE_003", "DIRECTIVE_010", "LOCAL_NEW"]
    assert result.metadata["directives_source"] == "activation+project_local"
    assert any(
        "project-local directive" in line and "LOCAL_NEW" in line
        for line in result.diagnostics
    ), result.diagnostics


def test_resolve_governance_for_profile_merges_profile_directives_first() -> None:
    interview = default_interview(mission="software-dev", profile="minimal")
    interview = default_interview(mission="software-dev", profile="minimal")
    object.__setattr__(interview, "selected_directives", ["INTERVIEW_DIRECTIVE", "PROFILE_DIRECTIVE"])

    profile = SimpleNamespace(
        profile_id="reviewer",
        directive_references=[
            SimpleNamespace(code="PROFILE_DIRECTIVE"),
            SimpleNamespace(code="PROFILE_SECOND"),
        ],
    )
    charter_service = MagicMock()
    charter_service.agent_profiles.resolve_profile.return_value = profile
    charter_service.directives.get.side_effect = lambda artifact_id: SimpleNamespace(
        id=artifact_id,
        title=artifact_id,
        intent=f"Intent for {artifact_id}",
        tactic_refs=[],
    )
    charter_service.tactics.get.return_value = None
    charter_service.styleguides.get.return_value = None
    charter_service.toolguides.get.return_value = None
    charter_service.procedures.get.return_value = None

    resolution = resolve_governance_for_profile("reviewer", "reviewer", charter_service, interview)

    assert resolution.profile_id == "reviewer"
    assert resolution.role == "reviewer"
    assert resolution.directives == ["PROFILE_DIRECTIVE", "PROFILE_SECOND", "INTERVIEW_DIRECTIVE"]
    assert resolution.metadata["directives_source"] == "profile+interview"


def test_resolve_governance_for_profile_populates_graph_artifacts_and_normalizes_role() -> None:
    interview = default_interview(mission="software-dev", profile="minimal")
    object.__setattr__(interview, "selected_directives", ["INTERVIEW_DIRECTIVE", "PROFILE_DIRECTIVE"])

    profile = SimpleNamespace(
        profile_id="reviewer",
        directive_references=[
            SimpleNamespace(code=" PROFILE_DIRECTIVE "),
            SimpleNamespace(code=""),
            SimpleNamespace(code="PROFILE_SECOND"),
        ],
    )
    charter_service = MagicMock()
    charter_service.agent_profiles.resolve_profile.return_value = profile

    # Post-WP03: monkeypatch charter.activation.resolver.resolve_transitive_refs; its
    # result is a :class:`charter.offering.drg.query.ResolveTransitiveRefsResult`
    # look-alike (SimpleNamespace is structurally compatible here).
    monkeypatch_graph = SimpleNamespace(
        tactics=["TACTIC_001"],
        styleguides=["STYLE_001"],
        toolguides=["TOOL_001"],
        procedures=["PROC_001"],
        unresolved=[("directive:MISSING_DIRECTIVE", "directive:MISSING_DIRECTIVE")],
    )

    # Provide a stand-in graph so the resolver invokes resolve_transitive_refs.
    stub_graph = SimpleNamespace()

    with patch(
        "charter.activation.resolver.resolve_references_transitively",
        return_value=monkeypatch_graph,
    ):
        resolution = resolve_governance_for_profile(
            " reviewer ",
            "   ",
            charter_service,
            interview,
            graph=stub_graph,
        )

    assert resolution.directives == ["PROFILE_DIRECTIVE", "PROFILE_SECOND", "INTERVIEW_DIRECTIVE"]
    assert resolution.tactics == ["TACTIC_001"]
    assert resolution.styleguides == ["STYLE_001"]
    assert resolution.toolguides == ["TOOL_001"]
    assert resolution.procedures == ["PROC_001"]
    assert resolution.role is None
    assert resolution.metadata["profile_directives_count"] == "2"
    assert any("MISSING_DIRECTIVE" in line for line in resolution.diagnostics)


def test_resolve_governance_for_profile_missing_profile_raises_value_error() -> None:
    interview = default_interview(mission="software-dev", profile="minimal")
    charter_service = MagicMock()
    charter_service.agent_profiles.resolve_profile.side_effect = KeyError("missing")

    with pytest.raises(ValueError) as exc:
        resolve_governance_for_profile("missing", None, charter_service, interview)

    assert "missing" in str(exc.value)


def test_resolve_governance_for_profile_rejects_blank_profile_id() -> None:
    interview = default_interview(mission="software-dev", profile="minimal")
    charter_service = MagicMock()

    with pytest.raises(ValueError, match="Profile ID is required"):
        resolve_governance_for_profile("   ", None, charter_service, interview)


def test_resolve_governance_for_profile_records_unresolved_references_in_diagnostics() -> None:
    """Post-WP03, unresolved references surface via the DRG walker.

    The ``unresolved`` entries in the :class:`ResolveTransitiveRefsResult`
    are formatted into ``diagnostics`` by ``resolve_governance_for_profile``.
    """
    interview = default_interview(mission="software-dev", profile="minimal")
    object.__setattr__(interview, "selected_directives", [])

    profile = SimpleNamespace(
        profile_id="reviewer",
        directive_references=[SimpleNamespace(code="MISSING_DIRECTIVE")],
    )
    charter_service = MagicMock()
    charter_service.agent_profiles.resolve_profile.return_value = profile

    monkeypatch_graph = SimpleNamespace(
        tactics=[],
        styleguides=[],
        toolguides=[],
        procedures=[],
        unresolved=[
            (
                "directive:MISSING_DIRECTIVE",
                "directive:MISSING_DIRECTIVE",
            )
        ],
    )
    stub_graph = SimpleNamespace()

    with patch(
        "charter.activation.resolver.resolve_references_transitively",
        return_value=monkeypatch_graph,
    ):
        resolution = resolve_governance_for_profile(
            "reviewer",
            None,
            charter_service,
            interview,
            graph=stub_graph,
        )

    assert resolution.directives == ["MISSING_DIRECTIVE"]
    assert any("MISSING_DIRECTIVE" in line for line in resolution.diagnostics)


def test_collect_governance_diagnostics_returns_success_diagnostics(
    tmp_path: Path,
) -> None:
    _write_charter_files(tmp_path, governance="charter: {}\n")

    diagnostics = collect_governance_diagnostics(
        tmp_path,
        tool_registry={"git"},
        fallback_template_set="fallback-pack",
    )

    assert any("runtime tool registry fallback" in line for line in diagnostics)
    assert any("fallback-pack" in line for line in diagnostics)


# ---------------------------------------------------------------------------
# T017: Regression tests — named-ID failures, shipped-only, no agents.yaml
# ---------------------------------------------------------------------------


def _make_doctrine_root(tmp_path: Path, *, with_paradigm: str | None = None) -> Path:
    """Create a minimal doctrine root for resolver tests."""
    offering_root = tmp_path / "offering_root"
    paradigms_shipped = offering_root / "paradigms" / "built-in"
    paradigms_shipped.mkdir(parents=True)
    if with_paradigm:
        (paradigms_shipped / f"{with_paradigm}.paradigm.yaml").write_text(
            f"id: {with_paradigm}\n"
        )
    (offering_root / "directives" / "built-in").mkdir(parents=True)
    (offering_root / "agent_profiles" / "built-in").mkdir(parents=True)
    (offering_root / "missions" / "software-dev").mkdir(parents=True)
    (offering_root / "missions" / "software-dev" / "mission.yaml").write_text("name: software-dev\n")
    return offering_root


def test_paradigm_failure_names_exact_offending_id(tmp_path: Path, monkeypatch) -> None:
    """Error message names the exact paradigm ID that was not in the shipped catalog."""
    offering_root = _make_doctrine_root(tmp_path)
    monkeypatch.setattr(catalog_module, "resolve_offering_root", lambda: offering_root)

    repo_root = tmp_path / "repo"
    _write_charter_files(
        repo_root,
        governance="charter:\n  selected_paradigms: [my-bad-paradigm]\n",
    )

    with pytest.raises(GovernanceResolutionError) as exc:
        resolve_project_governance(repo_root)

    error_text = str(exc.value)
    assert "my-bad-paradigm" in error_text


def test_paradigm_failure_skipped_when_shipped_dir_absent(tmp_path: Path, monkeypatch) -> None:
    """When the paradigms shipped directory does not exist, validation is skipped gracefully."""
    offering_root = tmp_path / "offering_root"
    # Do NOT create paradigms directory at all
    (offering_root / "directives").mkdir(parents=True)
    (offering_root / "agent_profiles").mkdir(parents=True)
    (offering_root / "missions" / "software-dev").mkdir(parents=True)
    (offering_root / "missions" / "software-dev" / "mission.yaml").write_text("name: software-dev\n")
    monkeypatch.setattr(catalog_module, "resolve_offering_root", lambda: offering_root)
    # Built-in pack content resolves per-kind via ``built_in_dir`` post-relocation
    # (mission doctrine-built-in-seam-consolidation-01KYW3TX, WP02); the synthetic
    # root has no paradigms dir, so validation must skip gracefully.
    monkeypatch.setattr(catalog_module, "built_in_dir", lambda kind: offering_root / kind.plural)

    repo_root = tmp_path / "repo"
    _write_charter_files(
        repo_root,
        governance="charter:\n  selected_paradigms: [any-value]\n",
    )

    # Should not raise — domain is absent so skip validation
    result = resolve_project_governance(repo_root, tool_registry={"git"})
    assert result.paradigms == ["any-value"]


def test_directive_failure_names_exact_offending_id(tmp_path: Path, monkeypatch) -> None:
    """Error message names the exact directive ID that was not found."""
    offering_root = _make_doctrine_root(tmp_path)
    monkeypatch.setattr(catalog_module, "resolve_offering_root", lambda: offering_root)

    repo_root = tmp_path / "repo"
    _write_charter_files(
        repo_root,
        governance="charter:\n  selected_directives: [GHOST_DIRECTIVE]\n",
    )

    with pytest.raises(GovernanceResolutionError) as exc:
        resolve_project_governance(repo_root)

    assert "GHOST_DIRECTIVE" in str(exc.value)


def test_template_set_failure_names_exact_offending_value(tmp_path: Path, monkeypatch) -> None:
    """Error message names the exact template_set value that was not in shipped catalog."""
    offering_root = _make_doctrine_root(tmp_path)
    monkeypatch.setattr(catalog_module, "resolve_offering_root", lambda: offering_root)

    repo_root = tmp_path / "repo"
    _write_charter_files(
        repo_root,
        governance="charter:\n  template_set: ghost-template-set\n",
    )

    with pytest.raises(GovernanceResolutionError) as exc:
        resolve_project_governance(repo_root)

    assert "ghost-template-set" in str(exc.value)


def test_tool_outside_registry_appears_in_diagnostic(tmp_path: Path, monkeypatch) -> None:
    """A charter-declared tool not in the runtime registry is unioned into the
    resolved tools and the operator is informed via diagnostics (DRIFT-1 remediation).

    The pre-remediation behaviour raised GovernanceResolutionError; the union
    semantic treats the runtime registry as a baseline of always-available
    tools and the charter declaration as additive. The diagnostic message
    names the exact tool(s) that came from the charter so operators can audit.
    """
    offering_root = _make_doctrine_root(tmp_path)
    monkeypatch.setattr(catalog_module, "resolve_offering_root", lambda: offering_root)

    repo_root = tmp_path / "repo"
    _write_charter_files(
        repo_root,
        governance="charter:\n  available_tools: [ghost-tool]\n",
    )

    result = resolve_project_governance(repo_root, tool_registry={"git"})

    assert "ghost-tool" in result.tools
    assert "git" in result.tools
    diagnostic_text = "\n".join(result.diagnostics)
    assert "ghost-tool" in diagnostic_text
    assert "Charter declared additional tool" in diagnostic_text


def test_local_support_declaration_bypasses_catalog_validation(tmp_path: Path, monkeypatch) -> None:
    """Directives declared in directives.yaml are valid without being in the shipped catalog."""
    offering_root = _make_doctrine_root(tmp_path)
    monkeypatch.setattr(catalog_module, "resolve_offering_root", lambda: offering_root)

    repo_root = tmp_path / "repo"
    _write_charter_files(
        repo_root,
        governance="charter:\n  selected_directives: [LOCAL_ONLY]\n",
        directives="directives:\n  - id: LOCAL_ONLY\n    title: Local rule\n",
    )

    # Should NOT raise — LOCAL_ONLY is declared in directives.yaml
    result = resolve_project_governance(repo_root, tool_registry={"git"})
    assert "LOCAL_ONLY" in result.directives


def test_sync_output_does_not_include_agents_yaml(tmp_path: Path) -> None:
    """consolidate-charter-bundle (IC-04 / WP04): sync() writes nothing at all now.

    The prose->triad scrape this test originally pinned (governance/
    directives/metadata, never agents.yaml) is retired -- ``sync()``
    always reports ``synced=False`` / ``files_written=[]``, which trivially
    satisfies "no agents.yaml" but for a stronger reason than before.
    """
    from charter.activation.sync import sync

    charter_file = tmp_path / "charter.md"
    charter_file.write_text("# Project\n\n## Directives\n1. Write tests\n")

    result = sync(charter_file, tmp_path)

    assert result.synced is False
    assert result.files_written == []
    assert not (tmp_path / "agents.yaml").exists()


# ---------------------------------------------------------------------------
# ActiveCharterService wrapper — activation filter coverage (FR-016 / FR-017)
# ---------------------------------------------------------------------------


def test_doctrine_service_paradigms_filtered_by_pack_context() -> None:
    """ActiveCharterService.paradigms applies pack_context.activated_paradigms filter."""
    from unittest.mock import MagicMock
    from charter.activation.pack_context import PackContext

    paradigm_a = MagicMock()
    paradigm_a.id = "test-first"
    paradigm_b = MagicMock()
    paradigm_b.id = "ddd"

    inner = MagicMock()
    inner.paradigms.list_all.return_value = [paradigm_a, paradigm_b]

    pack_ctx = MagicMock(spec=PackContext)
    pack_ctx.activated_paradigms = frozenset({"test-first"})

    service = ActiveCharterService(inner, pack_context=pack_ctx)
    result = service.paradigms

    assert "test-first" in result
    assert "ddd" not in result


def test_doctrine_service_paradigms_unfiltered_when_pack_context_none() -> None:
    """ActiveCharterService.paradigms returns all when pack_context is None."""
    from unittest.mock import MagicMock

    paradigm_a = MagicMock()
    paradigm_a.id = "test-first"
    inner = MagicMock()
    inner.paradigms.list_all.return_value = [paradigm_a]

    service = ActiveCharterService(inner, pack_context=None)
    result = service.paradigms

    assert "test-first" in result


def test_doctrine_service_procedures_filtered_by_pack_context() -> None:
    """ActiveCharterService.procedures applies pack_context.activated_procedures filter."""
    from unittest.mock import MagicMock
    from charter.activation.pack_context import PackContext

    proc_a = MagicMock()
    proc_a.id = "tdd"
    proc_b = MagicMock()
    proc_b.id = "bdd"

    inner = MagicMock()
    inner.procedures.list_all.return_value = [proc_a, proc_b]

    pack_ctx = MagicMock(spec=PackContext)
    pack_ctx.activated_procedures = frozenset({"tdd"})

    service = ActiveCharterService(inner, pack_context=pack_ctx)
    result = service.procedures

    assert "tdd" in result
    assert "bdd" not in result


def test_doctrine_service_getattr_delegates_to_inner() -> None:
    """Unknown attributes on ActiveCharterService are forwarded to the inner service."""
    from unittest.mock import MagicMock

    inner = MagicMock()
    inner.some_custom_attr = "sentinel"

    service = ActiveCharterService(inner, pack_context=None)

    assert service.some_custom_attr == "sentinel"


def test_resolve_governance_for_profile_raises_when_profile_not_in_dict() -> None:
    """resolve_governance_for_profile raises ValueError when profile dict has no match."""
    from unittest.mock import MagicMock
    from charter.activation.interview import CharterInterview

    service = MagicMock(spec=ActiveCharterService)
    service.agent_profiles = {}  # empty dict, isinstance check will be True

    interview = MagicMock(spec=CharterInterview)
    interview.selected_directives = []

    with pytest.raises(ValueError, match="not found"):
        resolve_governance_for_profile(
            "nonexistent-profile",
            role=None,
            charter_service=service,
            interview=interview,
        )
