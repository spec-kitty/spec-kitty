"""Guard tests for #3311 — re-finalize preserves planning provenance once
execution has begun (mission-a-p0-consistency-01KZWHY1 WP04).

The finalize path (``_compute_and_write_lanes`` in
``src/specify_cli/cli/commands/agent/mission_finalize.py``) used to
unconditionally recompute ``lanes.json`` and re-capture
``planning_commit_sha`` on every non-``--validate-only`` run, destroying
established planning provenance in response to a benign ownership-only WP
amendment. The fix gates the recompute/re-capture on an "execution has
begun" signal (``_execution_has_begun`` / T014): before execution begins,
re-finalize keeps regenerating freely; once any WP has moved past
``planned``, re-finalize PRESERVES the recorded ``planning_commit_sha``
instead of clobbering it.

These three tests each pin a distinct, non-fakeable facet of the fix:

* ``test_execution_begun_preserves_recorded_sha_against_differing_tip`` —
  the crux regression case. It runs finalize against a REAL git repo so
  ``capture_branch_tip`` would return an actual, non-``None`` SHA
  that DIFFERS from the recorded provenance if the buggy recompute path
  ran. A naive ``if sha is not None: keep old`` guard (which only survives
  the None-tip case the original #3311 repro covered) fails this test.
* ``test_pre_execution_amendment_actually_regenerates`` — the mirror case:
  before execution begins, an ownership-only amendment must still visibly
  regenerate (lane topology union or a re-captured tip), so the fix cannot
  be a blanket "never touch lanes.json again" refusal.
* ``test_execution_begun_path_does_not_write_status_json`` — the read-does-
  not-write invariant. It snapshots the resolved status-surface directory's
  file set + content hashes before/after the execution-begun finalize call
  and asserts nothing changed, so a lazy ``reducer.materialize()`` swapped
  in for the mandated read-only ``get_all_wp_lanes`` recipe fails loudly
  instead of merely looking correct to a reviewer.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.coordination.surface_resolver import (
    resolve_status_surface_with_anchor,
)
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

from tests.specify_cli.cli.commands.agent.test_feature_finalize_bootstrap import (
    MODULE,
    _common_patches,
    _make_bootstrap_result,
    _setup_lane_based_feature,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SEEDED_PLANNING_SHA = "deadbeef000deadbeef000deadbeef000deadbeef"


def _run_finalize(mission_slug: str, patches: dict[str, object]) -> None:
    from specify_cli.cli.commands.agent.mission import finalize_tasks

    ctx_patches = {k: patch(k, v) for k, v in patches.items()}
    for p in ctx_patches.values():
        p.start()
    try:
        finalize_tasks(feature=mission_slug, json_output=True, validate_only=False)
    except (typer.Exit, SystemExit):
        pass  # finalize-tasks may exit; the file writes are what we assert on
    finally:
        for p in ctx_patches.values():
            p.stop()


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _git_init_with_first_commit(repo_root: Path) -> None:
    """Real git repo so ``capture_branch_tip`` returns a real SHA.

    Required for the non-fakeable "differing tip" preservation test — a
    non-git ``tmp_path`` always makes ``git rev-parse`` fail and
    ``capture_branch_tip`` return ``None``, which only exercises the
    weaker "None tip" case the original #3311 repro already covered.
    """
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")


def _git_advance_tip(repo_root: Path) -> str:
    """Commit again on ``main`` so the branch tip differs from any earlier SHA."""
    marker = repo_root / "TIP_MARKER.txt"
    marker.write_text("advance\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "advance tip")
    return _git(repo_root, "rev-parse", "--verify", "main")


def _seed_execution_begun_event(repo_root: Path, mission_slug: str, wp_id: str) -> None:
    """Append a real WP-past-``planned`` event to the resolved status surface.

    Uses the same read-dir authority (``resolve_status_surface_with_anchor``)
    the fix under test reads from, and the pure JSONL append (``append_event``)
    — never ``reducer.materialize()`` — so this seed itself demonstrates the
    read-only recipe round-trips correctly.
    """
    read_dir = resolve_status_surface_with_anchor(repo_root, mission_slug).read_dir
    event = StatusEvent(
        event_id="01HXYZEXECUTIONBEGUNTESTEVT",
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-08-13T00:00:00Z",
        actor="claude-sonnet",
        force=False,
        execution_mode="worktree",
    )
    append_event(read_dir, event)


def _amend_wp01_owned_files(feature_dir: Path) -> None:
    """Ownership-only amendment: WP01 additionally owns a path WP02 owns."""
    wp01 = feature_dir / "tasks" / "WP01-test.md"
    wp01.write_text(
        wp01.read_text(encoding="utf-8").replace(
            "owned_files:\n  - src/alpha.py\n",
            "owned_files:\n  - src/alpha.py\n  - src/beta.py\n",
        ),
        encoding="utf-8",
    )


def _base_patches(tmp_path: Path, mission_slug: str, feature_dir: Path) -> dict[str, object]:
    patches = _common_patches(tmp_path, mission_slug)
    patches[f"{MODULE}._find_feature_directory"] = MagicMock(return_value=feature_dir)
    patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(
        return_value=_make_bootstrap_result()
    )
    return patches


@pytest.fixture(autouse=True)
def _disable_saas_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep finalize-tasks on the offline path (mirrors sibling finalize tests).

    ``tests/conftest.py`` enables SaaS sync globally, which can let a
    machine-local daemon-owner record short-circuit finalize before these
    assertions run.
    """
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")


def test_execution_begun_preserves_recorded_sha_against_differing_tip(
    tmp_path: Path,
) -> None:
    """#3311 crux case: a REAL, differing branch tip must not clobber the SHA.

    The original repro only proved the ``None``-tip case (no git repo), which
    a naive ``if sha is not None: keep old`` guard fakes. Here
    ``capture_branch_tip`` is made to resolve to an actual SHA that
    differs from the recorded provenance, so only a genuine execution-begun
    gate (not a tip-nullness check) survives.
    """
    mission_slug = "062-lane-feature"
    feature_dir = _setup_lane_based_feature(tmp_path, mission_slug)
    _git_init_with_first_commit(tmp_path)

    patches = _base_patches(tmp_path, mission_slug, feature_dir)

    # Run 1: materialize the established topology (WP01/WP02 -> two lanes).
    _run_finalize(mission_slug, patches)
    established = read_lanes_json(feature_dir)
    assert established is not None
    baseline_topology = {lane.lane_id: sorted(lane.wp_ids) for lane in established.lanes}
    assert sorted(baseline_topology.values()) == [["WP01"], ["WP02"]], (
        "sanity: two disjoint WPs must materialize two independent single-WP "
        f"lanes; got {baseline_topology}"
    )

    # Seed the recorded planning provenance SHA for an established mission.
    established.planning_commit_sha = _SEEDED_PLANNING_SHA
    write_lanes_json(feature_dir, established)

    # Simulate execution-begun: WP01 has moved past `planned`.
    _seed_execution_begun_event(tmp_path, mission_slug, "WP01")

    # Advance the REAL branch tip so a re-capture (the buggy path) would
    # write a DIFFERENT, non-None SHA — never silently degrade to None.
    new_tip = _git_advance_tip(tmp_path)
    assert new_tip and new_tip != _SEEDED_PLANNING_SHA

    # Ownership-only amendment.
    _amend_wp01_owned_files(feature_dir)

    # Run 2: the execution-begun re-finalize.
    _run_finalize(mission_slug, patches)
    after = read_lanes_json(feature_dir)
    assert after is not None

    assert after.planning_commit_sha == _SEEDED_PLANNING_SHA, (
        "execution has begun: an ownership-only amendment must PRESERVE the "
        f"recorded planning_commit_sha ({_SEEDED_PLANNING_SHA!r}), not "
        f"re-capture the current (differing) branch tip; got "
        f"{after.planning_commit_sha!r} (current tip {new_tip!r})"
    )


def test_pre_execution_amendment_actually_regenerates(tmp_path: Path) -> None:
    """Benign case: with no WP past `planned`, regeneration must ACTUALLY run.

    "Did not refuse" alone is insufficient — this asserts the amended
    topology is observably reflected (WP01 and WP02 collapse into ONE lane
    once WP01 also claims WP02's file) or the recorded SHA visibly advances
    to the new tip, proving the pre-execution path still regenerates freely
    rather than accidentally inheriting the preserve behavior.
    """
    mission_slug = "063-lane-feature"
    feature_dir = _setup_lane_based_feature(tmp_path, mission_slug)
    _git_init_with_first_commit(tmp_path)

    patches = _base_patches(tmp_path, mission_slug, feature_dir)

    # Run 1: materialize the established topology. No status events are
    # seeded here — every WP is (at most) `planned` — so execution has not
    # begun.
    _run_finalize(mission_slug, patches)
    established = read_lanes_json(feature_dir)
    assert established is not None
    baseline_topology = {lane.lane_id: sorted(lane.wp_ids) for lane in established.lanes}
    assert sorted(baseline_topology.values()) == [["WP01"], ["WP02"]]
    first_tip = established.planning_commit_sha

    # Advance the branch tip so a re-capture is observable.
    new_tip = _git_advance_tip(tmp_path)
    assert new_tip != first_tip

    # Ownership-only amendment that also changes observable topology: WP01
    # now shares an owned file with WP02, so compute_lanes' Rule-1 union-find
    # merges them into a single lane.
    _amend_wp01_owned_files(feature_dir)

    # Run 2: the pre-execution re-finalize.
    _run_finalize(mission_slug, patches)
    after = read_lanes_json(feature_dir)
    assert after is not None
    after_topology = {lane.lane_id: sorted(lane.wp_ids) for lane in after.lanes}

    topology_changed = sorted(after_topology.values()) != sorted(baseline_topology.values())
    tip_recaptured = after.planning_commit_sha == new_tip
    assert topology_changed or tip_recaptured, (
        "pre-execution re-finalize must actually regenerate (topology "
        "collapse or a re-captured tip), not silently no-op; "
        f"before={baseline_topology!r} after={after_topology!r} "
        f"before_tip={first_tip!r} after_tip={after.planning_commit_sha!r} "
        f"expected_new_tip={new_tip!r}"
    )


def _hash_status_surface_files(directory: Path) -> dict[str, str]:
    """Content-hash the STATUS-surface files under ``directory``.

    Scoped to ``status.json`` (must never exist — a ``reducer.materialize()``
    call is the only thing that creates it) and ``status.events.jsonl`` (the
    event log the read-only recipe reads but must never append to). Deliberately
    EXCLUDES ``lanes.json`` and every other planning artifact: those are the
    NORMAL write surface finalize legitimately rewrites on every run (T015
    scopes this WP strictly to preserving the ``planning_commit_sha`` FIELD
    inside that rewrite, not freezing the whole file) — asserting them
    unchanged would conflate the write phase with the read-only gate this
    test targets.
    """
    hashes: dict[str, str] = {}
    for name in ("status.json", "status.events.jsonl"):
        path = directory / name
        if path.is_file():
            # Non-charter use (TID251): a byte-for-byte file-integrity check
            # on the raw status-surface files, not charter markdown content —
            # `charter.hasher.hash_content()` normalizes BOM/line-endings for
            # charter staleness comparison, which is the wrong semantics here.
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: TID251
    return hashes


def test_execution_begun_path_does_not_write_status_json(tmp_path: Path) -> None:
    """Renata's crux hazard: the execution-begun read path must not WRITE.

    Pins the read-does-not-write invariant two ways: (1) ``status.json`` must
    not exist before or after, and ``status.events.jsonl`` must be
    byte-identical before/after; (2) ``reducer.materialize`` must never be
    called. A lazy ``reducer.materialize()`` swapped in for the mandated
    ``get_all_wp_lanes`` read would create ``status.json`` and fail assertion
    (1) even if it happened to also satisfy the preservation behavior — no
    reviewer eyeball can catch that without this pin.
    """
    mission_slug = "064-lane-feature"
    feature_dir = _setup_lane_based_feature(tmp_path, mission_slug)
    _git_init_with_first_commit(tmp_path)

    patches = _base_patches(tmp_path, mission_slug, feature_dir)

    # Run 1: materialize the established topology.
    _run_finalize(mission_slug, patches)
    established = read_lanes_json(feature_dir)
    assert established is not None
    established.planning_commit_sha = _SEEDED_PLANNING_SHA
    write_lanes_json(feature_dir, established)

    # Simulate execution-begun.
    _seed_execution_begun_event(tmp_path, mission_slug, "WP02")
    _git_advance_tip(tmp_path)
    _amend_wp01_owned_files(feature_dir)

    read_dir = resolve_status_surface_with_anchor(tmp_path, mission_slug).read_dir
    assert not (read_dir / "status.json").exists(), (
        "sanity: status.json must not exist before the execution-begun run "
        "(reducer.materialize() has never been called yet)"
    )
    before_files = _hash_status_surface_files(read_dir)
    assert before_files, "sanity: the status surface must already contain the seeded event log"

    with patch(
        "specify_cli.status.reducer.materialize",
        side_effect=AssertionError(
            "reducer.materialize() must NEVER be called by the execution-begun "
            "finalize gate — it writes status.json to disk, which a read-only "
            "signal helper must never do (C-005)."
        ),
    ) as materialize_spy:
        _run_finalize(mission_slug, patches)

    materialize_spy.assert_not_called()
    assert not (read_dir / "status.json").exists(), (
        "the execution-begun finalize path must not create status.json — that "
        "is exclusively reducer.materialize()'s side effect"
    )

    after_files = _hash_status_surface_files(read_dir)
    assert after_files == before_files, (
        "the execution-begun finalize path must not modify status.json or "
        f"status.events.jsonl under the resolved status surface ({read_dir}); "
        f"before={before_files!r} after={after_files!r}"
    )
