"""Direct unit tests for the finalize-tasks phase helpers (#2056 WP07, T029/T030).

The pre-decomposition ``finalize_tasks`` was a 1227-LOC monolith — the worst
offender in ``mission.py``. WP07 relocated it to ``mission_finalize`` and split
the body into ≤15-CC phase helpers. These tests exercise each deterministic
helper's branches in isolation: artifact collection + branch-tree path mapping,
the 3-tier dependency/requirement resolution, the cycle + requirement-mapping
gates, the disagree-loud conflict gate, the 8-field bootstrap-mutation applies
(including the INV-6 zero-mutation invariant), the owned-files / kitty-specs
gate, and the validation-frontmatter acquisition.

The end-to-end command stays pinned by ``test_mission_finalize_tasks.py``,
``test_feature_finalize_bootstrap.py``, the validate-only readonly suite, and
the WP01 golden harness. The relocated ``_collect_finalize_artifacts`` /
``_branch_tree_relative_path`` keep their existing integration coverage via
``test_finalize_coord_staging.py`` (which still imports them off ``mission``).
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest
import typer
from rich.console import Console

from specify_cli.cli.commands.agent import mission_finalize as seam
from specify_cli.lanes.models import LanesManifest
from specify_cli.ownership.models import WorkProductKind, OwnershipManifest
from specify_cli.status import Lane, WPMetadata

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# _branch_tree_relative_path
# ---------------------------------------------------------------------------


def test_branch_tree_relative_path_plain(tmp_path: Path) -> None:
    repo = tmp_path
    f = repo / "kitty-specs" / "m" / "tasks.md"
    f.parent.mkdir(parents=True)
    f.write_text("x", encoding="utf-8")
    assert seam._branch_tree_relative_path(f, repo) == "kitty-specs/m/tasks.md"


def test_branch_tree_relative_path_strips_worktree_prefix(tmp_path: Path) -> None:
    repo = tmp_path
    wt = repo / ".worktrees" / "lane-a"
    target = wt / "kitty-specs" / "m" / "tasks.md"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    # ``.worktrees/<name>`` is a real dir → the prefix is dropped.
    assert seam._branch_tree_relative_path(target, repo) == "kitty-specs/m/tasks.md"


# ---------------------------------------------------------------------------
# _collect_finalize_artifacts
# ---------------------------------------------------------------------------


def test_collect_finalize_artifacts_dedupes_and_filters_missing(tmp_path: Path) -> None:
    feature = tmp_path / "kitty-specs" / "001-m"
    tasks = feature / "tasks"
    tasks.mkdir(parents=True)
    (feature / "tasks.md").write_text("x", encoding="utf-8")
    (feature / "status.json").write_text("{}", encoding="utf-8")
    (tasks / "WP01.md").write_text("x", encoding="utf-8")
    lanes = feature / "lanes.json"
    lanes.write_text("{}", encoding="utf-8")

    artifacts = seam._collect_finalize_artifacts(feature, tasks, lanes_path=lanes)

    # Only existing files; no duplicates; missing candidates (events log, matrices) skipped.
    assert (feature / "tasks.md") in artifacts
    assert (feature / "status.json") in artifacts
    assert (tasks / "WP01.md") in artifacts
    assert lanes in artifacts
    assert len(artifacts) == len(set(artifacts))
    assert all(p.exists() for p in artifacts)


# ---------------------------------------------------------------------------
# _branch_strategy_text
# ---------------------------------------------------------------------------


def test_branch_strategy_text_embeds_target_branch() -> None:
    text = seam._branch_strategy_text("prog/x")
    assert "generated on prog/x" in text
    assert "merge back into prog/x" in text


def test_apply_ownership_inference_rejects_code_change_empty_owned_files() -> None:
    meta = WPMetadata(
        work_package_id="WP01",
        title="Code",
        execution_mode="code_change",
        owned_files=[],
    )

    changed, warnings, contradiction = seam._apply_ownership_inference(
        meta.builder(),
        meta,
        "---\nowned_files: []\n---\n# WP01\n",
        "001-mission",
        {},
    )

    assert changed is False
    assert warnings == []
    assert contradiction is not None
    assert "WP01" in contradiction


def test_raise_ownership_contradictions_reports_all_json(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(seam, "_emit_json", emitted.append)
    state = seam._BootstrapState(
        ownership_contradictions=[
            "WP01: code_change WP declares no owned files",
            "WP03: code_change WP declares no owned files",
        ]
    )

    with pytest.raises(typer.Exit):
        seam._raise_ownership_contradictions_if_any(state, ["WP01", "WP03"], json_output=True)

    assert emitted[0]["error_code"] == seam.OWNERSHIP_CONTRADICTION_CODE_CHANGE_EMPTY_OWNED_FILES
    assert emitted[0]["ownership_contradiction_wp_ids"] == ["WP01", "WP03"]


def test_project_lane_inputs_excludes_canceled_wps() -> None:
    manifests = {
        "WP01": OwnershipManifest(WorkProductKind.CODE_CHANGE, ("src/a.py",), "src/"),
        "WP02": OwnershipManifest(WorkProductKind.CODE_CHANGE, ("src/b.py",), "src/"),
        "WP03": OwnershipManifest(WorkProductKind.CODE_CHANGE, ("src/c.py",), "src/"),
    }
    frontmatters = {
        "WP01": WPMetadata(work_package_id="WP01", title="A", lane=Lane.PLANNED),
        "WP02": WPMetadata(work_package_id="WP02", title="B", lane=Lane.CANCELED),
        "WP03": WPMetadata(work_package_id="WP03", title="C", lane=Lane.PLANNED),
    }

    eligibility, lane_manifests, lane_dependencies, lane_bodies = seam._project_lane_inputs(
        manifests,
        {"WP01": [], "WP02": [], "WP03": ["WP01"]},
        frontmatters,
        {"WP01": "a", "WP02": "b", "WP03": "c"},
    )

    assert eligibility.canceled_wp_ids == ("WP02",)
    assert set(lane_manifests) == {"WP01", "WP03"}
    assert lane_dependencies == {"WP01": [], "WP03": ["WP01"]}
    assert lane_bodies == {"WP01": "a", "WP03": "c"}


def test_stale_canceled_dependencies_fail_loud_json(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(seam, "_emit_json", emitted.append)
    frontmatters = {
        "WP01": WPMetadata(work_package_id="WP01", title="A", lane=Lane.CANCELED),
        "WP02": WPMetadata(work_package_id="WP02", title="B", lane=Lane.PLANNED),
    }
    eligibility, *_ = seam._project_lane_inputs({}, {"WP01": [], "WP02": ["WP01"]}, frontmatters, {})

    with pytest.raises(typer.Exit):
        seam._raise_stale_canceled_dependencies_if_any(eligibility, json_output=True)

    assert emitted[0]["error_code"] == "STALE_CANCELED_DEPENDENCIES"
    assert emitted[0]["stale_canceled_dependencies"] == [
        {
            "dependent_wp_id": "WP02",
            "canceled_dependency_wp_id": "WP01",
            "recovery": "Remove the dependency or repoint WP02 to a non-canceled prerequisite.",
        }
    ]


def test_compute_and_write_lanes_empty_code_change_inputs_fail_loud(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(seam, "_emit_json", emitted.append)

    with pytest.raises(typer.Exit):
        seam._compute_and_write_lanes(
            tmp_path,
            tmp_path,
            "001-mission",
            {},
            {},
            {"WP01": WPMetadata(work_package_id="WP01", title="A", execution_mode="code_change")},
            {},
            None,
            "main",
            json_output=True,
        )

    assert emitted[0]["error_code"] == seam.LANE_COMPUTATION_ABORTED_EMPTY_INPUTS


def test_compute_and_write_lanes_empty_planning_artifact_inputs_are_laneless(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam, "_preserve_or_capture_planning_commit_sha", lambda *args, **kwargs: None)
    monkeypatch.setattr(seam, "_report_parallelization_risk", lambda *args, **kwargs: None)

    lanes_path, lanes_manifest, planning_sha = seam._compute_and_write_lanes(
        tmp_path,
        tmp_path,
        "001-mission",
        {},
        {},
        {
            "WP01": WPMetadata(
                work_package_id="WP01",
                title="A",
                execution_mode="planning_artifact",
                owned_files=[],
            )
        },
        {},
        None,
        "main",
        json_output=True,
    )

    assert lanes_path == tmp_path / "lanes.json"
    assert lanes_manifest is not None
    assert lanes_manifest.lanes == []
    # #4141: the third return element is the planning_commit_sha decision —
    # None here because the monkeypatched seam returns None (the tolerated
    # historical shape), and the manifest was assigned that None verbatim.
    assert planning_sha is None
    assert lanes_manifest.planning_commit_sha is None


def test_validate_only_previews_empty_code_change_input_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(seam, "_emit_json", emitted.append)
    monkeypatch.setattr(
        seam,
        "_bootstrap_canonical_state_via_mission",
        lambda *args, **kwargs: seam.BootstrapResult(0, 0, 0),
    )
    state = seam._BootstrapState(inmemory_frontmatter={"WP01": WPMetadata(work_package_id="WP01", title="A", execution_mode="code_change")})

    with pytest.raises(typer.Exit):
        seam._emit_validate_only_report(
            tmp_path,
            "001-mission",
            None,
            state,
            {},
            {},
            {},
            "main",
            json_output=True,
        )

    assert emitted[0]["error_code"] == seam.LANE_COMPUTATION_ABORTED_EMPTY_INPUTS


# ---------------------------------------------------------------------------
# _validate_dependency_graph
# ---------------------------------------------------------------------------


def test_validate_dependency_graph_passes_for_acyclic() -> None:
    # No exception for a valid DAG.
    seam._validate_dependency_graph({"WP02": ["WP01"], "WP01": []}, json_output=True)


def test_validate_dependency_graph_rejects_cycle() -> None:
    with pytest.raises(typer.Exit):
        seam._validate_dependency_graph({"WP01": ["WP02"], "WP02": ["WP01"]}, json_output=True)


def test_validate_dependency_graph_noop_when_empty() -> None:
    seam._validate_dependency_graph({}, json_output=True)


# ---------------------------------------------------------------------------
# _validate_requirement_mapping
# ---------------------------------------------------------------------------


def test_requirement_mapping_passes_when_all_functional_covered() -> None:
    seam._validate_requirement_mapping(
        ["WP01"],
        {"WP01": ["FR-001"]},
        {"FR-001"},
        {"FR-001"},
        {"WP01": []},
        json_output=True,
    )


def test_requirement_mapping_rejects_unmapped_functional() -> None:
    with pytest.raises(typer.Exit):
        seam._validate_requirement_mapping(
            ["WP01"],
            {"WP01": ["FR-001"]},
            {"FR-001", "FR-002"},
            {"FR-001", "FR-002"},
            {"WP01": []},
            json_output=True,
        )


def test_requirement_mapping_rejects_missing_refs() -> None:
    with pytest.raises(typer.Exit):
        seam._validate_requirement_mapping(
            ["WP01"],
            {},
            {"FR-001"},
            {"FR-001"},
            {"WP01": []},
            json_output=True,
        )


def test_requirement_mapping_rejects_unknown_ref() -> None:
    with pytest.raises(typer.Exit):
        seam._validate_requirement_mapping(
            ["WP01"],
            {"WP01": ["FR-999"]},
            {"FR-001"},
            {"FR-001"},
            {"WP01": []},
            json_output=True,
        )


# ---------------------------------------------------------------------------
# _classify_wp_requirement_refs (WP02 campsite-clean extraction)
# ---------------------------------------------------------------------------


def test_classify_wp_requirement_refs_buckets_missing_unknown_mapped() -> None:
    missing, unknown, mapped = seam._classify_wp_requirement_refs(
        ["WP01", "WP02", "WP03"],
        {"WP01": [], "WP02": ["FR-999"], "WP03": ["FR-001", "FR-002"]},
        {"FR-001", "FR-002"},
    )
    assert missing == ["WP01"]
    assert unknown == {"WP02": ["FR-999"]}
    assert mapped == {"FR-001", "FR-002"}


def test_classify_wp_requirement_refs_dedupes_and_sorts_wp_ids() -> None:
    # Duplicate wp_ids collapse via `sorted(set(...))`; unsorted input still
    # produces deterministic (sorted) bucket membership.
    missing, unknown, mapped = seam._classify_wp_requirement_refs(
        ["WP02", "WP01", "WP01"],
        {},
        set(),
    )
    assert missing == ["WP01", "WP02"]
    assert unknown == {}
    assert mapped == set()


# ---------------------------------------------------------------------------
# _emit_requirement_mapping_report (WP02 campsite-clean extraction)
# ---------------------------------------------------------------------------


def test_emit_requirement_mapping_report_json(capsys: pytest.CaptureFixture[str]) -> None:
    seam._emit_requirement_mapping_report(
        json_output=True,
        missing_requirement_refs_wps=["WP01"],
        unknown_requirement_refs={"WP02": ["FR-999"]},
        unmapped_functional_requirements=["FR-002"],
        bare_prose_requirement_ids=[],
        wp_dependencies={"WP01": []},
        wp_requirement_refs={"WP02": ["FR-999"]},
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "error": "Requirement mapping validation failed",
        "missing_requirement_refs_wps": ["WP01"],
        "unknown_requirement_refs": {"WP02": ["FR-999"]},
        "unmapped_functional_requirements": ["FR-002"],
        "bare_prose_requirement_ids": [],
        "dependencies_parsed": {"WP01": []},
        "requirement_refs_parsed": {"WP02": ["FR-999"]},
    }


def test_emit_requirement_mapping_report_console(capsys: pytest.CaptureFixture[str]) -> None:
    seam._emit_requirement_mapping_report(
        json_output=False,
        missing_requirement_refs_wps=["WP01"],
        unknown_requirement_refs={"WP02": ["FR-999"]},
        unmapped_functional_requirements=["FR-002"],
        bare_prose_requirement_ids=[],
        wp_dependencies={"WP01": []},
        wp_requirement_refs={"WP02": ["FR-999"]},
    )
    output = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
    assert "Requirement mapping validation failed" in output
    assert "Missing requirement refs:" in output
    assert "- WP01" in output
    assert "Unknown requirement refs:" in output
    assert "- WP02: FR-999" in output
    assert "Unmapped functional requirements:" in output
    assert "- FR-002" in output


def test_emit_requirement_mapping_report_json_includes_bare_prose_ids(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """WP06 (#3396): ``bare_prose_requirement_ids`` is additive, never merged
    into ``unmapped_functional_requirements``."""
    seam._emit_requirement_mapping_report(
        json_output=True,
        missing_requirement_refs_wps=[],
        unknown_requirement_refs={},
        unmapped_functional_requirements=[],
        bare_prose_requirement_ids=["FR-001", "FR-002"],
        wp_dependencies={"WP01": []},
        wp_requirement_refs={"WP01": ["NFR-001"]},
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["bare_prose_requirement_ids"] == ["FR-001", "FR-002"]
    assert payload["unmapped_functional_requirements"] == []


def test_emit_requirement_mapping_report_console_includes_bare_prose_ids(
    capsys: pytest.CaptureFixture[str],
) -> None:
    seam._emit_requirement_mapping_report(
        json_output=False,
        missing_requirement_refs_wps=[],
        unknown_requirement_refs={},
        unmapped_functional_requirements=[],
        bare_prose_requirement_ids=["FR-001", "FR-002"],
        wp_dependencies={"WP01": []},
        wp_requirement_refs={"WP01": ["NFR-001"]},
    )
    output = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
    assert "Bare-prose requirement id(s) found, uncounted:" in output
    assert "- FR-001" in output
    assert "- FR-002" in output


# ---------------------------------------------------------------------------
# WP06 (#3396) T031/T033: bare-prose requirement ids wired into
# _validate_requirement_mapping (Story 1 AC1/AC2 -- the issue's exact repro).
# ---------------------------------------------------------------------------

#: The issue's exact repro Functional Requirements section: FR-001/FR-002
#: written as bare, unbulleted, unbolded prose alongside a properly DECLARED
#: NFR-001 table row in the SAME section.
_BARE_PROSE_REPRO_SPEC = (
    "### Functional Requirements\n\n"
    "FR-001 the loader must reject an unknown pack.\n"
    "FR-002 the error must name the offending path.\n\n"
    "| ID | Requirement |\n"
    "|----|-------------|\n"
    "| NFR-001 | Resolution completes within 200ms |\n"
)


def test_requirement_mapping_rejects_bare_prose_requirement_ids(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Story 1 AC1/AC2: the repro spec.md fails ``finalize-tasks``'s
    requirement-mapping gate even though every WP's own missing/unknown/
    unmapped bucket is otherwise clean -- naming FR-001/FR-002 explicitly in
    a distinct field, never merely appended to
    ``requirement_extraction_warnings`` (which this call site does not even
    see)."""
    with pytest.raises(typer.Exit):
        seam._validate_requirement_mapping(
            ["WP01"],
            {"WP01": ["NFR-001"]},
            {"NFR-001"},
            set(),
            {"WP01": []},
            _BARE_PROSE_REPRO_SPEC,
            json_output=True,
        )
    payload = json.loads(capsys.readouterr().out)
    assert payload["bare_prose_requirement_ids"] == ["FR-001", "FR-002"]
    assert payload["unmapped_functional_requirements"] == []
    assert payload["missing_requirement_refs_wps"] == []
    assert payload["unknown_requirement_refs"] == {}


def test_requirement_mapping_passes_when_spec_content_defaults_empty() -> None:
    """Backward-compat: the pre-existing 5-positional-arg call shape (no
    ``spec_content``) still passes cleanly -- the new parameter's default
    ("") detects zero bare-prose ids."""
    seam._validate_requirement_mapping(
        ["WP01"],
        {"WP01": ["FR-001"]},
        {"FR-001"},
        {"FR-001"},
        {"WP01": []},
        json_output=True,
    )


def test_requirement_mapping_bare_prose_detection_is_fail_loud(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """WP06 (#3396) IC-04 fault injection: a detector exception becomes an
    explicit, non-empty failure (NFR-002) -- never a swallowed "0 uncounted"
    result -- even though every WP mapping bucket is otherwise clean."""
    import specify_cli.requirement_mapping as req_mapping_module

    def _boom(_spec_content: str) -> list[object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(req_mapping_module, "find_bare_prose_requirement_ids", _boom)
    with pytest.raises(typer.Exit):
        seam._validate_requirement_mapping(
            ["WP01"],
            {"WP01": ["FR-001"]},
            {"FR-001"},
            {"FR-001"},
            {"WP01": []},
            "irrelevant spec content",
            json_output=True,
        )
    payload = json.loads(capsys.readouterr().out)
    assert payload["bare_prose_requirement_ids"], "expected a non-empty failure entry"
    assert "boom" in payload["bare_prose_requirement_ids"][0]


# ---------------------------------------------------------------------------
# _read_spec_requirement_ids (WP06 T031 plumbing fix: also returns spec_content)
# ---------------------------------------------------------------------------


def test_read_spec_requirement_ids_also_returns_raw_spec_content(tmp_path: Path) -> None:
    planning_dir = tmp_path
    (planning_dir / "spec.md").write_text(_BARE_PROSE_REPRO_SPEC, encoding="utf-8")
    all_ids, functional_ids, _warnings, spec_content = seam._read_spec_requirement_ids(planning_dir, json_output=True)
    assert all_ids == {"NFR-001"}
    assert functional_ids == set()
    assert spec_content == _BARE_PROSE_REPRO_SPEC


# ---------------------------------------------------------------------------
# _detect_dependency_conflicts (disagree-loud, T004)
# ---------------------------------------------------------------------------


def _wp_file(tmp_path: Path, name: str, deps: list[str]) -> Path:
    f = tmp_path / name
    dep_yaml = "[]" if not deps else "[" + ", ".join(deps) + "]"
    f.write_text(
        f"---\nwork_package_id: {name[:4]}\ntitle: t\ndependencies: {dep_yaml}\n---\nbody\n",
        encoding="utf-8",
    )
    return f


def test_detect_dependency_conflicts_noop_when_agree(tmp_path: Path) -> None:
    wp = _wp_file(tmp_path, "WP02.md", ["WP01"])
    seam._detect_dependency_conflicts([wp], {"WP02": ["WP01"]}, json_output=True)


def test_detect_dependency_conflicts_raises_on_disagreement(tmp_path: Path) -> None:
    wp = _wp_file(tmp_path, "WP02.md", ["WP01"])
    with pytest.raises(typer.Exit):
        seam._detect_dependency_conflicts([wp], {"WP02": ["WP03"]}, json_output=True)


# ---------------------------------------------------------------------------
# _apply_bootstrap_fields + _apply_ownership_inference
# ---------------------------------------------------------------------------


def test_apply_bootstrap_fields_marks_changes() -> None:
    meta = WPMetadata(work_package_id="WP01", title="t")
    bld = meta.builder()
    changed, fields = seam._apply_bootstrap_fields(
        bld,
        meta,
        deps=["WP00"],
        has_dependencies_line=False,
        requirement_refs=["FR-001"],
        has_requirement_refs_line=False,
        target_branch="prog/x",
    )
    assert changed is True
    assert fields["dependencies"] == ["WP00"]
    assert fields["merge_target_branch"] == "prog/x"
    built = bld.build()
    assert list(built.dependencies) == ["WP00"]
    assert built.merge_target_branch == "prog/x"


def test_apply_bootstrap_fields_keeps_planning_and_final_targets_distinct() -> None:
    meta = WPMetadata(work_package_id="WP01", title="t")
    bld = meta.builder()

    changed, fields = seam._apply_bootstrap_fields(
        bld,
        meta,
        deps=[],
        has_dependencies_line=True,
        requirement_refs=["FR-001"],
        has_requirement_refs_line=True,
        target_branch="op/mission-planning",
        merge_target_branch="main",
    )

    assert changed is True
    assert fields["planning_base_branch"] == "op/mission-planning"
    assert fields["merge_target_branch"] == "main"
    built = bld.build()
    assert built.planning_base_branch == "op/mission-planning"
    assert built.merge_target_branch == "main"
    assert "generated on op/mission-planning" in str(built.branch_strategy)
    assert "merge back into main" in str(built.branch_strategy)


def test_apply_bootstrap_fields_noop_when_already_set() -> None:
    branch = "prog/x"
    meta = WPMetadata(
        work_package_id="WP01",
        title="t",
        dependencies=["WP00"],
        requirement_refs=["FR-001"],
        planning_base_branch=branch,
        merge_target_branch=branch,
        branch_strategy=seam._branch_strategy_text(branch),
    )
    bld = meta.builder()
    changed, fields = seam._apply_bootstrap_fields(
        bld,
        meta,
        deps=["WP00"],
        has_dependencies_line=True,
        requirement_refs=["FR-001"],
        has_requirement_refs_line=True,
        target_branch=branch,
    )
    assert changed is False
    assert fields == {}


# ---------------------------------------------------------------------------
# #3941: legacy string-form dependencies normalization
# ---------------------------------------------------------------------------


def test_raw_frontmatter_dependencies_is_string_form_detects_legacy_forms(tmp_path: Path) -> None:
    """The three legacy string forms (F-55) are all detected as string form."""
    from specify_cli.cli.commands.agent.mission_parsing import (
        _raw_frontmatter_dependencies_is_string_form,
    )

    for raw_value in ('"[]"', '"WP01, WP02"', "WP01"):
        wp_file = tmp_path / "WP02-test.md"
        wp_file.write_text(
            f"---\nwork_package_id: WP02\ntitle: t\ndependencies: {raw_value}\n---\n\nbody\n",
            encoding="utf-8",
        )
        assert _raw_frontmatter_dependencies_is_string_form(wp_file) is True, raw_value


def test_raw_frontmatter_dependencies_is_string_form_false_for_canonical(tmp_path: Path) -> None:
    """Canonical list forms — and an absent field — are not string form."""
    from specify_cli.cli.commands.agent.mission_parsing import (
        _raw_frontmatter_dependencies_is_string_form,
    )

    cases = {
        "dependencies: []\n": False,
        "dependencies:\n  - WP01\n": False,
        "": False,  # field absent entirely
    }
    for dep_line, expected in cases.items():
        wp_file = tmp_path / "WP02-test.md"
        wp_file.write_text(
            f"---\nwork_package_id: WP02\ntitle: t\n{dep_line}---\n\nbody\n",
            encoding="utf-8",
        )
        assert _raw_frontmatter_dependencies_is_string_form(wp_file) is expected, dep_line


def test_apply_bootstrap_fields_normalizes_string_form_even_when_values_equal() -> None:
    """A string-form dependencies line forces the rewrite (#3941).

    WPMetadata coerces ``"WP01"`` to ``["WP01"]`` at read time, so the value
    comparison alone sees "no change" and the string form would survive into
    the tree. The string-form flag must force the canonical rewrite.
    """
    branch = "prog/x"
    meta = WPMetadata(
        work_package_id="WP01",
        title="t",
        dependencies=["WP00"],  # the coerced form of the on-disk string "WP00"
        requirement_refs=["FR-001"],
        planning_base_branch=branch,
        merge_target_branch=branch,
        branch_strategy=seam._branch_strategy_text(branch),
    )
    bld = meta.builder()
    changed, fields = seam._apply_bootstrap_fields(
        bld,
        meta,
        deps=["WP00"],
        has_dependencies_line=True,
        requirement_refs=["FR-001"],
        has_requirement_refs_line=True,
        target_branch=branch,
        dependencies_string_form=True,
    )
    assert changed is True
    assert fields == {"dependencies": ["WP00"]}
    built = bld.build()
    assert list(built.dependencies) == ["WP00"]


def test_apply_ownership_inference_skips_when_present() -> None:
    meta = WPMetadata(
        work_package_id="WP01",
        title="t",
        execution_mode="code_change",
        owned_files=["src/x.py"],
        authoritative_surface="src/x.py",
    )
    bld = meta.builder()
    changed, warnings, contradiction = seam._apply_ownership_inference(bld, meta, "body", "001-m", {})
    assert changed is False
    assert warnings == []
    assert contradiction is None


def test_post_integration_acceptance_warning_is_code_wp_only() -> None:
    code_wp = """---
work_package_id: WP01
title: t
---
# WP01
## Acceptance Criteria
- Check the dashboard once merged.
"""
    planning_wp = code_wp + "\nUpdate kitty-specs/001-m/plan.md only.\n"

    warnings = seam.detect_post_integration_acceptance(code_wp, ["src/x.py"])

    assert warnings
    assert "once merged" in warnings[0]
    assert seam.detect_post_integration_acceptance(planning_wp, ["kitty-specs/001-m/plan.md"]) == []


def test_discarded_sc_refs_warning_names_dropped_token(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: t\nrequirement_refs: [FR-001, SC-008]\n---\nbody\n",
        encoding="utf-8",
    )

    warnings = seam.find_discarded_sc_refs(tasks_dir)

    assert warnings == [
        "WP01 declares Success-Criteria token(s) (SC-008) in requirement_refs "
        "that the FR/NFR/C ref graph does not admit -- they are DROPPED, not traced. "
        "Success-Criteria ids are not first-class requirement refs; move the coverage "
        "claim to the WP's success-criteria surface, or restate it as an FR/NFR/C "
        "requirement if it must be traced."
    ]


# ---------------------------------------------------------------------------
# INV-6: --validate-only zero-mutation invariant
# ---------------------------------------------------------------------------


def test_assert_no_write_in_validate_only_passes_when_empty() -> None:
    state = seam._BootstrapState()
    seam._assert_no_write_in_validate_only(state, validate_only=True)


def test_assert_no_write_in_validate_only_raises_when_queued() -> None:
    state = seam._BootstrapState()
    meta = WPMetadata(work_package_id="WP01", title="t")
    state.pending_writes.append((Path("WP01.md"), meta, "body"))
    with pytest.raises(AssertionError):
        seam._assert_no_write_in_validate_only(state, validate_only=True)


def test_assert_no_write_outside_validate_only_is_noop() -> None:
    state = seam._BootstrapState()
    meta = WPMetadata(work_package_id="WP01", title="t")
    state.pending_writes.append((Path("WP01.md"), meta, "body"))
    # No assertion fires when not validate_only — writes are legitimate.
    seam._assert_no_write_in_validate_only(state, validate_only=False)


def test_flush_frontmatter_writes_skips_in_validate_only(tmp_path: Path) -> None:
    state = seam._BootstrapState()
    target = tmp_path / "WP01.md"
    meta = WPMetadata(work_package_id="WP01", title="t")
    state.pending_writes.append((target, meta, "body"))
    seam._flush_frontmatter_writes(state, validate_only=True)
    assert not target.exists()  # INV-6: zero disk mutation in validate-only.


def test_flush_frontmatter_writes_persists_when_committing(tmp_path: Path) -> None:
    state = seam._BootstrapState()
    target = tmp_path / "WP01.md"
    meta = WPMetadata(work_package_id="WP01", title="t")
    state.pending_writes.append((target, meta, "body"))
    seam._flush_frontmatter_writes(state, validate_only=False)
    assert target.exists()


# ---------------------------------------------------------------------------
# T017 tasks.md regeneration / staleness report (#3221)
# ---------------------------------------------------------------------------


def _tasks_md_manifest() -> seam.WpsManifest:
    from specify_cli.core.wps_manifest import WorkPackageEntry, WpsManifest

    return WpsManifest(work_packages=[WorkPackageEntry(id="WP01", title="T1", requirement_refs=["FR-001"])])


def test_regenerate_tasks_md_no_manifest_reports_not_stale(tmp_path: Path) -> None:
    # No wps.yaml → nothing to regenerate; never creates tasks.md.
    assert seam._regenerate_or_report_tasks_md(tmp_path, None, "001-mission", validate_only=True, json_output=True) is False
    assert not (tmp_path / "tasks.md").exists()


def test_regenerate_tasks_md_validate_only_leaves_stale_file_untouched(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    manifest = _tasks_md_manifest()
    tasks_md = tmp_path / "tasks.md"
    stale_bytes = "# stale hand-edited tasks.md\n\n<!-- deliberate staleness probe -->\n"
    tasks_md.write_text(stale_bytes, encoding="utf-8")

    stale = seam._regenerate_or_report_tasks_md(tmp_path, manifest, "001-mission", validate_only=True, json_output=False)

    # #3221 / INV-6: byte-identical afterwards — the check reports, never repairs.
    assert stale is True
    assert tasks_md.read_text(encoding="utf-8") == stale_bytes
    assert "stale relative to wps.yaml" in capsys.readouterr().out


def test_regenerate_tasks_md_validate_only_fresh_file_reports_not_stale(
    tmp_path: Path,
) -> None:
    from specify_cli.core.wps_manifest import generate_tasks_md_from_manifest

    manifest = _tasks_md_manifest()
    tasks_md = tmp_path / "tasks.md"
    fresh = generate_tasks_md_from_manifest(manifest, "001-mission")
    tasks_md.write_text(fresh, encoding="utf-8")

    stale = seam._regenerate_or_report_tasks_md(tmp_path, manifest, "001-mission", validate_only=True, json_output=True)

    assert stale is False
    assert tasks_md.read_text(encoding="utf-8") == fresh


def test_regenerate_tasks_md_validate_only_missing_file_is_stale_not_created(
    tmp_path: Path,
) -> None:
    manifest = _tasks_md_manifest()

    stale = seam._regenerate_or_report_tasks_md(tmp_path, manifest, "001-mission", validate_only=True, json_output=True)

    # A missing tasks.md would be CREATED by the regeneration — report it,
    # never create it in validate-only mode.
    assert stale is True
    assert not (tmp_path / "tasks.md").exists()


def test_regenerate_tasks_md_validate_only_unreadable_file_is_stale(
    tmp_path: Path,
) -> None:
    manifest = _tasks_md_manifest()
    tasks_md = tmp_path / "tasks.md"
    tasks_md.write_bytes(b"\xff\xfe not utf-8 \xff")

    stale = seam._regenerate_or_report_tasks_md(tmp_path, manifest, "001-mission", validate_only=True, json_output=True)

    # A corrupt tasks.md cannot be compared — report stale (the commit-phase
    # write replaces it wholesale) instead of crashing the read-only pre-flight.
    assert stale is True


def test_regenerate_tasks_md_commit_phase_writes(tmp_path: Path) -> None:
    from specify_cli.core.wps_manifest import generate_tasks_md_from_manifest

    manifest = _tasks_md_manifest()
    tasks_md = tmp_path / "tasks.md"
    tasks_md.write_text("stale\n", encoding="utf-8")

    stale = seam._regenerate_or_report_tasks_md(tmp_path, manifest, "001-mission", validate_only=False, json_output=True)

    assert stale is False
    assert tasks_md.read_text(encoding="utf-8") == generate_tasks_md_from_manifest(manifest, "001-mission")


# ---------------------------------------------------------------------------
# _validate_owned_files_not_in_kitty_specs
# ---------------------------------------------------------------------------


def test_owned_files_kitty_specs_gate_passes_for_source_paths() -> None:
    meta = WPMetadata(work_package_id="WP01", title="t", owned_files=["src/x.py"])
    seam._validate_owned_files_not_in_mission_specs({"WP01": meta}, json_output=True)


def test_owned_files_kitty_specs_gate_rejects_kitty_specs_path() -> None:
    meta = WPMetadata(work_package_id="WP01", title="t", owned_files=["kitty-specs/001-m/spec.md"])
    with pytest.raises(typer.Exit):
        seam._validate_owned_files_not_in_mission_specs({"WP01": meta}, json_output=True)


def test_owned_files_kitty_specs_gate_exempts_confined_planning_wp() -> None:
    """A ``planning_artifact`` WP confined to planning surfaces is exempt from the
    kitty-specs ban and does not raise (#3222 / #2643, FR-001/FR-004)."""
    meta = WPMetadata(
        work_package_id="WP01",
        title="t",
        execution_mode="planning_artifact",
        owned_files=["kitty-specs/001-m/disposition-matrix.md"],
    )
    seam._validate_owned_files_not_in_mission_specs({"WP01": meta}, json_output=True)


def test_owned_files_kitty_specs_gate_rejects_mislabeled_planning_owning_code() -> None:
    """Confinement (FR-004, INV-4): a ``planning_artifact`` WP that also owns a
    ``src/`` path is NOT exempted — the kitty-specs path still trips the ban."""
    meta = WPMetadata(
        work_package_id="WP01",
        title="t",
        execution_mode="planning_artifact",
        owned_files=["kitty-specs/001-m/spec.md", "src/foo.py"],
    )
    with pytest.raises(typer.Exit):
        seam._validate_owned_files_not_in_mission_specs({"WP01": meta}, json_output=True)


# ---------------------------------------------------------------------------
# _gather_validation_frontmatter (prefer-in-memory-then-disk, FR-031)
# ---------------------------------------------------------------------------


def test_gather_validation_frontmatter_prefers_inmemory(tmp_path: Path) -> None:
    wp = _wp_file(tmp_path, "WP01.md", [])
    state = seam._BootstrapState()
    inmemory = WPMetadata(work_package_id="WP01", title="t", dependencies=["WP00"])
    state.inmemory_frontmatter["WP01"] = inmemory
    state.inmemory_bodies["WP01"] = "inmem-body"

    fms, bodies = seam._gather_validation_frontmatter([wp], state)
    assert list(fms["WP01"].dependencies) == ["WP00"]
    assert bodies["WP01"] == "inmem-body"


def test_gather_validation_frontmatter_falls_back_to_disk(tmp_path: Path) -> None:
    wp = _wp_file(tmp_path, "WP01.md", ["WP00"])
    state = seam._BootstrapState()
    fms, _bodies = seam._gather_validation_frontmatter([wp], state)
    assert list(fms["WP01"].dependencies) == ["WP00"]


# ---------------------------------------------------------------------------
# #4141 — the planning_commit_sha refresh decision helpers
# ---------------------------------------------------------------------------


def _capture_console(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Point ``seam.console`` at an in-memory buffer and return it."""
    buf = io.StringIO()
    monkeypatch.setattr(seam, "console", Console(file=buf, force_terminal=False, width=200))
    return buf


def _manifest_with_planning_sha(sha: str | None) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug="001-mission",
        mission_id=None,
        mission_branch="kitty/mission-001-mission",
        target_branch="main",
        lanes=[],
        computed_at="2026-09-09T00:00:00Z",
        computed_from="test",
        planning_commit_sha=sha,
    )


def test_report_planning_sha_decision_silent_in_json_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = _capture_console(monkeypatch)
    seam._report_planning_sha_decision(
        "main",
        seam.PlanningCommitResolution(sha="b" * 40, action="refreshed", previous_sha="a" * 40),
        json_output=True,
    )
    assert buf.getvalue() == ""


def test_report_planning_sha_decision_silent_on_none_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = _capture_console(monkeypatch)
    seam._report_planning_sha_decision("main", None, json_output=False)
    assert buf.getvalue() == ""


def test_report_planning_sha_decision_reports_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = _capture_console(monkeypatch)
    seam._report_planning_sha_decision(
        "main",
        seam.PlanningCommitResolution(sha="b" * 40, action="refreshed", previous_sha="a" * 40),
        json_output=False,
    )
    out = buf.getvalue()
    assert "Refreshed planning_commit_sha" in out
    assert "a" * 40 in out and "b" * 40 in out


def test_report_planning_sha_decision_warns_on_preserved_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = _capture_console(monkeypatch)
    seam._report_planning_sha_decision(
        "main",
        seam.PlanningCommitResolution(
            sha="a" * 40,
            action="preserved",
            previous_sha="a" * 40,
            branch_tip="b" * 40,
        ),
        json_output=False,
    )
    out = buf.getvalue()
    assert "--refresh-planning-commit" in out
    assert "a" * 40 in out and "b" * 40 in out


def test_report_planning_sha_decision_silent_when_no_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = _capture_console(monkeypatch)
    seam._report_planning_sha_decision(
        "main",
        seam.PlanningCommitResolution(sha="a" * 40, action="preserved", previous_sha="a" * 40, branch_tip="a" * 40),
        json_output=False,
    )
    # No drift (tip == recorded) and no recorded provenance gap → nothing to say.
    assert buf.getvalue() == ""


def test_refuse_planning_sha_refresh_prints_error_in_human_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buf = _capture_console(monkeypatch)
    with pytest.raises(typer.Exit):
        seam._refuse_planning_sha_refresh("refusal message", json_output=False)
    assert "refusal message" in buf.getvalue()


def _preserve_or_capture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    execution_begun: bool,
    recorded_sha: str | None,
    tip: str | None,
    ancestor: bool = True,
    refresh: bool = False,
    allow_orphaned: bool = False,
) -> object:
    """Drive ``_preserve_or_capture_planning_commit_sha`` with git faked out.

    #4827: the ancestry check moved to the shared WP01
    ``classify_recorded_pin`` authority (``_recorded_planning_sha_is_
    ancestor_of_tip`` was retired). ``ancestor`` keeps its historical
    True/False meaning here by mapping onto the two classes these existing
    fixtures exercise: ``True`` -> ADVANCED (the pre-#4827 "is an ancestor"
    case), ``False`` -> ORPHANED (the pre-#4827 "not an ancestor" case --
    #4141's own diverged-side-branch fixture is exactly this shape per
    research.md D3, so ORPHANED is the faithful mapping, not FOREIGN).
    """
    monkeypatch.setattr(seam, "_execution_has_begun", lambda *a, **k: execution_begun)
    monkeypatch.setattr(seam, "_capture_target_branch_tip", lambda *a, **k: tip)
    monkeypatch.setattr(
        seam,
        "classify_recorded_pin",
        lambda *a, **k: seam.PinClass.ADVANCED if ancestor else seam.PinClass.ORPHANED,
    )
    monkeypatch.setattr(
        "specify_cli.lanes.persistence.read_lanes_json",
        lambda *_a, **_k: _manifest_with_planning_sha(recorded_sha),
    )
    return seam._preserve_or_capture_planning_commit_sha(
        tmp_path,
        tmp_path,
        "001-mission",
        "main",
        json_output=True,
        refresh_planning_commit=refresh,
        allow_orphaned=allow_orphaned,
    )


def test_preserve_or_capture_pre_execution_captures_tip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resolution = _preserve_or_capture(monkeypatch, tmp_path, execution_begun=False, recorded_sha="a" * 40, tip="b" * 40)
    assert resolution == seam.PlanningCommitResolution(sha="b" * 40, action="captured")


def test_preserve_or_capture_execution_begun_preserves_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resolution = _preserve_or_capture(monkeypatch, tmp_path, execution_begun=True, recorded_sha="a" * 40, tip="b" * 40)
    assert resolution == seam.PlanningCommitResolution(
        sha="a" * 40,
        action="preserved",
        previous_sha="a" * 40,
        branch_tip="b" * 40,
    )


def test_preserve_or_capture_refresh_repoints_to_tip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resolution = _preserve_or_capture(monkeypatch, tmp_path, execution_begun=True, recorded_sha="a" * 40, tip="b" * 40, ancestor=True, refresh=True)
    assert resolution == seam.PlanningCommitResolution(
        sha="b" * 40,
        action="refreshed",
        previous_sha="a" * 40,
        branch_tip="b" * 40,
    )


def test_preserve_or_capture_refresh_from_none_recorded_sha_is_a_safe_advance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A legacy lanes.json with no recorded SHA has no provenance to clobber."""
    resolution = _preserve_or_capture(monkeypatch, tmp_path, execution_begun=True, recorded_sha=None, tip="b" * 40, refresh=True)
    assert resolution == seam.PlanningCommitResolution(sha="b" * 40, action="refreshed", previous_sha=None, branch_tip="b" * 40)


def test_preserve_or_capture_refresh_refused_when_tip_uncapturable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(seam, "_emit_json", emitted.append)
    with pytest.raises(typer.Exit):
        _preserve_or_capture(monkeypatch, tmp_path, execution_begun=True, recorded_sha="a" * 40, tip=None, refresh=True)
    assert any("could not be captured" in str(e.get("error", "")) for e in emitted)


def test_preserve_or_capture_refresh_refused_when_recorded_not_ancestor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(seam, "_emit_json", emitted.append)
    with pytest.raises(typer.Exit):
        _preserve_or_capture(monkeypatch, tmp_path, execution_begun=True, recorded_sha="a" * 40, tip="b" * 40, ancestor=False, refresh=True)
    assert any("not an ancestor" in str(e.get("error", "")) for e in emitted)
