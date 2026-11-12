"""#7540 item 2: ``ResidueContext.for_mission`` reads the stored topology where the Mission's ``meta.json`` lives.

A default Mission settled to ``lanes_with_coord`` keeps its ``meta.json`` only on its Mission branch,
which the coordination worktree holds; the repository root checkout has none. The context now reads
the placement seam's ``PRIMARY_METADATA`` directory first and the raw ``<root>/kitty-specs/<slug>``
join second, so the lookup only widens.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import mission_runtime
from mission_runtime import MissionTopology
from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable
from specify_cli.coordination.coherence import (
    CheckoutRole,
    NothingIsResidue,
    ResidueContext,
    residue_context_or_strictest,
)
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    THREE_LANES,
    make_default_mission,
    run_finalize,
)

_SLUG = "probe-7540"


class _RaisingSeam:
    def read_dir(self, _kind: object) -> Path:
        raise WorktreeRegistryUnavailable(repo_root=Path("."), detail="seam cannot resolve")


class _FixedSeam:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def read_dir(self, _kind: object) -> Path:
        return self._directory


def _write_meta(mission_dir: Path, topology: MissionTopology) -> None:
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_slug": mission_dir.name, "topology": topology.value}), encoding="utf-8")


@pytest.fixture
def _quiet_status_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.non_sandbox
@pytest.mark.usefixtures("_quiet_status_fanout")
def test_settled_default_mission_reads_topology_from_the_coordination_worktree(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES, standing_on="work")
    code, payload = run_finalize(mission)
    assert code == 0, payload
    assert not (mission.root / "kitty-specs" / mission.slug / "meta.json").exists()
    assert (mission.coord_mission_dir / "meta.json").is_file()

    context = ResidueContext.for_mission(mission.root, mission.slug, CheckoutRole.REPOSITORY_ROOT)

    assert context.topology is MissionTopology.LANES_WITH_COORD
    coordination = context.for_checkout(mission.root, mission.coord_mission_dir.parents[1])
    assert coordination.role is CheckoutRole.COORDINATION
    assert coordination.is_disposable(f"kitty-specs/{mission.slug}/status.events.jsonl")
    assert coordination.is_disposable(f"kitty-specs/{mission.slug}/status.json")
    assert not coordination.is_disposable(f"kitty-specs/{mission.slug}/notes.md")
    assert not coordination.is_disposable("src/one.py")


def test_seam_failure_falls_back_to_the_raw_join(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_meta(tmp_path / "kitty-specs" / _SLUG, MissionTopology.COORD)
    monkeypatch.setattr(mission_runtime, "placement_seam", lambda *_a, **_k: _RaisingSeam())

    context = ResidueContext.for_mission(tmp_path, _SLUG, CheckoutRole.LANE)

    assert context.topology is MissionTopology.COORD


def test_seam_dir_without_meta_falls_back_to_the_raw_join(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_meta(tmp_path / "kitty-specs" / _SLUG, MissionTopology.LANES)
    empty = tmp_path / "elsewhere" / _SLUG
    empty.mkdir(parents=True)
    monkeypatch.setattr(mission_runtime, "placement_seam", lambda *_a, **_k: _FixedSeam(empty))

    assert ResidueContext.for_mission(tmp_path, _SLUG, CheckoutRole.LANE).topology is MissionTopology.LANES


def test_absent_everywhere_raises_and_the_strictest_classifier_applies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mission_runtime, "placement_seam", lambda *_a, **_k: _RaisingSeam())

    with pytest.raises(FileNotFoundError):
        ResidueContext.for_mission(tmp_path, _SLUG, CheckoutRole.REPOSITORY_ROOT)
    assert isinstance(residue_context_or_strictest(tmp_path, _SLUG, CheckoutRole.REPOSITORY_ROOT), NothingIsResidue)


def test_a_foreign_file_in_the_coordination_role_stays_non_disposable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seam_dir = tmp_path / ".worktrees" / f"{_SLUG}-coord" / "kitty-specs" / _SLUG
    _write_meta(seam_dir, MissionTopology.LANES_WITH_COORD)
    monkeypatch.setattr(mission_runtime, "placement_seam", lambda *_a, **_k: _FixedSeam(seam_dir))

    context = ResidueContext.for_mission(tmp_path, _SLUG, CheckoutRole.COORDINATION)

    assert context.is_disposable(f"kitty-specs/{_SLUG}/status.events.jsonl")
    assert not context.is_disposable(f"kitty-specs/{_SLUG}/notes.md")
    assert not context.is_disposable("README.md")
