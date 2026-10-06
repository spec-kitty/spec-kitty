"""Patch-free characterisation of the three bridge adapter behaviours (#2561 WP01).

Three bridge delegates are not pure forwards; each adds behaviour the owning seam
does not have on its own:

* ``_load_feature_runs`` resolves the runs-index path from ``repo_root``
  (``load_feature_runs(_feature_runs_path(repo_root))``);
* ``_build_run_ref`` threads an explicit ``run_ref_cls=`` (its seam-level
  tests live in ``tests/runtime/test_bridge_io.py``);
* ``_parse_requirement_refs_from_tasks_md`` injects ``grammar=``.

The mission deletes those delegates and moves their behaviour to the call
sites. A naive rename already regressed once (the grounding prototype), and only
a patch-free test caught it. These tests therefore drive production entry points
and the owning seams, never a removed name on ``runtime_bridge``, so they stay
green and unmodified through WP02-WP05. They reference only the owning seams,
the two kept public re-exports and bridge-owned names.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest

from runtime.next import runtime_bridge_cores, runtime_bridge_io
from runtime.next._internal_runtime import MissionRunRef
from runtime.next.runtime_bridge_cores import RequirementGrammarLike
from specify_cli.requirement_mapping import grammar
from tests.runtime._next_mission_scaffold import scaffold_software_dev
from runtime.next import runtime_bridge_guards as bridge_guards

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# The grammar module satisfies the Protocol structurally; mypy cannot see a module do so.
_GRAMMAR = cast("RequirementGrammarLike", grammar)

_SLUG = "042-characterise"
_MISSION_TYPE = "software-dev"
_SPEC = """# Spec

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | First. | Covered. | proposed |
| FR-006a | Suffixed. | Covered. | proposed |

## Success Criteria

- **SC-001**: First success criterion.
"""


# ---------------------------------------------------------------------------
# Run index: _load_feature_runs and _build_run_ref, through the entry points
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def started_run(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, MissionRunRef]]:
    """One real run started once (starting a run bootstraps templates, which is slow)."""
    repo_root = tmp_path_factory.mktemp("characterise-run")
    scaffold_software_dev(repo_root, _SLUG, wps={"WP01": "planned"})
    yield repo_root, runtime_bridge_io.get_or_start_run(_SLUG, repo_root, _MISSION_TYPE)


def test_first_start_returns_a_mission_run_ref_under_the_runs_dir(started_run: tuple[Path, MissionRunRef]) -> None:
    repo_root, run_ref = started_run
    assert isinstance(run_ref, MissionRunRef)
    assert run_ref.mission_key == _MISSION_TYPE
    assert run_ref.run_id
    assert Path(run_ref.run_dir) == repo_root / ".kittify" / "runtime" / "runs" / run_ref.run_id
    assert Path(run_ref.run_dir).is_dir()


def test_second_start_reuses_the_run_read_back_from_the_resolved_index(started_run: tuple[Path, MissionRunRef]) -> None:
    """Proves the index is read from the path derived from ``repo_root``.

    Reading the wrong path (the grounding prototype's regression) would find no
    entry and start a second run with a new ``run_id``.
    """
    repo_root, first = started_run
    again = runtime_bridge_io.get_or_start_run(_SLUG, repo_root, _MISSION_TYPE)
    assert again.run_id == first.run_id
    assert again.run_dir == first.run_dir
    assert again.mission_key == first.mission_key


def test_runs_index_on_disk_maps_the_mission_to_the_started_run(started_run: tuple[Path, MissionRunRef]) -> None:
    repo_root, first = started_run
    index = runtime_bridge_io.load_feature_runs(runtime_bridge_io._feature_runs_path(repo_root))
    entries = [e for e in index.values() if e["run_id"] == first.run_id]
    assert len(entries) == 1
    assert entries[0]["mission_slug"] == _SLUG
    assert entries[0]["mission_type"] == _MISSION_TYPE
    assert runtime_bridge_io._feature_runs_path(repo_root) == repo_root / ".kittify" / "runtime" / "feature-runs.json"


def test_load_feature_runs_of_a_missing_index_is_empty(tmp_path: Path) -> None:
    assert runtime_bridge_io.load_feature_runs(runtime_bridge_io._feature_runs_path(tmp_path)) == {}


# ---------------------------------------------------------------------------
# tasks.md requirement refs: grammar injection
# ---------------------------------------------------------------------------


def _seed_tasks_md_mission(tmp_path: Path, tasks_md: str) -> Path:
    """A mission whose only requirement source is the ``tasks.md`` fallback.

    The WP files carry empty frontmatter refs and there is no ``wps.yaml``, so
    the production preflight must read ``Requirement Refs:`` lines from tasks.md.
    """
    feature_dir = tmp_path / "kitty-specs" / "001-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(_SPEC, encoding="utf-8")
    (feature_dir / "meta.json").write_text("{}", encoding="utf-8")
    (feature_dir / "tasks.md").write_text(tasks_md, encoding="utf-8")
    for wp_id in ("WP01", "WP02", "WP03"):
        glob = f"src/{wp_id.lower()}/**"
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f'---\nwork_package_id: "{wp_id}"\ntitle: "Test {wp_id}"\nrequirement_refs: []\ndependencies: []\n'
            f'execution_mode: "code_change"\nowned_files:\n  - "{glob}"\nauthoritative_surface: "{glob}"\n---\n\n# {wp_id}\n',
            encoding="utf-8",
        )
    return feature_dir


def _tasks_md(**refs_by_wp: str) -> str:
    return "# Tasks\n\n" + "\n".join(f"## {wp}\n\nRequirement Refs: {refs}\n" for wp, refs in refs_by_wp.items())


def test_preflight_accepts_suffixed_and_success_criterion_refs_from_tasks_md(tmp_path: Path) -> None:
    """Needs the injected grammar: a hand-rolled pattern misses ``SC-001`` and ``FR-006a``."""
    feature_dir = _seed_tasks_md_mission(tmp_path, _tasks_md(WP01="FR-001, SC-001", WP02="FR-006a", WP03="FR-001"))
    assert bridge_guards._check_requirement_mapping_ready(feature_dir) == []


def test_preflight_reports_an_unknown_ref_read_from_tasks_md(tmp_path: Path) -> None:
    feature_dir = _seed_tasks_md_mission(tmp_path, _tasks_md(WP01="FR-001, SC-001", WP02="FR-006a", WP03="FR-999"))
    (finding,) = bridge_guards._check_requirement_mapping_ready(feature_dir)
    assert "WP03: FR-999 (unknown_spec_id)" in finding
    assert "WP01" not in finding
    assert "WP02" not in finding


def test_preflight_reports_a_wp_whose_tasks_md_refs_are_all_malformed(tmp_path: Path) -> None:
    feature_dir = _seed_tasks_md_mission(tmp_path, _tasks_md(WP01="FR-001, SC-001", WP02="FR-006a", WP03="bogus, FR-"))
    (finding,) = bridge_guards._check_requirement_mapping_ready(feature_dir)
    assert "missing refs for WPs: WP03" in finding


_GRAMMAR_FORMS_TASKS_MD = """# Tasks

## WP01

Requirement Refs: FR-001, FR-002a, NFR-001, C-001, SC-003

## WP02

Requirement Refs: other-mission#FR-003, bogus, FR-

## WP03

No refs authored here.

## WP04

Requirement Refs: FR-004, FR-004
"""


def test_cores_parse_with_injected_grammar_pins_each_reference_form() -> None:
    """The post-mission call shape: ``_parse_requirement_refs_from_tasks_md(content, grammar=grammar)``."""
    parsed = runtime_bridge_cores._parse_requirement_refs_from_tasks_md(_GRAMMAR_FORMS_TASKS_MD, grammar=_GRAMMAR)
    assert parsed == {
        "WP01": ["FR-001", "FR-002a", "NFR-001", "C-001", "SC-003"],
        "WP02": ["other-mission#FR-003"],
        "WP03": [],
        "WP04": ["FR-004"],
    }
