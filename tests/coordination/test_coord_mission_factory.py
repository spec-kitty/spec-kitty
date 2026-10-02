"""Self-tests for the shared coordination-Mission fixture harness (WP02, FR-016).

Pins that each builder in ``tests._factories.coord_mission`` keeps producing
its documented shape at the current base. This WP ships no reproduction --
every assertion here is GREEN by design (analyze C2: red-evidence exempt,
harness only).

L2: markers are applied per-test (not as a module-level ``pytestmark``) so
the pure probe tests (``fast``/``unit``) stay in ``make test-fast``'s
``(fast or unit)`` selection -- a module-level ``integration`` mark would
exclude them (``FAST_TIER_MARKERS`` deselects ``not integration``).

How later WPs use this (research red-first list):
    R1/R1b/R6/R20 (WP06) -- ``make_prefix_coord_mission``.
    R2 (WP05)            -- ``make_coord_mission``.
    R3/R14/R15/R16 (WP17) -- ``make_fork_fixture`` (shapes b/c/d).
    R4 (WP09)            -- ``make_prefix_coord_mission`` + ``commits_touching``.
    R22/R23/R24 (WP18)   -- ``make_coord_mission`` / ``event_ids``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Literal

import pytest

from mission_runtime import MissionTopology
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.missions._read_path_resolver import CoordState, probe_coord_state
from tests._factories.coord_mission import (
    COORD_TOPOLOGIES,
    CoordMission,
    ForkFixture,
    coord_tree_has,
    commits_touching,
    event_ids,
    index_entry_ids,
    lamports,
    make_coord_mission,
    make_fork_fixture,
    make_prefix_coord_mission,
    _rewrite_into_prefix_shape,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _is_ancestor(repo: Path, ancestor_sha: str, descendant_ref: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor_sha, descendant_ref],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _first_event_type(path: Path) -> str:
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    event_type = json.loads(first_line)["event_type"]
    return str(event_type)


# ---------------------------------------------------------------------------
# T008 -- make_coord_mission, every via x topology
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("via", ["core", "cli_topology", "cli_pr_bound"])
@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_make_coord_mission_records_requested_topology(
    tmp_path: Path,
    topology: MissionTopology,
    via: Literal["core", "cli_topology", "cli_pr_bound"],
) -> None:
    coord = make_coord_mission(tmp_path, topology, via=via, slug="viacheck")

    assert coord.topology is topology
    assert _git(coord.repo_root, "rev-parse", "--verify", coord.coordination_branch)
    assert _is_ancestor(coord.repo_root, coord.creation_base_sha, coord.target_branch)


@pytest.mark.integration
@pytest.mark.git_repo
def test_make_coord_mission_materialized_true_reaches_materialized(tmp_path: Path) -> None:
    coord = make_coord_mission(tmp_path, MissionTopology.COORD, materialized=True)

    state = probe_coord_state(
        coord.repo_root,
        coord.mission_dir_name,
        coord.mid8,
        coordination_branch=coord.coordination_branch,
    )
    assert state is CoordState.MATERIALIZED
    assert coord.coord_mission_dir.exists()
    # Re-pinned (coord-artifact-single-home-01M3V4BE WP06, D4/D6): a default
    # (``via="core"``) coordination-routed create now seeds the surface
    # itself, so `_materialize_coord_surface`'s own fixture write is a no-op
    # here (`coord_mission_dir` already exists) and the MATERIALIZED state is
    # reached by create's own post-fix (trailer-bearing) seed commit, not by
    # the factory's pre-fix-shaped fallback write. The trailer presence is
    # exactly what D4 requires for a freshly created Mission -- the stale
    # "no trailer" assertion described the pre-WP06 shape this factory's own
    # docstring flagged as changing once WP06 landed.
    log = _git(coord.coord_worktree_path, "log", "-1", "--format=%B")
    assert "Spec-Kitty-Coordination-Seed" in log


@pytest.mark.integration
@pytest.mark.git_repo
def test_make_coord_mission_unknown_via_raises(tmp_path: Path) -> None:
    # L1: pass the bad value through an Any-typed local rather than a
    # `# type: ignore` -- the branch is deliberately outside the `via`
    # Literal, to exercise the runtime fail-closed else-branch a
    # type-correct caller can never reach statically.
    bogus_via: Any = "bogus"
    with pytest.raises(ValueError, match="Unknown via"):
        make_coord_mission(tmp_path, MissionTopology.COORD, via=bogus_via)


# ---------------------------------------------------------------------------
# M1 -- topology=None (WP06's real default path: no --topology, product-resolved)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_make_coord_mission_cli_pr_bound_no_topology_resolves_to_coord(tmp_path: Path) -> None:
    """WP06 US1.4's real default path: pr-bound, protected primary, NO --topology."""
    coord = make_coord_mission(tmp_path, None, via="cli_pr_bound", protected_primary=True)

    assert coord.topology is MissionTopology.COORD


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("via", ["core", "cli_topology"])
def test_make_coord_mission_topology_none_rejected_for_non_pr_bound_via(tmp_path: Path, via: Literal["core", "cli_topology"]) -> None:
    with pytest.raises(ValueError, match="topology=None"):
        make_coord_mission(tmp_path, None, via=via)


# ---------------------------------------------------------------------------
# M2 -- protected_primary protects the Primary Branch (main), consistently
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("via", ["core", "cli_topology", "cli_pr_bound"])
def test_make_coord_mission_protected_primary_protects_main_for_every_via(tmp_path: Path, via: Literal["core", "cli_topology", "cli_pr_bound"]) -> None:
    coord = make_coord_mission(tmp_path, MissionTopology.COORD, via=via, protected_primary=True)

    policy = ProtectionPolicy.resolve(coord.repo_root)
    assert policy.is_protected("main"), f"via={via} did not protect the Primary Branch"


@pytest.mark.integration
@pytest.mark.git_repo
def test_make_coord_mission_default_writes_no_protection_config(tmp_path: Path) -> None:
    """Without protected_primary, the fixture itself never writes a ``protection``
    key -- it is production's own fail-safe default (``{main, master}``) that
    protects ``main`` regardless, not something this fixture configured. A
    literal ``is_protected("main") is False`` assertion would be FALSE here
    even on a correct fixture, since that default applies with zero config.
    """
    coord = make_coord_mission(tmp_path, MissionTopology.COORD)

    config_text = (coord.repo_root / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    assert "protection" not in config_text


# ---------------------------------------------------------------------------
# T009 -- make_prefix_coord_mission, every variant
# ---------------------------------------------------------------------------


def _assert_root_log_has_creation_events(coord: CoordMission) -> None:
    ids = event_ids(coord.root_mission_dir / "status.events.jsonl")
    assert ids, "root checkout status log must contain the creation events"
    # L3: assert the documented event type, not merely non-empty ids.
    assert _first_event_type(coord.root_mission_dir / "status.events.jsonl") == "MissionCreated"
    # L3: assert the log is actually committed on the target branch, as the
    # docstring claims -- not merely present on disk.
    rel = f"kitty-specs/{coord.mission_dir_name}/status.events.jsonl"
    assert coord_tree_has(coord.repo_root, coord.target_branch, rel)


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("worktree", ["absent", "empty"])
def test_make_prefix_coord_mission_worktree_variants(tmp_path: Path, worktree: Literal["absent", "empty"]) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree=worktree)

    expected = CoordState.UNMATERIALIZED if worktree == "absent" else CoordState.EMPTY
    state = probe_coord_state(
        coord.repo_root,
        coord.mission_dir_name,
        coord.mid8,
        coordination_branch=coord.coordination_branch,
    )
    assert state is expected
    _assert_root_log_has_creation_events(coord)
    mission_dir_path = f"kitty-specs/{coord.mission_dir_name}"
    assert not coord_tree_has(coord.repo_root, coord.coordination_branch, mission_dir_path)


@pytest.mark.integration
@pytest.mark.git_repo
def test_make_prefix_coord_mission_remote_only(tmp_path: Path) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, remote_only=True)

    state = probe_coord_state(
        coord.repo_root,
        coord.mission_dir_name,
        coord.mid8,
        coordination_branch=coord.coordination_branch,
    )
    assert state is CoordState.UNMATERIALIZED
    # Local head is gone; only the remote-tracking ref remains.
    local_heads = _git(coord.repo_root, "branch", "--list", coord.coordination_branch)
    assert local_heads == ""


@pytest.mark.integration
@pytest.mark.git_repo
def test_make_prefix_coord_mission_branch_deleted(tmp_path: Path) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, branch_deleted=True)

    state = probe_coord_state(
        coord.repo_root,
        coord.mission_dir_name,
        coord.mid8,
        coordination_branch=coord.coordination_branch,
    )
    assert state is CoordState.DELETED


@pytest.mark.integration
@pytest.mark.git_repo
def test_make_prefix_coord_mission_extra_events_are_uncommitted(tmp_path: Path) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, extra_events=2)

    ids = event_ids(coord.root_mission_dir / "status.events.jsonl")
    assert len(ids) == 4  # MissionCreated + SpecifyStarted + 2 extras
    status = _git(coord.repo_root, "status", "--porcelain")
    rel = f"kitty-specs/{coord.mission_dir_name}/status.events.jsonl"
    assert rel in status


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_make_prefix_coord_mission_both_topologies(tmp_path: Path, topology: MissionTopology) -> None:
    coord = make_prefix_coord_mission(tmp_path, topology)
    assert coord.topology is topology


# ---------------------------------------------------------------------------
# H1 -- the pre-fix builder is built explicitly, independent of create's placement
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_rewrite_into_prefix_shape_handles_real_post_fix_create_output(tmp_path: Path) -> None:
    """Re-pinned (coord-artifact-single-home-01M3V4BE WP06 landed): this test used
    to SIMULATE "WP06's FUTURE create output" (coordination branch seeded with the
    Mission dir + status log, root checkout never gets it) via
    ``_simulate_post_fix_seeded_coordination``, to prove (H1) the rewrite step does
    not depend on today's then-current pre-fix create placement. WP06 has now
    landed: a real ``via="core"`` create already produces exactly that shape, so
    the simulation helper is retired and this test drives the rewrite step against
    create's REAL output directly.
    """
    coord = make_coord_mission(tmp_path, MissionTopology.COORD, via="core", slug="simfuture")

    mission_dir_path = f"kitty-specs/{coord.mission_dir_name}"
    # Sanity: create's real output already carries the Mission dir on the
    # coordination branch and nothing at the root checkout (#5440).
    assert not (coord.root_mission_dir / "status.events.jsonl").exists()
    assert coord_tree_has(coord.repo_root, coord.coordination_branch, mission_dir_path)

    _rewrite_into_prefix_shape(coord)

    # Now it must match the documented pre-fix shape, built explicitly.
    assert not coord_tree_has(coord.repo_root, coord.coordination_branch, mission_dir_path)
    assert not coord.coord_worktree_path.exists()
    _assert_root_log_has_creation_events(coord)


@pytest.mark.integration
@pytest.mark.git_repo
def test_rewrite_into_prefix_shape_is_a_no_op_on_already_prefix_shaped_output(
    tmp_path: Path,
) -> None:
    """The rewrite step is idempotent once a Mission is ALREADY in the pre-fix
    shape.

    Re-pinned (coord-artifact-single-home-01M3V4BE WP06 landed): a real
    ``via="core"`` create no longer produces the pre-fix shape directly (D6) --
    ``make_prefix_coord_mission`` reaches it by calling
    :func:`_rewrite_into_prefix_shape` once already; this test calls it a SECOND
    time on that already-rewritten output to prove idempotency.
    """
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD)
    base_tip = _git(coord.repo_root, "rev-parse", coord.coordination_branch)

    _rewrite_into_prefix_shape(coord)

    assert _git(coord.repo_root, "rev-parse", coord.coordination_branch) == base_tip


# ---------------------------------------------------------------------------
# H2/H3 -- NFR-002 fork fixtures, per-stream, self-checked at construction
# ---------------------------------------------------------------------------


def _stream_filename(stream: Literal["status_log", "decision_log"]) -> str:
    return "status.events.jsonl" if stream == "status_log" else "decisions.events.jsonl"


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("stream", ["status_log", "decision_log", "both"])
def test_fork_fixture_root_uncommitted_coord_untracked_per_stream(tmp_path: Path, stream: Literal["status_log", "decision_log", "both"]) -> None:
    fixture = make_fork_fixture(tmp_path, "root_uncommitted_coord_untracked", MissionTopology.COORD, stream=stream)

    streams: tuple[Literal["status_log", "decision_log"], ...] = ("status_log", "decision_log") if stream == "both" else (stream,)
    for one_stream in streams:
        filename = _stream_filename(one_stream)
        root_ids = event_ids(fixture.root_mission_dir / filename)
        coord_ids = event_ids(fixture.coord_mission_dir / filename)
        assert root_ids and coord_ids
        root_set, coord_set = set(root_ids), set(coord_ids)
        assert not root_set.issubset(coord_set)
        assert not coord_set.issubset(root_set)
    assert fixture.decision_ids_root != fixture.decision_ids_coord

    # The OTHER stream is untouched by this fixture's injection (H2: "absent
    # or single-home"). `status.events.jsonl` is single-home on the root
    # (the normal, un-diverged creation copy) when `decision_log` is the
    # selected stream; `decisions.events.jsonl` is brand new and so fully
    # absent on both surfaces when `status_log` is selected.
    if stream != "both":
        other: Literal["status_log", "decision_log"] = "decision_log" if stream == "status_log" else "status_log"
        other_filename = _stream_filename(other)
        if other == "status_log":
            assert (fixture.root_mission_dir / other_filename).exists()
        else:
            assert not (fixture.root_mission_dir / other_filename).exists()
        assert not (fixture.coord_mission_dir / other_filename).exists()

    root_status = _git(fixture.repo_root, "status", "--porcelain")
    coord_status = _git(fixture.coord_worktree_path, "status", "--porcelain")
    assert "kitty-specs/" in root_status  # uncommitted in the root checkout
    assert "kitty-specs/" in coord_status  # untracked in the coord worktree


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("stream", ["status_log", "decision_log", "both"])
def test_fork_fixture_both_committed_per_stream(tmp_path: Path, stream: Literal["status_log", "decision_log", "both"]) -> None:
    fixture = make_fork_fixture(tmp_path, "both_committed", MissionTopology.COORD, stream=stream)

    # Both event logs are committed on their respective branches -- neither
    # appears as a pending (untracked/modified) path, regardless of other
    # unrelated scaffold files (.kittify/, spec.md, ...) the create path
    # leaves uncommitted in the root checkout.
    root_status = _git(fixture.repo_root, "status", "--porcelain")
    coord_status = _git(fixture.coord_worktree_path, "status", "--porcelain")
    streams: tuple[Literal["status_log", "decision_log"], ...] = ("status_log", "decision_log") if stream == "both" else (stream,)
    for one_stream in streams:
        filename = _stream_filename(one_stream)
        rel = f"kitty-specs/{fixture.mission_dir_name}/{filename}"
        assert rel not in root_status
        assert rel not in coord_status
        assert coord_tree_has(fixture.repo_root, fixture.coordination_branch, rel)
        assert coord_tree_has(fixture.repo_root, fixture.target_branch, rel)


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("stream", ["status_log", "decision_log"])
def test_fork_fixture_fresh_clone_per_stream(tmp_path: Path, stream: Literal["status_log", "decision_log"]) -> None:
    fixture = make_fork_fixture(tmp_path, "fresh_clone", MissionTopology.COORD, stream=stream)

    assert fixture.clone_root is not None
    assert not (fixture.clone_root / ".worktrees").exists()
    relpath = f"kitty-specs/{fixture.mission_dir_name}/{_stream_filename(stream)}"
    ids = event_ids((fixture.clone_root, fixture.coordination_branch, relpath))
    assert ids


@pytest.mark.integration
@pytest.mark.git_repo
def test_fork_fixture_ledger_only_on_coordination(tmp_path: Path) -> None:
    fixture = make_fork_fixture(tmp_path, "ledger_only_on_coordination", MissionTopology.COORD)

    assert not (fixture.root_mission_dir / "decisions").exists()
    decisions_path = f"kitty-specs/{fixture.mission_dir_name}/decisions"
    assert coord_tree_has(fixture.repo_root, fixture.coordination_branch, decisions_path)
    index_path = f"{decisions_path}/index.json"
    coord_ids = index_entry_ids((fixture.repo_root, fixture.coordination_branch, index_path))
    assert fixture.decision_ids_coord[0] in coord_ids

    # Downstream note: `_read_source` returns "" both for a missing path and
    # for a bad ref, so a wrong ref would make this negative pass without
    # testing anything. Assert the ref resolves FIRST.
    assert _git(fixture.repo_root, "rev-parse", "--verify", fixture.target_branch)
    target_ids = index_entry_ids((fixture.repo_root, fixture.target_branch, index_path))
    assert target_ids == set()


@pytest.mark.integration
@pytest.mark.git_repo
def test_make_fork_fixture_unknown_shape_raises(tmp_path: Path) -> None:
    # L1: Any-typed local for the deliberately-ill-typed call (see
    # test_make_coord_mission_unknown_via_raises for the same pattern).
    bogus_shape: Any = "bogus-shape"
    with pytest.raises(ValueError, match="Unknown fork fixture shape"):
        make_fork_fixture(tmp_path, bogus_shape)


# ---------------------------------------------------------------------------
# T010 -- pure probe tests on a tiny hand-made repo
# ---------------------------------------------------------------------------


@pytest.fixture
def tiny_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "tiny"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    return repo


@pytest.mark.fast
@pytest.mark.unit
def test_commits_touching_empty_when_path_never_changed(tiny_repo: Path) -> None:
    assert commits_touching(tiny_repo, "HEAD", "never-existed.txt") == []


@pytest.mark.fast
@pytest.mark.unit
def test_commits_touching_non_empty_when_path_changed(tiny_repo: Path) -> None:
    (tiny_repo / "touched.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "touched.txt"], cwd=tiny_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "touch"], cwd=tiny_repo, check=True)

    shas = commits_touching(tiny_repo, "HEAD", "touched.txt")
    assert len(shas) == 1


@pytest.mark.fast
@pytest.mark.unit
def test_coord_tree_has_true_and_false(tiny_repo: Path) -> None:
    assert coord_tree_has(tiny_repo, "main", "README.md")
    assert not coord_tree_has(tiny_repo, "main", "does-not-exist.md")


@pytest.mark.fast
@pytest.mark.unit
def test_event_ids_and_lamports_tolerate_missing_fields(tmp_path: Path) -> None:
    jsonl = tmp_path / "events.jsonl"
    jsonl.write_text(
        '{"event_id": "A", "lamport_clock": 2}\n{"event_id": "B", "payload": {"event_lamport": 5}}\n{"event_id": "C"}\n',
        encoding="utf-8",
    )

    assert event_ids(jsonl) == ("A", "B", "C")
    assert lamports(jsonl) == (2, 5, None)


@pytest.mark.fast
@pytest.mark.unit
def test_event_ids_absent_file_returns_empty_tuple(tmp_path: Path) -> None:
    assert event_ids(tmp_path / "missing.jsonl") == ()
    assert index_entry_ids(tmp_path / "missing-index.json") == set()


# ---------------------------------------------------------------------------
# T011 -- pytest fixture smoke tests (no clash with existing fixtures in this dir)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_coord_mission_fixture_both_topologies_parametrized(coord_mission: CoordMission) -> None:
    assert coord_mission.topology in COORD_TOPOLOGIES
    assert coord_mission.coordination_branch


@pytest.mark.integration
@pytest.mark.git_repo
def test_prefix_coord_mission_fixture_default_is_empty(prefix_coord_mission: CoordMission) -> None:
    state = probe_coord_state(
        prefix_coord_mission.repo_root,
        prefix_coord_mission.mission_dir_name,
        prefix_coord_mission.mid8,
        coordination_branch=prefix_coord_mission.coordination_branch,
    )
    assert state is CoordState.EMPTY


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("prefix_coord_mission", [{"worktree": "absent"}], indirect=True)
def test_prefix_coord_mission_fixture_indirect_override(
    prefix_coord_mission: CoordMission,
) -> None:
    state = probe_coord_state(
        prefix_coord_mission.repo_root,
        prefix_coord_mission.mission_dir_name,
        prefix_coord_mission.mid8,
        coordination_branch=prefix_coord_mission.coordination_branch,
    )
    assert state is CoordState.UNMATERIALIZED


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("fork_fixture", ["both_committed"], indirect=True)
def test_fork_fixture_indirect_shape(fork_fixture: ForkFixture) -> None:
    assert fork_fixture.decision_ids_root
    assert fork_fixture.decision_ids_coord


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize(
    "fork_fixture",
    [{"shape": "both_committed", "stream": "decision_log"}],
    indirect=True,
)
def test_fork_fixture_indirect_shape_and_stream(fork_fixture: ForkFixture) -> None:
    relpath = f"kitty-specs/{fork_fixture.mission_dir_name}/decisions.events.jsonl"
    assert coord_tree_has(fork_fixture.repo_root, fork_fixture.coordination_branch, relpath)
