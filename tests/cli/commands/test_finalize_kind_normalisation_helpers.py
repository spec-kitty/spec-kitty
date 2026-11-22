"""``finalize-tasks`` kind-normalisation helpers in process (#7809): the arms the end-to-end tests do not reach.

The end-to-end coverage is ``tests/lanes/test_finalize_docs_wp_lane_normalisation.py``;
these call the helpers directly.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from rich.console import Console

from specify_cli.cli.commands.agent import mission_finalize, mission_finalize_bootstrap, mission_finalize_lanes
from specify_cli.lanes.topology_settlement import TopologyDecision
from specify_cli.ownership.kind_normalisation import KindRewrite, normalise_kinds_for_lane_topology
from specify_cli.ownership.models import OwnershipManifest, WorkProductKind
from specify_cli.status import WPMetadata
from specify_cli.status.wp_metadata import read_wp_frontmatter

pytestmark = [pytest.mark.unit]

_DOCS_REWRITE = KindRewrite(wp_id="WP01", paths_outside_kitty_specs=("docs/a.md",), owns_kitty_specs_paths=False)


def test_the_kitty_specs_refusal_prints_its_remedy_in_human_output(monkeypatch: pytest.MonkeyPatch) -> None:
    out = io.StringIO()
    monkeypatch.setattr(mission_finalize, "console", Console(file=out, width=400))

    with pytest.raises(typer.Exit) as raised:
        mission_finalize_bootstrap._refuse_kitty_specs_owned_files([{"wp_id": "WP01", "path": "kitty-specs/m/a.md"}], json_output=False, remedy="Split WP01.")

    assert raised.value.exit_code == 1
    text = out.getvalue()
    assert "WP01: kitty-specs/m/a.md" in text
    assert "Remedy: Split WP01." in text


def test_persisting_a_rewrite_with_no_task_file_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _never(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("no write expected")

    monkeypatch.setattr(mission_finalize_bootstrap, "_flush_one_frontmatter_write", _never)

    mission_finalize_bootstrap._persist_kind_rewrites([_DOCS_REWRITE], tmp_path, [tmp_path / "WP02-other.md"], {}, {})


def test_a_refresh_only_run_never_normalises(monkeypatch: pytest.MonkeyPatch) -> None:
    def _never(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a refresh-only run binds and reports nothing")

    monkeypatch.setattr(mission_finalize, "_bind_kind_normalisation", _never)
    gates: Any = object()
    no_context: Any = None  # the refresh-only arm reads no context

    result = mission_finalize._apply_kind_normalisation(
        no_context,
        gates,
        None,
        None,
        None,
        refresh_planning_commit=True,
        json_output=False,
    )

    assert result == (gates, ())


def test_a_started_docs_wp_is_never_rewritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A re-finalize with a started docs WP keeps its frozen kind; an unstarted one is still rewritten."""
    manifests = {
        wp_id: OwnershipManifest(execution_mode=WorkProductKind.PLANNING_ARTIFACT, owned_files=(f"docs/{wp_id}.md",), authoritative_surface="docs/")
        for wp_id in ("WP01", "WP02")
    }
    monkeypatch.setattr(mission_finalize_lanes, "_started_wp_ids_for_normalisation", lambda *_a, **_k: frozenset({"WP01"}))

    result = mission_finalize_lanes._kind_normalisation_for(tmp_path, tmp_path, "m", manifests, {"topology": "lanes"}, owned=None)

    assert [rewrite.wp_id for rewrite in result.rewritten] == ["WP02"]
    assert result.manifests["WP01"].execution_mode is WorkProductKind.PLANNING_ARTIFACT
    assert result.manifests["WP02"].execution_mode is WorkProductKind.CODE_CHANGE


# --------------------------------------------------------------------------- the lane-topology rewrite


def _planning(*owned: str) -> OwnershipManifest:
    return OwnershipManifest(execution_mode=WorkProductKind.PLANNING_ARTIFACT, owned_files=owned, authoritative_surface=owned[0] if owned else "")


def _meta(wp_id: str, *owned: str) -> WPMetadata:
    return WPMetadata(work_package_id=wp_id, title=wp_id, execution_mode="planning_artifact", owned_files=list(owned))


def _gates(manifests: dict[str, OwnershipManifest]) -> Any:
    placeholder: Any = None
    return mission_finalize._FinalizeOwnershipGates(
        state=placeholder,
        tasks_md_stale=False,
        wp_frontmatters={wp_id: _meta(wp_id, *manifest.owned_files) for wp_id, manifest in manifests.items()},
        wp_bodies={},
        wp_manifests=dict(manifests),
        eligibility=placeholder,
        lane_wp_manifests=dict(manifests),
        lane_wp_dependencies={},
        lane_wp_bodies={},
    )


def _ctx(tmp_path: Path) -> Any:
    return SimpleNamespace(planning_dir=tmp_path)


@pytest.fixture
def envelope_extras() -> Iterator[Any]:
    token = mission_finalize._OWNED_ENVELOPE_EXTRAS.set(None)
    yield mission_finalize._OWNED_ENVELOPE_EXTRAS
    mission_finalize._OWNED_ENVELOPE_EXTRAS.reset(token)


def test_a_lane_topology_records_a_docs_wp_as_code_change(tmp_path: Path, envelope_extras: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    err = io.StringIO()
    monkeypatch.setattr(mission_finalize, "err_console", Console(file=err, width=400))
    manifests = {"WP01": _planning("docs/a.md"), "WP02": _planning("kitty-specs/m/plan.md")}
    normalisation = normalise_kinds_for_lane_topology(manifests, started_wp_ids=frozenset())

    gates, rewrites = mission_finalize._apply_kind_normalisation(
        _ctx(tmp_path), _gates(manifests), normalisation, {"topology": "lanes"}, None, refresh_planning_commit=False, json_output=False
    )

    assert [rewrite.wp_id for rewrite in rewrites] == ["WP01"]
    assert gates.lane_wp_manifests["WP01"].execution_mode is WorkProductKind.CODE_CHANGE
    assert gates.wp_manifests["WP01"].execution_mode is WorkProductKind.CODE_CHANGE
    assert str(gates.wp_frontmatters["WP01"].execution_mode) == WorkProductKind.CODE_CHANGE.value
    assert str(gates.wp_frontmatters["WP02"].execution_mode) == WorkProductKind.PLANNING_ARTIFACT.value
    assert envelope_extras.get()["kind_normalised"] == [rewrites[0].as_payload()]
    assert "Notice: WP01 owns paths outside kitty-specs/ (docs/a.md); recorded as code_change" in err.getvalue()


def test_a_single_branch_decision_keeps_the_authored_kinds(tmp_path: Path, envelope_extras: Any) -> None:
    manifests = {"WP01": _planning("docs/a.md")}
    normalisation = normalise_kinds_for_lane_topology(manifests, started_wp_ids=frozenset())
    decision = TopologyDecision(rule="size", wp_count=1, code_lane_count=1, from_topology="single_branch", to_topology="single_branch", target_protected=False)
    gates = _gates(manifests)

    kept, rewrites = mission_finalize._apply_kind_normalisation(_ctx(tmp_path), gates, normalisation, {}, decision, refresh_planning_commit=False, json_output=True)

    assert (kept, rewrites) == (gates, ())
    assert envelope_extras.get()["kind_normalised"] == []


def test_a_mixed_docs_wp_refuses_with_the_split_remedy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, envelope_extras: Any) -> None:
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(mission_finalize, "_emit_json", emitted.append)
    manifests = {"WP01": _planning("docs/a.md", "kitty-specs/m/plan.md")}
    normalisation = normalise_kinds_for_lane_topology(manifests, started_wp_ids=frozenset())

    with pytest.raises(typer.Exit):
        mission_finalize._apply_kind_normalisation(
            _ctx(tmp_path), _gates(manifests), normalisation, {"topology": "lanes"}, None, refresh_planning_commit=False, json_output=True
        )

    assert emitted[0]["invalid_owned_files"] == [{"wp_id": "WP01", "path": "kitty-specs/m/plan.md"}]
    assert "Split WP01" in str(emitted[0]["remedy"])


def test_json_output_reports_no_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    def _never(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("JSON carries kind_normalised instead")

    monkeypatch.setattr(mission_finalize.err_console, "print", _never)
    mission_finalize_bootstrap._report_kind_rewrites([_DOCS_REWRITE], json_output=True)


def test_persisting_a_rewrite_writes_code_change_to_its_task_file(tmp_path: Path) -> None:
    task = tmp_path / "tasks" / "WP01-docs.md"
    task.parent.mkdir()
    task.write_text("---\nwork_package_id: WP01\ntitle: Docs\nexecution_mode: planning_artifact\nowned_files: [docs/a.md]\n---\n\n# WP01\n", encoding="utf-8")
    meta, body = read_wp_frontmatter(task)

    mission_finalize_bootstrap._persist_kind_rewrites(
        [_DOCS_REWRITE], task.parent, [task, tmp_path / "notes.md"], {"WP01": meta}, {"WP01": body}, repo_root=tmp_path
    )

    assert str(read_wp_frontmatter(task)[0].execution_mode) == WorkProductKind.CODE_CHANGE.value


def test_the_mission_specs_check_passes_a_wp_outside_kitty_specs_and_refuses_one_inside(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(mission_finalize, "_emit_json", emitted.append)
    code_wp = WPMetadata(work_package_id="WP01", title="t", execution_mode="code_change", owned_files=["src/a.py"])
    mission_finalize_bootstrap._validate_owned_files_not_in_mission_specs({"WP01": code_wp}, json_output=True)
    assert emitted == []

    bad = WPMetadata(work_package_id="WP02", title="t", execution_mode="code_change", owned_files=["kitty-specs/m/a.md"])
    with pytest.raises(typer.Exit):
        mission_finalize_bootstrap._validate_owned_files_not_in_mission_specs({"WP02": bad}, json_output=True)
    assert emitted[0]["invalid_owned_files"] == [{"wp_id": "WP02", "path": "kitty-specs/m/a.md"}]


# --------------------------------------------------------------------------- the lanes-side entry


def test_a_first_finalize_reads_no_started_set(tmp_path: Path) -> None:
    assert mission_finalize_lanes._started_wp_ids_for_normalisation(tmp_path, tmp_path, "m", owned=None) == frozenset()


def test_a_settled_single_branch_mission_is_never_normalised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _never(*_args: object, **_kwargs: object) -> frozenset[str]:
        raise AssertionError("the status surface is never read")

    monkeypatch.setattr(mission_finalize_lanes, "_started_wp_ids_for_normalisation", _never)
    manifests = {"WP01": _planning("docs/a.md")}

    result = mission_finalize_lanes._kind_normalisation_for(tmp_path, tmp_path, "m", manifests, {"topology": "single_branch"}, owned=None)

    assert result.rewritten == ()
    assert result.manifests == manifests


@pytest.mark.parametrize(
    ("manifests", "rewritten"),
    [
        pytest.param({"WP01": _planning("kitty-specs/m/plan.md")}, [], id="nothing-to-rewrite"),
        pytest.param({"WP01": _planning("docs/a.md")}, ["WP01"], id="nothing-started"),
    ],
)
def test_the_started_set_is_read_only_when_it_could_matter(
    manifests: dict[str, OwnershipManifest], rewritten: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads: list[str] = []

    def _started(*_args: object, **_kwargs: object) -> frozenset[str]:
        reads.append("read")
        return frozenset()

    monkeypatch.setattr(mission_finalize_lanes, "_started_wp_ids_for_normalisation", _started)

    result = mission_finalize_lanes._kind_normalisation_for(tmp_path, tmp_path, "m", manifests, {"topology": "lanes"}, owned=None)

    assert [rewrite.wp_id for rewrite in result.rewritten] == rewritten
    assert reads == (["read"] if rewritten else [])


@pytest.mark.parametrize(
    ("meta", "to_topology", "expected"),
    [
        pytest.param({"topology": "lanes"}, None, True, id="explicit-lanes"),
        pytest.param({"topology": "single_branch"}, None, False, id="explicit-single-branch"),
        pytest.param({}, "lanes_with_coord", True, id="settled-now-to-lanes"),
        pytest.param({}, "single_branch", False, id="settled-now-to-single-branch"),
    ],
)
def test_lane_topology_this_run(meta: dict[str, object], to_topology: str | None, expected: bool, tmp_path: Path) -> None:
    decision = (
        TopologyDecision(rule="size", wp_count=3, code_lane_count=3, from_topology="single_branch", to_topology=to_topology, target_protected=False)
        if to_topology
        else None
    )
    assert mission_finalize_lanes._is_lane_topology_this_run(meta, tmp_path, decision) is expected


def test_a_refinalize_reads_the_started_set_from_the_status_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes import persistence

    monkeypatch.setattr(persistence, "read_lanes_json", lambda _dir: object())
    monkeypatch.setattr(mission_finalize_lanes, "_read_started_wp_ids", lambda *_a, **_k: frozenset({"WP01"}))

    assert mission_finalize_lanes._started_wp_ids_for_normalisation(tmp_path, tmp_path, "m", owned=None) == frozenset({"WP01"})


def test_a_provisional_mission_is_normalised_for_its_size_decision(tmp_path: Path) -> None:
    meta = {"topology": "single_branch", "topology_source": "default", "topology_settled": False}

    assert mission_finalize_lanes._is_settled_single_branch(meta, tmp_path) is False
