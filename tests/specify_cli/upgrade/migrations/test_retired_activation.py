"""Tests for the shared retired-activation engine (``_retired_activation.py``).

The generic mechanics behind both
``m_3_2_6_retire_rtk_search_tooling`` and
``m_4_0_0rc5_retire_single_owner_doctrine_ids``. These tests exercise the
engine directly with synthetic retirement rows (rather than the production
table, which ``test_m_4_0_0rc5_retire_single_owner_doctrine_ids.py`` covers)
so the mechanics are pinned independently of any one migration's data.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.upgrade.migrations._retired_activation import (
    Retirement,
    apply_retirements,
    detect_retirements,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_CHARTER_RELATIVE_PATH = Path(".kittify") / "charter" / "charter.yaml"
_CONFIG_RELATIVE_PATH = Path(".kittify") / "config.yaml"
_REFERENCES_RELATIVE_PATH = Path(".kittify") / "charter" / "references.yaml"
_ANSWERS_RELATIVE_PATH = Path(".kittify") / "charter" / "interview" / "answers.yaml"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _load(path: Path) -> dict:
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# detect(): parametrized over every surface shape
# --------------------------------------------------------------------------- #


def test_reference_id_composes_prefix_and_stem() -> None:
    retirement = Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC")
    assert retirement.reference_id == "TACTIC:widget-polish"


@pytest.mark.parametrize(
    "relative_path,text",
    [
        (_CONFIG_RELATIVE_PATH, "activated_tactics:\n- widget-polish\n"),
        (_CHARTER_RELATIVE_PATH, "activated_tactics:\n- widget-polish\n"),
        (
            _CHARTER_RELATIVE_PATH,
            "catalog:\n  references:\n  - id: TACTIC:widget-polish\n    kind: tactic\n",
        ),
        (
            _CHARTER_RELATIVE_PATH,
            "catalog:\n- id: TACTIC:widget-polish\n  kind: tactic\n",
        ),
        (_REFERENCES_RELATIVE_PATH, "references:\n- id: TACTIC:widget-polish\n  kind: tactic\n"),
        (_ANSWERS_RELATIVE_PATH, "selected_tactics:\n- widget-polish\n"),
    ],
    ids=[
        "config-activation",
        "charter-activation",
        "charter-catalog-nested",
        "charter-catalog-flat",
        "references-block",
        "answers-selected",
    ],
)
def test_detect_true_for_every_surface_shape(tmp_path: Path, relative_path: Path, text: str) -> None:
    retirement = Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC")
    _write(tmp_path / relative_path, text)

    assert detect_retirements(tmp_path, (retirement,), include_answers_surface=True) is True


def test_detect_ignores_answers_surface_when_excluded(tmp_path: Path) -> None:
    retirement = Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC")
    _write(tmp_path / _ANSWERS_RELATIVE_PATH, "selected_tactics:\n- widget-polish\n")

    assert detect_retirements(tmp_path, (retirement,), include_answers_surface=False) is False


def test_detect_false_when_nothing_present(tmp_path: Path) -> None:
    retirement = Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC")

    assert detect_retirements(tmp_path, (retirement,), include_answers_surface=True) is False


# --------------------------------------------------------------------------- #
# apply(): duplicates, siblings, successor activation
# --------------------------------------------------------------------------- #


def _seed_full_project(tmp_path: Path) -> Path:
    _write(
        tmp_path / _CONFIG_RELATIVE_PATH,
        "project_name: demo\nactivated_tactics:\n- alpha-tactic\n- widget-polish\n- omega-tactic\n",
    )
    _write(
        tmp_path / _CHARTER_RELATIVE_PATH,
        "schema_version: 2.0.0\n"
        "catalog:\n"
        "  mission: software-dev\n"
        "  references:\n"
        "  - id: TACTIC:alpha-tactic\n"
        "    kind: tactic\n"
        "  - id: TACTIC:widget-polish\n"
        "    kind: tactic\n"
        "  - id: TACTIC:omega-tactic\n"
        "    kind: tactic\n"
        "activated_tactics:\n"
        "- alpha-tactic\n"
        "- widget-polish\n"
        "- widget-polish\n"  # duplicate: apply() must remove every occurrence
        "- omega-tactic\n"
        "activated_procedures: []\n",  # already-narrowed empty list: successor list EXISTS here
    )
    _write(
        tmp_path / _REFERENCES_RELATIVE_PATH,
        "schema_version: 1.0.0\nreferences:\n- id: TACTIC:alpha-tactic\n- id: TACTIC:widget-polish\n- id: TACTIC:omega-tactic\n",
    )
    _write(
        tmp_path / _ANSWERS_RELATIVE_PATH,
        "selected_tactics:\n- alpha-tactic\n- widget-polish\n- omega-tactic\n",
    )
    return tmp_path


def _retirement_with_successor() -> Retirement:
    return Retirement(
        kind_key="activated_tactics",
        stem="widget-polish",
        reference_prefix="TACTIC",
        successors=(("activated_procedures", "widget-audit"),),
    )


def test_apply_removes_duplicates_keeps_siblings_across_every_surface(tmp_path: Path) -> None:
    project = _seed_full_project(tmp_path)

    result = apply_retirements(project, (_retirement_with_successor(),), include_answers_surface=True)

    assert result.success is True

    config = _load(project / _CONFIG_RELATIVE_PATH)
    assert config["activated_tactics"] == ["alpha-tactic", "omega-tactic"]
    # config.yaml never had an activated_procedures list -- successor is NOT invented here.
    assert "activated_procedures" not in config

    charter = _load(project / _CHARTER_RELATIVE_PATH)
    assert charter["activated_tactics"] == ["alpha-tactic", "omega-tactic"]
    assert [entry["id"] for entry in charter["catalog"]["references"]] == [
        "TACTIC:alpha-tactic",
        "TACTIC:omega-tactic",
    ]
    # charter.yaml's activated_procedures list EXISTED (as []) -- successor activated there.
    assert charter["activated_procedures"] == ["widget-audit"]

    references = _load(project / _REFERENCES_RELATIVE_PATH)
    assert [entry["id"] for entry in references["references"]] == [
        "TACTIC:alpha-tactic",
        "TACTIC:omega-tactic",
    ]

    answers = _load(project / _ANSWERS_RELATIVE_PATH)
    assert answers["selected_tactics"] == ["alpha-tactic", "omega-tactic"]


def test_apply_does_not_reactivate_an_already_present_successor(tmp_path: Path) -> None:
    project = _seed_full_project(tmp_path)
    # charter.yaml's successor list already carries the successor.
    charter_path = project / _CHARTER_RELATIVE_PATH
    text = charter_path.read_text(encoding="utf-8").replace("activated_procedures: []\n", "activated_procedures:\n- widget-audit\n")
    charter_path.write_text(text, encoding="utf-8")

    result = apply_retirements(project, (_retirement_with_successor(),), include_answers_surface=True)

    assert result.success is True
    charter = _load(charter_path)
    assert charter["activated_procedures"] == ["widget-audit"]
    assert not any("Activated successor" in change for change in result.changes_made)


def test_apply_is_idempotent_second_run_is_a_no_op(tmp_path: Path) -> None:
    project = _seed_full_project(tmp_path)
    retirement = (_retirement_with_successor(),)

    first = apply_retirements(project, retirement, include_answers_surface=True)
    snapshot = {
        rel: (project / rel).read_text(encoding="utf-8")
        for rel in (_CONFIG_RELATIVE_PATH, _CHARTER_RELATIVE_PATH, _REFERENCES_RELATIVE_PATH, _ANSWERS_RELATIVE_PATH)
    }

    second = apply_retirements(project, retirement, include_answers_surface=True)

    assert first.success is True
    assert second.success is True
    assert second.changes_made == []
    assert detect_retirements(project, retirement, include_answers_surface=True) is False
    for rel, text in snapshot.items():
        assert (project / rel).read_text(encoding="utf-8") == text


def test_apply_on_a_bare_project_makes_no_changes_and_creates_nothing(tmp_path: Path) -> None:
    retirement = (Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC"),)

    result = apply_retirements(tmp_path, retirement, include_answers_surface=True)

    assert result.success is True
    assert result.changes_made == []
    assert result.errors == []
    assert not (tmp_path / ".kittify").exists()


def test_apply_skips_malformed_yaml_and_still_handles_the_other_surfaces(tmp_path: Path) -> None:
    retirement = (Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC"),)
    _write(tmp_path / _CONFIG_RELATIVE_PATH, "activated_tactics:\n- widget-polish\n")
    malformed = "catalog: [unterminated\nactivated_tactics:\n- widget-polish\n"
    _write(tmp_path / _CHARTER_RELATIVE_PATH, malformed)

    result = apply_retirements(tmp_path, retirement, include_answers_surface=True)

    assert result.success is True
    assert result.errors == []
    config = _load(tmp_path / _CONFIG_RELATIVE_PATH)
    assert "widget-polish" not in config["activated_tactics"]
    # The malformed file is left byte-for-byte untouched, never written to.
    assert (tmp_path / _CHARTER_RELATIVE_PATH).read_text(encoding="utf-8") == malformed


def test_apply_warns_once_per_unparseable_surface_file(tmp_path: Path) -> None:
    retirements = (
        Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC"),
        Retirement(kind_key="activated_tactics", stem="alpha-tactic", reference_prefix="TACTIC"),
    )
    _write(tmp_path / _CONFIG_RELATIVE_PATH, "activated_tactics:\n- widget-polish\n")
    _write(tmp_path / _CHARTER_RELATIVE_PATH, "catalog: [unterminated\n")

    result = apply_retirements(tmp_path, retirements, include_answers_surface=True)

    assert result.success is True
    charter_warnings = [w for w in result.warnings if ".kittify/charter/charter.yaml" in w]
    # One warning for the file, not one per (retirement x surface) visit.
    assert len(charter_warnings) == 1
    assert "could not be parsed" in charter_warnings[0]


def test_apply_warns_when_a_surface_file_is_not_a_mapping(tmp_path: Path) -> None:
    retirement = (Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC"),)
    _write(tmp_path / _CONFIG_RELATIVE_PATH, "- just\n- a list\n")

    result = apply_retirements(tmp_path, retirement, include_answers_surface=False)

    assert result.success is True
    assert any(".kittify/config.yaml" in w and "not a mapping" in w for w in result.warnings)


def test_apply_dry_run_also_warns_about_an_unparseable_surface_file(tmp_path: Path) -> None:
    retirement = (Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC"),)
    _write(tmp_path / _CONFIG_RELATIVE_PATH, "activated_tactics: [unterminated\n")

    result = apply_retirements(tmp_path, retirement, include_answers_surface=False, dry_run=True)

    assert any(".kittify/config.yaml" in w for w in result.warnings)


def test_apply_does_not_warn_for_absent_or_empty_surface_files(tmp_path: Path) -> None:
    retirement = (Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC"),)
    _write(tmp_path / _CONFIG_RELATIVE_PATH, "")

    result = apply_retirements(tmp_path, retirement, include_answers_surface=True)

    assert result.warnings == []


def test_apply_dry_run_writes_nothing(tmp_path: Path) -> None:
    project = _seed_full_project(tmp_path)
    before = {
        rel: (project / rel).read_text(encoding="utf-8")
        for rel in (_CONFIG_RELATIVE_PATH, _CHARTER_RELATIVE_PATH, _REFERENCES_RELATIVE_PATH, _ANSWERS_RELATIVE_PATH)
    }

    result = apply_retirements(project, (_retirement_with_successor(),), include_answers_surface=True, dry_run=True)

    assert result.success is True
    assert result.changes_made, "dry-run should still report what it WOULD do"
    assert all(change.startswith("Would remove") or change.startswith("Would activate") for change in result.changes_made)
    for rel, text in before.items():
        assert (project / rel).read_text(encoding="utf-8") == text
    assert detect_retirements(project, (_retirement_with_successor(),), include_answers_surface=True) is True


# --------------------------------------------------------------------------- #
# Org-pack-resolvable skip
# --------------------------------------------------------------------------- #


def test_still_resolves_via_org_pack_is_left_entirely_untouched(tmp_path: Path) -> None:
    retirement = (Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC"),)
    pack_dir = tmp_path / "packs" / "internal" / "tactics"
    pack_dir.mkdir(parents=True)
    (pack_dir / "widget-polish.tactic.yaml").write_text("id: widget-polish\n", encoding="utf-8")
    _write(
        tmp_path / _CONFIG_RELATIVE_PATH,
        "activated_tactics:\n- widget-polish\ncharter_packs:\n  org:\n    packs:\n    - name: internal\n      local_path: packs/internal\n",
    )
    _write(tmp_path / _CHARTER_RELATIVE_PATH, "activated_tactics:\n- widget-polish\n")

    assert detect_retirements(tmp_path, retirement, include_answers_surface=True) is False

    result = apply_retirements(tmp_path, retirement, include_answers_surface=True)

    assert result.success is True
    assert result.changes_made == []
    config = _load(tmp_path / _CONFIG_RELATIVE_PATH)
    assert config["activated_tactics"] == ["widget-polish"]
    charter = _load(tmp_path / _CHARTER_RELATIVE_PATH)
    assert charter["activated_tactics"] == ["widget-polish"]


@pytest.mark.parametrize(
    "org_config",
    [
        "doctrine:\n  org:\n    packs:\n    - name: internal\n      local_path: packs/internal\n",
        "doctrine:\n  org:\n    local_path: packs\n    subdir: internal\n",
        "organisation_packs:\n- name: internal\n  path: packs/internal\n",
    ],
    ids=["doctrine-org-packs", "doctrine-org-single-pack", "organisation-packs"],
)
def test_org_pack_declared_under_a_retired_key_still_counts(tmp_path: Path, org_config: str) -> None:
    """The retired org keys can still be on disk when this engine's ``detect()`` runs (#3732 FR-011).

    The org-pack registry no longer reads them, so the check reads them itself:
    an id an org pack declared there still carries is left untouched.
    """
    retirement = (Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC"),)
    pack_dir = tmp_path / "packs" / "internal" / "tactics"
    pack_dir.mkdir(parents=True)
    (pack_dir / "widget-polish.tactic.yaml").write_text("id: widget-polish\n", encoding="utf-8")
    _write(tmp_path / _CONFIG_RELATIVE_PATH, "activated_tactics:\n- widget-polish\n" + org_config)

    assert detect_retirements(tmp_path, retirement, include_answers_surface=True) is False


def test_retired_org_key_without_the_id_does_not_count(tmp_path: Path) -> None:
    """Control: a retired-key org pack that does not carry the id leaves the retirement due."""
    retirement = (Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC"),)
    (tmp_path / "packs" / "internal" / "tactics").mkdir(parents=True)
    _write(
        tmp_path / _CONFIG_RELATIVE_PATH,
        "activated_tactics:\n- widget-polish\norganisation_packs:\n- name: internal\n  path: packs/internal\n- not-a-mapping\n"
        "doctrine:\n  org:\n    packs:\n    - name: no-local-path\n    - not-a-mapping\n",
    )

    assert detect_retirements(tmp_path, retirement, include_answers_surface=True) is True


def test_org_pack_check_ignores_a_different_kind_directory(tmp_path: Path) -> None:
    """A same-name file under the WRONG kind directory must not count as resolving."""
    retirement = (Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC"),)
    pack_dir = tmp_path / "packs" / "internal" / "procedures"
    pack_dir.mkdir(parents=True)
    (pack_dir / "widget-polish.tactic.yaml").write_text("id: widget-polish\n", encoding="utf-8")
    _write(
        tmp_path / _CONFIG_RELATIVE_PATH,
        "activated_tactics:\n- widget-polish\ncharter_packs:\n  org:\n    packs:\n    - name: internal\n      local_path: packs/internal\n",
    )

    assert detect_retirements(tmp_path, retirement, include_answers_surface=True) is True


# --------------------------------------------------------------------------- #
# Kind-key exclusivity: a directive and a tactic of the same slug never collide
# --------------------------------------------------------------------------- #


def test_kind_key_scoping_leaves_a_same_slug_directive_untouched(tmp_path: Path) -> None:
    retirement = (Retirement(kind_key="activated_tactics", stem="locality-of-change", reference_prefix="TACTIC"),)
    _write(
        tmp_path / _CHARTER_RELATIVE_PATH,
        "activated_directives:\n- 024-locality-of-change\nactivated_tactics:\n- locality-of-change\n- other-tactic\n",
    )

    result = apply_retirements(tmp_path, retirement, include_answers_surface=True)

    assert result.success is True
    charter = _load(tmp_path / _CHARTER_RELATIVE_PATH)
    assert charter["activated_directives"] == ["024-locality-of-change"]
    assert charter["activated_tactics"] == ["other-tactic"]


# --------------------------------------------------------------------------- #
# Rule 6 evidence: consumer graph.yml has no src/ reader, so it is correctly
# left out of every retirement's surfaces.
# --------------------------------------------------------------------------- #


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / ".kittify").is_dir() and (parent / "src").is_dir():
            return parent
    raise RuntimeError("Could not locate repo root (no .kittify/ + src/ marker found).")


def _code_string_constants(tree: object) -> set[str]:
    """String constants actually USED in code, excluding bare docstring/prose statements.

    A free-standing string statement (``ast.Expr(value=ast.Constant(str))`` --
    a module/class/function docstring, or any other floating string used as
    prose/documentation) carries no runtime path meaning, so it is excluded
    here exactly as the real charter path-literal AST gate excludes prose
    (see ``test_charter_path_literal_authority.py``'s module docstring).
    Every OTHER string constant -- an assignment RHS, a call argument, a
    dict/list element, an operand of a ``/`` path-join -- is a genuine code
    use and is kept.
    """
    import ast

    prose_ids = {
        id(node.value)
        for node in ast.walk(tree)  # type: ignore[arg-type]
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    }
    return {
        node.value
        for node in ast.walk(tree)  # type: ignore[arg-type]
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in prose_ids
    }


# --------------------------------------------------------------------------- #
# The legacy ``governance.charter.selected_<kind>`` block inside charter.yaml
# A fifth surface, nested inside the SAME charter.yaml file the top-level
# activated_<kind>/catalog surface already touches.
# --------------------------------------------------------------------------- #


def _seed_governance_charter_block(tmp_path: Path) -> Path:
    _write(
        tmp_path / _CHARTER_RELATIVE_PATH,
        "schema_version: 2.0.0\n"
        "governance:\n"
        "  charter:\n"
        "    selected_tactics:\n"
        "    - alpha-tactic\n"
        "    - widget-polish\n"
        "    - omega-tactic\n"
        "    selected_procedures: []\n",  # already-narrowed empty list: successor list EXISTS here
    )
    return tmp_path


def test_detect_true_for_governance_charter_selected_block(tmp_path: Path) -> None:
    retirement = Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC")
    _seed_governance_charter_block(tmp_path)

    assert detect_retirements(tmp_path, (retirement,), include_answers_surface=True) is True


def test_apply_removes_stem_from_governance_charter_selected_block(tmp_path: Path) -> None:
    project = _seed_governance_charter_block(tmp_path)
    retirement = Retirement(
        kind_key="activated_tactics",
        stem="widget-polish",
        reference_prefix="TACTIC",
        successors=(("activated_procedures", "widget-audit"),),
    )

    result = apply_retirements(project, (retirement,), include_answers_surface=True)

    assert result.success is True
    charter = _load(project / _CHARTER_RELATIVE_PATH)
    assert charter["governance"]["charter"]["selected_tactics"] == ["alpha-tactic", "omega-tactic"]
    # governance.charter.selected_procedures EXISTED (as []) -- successor activated there,
    # nested under governance.charter, matching the substitution rule applied to
    # the top-level activated_<kind> surfaces.
    assert charter["governance"]["charter"]["selected_procedures"] == ["widget-audit"]


def test_apply_does_not_invent_governance_charter_successor_list(tmp_path: Path) -> None:
    """bug-fixing-checklist-style row: the successor's selected_procedures list is absent entirely."""
    _write(
        tmp_path / _CHARTER_RELATIVE_PATH,
        "governance:\n  charter:\n    selected_tactics:\n    - widget-polish\n",
    )
    retirement = Retirement(
        kind_key="activated_tactics",
        stem="widget-polish",
        reference_prefix="TACTIC",
        successors=(("activated_procedures", "widget-audit"),),
    )

    result = apply_retirements(tmp_path, (retirement,), include_answers_surface=True)

    assert result.success is True
    charter = _load(tmp_path / _CHARTER_RELATIVE_PATH)
    assert charter["governance"]["charter"]["selected_tactics"] == []
    assert "selected_procedures" not in charter["governance"]["charter"]


def test_apply_does_not_reactivate_an_already_present_governance_charter_successor(tmp_path: Path) -> None:
    _write(
        tmp_path / _CHARTER_RELATIVE_PATH,
        "governance:\n  charter:\n    selected_tactics:\n    - widget-polish\n    selected_procedures:\n    - widget-audit\n",
    )
    retirement = Retirement(
        kind_key="activated_tactics",
        stem="widget-polish",
        reference_prefix="TACTIC",
        successors=(("activated_procedures", "widget-audit"),),
    )

    result = apply_retirements(tmp_path, (retirement,), include_answers_surface=True)

    assert result.success is True
    charter = _load(tmp_path / _CHARTER_RELATIVE_PATH)
    assert charter["governance"]["charter"]["selected_procedures"] == ["widget-audit"]
    assert not any("Activated successor" in change for change in result.changes_made)


def test_apply_is_idempotent_for_governance_charter_selected_block(tmp_path: Path) -> None:
    project = _seed_governance_charter_block(tmp_path)
    retirement = (
        Retirement(
            kind_key="activated_tactics",
            stem="widget-polish",
            reference_prefix="TACTIC",
            successors=(("activated_procedures", "widget-audit"),),
        ),
    )

    first = apply_retirements(project, retirement, include_answers_surface=True)
    second = apply_retirements(project, retirement, include_answers_surface=True)

    assert first.success is True
    assert second.success is True
    assert second.changes_made == []
    assert detect_retirements(project, retirement, include_answers_surface=True) is False


def test_apply_on_a_bare_project_creates_no_governance_key(tmp_path: Path) -> None:
    """No ``governance`` block at all -- charter.yaml is not created, and no key is invented."""
    retirement = (Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC"),)

    result = apply_retirements(tmp_path, retirement, include_answers_surface=True)

    assert result.success is True
    assert result.changes_made == []
    assert not (tmp_path / ".kittify").exists()


def test_apply_leaves_governance_charter_untouched_when_no_charter_subsection(tmp_path: Path) -> None:
    """A ``governance:`` block that carries no ``charter:`` subsection is left alone."""
    _write(tmp_path / _CHARTER_RELATIVE_PATH, "governance:\n  testing:\n    min_coverage: 90\n")
    retirement = (Retirement(kind_key="activated_tactics", stem="widget-polish", reference_prefix="TACTIC"),)

    result = apply_retirements(tmp_path, retirement, include_answers_surface=True)

    assert result.success is True
    assert result.changes_made == []
    charter = _load(tmp_path / _CHARTER_RELATIVE_PATH)
    assert charter == {"governance": {"testing": {"min_coverage": 90}}}


def test_no_src_module_reads_consumer_graph_yml() -> None:
    """Pins Rule 6's finding: nothing under src/ opens ``.kittify/charter/graph.yml``.

    A module nothing reads cannot be broken by a stale node/edge id inside
    it, so this migration deliberately does not add ``graph.yml`` to its
    surfaces. If a future change makes something under ``src/`` read
    ``graph.yml``, this guard fails and that decision must be revisited
    (see ``m_4_0_0rc5_retire_single_owner_doctrine_ids``'s module docstring,
    "Consumer graph.yml (Rule 6)"). Only genuine CODE uses of the literal are
    checked (see :func:`_code_string_constants`) -- this module's own
    docstring, and this test's, may freely discuss ``graph.yml`` in prose.
    """
    import ast

    src_root = _repo_root() / "src"
    offenders: list[str] = []
    for path in src_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any("graph.yml" in value for value in _code_string_constants(tree)):
            offenders.append(str(path.relative_to(src_root)))
    assert offenders == []
