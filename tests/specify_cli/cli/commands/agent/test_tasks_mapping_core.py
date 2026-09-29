"""Per-branch unit tests for the pure requirement-mapping core (WP04 / T018).

RED-first artifact (charter C-011): these tests import
``specify_cli.cli.commands.agent.tasks_mapping_core`` — which does NOT exist on
the lane base — so the whole module fails to collect (red) until :func:`plan_mapping`
is implemented (T019). Once green, every named branch of the ``MappingPlan``
decision entity (``data-model.md`` §MappingPlan) is exercised with ``--cov-branch``:
the offender buckets (malformed / unknown_spec_id), each mode (wp_refs / batch /
tracker_only), the replace-vs-union merge fork, the tasks.md union fallback, and
the ``unmapped_fr`` coverage projection over untouched WPs.

``plan_mapping`` is PURE (INV-4): every input here is an in-memory fact — no
filesystem, git, or clock access — so a Fake reader is unnecessary; the injected
reads ARE the request fields.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import tasks as tasks_module
from specify_cli.cli.commands.agent.tasks import app
from specify_cli.cli.commands.agent.tasks_mapping_core import (
    MappingOffenders,
    MappingPlan,
    MappingRequest,
    plan_mapping,
)
from tests.mocked_env import setup_mocked_env

pytestmark = pytest.mark.fast


def _req(
    *,
    new_mappings: dict[str, list[str]],
    mode: str,
    replace: bool = False,
    spec_all_ids: frozenset[str] = frozenset({"FR-001", "FR-002", "NFR-001", "C-001"}),
    spec_functional_ids: frozenset[str] = frozenset({"FR-001", "FR-002"}),
    existing_all_refs: dict[str, list[str]] | None = None,
    tasks_md_refs: dict[str, list[str]] | None = None,
    bare_prose_requirement_ids: frozenset[str] = frozenset(),
) -> MappingRequest:
    return MappingRequest(
        spec_all_ids=spec_all_ids,
        spec_functional_ids=spec_functional_ids,
        new_mappings=new_mappings,
        existing_all_refs=existing_all_refs or {},
        tasks_md_refs=tasks_md_refs or {},
        mode=mode,
        replace=replace,
        bare_prose_requirement_ids=bare_prose_requirement_ids,
    )


# ---------------------------------------------------------------------------
# Merge decision: union vs replace vs tasks.md fallback
# ---------------------------------------------------------------------------


def test_individual_union_merges_existing_and_new() -> None:
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-002"]},
            mode="wp_refs",
            replace=False,
            existing_all_refs={"WP01": ["FR-001"]},
        )
    )
    assert plan.to_write == {"WP01": ["FR-001", "FR-002"]}
    assert plan.offenders == MappingOffenders(malformed=(), unknown_spec_id=())


def test_individual_replace_overwrites_existing() -> None:
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-002"]},
            mode="wp_refs",
            replace=True,
            existing_all_refs={"WP01": ["FR-001"]},
        )
    )
    # replace drops the pre-existing FR-001 rather than unioning it in.
    assert plan.to_write == {"WP01": ["FR-002"]}


def test_union_falls_back_to_tasks_md_when_frontmatter_empty() -> None:
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-002"]},
            mode="wp_refs",
            replace=False,
            existing_all_refs={"WP01": []},
            tasks_md_refs={"WP01": ["FR-001"]},
        )
    )
    assert plan.to_write == {"WP01": ["FR-001", "FR-002"]}


def test_union_ignores_tasks_md_when_frontmatter_present() -> None:
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-002"]},
            mode="wp_refs",
            replace=False,
            existing_all_refs={"WP01": ["FR-001"]},
            tasks_md_refs={"WP01": ["NFR-001"]},
        )
    )
    # Frontmatter is present so the tasks.md fallback is NOT consulted.
    assert plan.to_write == {"WP01": ["FR-001", "FR-002"]}


def test_to_write_values_sorted_and_deduped() -> None:
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-002", "FR-001", "FR-002"]},
            mode="wp_refs",
            replace=True,
        )
    )
    assert plan.to_write == {"WP01": ["FR-001", "FR-002"]}


# ---------------------------------------------------------------------------
# requirement-id-grammar-01M3NRCA WP03 (T017): append-only merge -- existing
# items are kept byte-identical, in place, never re-sorted (FR-005).
# ---------------------------------------------------------------------------


def test_append_only_union_preserves_existing_order_not_sorted() -> None:
    """FR-005 append-only: order preserved (was sorted). Existing FR-002 stays
    first; the new FR-001 is appended after it, never re-sorted alphabetically."""
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-001"]},
            mode="wp_refs",
            replace=False,
            existing_all_refs={"WP01": ["FR-002"]},
        )
    )
    assert plan.to_write == {"WP01": ["FR-002", "FR-001"]}


def test_append_only_dedups_new_ref_by_canonical_form_keeps_stored_spelling() -> None:
    """An existing ``FR-006A`` plus a new canonical ``FR-006a`` gives ONE item,
    the original spelling -- dedup is by canonical form, never a respell."""
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-006a"]},
            mode="wp_refs",
            replace=False,
            existing_all_refs={"WP01": ["FR-006A"]},
        )
    )
    assert plan.to_write == {"WP01": ["FR-006A"]}


def test_append_only_never_collapses_pre_existing_duplicates() -> None:
    """The never-erase contract includes an author's own pre-existing
    duplicate -- the merge only guards NEW refs against the existing set,
    never the reverse."""
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-002"]},
            mode="wp_refs",
            replace=False,
            existing_all_refs={"WP01": ["FR-001", "FR-001"]},
        )
    )
    assert plan.to_write == {"WP01": ["FR-001", "FR-001", "FR-002"]}


def test_replace_preserves_stored_spelling_over_new_retyped_case() -> None:
    """``--replace`` never respells: a stored ``FR-006A`` stays ``FR-006A``
    even though the operator retyped it lowercase (analysis B7)."""
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-006a"]},
            mode="wp_refs",
            replace=True,
            existing_all_refs={"WP01": ["FR-006A"]},
        )
    )
    assert plan.to_write == {"WP01": ["FR-006A"]}


def test_replaced_refs_removed_lists_dropped_items_only_on_replace() -> None:
    """``--replace`` reports what it dropped, in original on-disk order; the
    default (union) leg never populates the field for that WP (positive
    control below)."""
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-001"]},
            mode="wp_refs",
            replace=True,
            existing_all_refs={"WP01": ["FR-009", "FR-001", "NFR-001"]},
        )
    )
    assert plan.to_write == {"WP01": ["FR-001"]}
    assert plan.replaced_refs_removed == {"WP01": ["FR-009", "NFR-001"]}


def test_replaced_refs_removed_empty_on_default_union_mode() -> None:
    """Positive control: the default (union) merge never drops anything, so
    ``replaced_refs_removed`` is empty for every WP it touches."""
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-002"]},
            mode="wp_refs",
            replace=False,
            existing_all_refs={"WP01": ["FR-001"]},
        )
    )
    assert plan.replaced_refs_removed == {}


# ---------------------------------------------------------------------------
# Modes: batch + tracker_only
# ---------------------------------------------------------------------------


def test_batch_mode_maps_multiple_wps() -> None:
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-001"], "WP02": ["FR-002"]},
            mode="batch",
            replace=True,
        )
    )
    assert plan.to_write == {"WP01": ["FR-001"], "WP02": ["FR-002"]}


def test_tracker_only_mode_yields_empty_to_write() -> None:
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": []},
            mode="tracker_only",
        )
    )
    # tracker-only touches tracker_refs (shell concern), never requirement_refs.
    assert plan.to_write == {}
    assert plan.offenders == MappingOffenders(malformed=(), unknown_spec_id=())


# ---------------------------------------------------------------------------
# Offenders: malformed + unknown_spec_id
# ---------------------------------------------------------------------------


def test_malformed_offender_detected() -> None:
    # requirement-id-grammar-01M3NRCA WP03: FR-1A now parses (a letter suffix
    # is well-formed grammar), so it is no longer a malformed-offender fixture.
    # FR_1 (underscore) genuinely fails to parse.
    plan = plan_mapping(
        _req(new_mappings={"WP01": ["FR_1"]}, mode="wp_refs", replace=True)
    )
    assert plan.offenders.malformed == ("FR_1",)
    # One reason per ref (FR-010): a malformed ref is never ALSO unknown.
    assert plan.offenders.unknown_spec_id == ()


def test_unknown_spec_id_offender_detected() -> None:
    plan = plan_mapping(
        _req(new_mappings={"WP01": ["FR-999"]}, mode="wp_refs", replace=True)
    )
    # Well-formed but not declared in spec.md → unknown_spec_id (not malformed).
    assert plan.offenders.malformed == ()
    assert plan.offenders.unknown_spec_id == ("FR-999",)


def test_both_offender_buckets_populated() -> None:
    plan = plan_mapping(
        _req(new_mappings={"WP01": ["FR_1", "FR-999"]}, mode="wp_refs", replace=True)
    )
    # requirement-id-grammar-01M3NRCA WP03 / FR-010: each ref carries exactly
    # one reason now -- FR_1 is malformed (raw), FR-999 is unknown_spec_id.
    assert plan.offenders.malformed == ("FR_1",)
    assert plan.offenders.unknown_spec_id == ("FR-999",)


def test_offenders_preserve_input_order() -> None:
    # requirement-id-grammar-01M3NRCA WP03: malformed refs are reported AS
    # TYPED, never uppercased (FR-010) -- "bogus" stays "bogus".
    plan = plan_mapping(
        _req(new_mappings={"WP01": ["fr-002", "bogus", "fr-001"]}, mode="wp_refs", replace=True)
    )
    assert plan.offenders.malformed == ("bogus",)


# ---------------------------------------------------------------------------
# unmapped_fr coverage projection
# ---------------------------------------------------------------------------


def test_unmapped_fr_lists_uncovered_functional_ids() -> None:
    plan = plan_mapping(
        _req(new_mappings={"WP01": ["FR-001"]}, mode="wp_refs", replace=True)
    )
    # FR-002 is functional but unmapped after the write.
    assert plan.unmapped_fr == ["FR-002"]


def test_unmapped_fr_empty_when_all_functional_mapped() -> None:
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-001", "FR-002"]},
            mode="batch",
            replace=True,
        )
    )
    assert plan.unmapped_fr == []


def test_unmapped_fr_counts_untouched_wps() -> None:
    # WP02 is NOT in the new mapping but already covers FR-002 on disk; the
    # coverage projection must union it so FR-002 counts as mapped.
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["FR-001"]},
            mode="wp_refs",
            replace=True,
            existing_all_refs={"WP02": ["FR-002"]},
        )
    )
    assert plan.unmapped_fr == []


def test_nonfunctional_refs_do_not_affect_unmapped_fr() -> None:
    # Mapping only NFR-001 / C-001 leaves both functional FRs unmapped.
    plan = plan_mapping(
        _req(new_mappings={"WP01": ["NFR-001", "C-001"]}, mode="wp_refs", replace=True)
    )
    assert plan.unmapped_fr == ["FR-001", "FR-002"]


def test_returns_mapping_plan_instance() -> None:
    plan = plan_mapping(_req(new_mappings={"WP01": ["FR-001"]}, mode="wp_refs", replace=True))
    assert isinstance(plan, MappingPlan)
    assert isinstance(plan.offenders, MappingOffenders)


# ---------------------------------------------------------------------------
# T021 -- fake-core sentinel: the plan's RETURN VALUE drives the command.
# ---------------------------------------------------------------------------
#
# The anti-shadow-code guard (FR-002): a "called-but-result-discarded" core would
# pass a grep-for-callers check while the old inline mapping/validation logic still
# ran. These tests inject a SENTINEL ``MappingPlan`` that CONTRADICTS what the real
# ``plan_mapping`` would produce and assert the command's observable result follows
# the sentinel — proving the core genuinely DRIVES ``map_requirements``.

_MID8 = "01KWF08S"


def _mapping_mission(root: Path, slug: str) -> Path:
    feature_dir = root / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True)
    (root / ".kittify").mkdir(exist_ok=True)
    (feature_dir / "tasks" / "WP01-fixture.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Fixture WP01\n"
        "execution_mode: code_change\n"
        "agent: testbot\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Work Packages\n\n## WP01 - fixture\n- [ ] T001 do a thing\n", encoding="utf-8"
    )
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## Functional Requirements\n\n"
        "- FR-001: do a thing.\n- FR-002: do another.\n",
        encoding="utf-8",
    )
    return feature_dir


def test_sentinel_offenders_drive_the_command_to_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sentinel ``offenders.malformed`` flips a would-succeed mapping to exit 1.

    The real ``plan_mapping`` on ``--wp WP01 --refs FR-001`` returns NO offenders
    (FR-001 is well-formed and declared), so the command would exit 0. The sentinel
    injects a malformed offender — the command refuses with exit 1 and the
    sentinel's token ONLY because the plan drives the pre-write gate.
    """
    fd = _mapping_mission(tmp_path, f"sentinel-map-refuse-{_MID8}")

    def _fake(_req: MappingRequest) -> MappingPlan:
        return MappingPlan(
            to_write={},
            offenders=MappingOffenders(malformed=("SENTINEL-BAD-9c1f",), unknown_spec_id=()),
            unmapped_fr=[],
        )

    monkeypatch.setattr(tasks_module, "plan_mapping", _fake)
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name):
        result = CliRunner().invoke(
            app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-001",
             "--mission", fd.name, "--no-auto-commit", "--json"],
        )
    assert result.exit_code == 1, result.output
    assert "SENTINEL-BAD-9c1f" in result.output


def test_sentinel_to_write_drives_the_written_refs_and_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sentinel ``to_write`` / ``unmapped_fr`` drives the write + the envelope.

    The operator asks to map WP01 → FR-001, but the sentinel plan writes FR-002 and
    reports FR-001 as unmapped. The command's observable result FOLLOWS the plan:

    * ``mapped`` (echoing the operator INPUT) stays ``FR-001``,
    * ``total_mappings`` (re-read from disk AFTER the write) is ``FR-002`` — proving
      the sentinel ``to_write`` drove the frontmatter write, not the input, and
    * ``coverage.unmapped_functional`` is ``FR-001`` — proving ``unmapped_fr`` drove
      the reported coverage.
    """
    fd = _mapping_mission(tmp_path, f"sentinel-map-write-{_MID8}")

    def _fake(_req: MappingRequest) -> MappingPlan:
        return MappingPlan(
            to_write={"WP01": ["FR-002"]},
            offenders=MappingOffenders(malformed=(), unknown_spec_id=()),
            unmapped_fr=["FR-001"],
        )

    monkeypatch.setattr(tasks_module, "plan_mapping", _fake)
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name):
        result = CliRunner().invoke(
            app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-001",
             "--mission", fd.name, "--no-auto-commit", "--json"],
        )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["mapped"]["WP01"] == ["FR-001"]
    assert payload["total_mappings"]["WP01"] == ["FR-002"]
    assert payload["coverage"]["unmapped_functional"] == ["FR-001"]

    # The written frontmatter itself follows the sentinel ``to_write``.
    body = (fd / "tasks" / "WP01-fixture.md").read_text(encoding="utf-8")
    assert "FR-002" in body and "FR-001" not in body


# ---------------------------------------------------------------------------
# #3394 review F1: non-blocking requirement-extraction-warning signal
# ---------------------------------------------------------------------------


def test_map_requirements_surfaces_undeclared_requirement_citations_without_failing(
    tmp_path: Path,
) -> None:
    """A spec whose Functional Requirements section is written as bare,
    unbulleted, unbolded sentences (FR-001, FR-002) yields zero declared ids
    for THOSE tokens -- ``map-requirements`` must still succeed (exit 0) when
    the operator maps WP01 against a SEPARATE, properly-declared FR-100, but
    the JSON payload must name the undeclared tokens instead of staying
    silent about them (review F1).
    """
    fd = _mapping_mission(tmp_path, f"undeclared-fr-warn-{_MID8}")
    (fd / "spec.md").write_text(
        "# Spec\n\n"
        "## Functional Requirements\n\nFR-001 must hold. FR-002 too.\n\n"
        "## Declared Functional Requirements\n\n- FR-100: The declared one.\n",
        encoding="utf-8",
    )
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name):
        result = CliRunner().invoke(
            app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-100",
             "--mission", fd.name, "--no-auto-commit", "--json"],
        )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    warnings = payload["requirement_extraction_warnings"]
    assert warnings, "expected a non-empty requirement_extraction_warnings"
    warning_text = " ".join(warnings)
    assert "FR-001" in warning_text
    assert "FR-002" in warning_text


# ---------------------------------------------------------------------------
# WP06 (#3396) T032/T032a: bare-prose requirement ids wired through
# MappingRequest -> plan_mapping -> MappingPlan, then surfaced by the
# map-requirements CLI's JSON payload (Story 1 AC1/AC2, non-clean-coverage
# leg of the Success criterion).
# ---------------------------------------------------------------------------


def test_plan_mapping_surfaces_bare_prose_requirement_ids() -> None:
    """``plan_mapping`` reads ``req.bare_prose_requirement_ids`` (already
    computed by the shell) and surfaces it, sorted, under the SAME field name
    on the returned ``MappingPlan`` -- never merged into ``unmapped_fr``."""
    plan = plan_mapping(
        _req(
            new_mappings={"WP01": ["NFR-001"]},
            mode="wp_refs",
            replace=True,
            bare_prose_requirement_ids=frozenset({"FR-002", "FR-001"}),
        )
    )
    assert plan.bare_prose_requirement_ids == ["FR-001", "FR-002"]


def test_plan_mapping_bare_prose_requirement_ids_empty_by_default() -> None:
    """The default ``MappingRequest.bare_prose_requirement_ids`` (empty
    frozenset) round-trips to an empty ``MappingPlan`` list -- pre-existing
    callers that never populate it are unaffected."""
    plan = plan_mapping(_req(new_mappings={"WP01": ["FR-001"]}, mode="wp_refs", replace=True))
    assert plan.bare_prose_requirement_ids == []


def test_map_requirements_cli_surfaces_bare_prose_requirement_ids(
    tmp_path: Path,
) -> None:
    """Story 1 AC1/AC2 at the CLI-command level: a spec.md whose Functional
    Requirements section writes FR-001/FR-002 as bare, unbulleted, unbolded
    prose alongside a properly-declared NFR-001 table row makes
    ``map-requirements`` name FR-001/FR-002 explicitly in the
    ``bare_prose_requirement_ids`` JSON field -- constructed here against the
    issue's exact repro shape and asserted on the REAL command's stdout (not
    a sentinel), proving the wiring survives the full
    ``_mr_resolve_read_dirs`` -> ``_mr_plan`` -> ``plan_mapping`` ->
    ``_mr_emit_output`` call chain."""
    fd = _mapping_mission(tmp_path, f"bare-prose-repro-{_MID8}")
    (fd / "spec.md").write_text(
        "# Spec\n\n"
        "### Functional Requirements\n\n"
        "FR-001 the loader must reject an unknown pack.\n"
        "FR-002 the error must name the offending path.\n\n"
        "| ID | Requirement |\n"
        "|----|-------------|\n"
        "| NFR-001 | Resolution completes within 200ms |\n",
        encoding="utf-8",
    )
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name):
        result = CliRunner().invoke(
            app,
            ["map-requirements", "--wp", "WP01", "--refs", "NFR-001",
             "--mission", fd.name, "--no-auto-commit", "--json"],
        )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["bare_prose_requirement_ids"] == ["FR-001", "FR-002"]
