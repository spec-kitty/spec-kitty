"""Pin the CI routing of ``uv.lock`` to the upgrade and status shards (#6238).

The spec-kitty-events bump (#6205) changed the reducer through ``uv.lock`` and selected
neither the ``upgrade`` nor the ``status`` module shard, so the break reached ``main``.
The non-src ``reducer_lock`` group (``DEPENDENCY_MODULE_FANOUT``, deliberately outside the
pack-scoped census) closes that. Operator ruling (decision 01M4XV6HM7WHEB2B8QG67N29HT):
``pyproject.toml`` is NOT in the group.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.ci.gate_selection import DEPENDENCY_MODULE_FANOUT, FANOUT_GROUPS, load_router, select_modules

pytestmark = pytest.mark.fast

ROUTER = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci-router.yml"
GROUP = "reducer_lock"


def _filter_globs() -> list[str]:
    workflow = yaml.safe_load(ROUTER.read_text(encoding="utf-8"))
    for step in _all_steps(workflow):
        filters = (step.get("with") or {}).get("filters")
        if filters:
            parsed = yaml.safe_load(filters)
            if GROUP in parsed:
                return list(parsed[GROUP])
    raise AssertionError(f"no filter group {GROUP!r} in {ROUTER}")


def _all_steps(workflow: dict) -> list[dict]:
    return [step for job in workflow["jobs"].values() for step in job.get("steps", [])]


def test_lock_only_change_selects_upgrade_and_status_not_everything() -> None:
    selected = select_modules(["uv.lock"], router=load_router())
    assert {"upgrade", "status"} <= selected
    assert "charter" not in selected  # not a run-all / unmatched-src path


def test_manifest_only_change_does_not_select_upgrade() -> None:
    assert "upgrade" not in select_modules(["pyproject.toml"], router=load_router())


def test_router_filter_is_exactly_the_lock_file() -> None:
    assert _filter_globs() == ["uv.lock"]


def test_dependency_fanout_stays_outside_the_pack_census() -> None:
    assert GROUP not in FANOUT_GROUPS
    assert DEPENDENCY_MODULE_FANOUT[GROUP] == frozenset({"upgrade", "status"})
