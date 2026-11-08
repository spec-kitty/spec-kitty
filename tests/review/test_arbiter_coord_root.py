"""FR-016 (WP07, arbiter-root-threading): the arbiter's caller-resolved
``main_repo_root`` must be threaded all the way into
:func:`specify_cli.review.arbiter.persist_arbiter_decision`, which must
NEVER self-infer it from ``feature_dir.parent.parent``.

The retired self-inference happened to coincide with the correct root only
for a SINGLE_BRANCH/LANES-topology mission -- the shape every pre-existing
test fixture for this path exercised. Under a *materialized coordination
topology*, ``_run_arbiter_override``'s own ``feature_dir`` is already the
caller's topology-resolved COORD surface (see ``tasks_move_task.py``'s
``_mt_issue_matrix_facts`` docstring: "the caller's already topology-resolved
COORD surface"), so ``feature_dir.parent.parent`` there yields the COORD
WORKTREE root -- not the real ``main_repo_root`` the downstream event-sourced
write needs to correctly resolve the coord partition. T036 proves this is a
real, materialized-topology bug (not merely a hypothetical), red against the
pre-WP07 self-inference; T037 is the threading fix; T038 confirms (without
repointing) that the arbiter's verdict READ path was already event-sourced
before this WP and stays that way.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from tests.integration.coord_topology_fixture import (  # noqa: F401 -- pytest fixture re-export
    coord_topology_mission,
)

# 2026-08-07 (landing fix, verdict-seam-write-unification #3245): this module
# shipped with no module-level pytestmark, orphaning all 5 of its tests.
# test_arbiter_override_under_coord_topology_threads_the_resolved_root drives
# the real git-backed `coord_topology_mission` fixture (a real subprocess-init
# repo, tests/integration/coord_topology_fixture.py), so this file routes as
# `git_repo` -- matching the module-level (not per-test) marker granularity
# every other tests/review/*.py file uses -- into the dedicated
# `integration-tests-review` job (`-m 'not windows_ci and (git_repo or
# integration)'`), which also covers this file's other 4 pure-introspection
# tests.
pytestmark = [pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# T036 / T037 -- root threading under a materialized coordination topology
# ---------------------------------------------------------------------------


def test_arbiter_override_under_coord_topology_threads_the_resolved_root(
    coord_topology_mission,  # noqa: F811 -- fixture shadows the re-exported name
) -> None:
    """An arbiter override driven through the REAL production entry point
    (``_run_arbiter_override``) against a materialized coord topology must
    persist using the CALLER-RESOLVED ``main_repo_root`` -- never a root
    self-inferred from ``feature_dir.parent.parent``.

    ``feature_dir`` is set to the coord-husk mission dir
    (``ctx.coord_feature_dir``), matching the real production shape:
    ``_run_arbiter_override``'s ``feature_dir`` argument is the caller's
    ALREADY topology-resolved COORD surface under a coord topology (see
    ``_mt_issue_matrix_facts``'s docstring in ``tasks_move_task.py``). The
    correct ``main_repo_root`` for this mission is the PRIMARY checkout root
    (``ctx.repo``) -- git worktree resolvers (``CoordinationWorkspace``,
    ``read_events_transactional``, ``_persist_review_artifact_override``)
    all resolve the coord partition FROM that root, not from within it.

    RED (pre-WP07): ``persist_arbiter_override_decision`` dropped
    ``main_repo_root`` entirely, so ``persist_arbiter_decision`` fell back to
    ``feature_dir.parent.parent`` == ``ctx.coord_feature_dir.parent.parent``
    == the COORD WORKTREE root (``.worktrees/<slug>-coord``) -- NOT
    ``ctx.repo``. GREEN (post-WP07): the resolved root is threaded through
    unchanged and lands on ``ctx.repo``.
    """
    ctx = coord_topology_mission
    wrong_root_if_self_inferred = ctx.coord_feature_dir.parent.parent
    assert wrong_root_if_self_inferred != ctx.repo, (
        "fixture invariant: the coord worktree root must differ from the "
        "primary repo root, or this test cannot distinguish threading from "
        "self-inference"
    )

    captured: dict[str, Any] = {}

    def _fake_persist_override(
        artifact_path: Path,
        *,
        repo_root: Path,
        wp_id: str,
        actor: str,
        reason: str,
    ) -> None:
        captured["repo_root"] = repo_root
        captured["wp_id"] = wp_id

    with (
        patch(
            "specify_cli.cli.commands.agent.tasks_materialization._persist_review_artifact_override",
            side_effect=_fake_persist_override,
        ),
        patch(
            "specify_cli.coordination.status_transition.read_events_transactional",
            return_value=[],
        ),
    ):
        from specify_cli.cli.commands.agent.tasks_move_task import (
            _run_arbiter_override,
        )

        review_ref = _run_arbiter_override(
            feature_dir=ctx.coord_feature_dir,
            mission_slug=ctx.slug,
            main_repo_root=ctx.repo,
            task_id="WP01",
            note_text="[pre_existing_failure] flaky in CI",
            agent="claude",
            json_output=True,
        )

    assert review_ref is None  # no prior events patched in -- nothing to link
    assert "repo_root" in captured, "the persist side effect was never reached"
    assert captured["repo_root"] == ctx.repo, (
        "main_repo_root was not threaded through: expected the caller-resolved "
        f"PRIMARY root {ctx.repo}, got {captured['repo_root']!r} -- this is "
        f"the coord-worktree self-inference ({wrong_root_if_self_inferred}) if "
        "it matches that value instead"
    )
    assert captured["wp_id"] == "WP01"


def test_persist_arbiter_decision_requires_repo_root_no_self_inference() -> None:
    """``persist_arbiter_decision`` must not accept an omitted ``repo_root``.

    T037: the ``or feature_dir.parent.parent`` fallback is retired entirely,
    not merely deprioritized -- calling without ``repo_root`` is a
    ``TypeError`` (missing required argument), not a silent, possibly-wrong
    inference.
    """
    from specify_cli.review.arbiter import persist_arbiter_decision

    signature = inspect.signature(persist_arbiter_decision)
    repo_root_param = signature.parameters["repo_root"]
    assert repo_root_param.default is inspect.Parameter.empty, (
        "repo_root must be a required parameter (no default) -- a default "
        "reopens the door to the retired self-inference fallback"
    )


# ---------------------------------------------------------------------------
# T038 -- confirming assertion (NOT a repoint): the arbiter's verdict read is
# already event-sourced; `.latest`/`cycle_number` on the WRITE path stays.
# ---------------------------------------------------------------------------


def test_arbiter_write_path_keeps_latest_for_cycle_number_only() -> None:
    """``persist_arbiter_decision`` (the WRITE path) still calls
    ``ReviewCycleArtifact.latest`` to derive ``cycle_number`` -- this is
    NOT a verdict read and must NOT be repointed (squad #1's corrected
    misdiagnosis). Asserts both halves of the invariant: ``.latest`` /
    ``cycle_number`` survive, and no ``.verdict`` attribute is read off the
    ``latest`` result anywhere in this function's source.
    """
    from specify_cli.review.arbiter import persist_arbiter_decision

    source = inspect.getsource(persist_arbiter_decision)
    assert "ReviewCycleArtifact.latest" in source, (
        "persist_arbiter_decision must keep resolving cycle_number via "
        "ReviewCycleArtifact.latest -- this WP is root-threading only, not "
        "a reader repoint"
    )
    assert "cycle_number" in source
    assert "latest.verdict" not in source and ".verdict" not in source, (
        "persist_arbiter_decision must never read a verdict off `latest` -- "
        "it is a WRITE-path artifact-location helper (cycle_number only), "
        "not a verdict reader"
    )


def test_arbiter_verdict_read_is_event_sourced() -> None:
    """The arbiter's verdict READ is event-sourced: ``arbiter_overrides_from_state`` reads the
    reduced snapshot state the caller got through the status read door (#7335), with no
    ``review-cycle-*.md`` frontmatter parse anywhere in its source. (It replaced
    ``get_arbiter_overrides_for_wp``, whose last caller #7431 moved onto the door.)
    """
    from specify_cli.review.arbiter import arbiter_overrides_from_state

    source = inspect.getsource(arbiter_overrides_from_state)
    assert "ReviewCycleArtifact" not in source, "the override read must not parse review-cycle artifact frontmatter"
    assert ".from_file(" not in source, "the override read must not load a review-cycle file"


def test_no_frontmatter_verdict_read_survives_anywhere_in_arbiter_module() -> None:
    """Whole-module confirming sweep: no ``.verdict`` attribute access and no
    ``review-cycle-*.md`` frontmatter parse anywhere in ``arbiter.py`` --
    the module's only verdict-adjacent reader is the already event-sourced
    ``get_arbiter_overrides_for_wp``, and its only ``ReviewCycleArtifact``
    touchpoint is the WRITE-path ``cycle_number`` derivation (T036/T037
    above), which this test does not disturb.
    """
    import specify_cli.review.arbiter as arbiter_module

    source = inspect.getsource(arbiter_module)
    assert "latest.verdict" not in source
    assert "ReviewCycleArtifact.from_file" not in source
