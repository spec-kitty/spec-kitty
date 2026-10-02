"""Real collection of one battery part (mission ci-runtime-stabilisation-01M3TZH6, WP14).

Split out of ``test_battery_partition_proof.py`` so the static three-way proof can sit
on the architectural fast roster: this test spawns a real ``pytest --collect-only`` (~6 s),
is marked ``slow`` (which the battery base marker does not exclude) and therefore runs in
the heavy legs, never in the fast job. The helpers are the proof module's own reference
side (``_gate_coverage``) and the registry; nothing is re-implemented here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest
import yaml

from scripts.ci import battery_partition_plugin as plugin
from scripts.ci.battery_partition_plugin import BatterySpec
from tests.architectural import _gate_coverage as gc

pytestmark = [pytest.mark.architectural]

_REGISTRY: Final[Path] = gc.REPO_ROOT / ".github" / "ci-module-registry.yml"


def _spec() -> BatterySpec:
    return plugin.load_battery_spec(yaml.safe_load(_REGISTRY.read_text(encoding="utf-8")))


@pytest.mark.slow
@pytest.mark.parametrize("github_actions", [False, True])
def test_collect_job_nodeids_on_a_partitioned_gate_collects_the_part(github_actions: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if github_actions:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
    else:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    base = _spec().base
    gate = gc.Gate("fixture.yml", "architectural-heavy", "1/2", paths=list(base.paths), ignores=list(base.deselect), marker_expr=base.marker, partition="1/2")
    nodeids = gc.collect_job_nodeids(gate)
    files = {re.split(r"::", nodeid, maxsplit=1)[0] for nodeid in nodeids}
    assert files, "collection of the part returned no tests"
    assert files <= gc.battery_part_files("1/2")
