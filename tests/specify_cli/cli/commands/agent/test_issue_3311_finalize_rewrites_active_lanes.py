"""#3311 — FIXED. Permanent guard: re-finalize after execution has begun must
preserve established planning provenance instead of clobbering it in
response to an ownership-only WP amendment.

Closed P0: https://github.com/Priivacy-ai/spec-kitty/issues/3311

Root cause (verified against source, scope-corrected during mission
mission-a-p0-consistency-01KZWHY1 WP04): the finalize path
(``_compute_and_write_lanes`` in
``src/specify_cli/cli/commands/agent/mission_finalize.py``) used to
unconditionally call ``compute_lanes`` (a pure recompute-from-scratch) and
overwrite ``lanes.json`` + ``planning_commit_sha`` on every
non-``--validate-only`` run, regardless of whether execution had begun. An
ownership-only amendment (adding one path to a WP's ``owned_files``) would
therefore silently clobber the recorded ``planning_commit_sha``.

Scope correction: the original report's "topology collapse / lane renumber"
narrative does NOT reproduce as a standalone bug — pre-execution re-finalize
recomputing topology from scratch is the documented, intentional, idempotent
behavior (``mission_finalize.py`` docstring). The FIX therefore gates the
clobber on an "execution has begun" signal (``_execution_has_begun`` /
T014): once any WP has moved past ``planned``, re-finalize now PRESERVES the
recorded ``planning_commit_sha`` (read from the on-disk ``lanes.json``)
instead of re-capturing the current branch tip. Before execution begins,
re-finalize keeps regenerating freely — that half of this file's original
scenario (no execution-begun signal) is now covered as the "benign
regeneration" case in the sibling
``test_finalize_provenance_guard.py::test_pre_execution_amendment_actually_regenerates``.

This still drives the REAL ``finalize_tasks`` entry point twice: once to
materialize the established lanes, then again — after seeding a WP-past-
``planned`` status event (the execution-begun signal) and an ownership-only
``owned_files`` amendment — to prove the recorded provenance survives.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from specify_cli.coordination.surface_resolver import (
    resolve_status_surface_with_anchor,
)
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

from tests.specify_cli.cli.commands.agent.finalize_runner import run_finalize
from tests.specify_cli.cli.commands.agent.test_feature_finalize_bootstrap import (
    MODULE,
    _common_patches,
    _make_bootstrap_result,
    _setup_lane_based_feature,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SEEDED_PLANNING_SHA = "deadbeef000deadbeef000deadbeef000deadbeef"


def test_ownership_only_amendment_preserves_established_lanes_and_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Keep finalize-tasks on the offline path: tests/conftest.py enables SaaS sync
    # globally, which can let a machine-local daemon-owner record short-circuit
    # finalize before these assertions run (mirrors the source module's autouse
    # guard, which does not apply to this importing module).
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")

    mission_slug = "061-lane-feature"
    feature_dir = _setup_lane_based_feature(tmp_path, mission_slug)

    patches = _common_patches(tmp_path, mission_slug)
    patches[f"{MODULE}._find_feature_directory"] = MagicMock(return_value=feature_dir)
    patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(
        return_value=_make_bootstrap_result()
    )

    # Run 1: materialize the established topology (WP01 and WP02 own disjoint
    # files → two independent lanes).
    run_finalize(mission_slug, patches)
    established = read_lanes_json(feature_dir)
    assert established is not None
    baseline_topology = {lane.lane_id: sorted(lane.wp_ids) for lane in established.lanes}
    assert sorted(baseline_topology.values()) == [["WP01"], ["WP02"]], (
        "sanity: two disjoint WPs must materialize two independent single-WP "
        f"lanes; got {baseline_topology}"
    )

    # Stand in a recorded planning provenance SHA (finalize cannot capture one in a
    # non-git tmp workspace), representing an established mission's committed plan.
    established.planning_commit_sha = _SEEDED_PLANNING_SHA
    write_lanes_json(feature_dir, established)

    # Execution-begun signal (T014/C-005): a WP has moved past `planned`. This
    # is what distinguishes the FIXED clobber scenario from the benign
    # pre-execution re-finalize, which is expected to keep regenerating.
    read_dir = resolve_status_surface_with_anchor(tmp_path, mission_slug).read_dir
    append_event(
        read_dir,
        StatusEvent(
            event_id="01HXYZ3311EXECUTIONBEGUNEVT",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-08-13T00:00:00Z",
            actor="claude-sonnet",
            force=False,
            execution_mode="worktree",
        ),
    )

    # Ownership-only amendment: add a path WP02 already owns to WP01's owned_files.
    # Nothing about dependencies, requirements, or lifecycle changes.
    wp01 = feature_dir / "tasks" / "WP01-test.md"
    wp01.write_text(
        wp01.read_text(encoding="utf-8").replace(
            "owned_files:\n  - src/alpha.py\n",
            "owned_files:\n  - src/alpha.py\n  - src/beta.py\n",
        ),
        encoding="utf-8",
    )

    # Run 2: the ownership-only amendment, now with execution already begun.
    run_finalize(mission_slug, patches)
    after = read_lanes_json(feature_dir)
    assert after is not None

    # Sanity: the established lanes.json is what got rewritten (same mission).
    assert after.mission_slug == established.mission_slug

    # FIXED: once execution has begun, an ownership-only amendment PRESERVES
    # the recorded planning_commit_sha instead of clobbering it.
    assert after.planning_commit_sha == _SEEDED_PLANNING_SHA, (
        "an ownership-only amendment after execution has begun must not "
        f"clear/overwrite established planning provenance; planning_commit_sha "
        f"went {_SEEDED_PLANNING_SHA!r} -> {after.planning_commit_sha!r}"
    )
