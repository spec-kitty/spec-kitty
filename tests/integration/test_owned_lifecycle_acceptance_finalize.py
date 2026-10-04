"""Acceptance tests: owned-checkout ``finalize-tasks`` (WP13, T070/T074).

owned-checkout-lifecycle-authority WP13 (FR-007/FR-013/FR-015/FR-021,
NFR-001/NFR-002, US4/O6). Builds on WP02's shared owned-checkout fixtures
(``make_owned_checkouts``, ``r_snapshot``, ``stale_root_copy``,
``owned_checkouts``) from ``tests/integration/conftest.py`` -- never a
hand-rolled R/P pair.

**Why a lane-cycle/ownership-overlap dual fixture isn't used (open question 3
from the WP13 handback; operator-confirmed).** T070 describes a single
WP01<->WP02/WP03<->WP04 fixture meant to trip BOTH the lane-dependency-cycle
gate and an ownership-manifest overlap. Against the REAL (unpatched)
``finalize-tasks`` path, ownership validation (``_validate_ownership_
manifests``) refuses literal ``owned_files`` glob overlap, so two ordinary
WPs sharing an owned file always trip that refusal FIRST, before lane
collapse or dependency-cycle detection ever runs -- a shared-file fixture is
therefore the OWNERSHIP-OVERLAP row, not the lane-cycle row.

A genuine, REACHABLE lane-cycle refusal needs WPs that pass ownership
validation yet still collapse into a shared lane. That is Rule 1 of
``compute_lanes`` (``lanes/compute.py::find_overlap_pairs``: literal
``owned_files`` overlap) with an exemption asymmetry: ownership VALIDATION
(``ownership/validation.py::validate_no_overlap``) exempts any
``scope: codebase-wide`` WP from every overlap pair, while Rule 1 has no such
exemption. So marking WP03/WP04 ``scope: codebase-wide`` and giving each the
SAME owned file as WP02/WP01 collapses {WP01,WP04} and {WP02,WP03}; the
dependencies WP01->WP02 and WP03->WP04 then close a two-lane cycle.
(Rule 2, the surface-keyword collapse, is NOT used: it skips the union
whenever ownership is provably disjoint.)
:func:`test_cyclic_lane_fixture_finalizes_to_the_single_repo_root_lane_
inside_owned_checkout_and_r_is_unchanged` builds exactly that fixture. Two
independent fixtures are therefore used, not one, matching the operator's
go-ahead on this question. Since origin/main's #5100 a ``single_branch``
mission (the only owned lifecycle topology) has ONE repo-root lane, so that
row can no longer reach a lane cycle and now pins the #5100 outcome instead;
the stale-canceled, planning-pin-orphan and issue-matrix rows keep the
post-write-refusal coverage.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest
from typer.testing import CliRunner

from mission_runtime import OwnedCheckout
from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.persistence import read_lanes_json
from tests._owned_fixtures import RSnapshotter
from tests._owned_tree_hash import hash_tree
from tests.integration.conftest import OwnedCheckouts
from tests.status.test_transition_request_owned import _write_finalizable_tasks_md

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


@pytest.fixture(autouse=True)
def _disable_saas_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    monkeypatch.setattr(emit_module, "_saas_fan_out", lambda *a, **k: None)


def _invoke_finalize(mission_slug: str, *extra: str) -> tuple[int, str]:
    from specify_cli.workspace.context import clear_workspace_resolution_caches

    clear_workspace_resolution_caches()
    result = runner.invoke(
        mission_app,
        ["finalize-tasks", "--mission", mission_slug, "--json", *extra],
        catch_exceptions=False,
    )
    return result.exit_code, result.output


def test_owned_worktrees_finalize_succeeds_and_r_is_unchanged(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """US4-AS1 / O6: an owned P at R/.worktrees/owned-a finalizes; R never changes.

    The base (pre-WP13) refuses this shape entirely ("must not target
    coordination worktree paths"); WP06/WP07 supply the enabling seams and
    this WP proves the behaviour end to end, atomically (not preceded by a
    partial write -- assert_unchanged covers HEAD/index/working
    tree/lock/home).
    """
    checkouts = make_owned_checkouts(placement="under_worktrees")
    _write_finalizable_tasks_md(checkouts)
    snapshotter = make_r_snapshot(checkouts)
    monkeypatch.chdir(checkouts.repository_root)
    before = snapshotter.take()

    exit_code, output = _invoke_finalize(checkouts.mission_slug, "--owned-checkout", str(checkouts.owned_root))

    assert exit_code == 0, output
    assert (checkouts.mission_dir / "lanes.json").is_file()
    events_path = checkouts.mission_dir / "status.events.jsonl"
    assert events_path.is_file()
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(row.get("to_lane") == "planned" for row in events)

    after = snapshotter.take()
    snapshotter.assert_unchanged(before, after, tolerate_status_mutex_for=checkouts.mission_slug)


def test_flagless_adoption_from_owned_worktrees_finalizes_p(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-021: running finalize-tasks from inside P without --owned-checkout adopts P.

    Same fixture as the explicit-flag case above, but ``cwd`` is P itself and
    no ``--owned-checkout`` is passed -- ``resolve_owned_or_adopt``'s
    flagless branch (``adopt_owned_checkout``) must resolve P and finalize
    it exactly as the explicit-flag path does.
    """
    checkouts = make_owned_checkouts(placement="under_worktrees")
    _write_finalizable_tasks_md(checkouts)
    snapshotter = make_r_snapshot(checkouts)
    monkeypatch.chdir(checkouts.owned_root)
    before = snapshotter.take()

    exit_code, output = _invoke_finalize(checkouts.mission_slug)

    assert exit_code == 0, output
    assert (checkouts.mission_dir / "lanes.json").is_file()

    after = snapshotter.take()
    snapshotter.assert_unchanged(before, after, tolerate_status_mutex_for=checkouts.mission_slug)


class POracle(NamedTuple):
    """FR-015 oracle, P's half: HEAD, porcelain (incl. ignored) and every file's content hash."""

    head: str
    porcelain: str
    files: dict[str, str]


def _take_p_oracle(root: Path) -> POracle:
    """(HEAD, porcelain-plus-ignored, content hashes incl. ignored files) for P.

    ``git status --porcelain --ignored`` alone cannot see a REWRITE of an
    already-dirty or ignored file (for example ``.kittify/derived/...`` or an
    append to an already-modified ``status.events.jsonl``), so every file's
    content is hashed too (``tests/_owned_tree_hash.hash_tree``).
    """
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=root, capture_output=True, text=True, check=True).stdout
    return POracle(head, status, hash_tree(root))


def _assert_p_unchanged(before: POracle, after: POracle, why: str) -> None:
    assert after.head == before.head, f"P's HEAD moved despite {why}"
    assert after.porcelain == before.porcelain, f"P's working tree left dirty after {why}:\n{after.porcelain!r}"
    assert after.files == before.files, f"a file in P changed despite {why}"


def _write_overlapping_wps(checkouts: OwnedCheckouts, *, spec_suffix: str = "") -> None:
    """Two WPs inside P claiming the same owned file (optionally citing an issue in spec.md)."""
    mission_dir = checkouts.mission_dir
    (mission_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01\n\n**Dependencies**: None\n\n## WP02\n\n**Dependencies**: None\n",
        encoding="utf-8",
    )
    for wp_id in ("WP01", "WP02"):
        (mission_dir / "tasks" / f"{wp_id}-owned.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Owned fixture task\ndependencies: []\n"
            "requirement_refs: [FR-001]\nsubtasks: []\nowned_files: [shared.py]\n"
            "authoritative_surface: shared.py\nexecution_mode: code_change\n"
            "create_intent:\n  - shared.py\n---\n\n# Task\n",
            encoding="utf-8",
        )
    if spec_suffix:
        spec_path = mission_dir / "spec.md"
        spec_path.write_text(spec_path.read_text(encoding="utf-8") + spec_suffix, encoding="utf-8")
    subprocess.run(["git", "add", "spec.md", "tasks.md", "tasks"], cwd=mission_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture: overlapping owned_files"], cwd=mission_dir, check=True)


def test_ownership_overlap_refusal_inside_owned_checkout_leaves_p_and_r_unchanged(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """US4-AS3 (owned): a genuine post-write refusal leaves P AND R unchanged.

    Two WPs inside P claim the same owned file -- the ownership-manifest-
    overlap refusal (see the module docstring for why this, not a lane
    cycle, is the reachable post-write refusal here) fires AFTER the WP
    frontmatter flush and the ``tasks.md`` regeneration (same R-07 ordering
    as the non-owned case ``test_finalize_atomicity.py`` already pins).
    """
    checkouts = make_owned_checkouts(placement="under_worktrees", wp_ids=("WP01", "WP02"))
    _write_overlapping_wps(checkouts)

    snapshotter = make_r_snapshot(checkouts)
    monkeypatch.chdir(checkouts.repository_root)
    before_r = snapshotter.take()
    before_p = _take_p_oracle(checkouts.owned_root)

    exit_code, output = _invoke_finalize(checkouts.mission_slug, "--owned-checkout", str(checkouts.owned_root))

    assert exit_code != 0, output
    assert "Ownership validation failed" in output, output

    after_r = snapshotter.take()
    snapshotter.assert_unchanged(before_r, after_r)
    after_p = _take_p_oracle(checkouts.owned_root)
    _assert_p_unchanged(before_p, after_p, "the ownership-overlap refusal")


def test_cyclic_lane_fixture_finalizes_to_the_single_repo_root_lane_inside_owned_checkout_and_r_is_unchanged(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """US4-AS3 (owned), the former LANE-CYCLE row, re-expressed for #5100.

    Before origin/main's #5100 (Invariant T-1) this fixture drove a real
    post-write ``LANE_DEPENDENCY_CYCLE`` refusal. #5100 computes a
    ``single_branch`` mission's lanes as the ONE repo-root ``lane-planning``
    lane (``lanes/compute.py::_build_single_branch_manifest``), so no lane
    graph -- and no lane cycle -- exists, and the owned lifecycle supports
    only ``single_branch`` (``LIFECYCLE_OWNED_TOPOLOGIES``): the lane-cycle
    refusal is unreachable inside an owned checkout. The row now pins that
    contract on the same fixture: finalize succeeds in P with exactly the
    repo-root lane, and R stays byte-identical.

    Original fixture rationale (kept, it still shapes the input):

    Per the module docstring: Rule 1 (``find_overlap_pairs`` in
    ``lanes/compute.py``) unions any two WPs whose ``owned_files`` globs
    overlap, with NO ``scope: codebase-wide`` exemption -- unlike ownership
    VALIDATION's own overlap check (``ownership/validation.py::
    validate_no_overlap``), which excludes a codebase-wide WP from every
    pair it appears in ("codebase-wide WPs ... are allowed to overlap with
    anything"). Marking WP04 and WP03 ``scope: codebase-wide`` and giving
    each the SAME ``owned_files`` entry as WP01 / WP02 respectively
    therefore collapses {WP01,WP04} into one lane and {WP02,WP03} into
    another WITHOUT tripping ownership validation. Dependencies WP01->WP02
    and WP03->WP04 then close a 2-lane cycle: lane {WP01,WP04} depends on
    lane {WP02,WP03} (via WP01->WP02) and vice versa (via WP03->WP04) --
    the same acyclic-WP/cyclic-lane shape as ``test_finalize_lane_
    dependency_cycle.py``'s ``_write_cyclic_mission``, reachable here
    WITHOUT mocking ownership validation.
    """
    checkouts = make_owned_checkouts(placement="under_worktrees", wp_ids=("WP01", "WP02", "WP03", "WP04"))
    mission_dir = checkouts.mission_dir
    (mission_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01\n\nDepends on WP02.\n\n## WP02\n\nNo dependencies.\n\n## WP03\n\nDepends on WP04.\n\n## WP04\n\nNo dependencies.\n",
        encoding="utf-8",
    )
    # (owned_file, dependencies, codebase_wide)
    wp_specs = {
        "WP01": ("src/one.py", ["WP02"], False),
        "WP02": ("src/two.py", [], False),
        "WP03": ("src/two.py", ["WP04"], True),  # shares WP02's file -> unions {WP02,WP03}
        "WP04": ("src/one.py", [], True),  # shares WP01's file -> unions {WP01,WP04}
    }
    for wp_id, (owned_file, deps, codebase_wide) in wp_specs.items():
        dep_yaml = "dependencies:\n" + "".join(f"  - {d}\n" for d in deps) if deps else "dependencies: []\n"
        scope_yaml = "scope: codebase-wide\n" if codebase_wide else ""
        (mission_dir / "tasks" / f"{wp_id}-owned.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Owned fixture task\n"
            f"{dep_yaml}"
            f"requirement_refs: [FR-001]\nsubtasks: []\nowned_files: [{owned_file}]\n"
            f"authoritative_surface: {owned_file}\nexecution_mode: code_change\n{scope_yaml}"
            f"create_intent:\n  - {owned_file}\n---\n\n# Task\n",
            encoding="utf-8",
        )
    subprocess.run(["git", "add", "tasks.md", "tasks"], cwd=mission_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture: codebase-wide-exempt overlap, cyclic collapsed lanes"], cwd=mission_dir, check=True)

    snapshotter = make_r_snapshot(checkouts)
    monkeypatch.chdir(checkouts.repository_root)
    before_r = snapshotter.take()
    before_p = _take_p_oracle(checkouts.owned_root)

    exit_code, output = _invoke_finalize(checkouts.mission_slug, "--owned-checkout", str(checkouts.owned_root))

    assert exit_code == 0, output
    assert "LANE_DEPENDENCY_CYCLE" not in output, output
    assert "Ownership validation failed" not in output, "fixture leaked an ownership overlap"
    manifest = read_lanes_json(mission_dir)
    assert manifest is not None
    assert [lane.lane_id for lane in manifest.lanes] == [PLANNING_LANE_ID]
    assert _take_p_oracle(checkouts.owned_root) != before_p, "finalize must land in P"

    after_r = snapshotter.take()
    snapshotter.assert_unchanged(before_r, after_r, tolerate_status_mutex_for=checkouts.mission_slug)


def test_stale_canceled_dependency_refusal_inside_owned_checkout_leaves_p_and_r_unchanged(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """US4-AS3 (owned), the STALE-CANCELED row: a real post-write refusal.

    WP01 is recorded ``lane: canceled`` in its own frontmatter; WP02 (not
    canceled) still depends on it. ``_raise_stale_canceled_dependencies_if_
    any`` refuses with ``STALE_CANCELED_DEPENDENCIES`` AFTER the same R-07
    writes (frontmatter flush, ``tasks.md`` regeneration) as the other rows.
    """
    checkouts = make_owned_checkouts(placement="under_worktrees", wp_ids=("WP01", "WP02"))
    mission_dir = checkouts.mission_dir
    (mission_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nDepends on WP01.\n",
        encoding="utf-8",
    )
    (mission_dir / "tasks" / "WP01-owned.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Canceled fixture task\ndependencies: []\n"
        "requirement_refs: [FR-001]\nsubtasks: []\nowned_files: [src/a.py]\n"
        "authoritative_surface: src/a.py\nexecution_mode: code_change\nlane: canceled\n"
        "create_intent:\n  - src/a.py\n---\n\n# Task\n",
        encoding="utf-8",
    )
    (mission_dir / "tasks" / "WP02-owned.md").write_text(
        "---\nwork_package_id: WP02\ntitle: Dependent fixture task\n"
        "dependencies:\n  - WP01\n"
        "requirement_refs: [FR-001]\nsubtasks: []\nowned_files: [src/b.py]\n"
        "authoritative_surface: src/b.py\nexecution_mode: code_change\n"
        "create_intent:\n  - src/b.py\n---\n\n# Task\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "tasks.md", "tasks"], cwd=mission_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture: WP02 depends on canceled WP01"], cwd=mission_dir, check=True)

    snapshotter = make_r_snapshot(checkouts)
    monkeypatch.chdir(checkouts.repository_root)
    before_r = snapshotter.take()
    before_p = _take_p_oracle(checkouts.owned_root)

    exit_code, output = _invoke_finalize(checkouts.mission_slug, "--owned-checkout", str(checkouts.owned_root))

    assert exit_code != 0, output
    assert "STALE_CANCELED_DEPENDENCIES" in output, output

    after_r = snapshotter.take()
    snapshotter.assert_unchanged(before_r, after_r, tolerate_status_mutex_for=checkouts.mission_slug)
    after_p = _take_p_oracle(checkouts.owned_root)
    _assert_p_unchanged(before_p, after_p, "the stale-canceled refusal")


def test_planning_pin_orphan_refusal_inside_owned_checkout_leaves_p_and_r_unchanged(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """US4-AS3 (owned), the PLANNING-PIN row: a real post-write refusal.

    A first, REAL (unpatched) owned finalize captures ``planning_commit_
    sha``. P's target branch is then rebased onto a diverged base (an
    ACTUAL ``git rebase``, mirroring ``test_issue_4827_repin_orphaned_
    planning_commit.py``'s harness) -- orphaning the recorded SHA: present
    in the repo, no longer an ancestor of the tip. A WP is claimed (execution
    has begun). A second, plain (no ``--refresh-planning-commit``) finalize
    must then refuse -- ``lanes.json`` (and everything else re-finalize would
    touch) staying byte-identical to the post-run-1 state, and R untouched.
    """
    checkouts = make_owned_checkouts(placement="under_worktrees", wp_ids=("WP01",))
    mission_dir = checkouts.mission_dir
    _write_finalizable_tasks_md(checkouts)

    snapshotter = make_r_snapshot(checkouts)
    monkeypatch.chdir(checkouts.repository_root)

    # Run 1: a real, successful owned finalize -- captures planning_commit_sha.
    exit_code, output = _invoke_finalize(checkouts.mission_slug, "--owned-checkout", str(checkouts.owned_root))
    assert exit_code == 0, output
    from specify_cli.lanes.persistence import read_lanes_json

    established = read_lanes_json(mission_dir)
    assert established is not None
    orphaned_sha = established.planning_commit_sha
    assert orphaned_sha is not None

    # Orphan it: rebase P's target branch onto an unrelated diverged base.
    target_branch = checkouts.target_branch
    subprocess.run(["git", "checkout", "-q", "--orphan", "_upstream_base"], cwd=checkouts.owned_root, check=True)
    subprocess.run(["git", "rm", "-rf", "-q", "."], cwd=checkouts.owned_root, check=True)
    (checkouts.owned_root / "UPSTREAM_ADVANCE.txt").write_text("upstream advanced independently\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=checkouts.owned_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "upstream advanced independently"], cwd=checkouts.owned_root, check=True)
    subprocess.run(["git", "checkout", "-q", target_branch], cwd=checkouts.owned_root, check=True)
    subprocess.run(["git", "rebase", "-q", "--onto", "_upstream_base", "--root", target_branch], cwd=checkouts.owned_root, check=True)
    is_ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", orphaned_sha, target_branch], cwd=checkouts.owned_root, capture_output=True, check=False)
    assert is_ancestor.returncode != 0, "sanity: the rebase must orphan the recorded SHA"
    object_present = subprocess.run(["git", "cat-file", "-e", f"{orphaned_sha}^{{commit}}"], cwd=checkouts.owned_root, capture_output=True, check=False)
    assert object_present.returncode == 0, "sanity: the orphaned commit object must still remain present"

    # Execution has begun: claim WP01 in P's own canonical event log.
    from specify_cli.status.emit import emit_status_transition

    emit_status_transition(
        feature_dir=mission_dir,
        mission_slug=checkouts.mission_slug,
        wp_id="WP01",
        to_lane="claimed",
        actor="test-fixture",
    )

    # A NEW planned WP so run 2's real bootstrap has something to seed BEFORE
    # the pin refusal fires (otherwise every gate before the refusal is a
    # no-op on a re-finalize and the row passes with the guards disabled):
    # seeding WP03 appends to status.events.jsonl, materializes the derived
    # cache and, in an owned checkout, commits a status transition to P.
    with (mission_dir / "tasks.md").open("a", encoding="utf-8") as tasks_md:
        tasks_md.write("\n## WP03\n\n**Dependencies**: None\n")
    (mission_dir / "tasks" / "WP03-owned.md").write_text(
        "---\nwork_package_id: WP03\ntitle: Owned fixture task\ndependencies: []\n"
        "requirement_refs: [FR-001]\nsubtasks: []\nowned_files: [wp03.py]\n"
        "authoritative_surface: wp03.py\nexecution_mode: code_change\n"
        "create_intent:\n  - wp03.py\n---\n\n# Task\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "tasks.md", "tasks"], cwd=mission_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture: a new planned WP03"], cwd=mission_dir, check=True)

    before_r = snapshotter.take()
    before_p_lanes = (mission_dir / "lanes.json").read_bytes()
    before_p = _take_p_oracle(checkouts.owned_root)

    # Run 2: a plain re-finalize (no --refresh-planning-commit / --allow-orphaned).
    exit_code, output = _invoke_finalize(checkouts.mission_slug, "--owned-checkout", str(checkouts.owned_root))

    assert exit_code != 0, output
    assert "--refresh-planning-commit" in output and "--allow-orphaned" in output, output

    after_r = snapshotter.take()
    snapshotter.assert_unchanged(before_r, after_r, tolerate_status_mutex_for=checkouts.mission_slug)
    after_p = _take_p_oracle(checkouts.owned_root)
    _assert_p_unchanged(before_p, after_p, "the planning-pin refusal")
    assert (mission_dir / "lanes.json").read_bytes() == before_p_lanes, "lanes.json changed despite the planning-pin refusal"


def test_stale_repository_root_copy_field_names_r_copy(
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-007/R-12: the additive ``stale_repository_root_copy`` field names R's copy.

    With ``stale_root_copy`` active, every owned finalize payload -- here,
    the validate-only report -- carries a top-level ``stale_repository_root_
    copy`` naming R's stale copy directory and the shared ``mission_id``.
    """
    _write_finalizable_tasks_md(owned_checkouts)
    r_copy_dir = stale_root_copy()
    monkeypatch.chdir(owned_checkouts.repository_root)

    exit_code, output = _invoke_finalize(owned_checkouts.mission_slug, "--owned-checkout", str(owned_checkouts.owned_root), "--validate-only")

    assert exit_code == 0, output
    payload = json.loads(output)
    assert payload["stale_repository_root_copy"] is not None
    assert Path(payload["stale_repository_root_copy"]["path"]) == r_copy_dir
    assert payload["stale_repository_root_copy"]["mission_id"] == owned_checkouts.mission_id


def test_stale_repository_root_copy_field_absent_without_owned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The additive key is absent (not merely ``null``) on a non-owned payload.

    An ordinary (non-owned, non-worktree) mission in a fresh repo -- the
    same shape as ``test_transition_request_owned.py``'s zero-validation
    control -- must never carry the key at all.
    """
    from tests.status.test_transition_request_owned import _init_git_repo

    repo = tmp_path / "plain-repo"
    _init_git_repo(repo)
    subprocess.run(["git", "checkout", "-qb", "codex/control"], cwd=repo, check=True)
    slug = "control-01M2D998"
    mission_dir = repo / "kitty-specs" / slug
    (mission_dir / "tasks").mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M2D998000000000000000001",
                "mission_slug": slug,
                "slug": slug,
                "mission_type": "software-dev",
                "topology": "single_branch",
                "target_branch": "codex/control",
                "flattened": False,
            }
        ),
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text(
        "# Spec\n\n## Functional Requirements\n| ID | Requirement | Acceptance Criteria | Status |\n"
        "|---|---|---|---|\n| FR-001 | Control | Correct path | proposed |\n",
        encoding="utf-8",
    )
    (mission_dir / "plan.md").write_text("# Plan\n\nControl.\n", encoding="utf-8")
    (mission_dir / "tasks.md").write_text("# Tasks\n\n## WP01\n\n**Dependencies**: None\n", encoding="utf-8")
    (mission_dir / "tasks" / "WP01-control.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Control task\ndependencies: []\n"
        "requirement_refs: [FR-001]\nsubtasks: []\nowned_files: [control.py]\n"
        "authoritative_surface: control.py\nexecution_mode: code_change\n"
        "create_intent:\n  - control.py\n---\n\n# Task\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "control mission"], cwd=repo, check=True)

    monkeypatch.chdir(repo)
    exit_code, output = _invoke_finalize(slug)

    assert exit_code == 0, output
    payload = json.loads(output)
    assert "stale_repository_root_copy" not in payload


def test_target_branch_override_mismatch_is_refused(
    owned_checkouts: OwnedCheckouts,
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T074: ``--target-branch`` with an owned checkout still refuses a mismatch.

    ``resolve_owned_or_adopt``'s explicit path forwards ``target_override``
    straight through to ``resolve_owned_mission``
    (``owned_mission.py``'s own target-override check), which refuses a
    ``--target-branch`` that does not match P's OWN recorded ``target_
    branch`` with ``OWNED_BRANCH_REFUSED`` -- this must survive the G2
    conversion off the direct ``resolve_owned_mission`` call.
    """
    _write_finalizable_tasks_md(owned_checkouts)
    snapshotter = make_r_snapshot(owned_checkouts)
    monkeypatch.chdir(owned_checkouts.repository_root)
    before = snapshotter.take()

    exit_code, output = _invoke_finalize(
        owned_checkouts.mission_slug,
        "--owned-checkout",
        str(owned_checkouts.owned_root),
        "--target-branch",
        "codex/not-the-recorded-branch",
    )

    assert exit_code != 0, output
    assert "OWNED_BRANCH_REFUSED" in output, output
    after = snapshotter.take()
    snapshotter.assert_unchanged(before, after)


def test_post_commit_failure_with_foreign_meta_field_keeps_p_head_at_the_landed_commit(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HIGH (review cycle 1), owned: a post-commit failure must not reset P's HEAD.

    A foreign uncommitted ``vcs`` field excludes meta.json from the finalize
    commit (``meta_commit_progress.committed`` stays False) although the commit
    landed; the guards used to key off that flag and ``git reset`` P to its
    pre-run sha, orphaning the finalize commit.
    """
    from unittest.mock import patch

    checkouts = make_owned_checkouts(placement="under_worktrees")
    _write_finalizable_tasks_md(checkouts)
    meta_path = checkouts.mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["vcs"] = "git"
    meta["vcs_locked_at"] = "2026-09-01T00:00:00+00:00"
    meta_path.write_text(json.dumps(meta) + "\n", encoding="utf-8")
    monkeypatch.chdir(checkouts.repository_root)
    head_before = _take_p_oracle(checkouts.owned_root).head
    head_when_report_runs: list[str] = []

    def _fail_after_commit(*_args: object, **_kwargs: object) -> None:
        head_when_report_runs.append(_take_p_oracle(checkouts.owned_root).head)
        raise RuntimeError("simulated post-commit failure")

    with patch("specify_cli.cli.commands.agent.mission_finalize._emit_success_report", side_effect=_fail_after_commit):
        exit_code, output = _invoke_finalize(checkouts.mission_slug, "--owned-checkout", str(checkouts.owned_root))

    assert exit_code != 0, output
    head_after = _take_p_oracle(checkouts.owned_root).head
    assert head_when_report_runs and head_when_report_runs[0] != head_before, "the finalize commit had not landed when the report ran"
    assert head_after == head_when_report_runs[0], "the guard reset P's HEAD, orphaning the already-landed finalize commit"
    assert (checkouts.mission_dir / "lanes.json").is_file(), "the guard deleted an artifact of the already-durable finalize commit"


def test_issue_matrix_scaffold_refusal_inside_owned_checkout_leaves_p_and_r_unchanged(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HIGH (review cycle 1), owned: the issue-matrix scaffold must not commit before the gates.

    ``spec.md`` cites ``#4242``; the ownership-overlap refusal then fires. The
    scaffold used to land its own commit on P first, which the refusal left
    stranded.
    """
    checkouts = make_owned_checkouts(placement="under_worktrees", wp_ids=("WP01", "WP02"))
    _write_overlapping_wps(checkouts, spec_suffix="\nTracks #4242.\n")
    snapshotter = make_r_snapshot(checkouts)
    monkeypatch.chdir(checkouts.repository_root)
    before_r = snapshotter.take()
    before_p = _take_p_oracle(checkouts.owned_root)

    exit_code, output = _invoke_finalize(checkouts.mission_slug, "--owned-checkout", str(checkouts.owned_root))

    assert exit_code != 0, output
    assert "Ownership validation failed" in output, output
    snapshotter.assert_unchanged(before_r, snapshotter.take())
    after_p = _take_p_oracle(checkouts.owned_root)
    _assert_p_unchanged(before_p, after_p, "the issue-matrix scaffold refusal")


def test_commit_failure_mid_finalize_inside_owned_checkout_leaves_p_and_r_unchanged(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T070 owned inject-before-commit row: a commit-step failure strands nothing in P or R.

    The single git-commit boundary, ``commit_for_mission``, raises after every
    earlier finalize write (frontmatter, tasks.md, bootstrap status commits on
    P, derived cache, lanes.json, the matrix scaffolds) has landed -- the
    latest, most realistic injection point.
    """
    from unittest.mock import patch

    checkouts = make_owned_checkouts(placement="under_worktrees")
    _write_finalizable_tasks_md(checkouts)
    snapshotter = make_r_snapshot(checkouts)
    monkeypatch.chdir(checkouts.repository_root)
    before_r = snapshotter.take()
    before_p = _take_p_oracle(checkouts.owned_root)

    with patch("specify_cli.coordination.commit_router.commit_for_mission", side_effect=RuntimeError("simulated commit failure (T070)")):
        exit_code, output = _invoke_finalize(checkouts.mission_slug, "--owned-checkout", str(checkouts.owned_root))

    assert exit_code != 0, output
    snapshotter.assert_unchanged(before_r, snapshotter.take(), tolerate_status_mutex_for=checkouts.mission_slug)
    _assert_p_unchanged(before_p, _take_p_oracle(checkouts.owned_root), "the injected commit failure")


def _last_json_object(output: str) -> dict[str, object]:
    """The final JSON object printed to stdout (a refusal may be preceded by progress lines)."""
    lines = [line for line in output.splitlines() if line.strip().startswith("{")]
    assert lines, output
    parsed: dict[str, object] = json.loads(lines[-1])
    return parsed


def test_stale_repository_root_copy_field_present_on_owned_success_payload(
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-007: a REAL (non-validate-only) owned finalize success payload names R's stale copy."""
    _write_finalizable_tasks_md(owned_checkouts)
    r_copy_dir = stale_root_copy()
    monkeypatch.chdir(owned_checkouts.repository_root)

    exit_code, output = _invoke_finalize(owned_checkouts.mission_slug, "--owned-checkout", str(owned_checkouts.owned_root))

    assert exit_code == 0, output
    payload = _last_json_object(output)
    assert payload["result"] == "success"
    stale = payload["stale_repository_root_copy"]
    assert isinstance(stale, dict)
    assert Path(str(stale["path"])) == r_copy_dir
    assert stale["mission_id"] == owned_checkouts.mission_id


def test_stale_repository_root_copy_field_present_on_owned_refusal_payload(
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-007: an owned finalize REFUSAL envelope carries the same additive key (with the error)."""
    _write_overlapping_wps(owned_checkouts)
    r_copy_dir = stale_root_copy()
    monkeypatch.chdir(owned_checkouts.repository_root)

    exit_code, output = _invoke_finalize(owned_checkouts.mission_slug, "--owned-checkout", str(owned_checkouts.owned_root))

    assert exit_code != 0, output
    payload = _last_json_object(output)
    assert "Ownership validation failed" in str(payload["error"])
    stale = payload["stale_repository_root_copy"]
    assert isinstance(stale, dict)
    assert Path(str(stale["path"])) == r_copy_dir


def test_owned_refusal_is_routed_through_emit_owned_refusal(
    owned_checkouts: OwnedCheckouts,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T074 step 2: a refused ``--owned-checkout`` claim renders via ``emit_owned_refusal``.

    Naming the repository root as the owned checkout is refused with the typed
    ``OWNED_CHECKOUT_IS_REPOSITORY_ROOT`` code. ``emit_owned_refusal`` validates
    the code against the registry and prints ``Error: [<code>] <message>`` in
    human mode and an envelope that keeps the finalize keys (``error`` plus
    ``error_code``) in JSON mode.
    """
    from specify_cli.workspace.context import clear_workspace_resolution_caches

    monkeypatch.chdir(owned_checkouts.repository_root)
    clear_workspace_resolution_caches()
    args = ["finalize-tasks", "--mission", owned_checkouts.mission_slug, "--owned-checkout", str(owned_checkouts.repository_root)]

    human = runner.invoke(mission_app, args, catch_exceptions=False)
    assert human.exit_code == 1, human.output
    assert "[OWNED_CHECKOUT_IS_REPOSITORY_ROOT]" in human.output, human.output

    clear_workspace_resolution_caches()
    machine = runner.invoke(mission_app, [*args, "--json"], catch_exceptions=False)
    assert machine.exit_code == 1, machine.output
    envelope = json.loads(machine.stdout)
    assert envelope["error_code"] == "OWNED_CHECKOUT_IS_REPOSITORY_ROOT"
    assert envelope["error"]
    # Finalize's other JSON payloads carry the CLI version; the refusal must too.
    from specify_cli import __version__

    assert envelope["spec_kitty_version"] == __version__


def test_owned_envelope_key_does_not_leak_into_a_later_non_owned_payload(
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stale-copy envelope key is scoped to the owned invocation that bound it.

    After an owned ``--validate-only`` finalize returns (through CliRunner, in
    the same process/context), a non-owned gate emitting through the same
    module-level ``_emit_json`` must not inherit ``stale_repository_root_copy``.
    """
    import typer

    from specify_cli.cli.commands.agent import mission as mission_module
    from specify_cli.cli.commands.agent import mission_finalize as finalize_module

    _write_finalizable_tasks_md(owned_checkouts)
    stale_root_copy()
    monkeypatch.chdir(owned_checkouts.repository_root)
    exit_code, output = _invoke_finalize(owned_checkouts.mission_slug, "--owned-checkout", str(owned_checkouts.owned_root), "--validate-only")
    assert exit_code == 0, output
    assert "stale_repository_root_copy" in output, "sanity: the owned run must have carried the key"

    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(mission_module, "_emit_json", emitted.append)
    with pytest.raises(typer.Exit):
        finalize_module._validate_dependency_graph({"WP01": ["WP02"], "WP02": ["WP01"]}, json_output=True)

    assert emitted, "the cyclic graph must have been reported"
    assert "stale_repository_root_copy" not in emitted[0], emitted[0]


def _arm_get_main_repo_root(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[list[str]], Callable[[], None]]:
    """Armed ``get_main_repo_root`` pin scoped to lifecycle-event LOG writes: ``(hits, passed_through, arm)``.

    WP09's pattern: every module alias of ``specify_cli.core.paths.
    get_main_repo_root`` is patched. Until ``arm()`` is called (right after the
    owned fact is minted -- the minter legitimately reads the main root) the
    original runs. Afterwards a call made from ``_repo_root_for_lifecycle_log``
    (the walk ``persist_lifecycle_event_local`` takes when no ``repo_root`` is
    passed -- WPCreated, MissionCreated, TasksStarted, TasksCompleted,
    SpecifyStarted, every lifecycle-event WRITE) is both RECORDED (with its
    frames -- the emitters swallow exceptions, so raising alone is vacuous)
    and raised. Every OTHER post-mint reader of the main root passes through to
    the original and its full frame chain is collected in ``passed_through`` so
    the caller can assert each one is an allowed resolver read (never a write).
    """
    import sys
    import traceback

    import specify_cli.core.paths as paths_module

    original = paths_module.get_main_repo_root
    state = {"armed": False}
    hits: list[str] = []
    passed_through: list[list[str]] = []

    def _guarded(*args: object, **kwargs: object) -> object:
        if state["armed"]:
            frames = [frame.name for frame in traceback.extract_stack()[:-1]]
            if "_repo_root_for_lifecycle_log" in frames:
                hits.append(" > ".join(frames[-8:]))
                raise AssertionError("owned arm resolved a lifecycle-log root via get_main_repo_root after the fact was minted")
            passed_through.append(frames)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    for module in list(sys.modules.values()):
        if getattr(module, "get_main_repo_root", None) is original:
            monkeypatch.setattr(module, "get_main_repo_root", _guarded)

    def _arm() -> None:
        state["armed"] = True

    return hits, passed_through, _arm


# Resolver frames that may still call ``get_main_repo_root`` after the owned fact
# is minted, in order of attribution (a pass-through read is attributed to the
# OUTERMOST of these frames on its stack). Each is a coordination/topology or
# placement resolver whose repository-root read is by design (the coordination
# branch and its topology record live at R), or the drain-posture read.
_RESOLVER_ENTRY_FRAMES = (
    "ledger_posture",
    "coord_read_dir_for",
    "_resolve_group_placement",
    "candidate_feature_dir_for_mission",
    "mission_has_coordination_branch",
    "_resolve_coordination_branch",
    "resolve_topology",
    "_resolve_topology",
)

# EXACT ledger of post-mint pass-through reads on an owned finalize (22 in
# total; 20 before the 2026-10-04 re-pin below, 37 before WP18, 68 before review cycles 3-4). Keyed on (outermost resolver entry frame,
# immediate caller of ``get_main_repo_root``) so a new read nested under an
# allowed entry frame -- a different leaf -- is a new key and fails. The pin
# asserts EQUALITY: every legitimate shrink must lower this table in the same
# commit, so no headroom exists for a new read to hide in. Any read under
# ``_declared_dependencies`` (WP dependency CONTENT read from R -- review
# cycle 3 MEDIUM-2, fixed in status/emit.py) is forbidden outright.
#   mission_has_coordination_branch  the status transaction's topology probe
#                                    (WP18 dropped the ``_resolve_group_placement`` rows:
#                                    ``finalize-tasks`` now hands ``commit_for_mission`` the
#                                    fact itself instead of the bare ``owned_root``, so its
#                                    placement no longer folds back to R.)
#                                    2026-10-04 (16 -> 18): ``read_primary_meta``'s raw-miss
#                                    fallback now routes through the shared
#                                    ``_canonicalize_primary_read_handle`` (coord-artifact-
#                                    single-home WP09 review cycle 2, B1-residual fix), adding
#                                    ``_preflight_policy_verdict > mission_has_coordination_branch
#                                    > resolve_topology > candidate_feature_dir_for_mission >
#                                    _stored_topology_best_effort > read_primary_meta >
#                                    _canonicalize_primary_read_handle >
#                                    _canonicalize_bare_modern_handle >
#                                    _compose_primary_feature_dir`` once per status transaction
#                                    (two transactions -> +2). Same entry frame, same leaf: a
#                                    WHERE lookup, not a content read.
#   ledger_posture                   the fan-out drain posture read
_RESOLVER_READ_LEDGER = {
    ("mission_has_coordination_branch", "_compose_primary_feature_dir"): 18,
    ("mission_has_coordination_branch", "resolve_topology"): 2,
    ("ledger_posture", "resolve_canonical_root"): 2,
}


def test_armed_get_main_repo_root_pin_owned_finalize(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Item 6: an end-to-end owned finalize (TasksStarted/TasksCompleted emissions) never re-derives R from the fact's root."""
    from specify_cli.cli.commands.agent import mission_finalize as finalize_module

    checkouts = make_owned_checkouts(placement="under_worktrees")
    _write_finalizable_tasks_md(checkouts)
    monkeypatch.chdir(checkouts.repository_root)
    snapshotter = make_r_snapshot(checkouts)
    before_r = snapshotter.take()
    hits, passed_through, arm = _arm_get_main_repo_root(monkeypatch)
    real_resolve = finalize_module.resolve_owned_or_adopt

    def _arming_resolve(*args: object, **kwargs: object) -> object:
        fact = real_resolve(*args, **kwargs)  # type: ignore[arg-type]
        if fact is not None:
            arm()
        return fact

    monkeypatch.setattr(finalize_module, "resolve_owned_or_adopt", _arming_resolve)

    exit_code, output = _invoke_finalize(checkouts.mission_slug, "--owned-checkout", str(checkouts.owned_root))

    assert exit_code == 0, output
    assert hits == [], "\n".join(hits)
    # What remains reaching ``get_main_repo_root`` after the mint is bounded by an
    # exact ledger of resolver entry frames (see ``_RESOLVER_READ_LEDGER``). These
    # are topology/placement lookups and the drain-posture read: they consult R
    # for WHERE the coordination branch or a directory lives. They are NOT all
    # "only which directory": a resolver read of R that supplied CONTENT (the WP
    # dependencies read by ``_declared_dependencies``) was a real leak and is
    # asserted absent below. That no read WRITES against R is proven by the
    # snapshot assertion after the ledger (R's files, HEAD, index, locks and home
    # are byte-identical after a full successful run).
    from collections import Counter

    assert not any("_declared_dependencies" in frames for frames in passed_through), "WP dependency content is read from R again"
    counts: Counter[tuple[str, str]] = Counter()
    unclassified: list[str] = []
    for frames in passed_through:
        entry = next((name for name in frames if name in _RESOLVER_ENTRY_FRAMES), None)
        if entry is None:
            unclassified.append(" > ".join(frames[-6:]))
        else:
            counts[(entry, frames[-1])] += 1
    assert unclassified == [], "\n".join(unclassified)
    assert dict(counts) == _RESOLVER_READ_LEDGER, (
        f"post-mint get_main_repo_root reads differ from the exact ledger (observed vs allowed): {dict(counts)} != {_RESOLVER_READ_LEDGER}"
    )
    snapshotter.assert_unchanged(before_r, snapshotter.take(), tolerate_status_mutex_for=checkouts.mission_slug)


def test_armed_get_main_repo_root_pin_owned_mission_create(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Item 6: an owned mission create (MissionCreated + SpecifyStarted) never re-derives R from the owned checkout's path.

    Since WP10 the owned create fact is an ``OwnedCreateRoot`` minted by
    ``resolve_owned_create_root`` (which legitimately reads the main root); the
    pin arms right after minting and then runs the create with that fact.
    """
    from mission_runtime import MissionTopology
    from specify_cli.core.mission_creation import create_mission_core
    from specify_cli.core.owned_mission import resolve_owned_create_root
    from tests.core.test_mission_create_checkout_restore import _init_owned_checkout_pair, _mission_summary

    primary, linked = _init_owned_checkout_pair(tmp_path)
    hits, passed_through, arm = _arm_get_main_repo_root(monkeypatch)
    create_root = resolve_owned_create_root(primary, linked)
    arm()

    result = create_mission_core(
        primary,
        "owned-armed-pin",
        allow_worktree_context=True,
        owned_create_root=create_root,
        topology=MissionTopology.SINGLE_BRANCH,
        **_mission_summary("owned-armed-pin"),
    )

    assert result.owned_checkout is not None
    assert hits == [], "\n".join(hits)
    # Nothing else reads the main root after the claim on the owned create path.
    assert passed_through == [], "\n".join(" > ".join(frames[-6:]) for frames in passed_through)


@pytest.mark.parametrize("r_copy", ["absent", "stale_declares_none"])
def test_owned_claim_dependency_gate_reads_p_not_the_repository_root(
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Callable[..., Path],
    r_copy: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review cycle 3 MEDIUM-2: an owned ``planned -> claimed`` reads WP ``dependencies`` from P.

    P's WP02 declares ``dependencies: [WP01]`` while WP01 is not approved, so
    claiming WP02 must be refused on the dependency gate. R either holds no
    copy of the mission (the leak reads that as "no dependencies") or a stale
    copy whose WP02 declares none. Before the fix ``status/emit.py`` re-anchored
    the planning dir through ``resolve_canonical_root`` to R and read R's tasks.
    """
    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent.tasks import app as tasks_app

    _write_finalizable_tasks_md(owned_checkouts)
    monkeypatch.chdir(owned_checkouts.repository_root)
    exit_code, output = _invoke_finalize(owned_checkouts.mission_slug, "--owned-checkout", str(owned_checkouts.owned_root))
    assert exit_code == 0, output

    wp02 = next((owned_checkouts.mission_dir / "tasks").glob("WP02-*.md"))
    wp02.write_text(wp02.read_text(encoding="utf-8").replace("dependencies: []", "dependencies: [WP01]"), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=owned_checkouts.owned_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture: WP02 depends on WP01"], cwd=owned_checkouts.owned_root, check=True)
    if r_copy == "stale_declares_none":
        stale_root_copy()

    result = CliRunner().invoke(
        tasks_app,
        ["move-task", "WP02", "--to", "doing", "--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug],
    )

    assert result.exit_code != 0, f"WP02 was claimed although P declares an unsatisfied dependency on WP01:\n{result.output}"
    assert "unsatisfied dependencies" in result.output, result.output


def test_owned_finalize_hands_the_fact_to_the_issue_matrix_scaffold_and_fails_closed(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review cycle 4 MEDIUM-2: the owned finalize runs the scaffold's OWNED arm.

    ``_scaffold_issue_matrix_if_present`` was called without ``owned``, so an
    owned finalize took the non-owned arm: no ``owned`` fact reached
    ``scaffold_issue_matrix``, and the owned
    fail-closed ``raise`` was dead code -- a scaffold failure only warned.
    """
    import specify_cli.tasks.issue_matrix as issue_matrix_module

    checkouts = make_owned_checkouts(placement="under_worktrees")
    _write_finalizable_tasks_md(checkouts)
    spec_path = checkouts.mission_dir / "spec.md"
    spec_path.write_text(spec_path.read_text(encoding="utf-8") + "\nTracks #4242.\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-q", "-am", "fixture: cite an issue"], cwd=checkouts.owned_root, check=True)
    monkeypatch.chdir(checkouts.repository_root)
    received: list[dict[str, object]] = []

    def _failing_scaffold(*_args: object, **kwargs: object) -> None:
        received.append(dict(kwargs))
        raise RuntimeError("simulated owned scaffold failure")

    monkeypatch.setattr(issue_matrix_module, "scaffold_issue_matrix", _failing_scaffold)

    exit_code, output = _invoke_finalize(checkouts.mission_slug, "--owned-checkout", str(checkouts.owned_root))

    assert received, "the scaffold was never reached"
    handed = received[0].get("owned")
    assert isinstance(handed, OwnedCheckout), received[0]
    assert handed.owned_root == checkouts.owned_root, received[0]
    assert "effective_root" not in received[0], received[0]
    assert exit_code != 0, f"an owned scaffold failure only warned:\n{output}"
    assert "simulated owned scaffold failure" in output, output
