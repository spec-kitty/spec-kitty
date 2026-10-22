"""#2647 — ``move-task`` cwd-independent status surface (WP06, T027-T031).

Reproduces the reported bug: ``agent tasks move-task WP## --to <lane>`` fails
with an "Illegal transition" error when run from a **real lane-worktree cwd**,
even though ``status.events.jsonl`` on the mission's primary checkout
correctly shows the WP already sitting in the FROM lane the transition
expects.

The repro is deliberately real, not mocked: a genuine ``git worktree add``
(so ``is_worktree_context(cwd)`` is tripped by the actual gitdir-pointer
topology, not a fabricated ``.git`` marker) plus a real
``monkeypatch.chdir(worktree)`` before driving the live Typer entry point
(``specify_cli.cli.commands.agent.tasks.app``, ``move-task`` command). No
``tests.mocked_env.setup_mocked_env`` — that helper patches
``locate_project_root`` to unconditionally return the fixture root, which
would erase the exact cwd-dependence this test exists to exercise.

Investigation finding (T027), REVISED after a live reproduction on this
mission's own WP06 lane worktree (see ``../traces/design-decisions.md`` for
the full account) -- the picture is more layered than the WP06 prompt's two
named suspects:

* ``_read_transactional_wp_lane`` (``tasks_move_task.py:308-312``) reads with
  ``repo_root=st.main_repo_root`` -- confirmed NOT the taint.
* ``locate_work_package`` (``task_utils/support.py:309``) internally calls
  ``get_main_repo_root(repo_root)`` again before resolving the WP file --
  confirmed NOT the taint.
* ``resolve_action_context`` (``mission_runtime/resolution.py``) derives every
  fragment from the canonicalized ``primary_root`` -- confirmed CWD-invariant.

Those three reads govern the DECISION half of ``move-task`` (is
``in_progress -> for_review`` a legal edge). The classes below (T028/T030)
pin that this half is genuinely cwd-independent -- GREEN today, and they stay
GREEN.

But ``move-task``'s WRITE half independently RE-DERIVES ``from_lane`` at
commit time, and THAT read is cwd-dependent:
``emit_status_transition_transactional`` ->
``BookkeepingTransaction.acquire`` -> ``_acquire_locked`` (all in
``src/specify_cli/coordination/transaction.py``) classifies any mission
whose ``meta.json`` lacks a ``coordination_branch`` key as "legacy"
(``_is_legacy_mission``, transaction.py:200) -- which is the case for every
modern coordination-less ``single_branch``/``lanes`` mission, not only
genuinely pre-SSOT ones -- and then resolves the write target via
``_resolve_legacy_lane_destination`` (transaction.py:279-330), whose FIRST
line is ``cwd = Path.cwd().resolve()``. That function walks up from the
literal process cwd to find the nearest ``.git`` marker and reads THAT
worktree's own on-disk ``kitty-specs/<slug>/status.events.jsonl`` -- which,
for a lane worktree that was created before later status transitions landed
on the primary/coordination branch, is a genuinely STALE local git-tracked
snapshot. ``BookkeepingTransaction.commit()``'s ``CommitTarget(ref=self.
destination_ref)`` construction at this exact site is ALREADY a tracked,
DEFERRED architectural-debt allow-list entry in
``tests/architectural/test_no_write_side_rederivation.py``
(``_CHECKOUT_GRAMMAR_ALLOW_LIST_SEED``, rationale: "tracked: #2453"), so this
is known, acknowledged debt -- just not previously connected to #2647's
user-visible symptom.

``test_write_side_from_lane_rederivation_no_longer_reproduces_2647`` below was
originally the red-first proof of that write-side taint (``xfail(strict=True)``
against a REAL lane worktree forked BEFORE later status events land on the
primary checkout). The operator expanded WP06's scope to fix #2453 in the same
cycle: ``coordination/transaction.py::_acquire_locked`` now distinguishes
genuinely-legacy missions (no stored topology -- keeps the cwd-derived
routing, there is no other reliable target) from modern coordination-less
missions (stored ``single_branch``/``lanes`` topology, or ``flattened`` --
reusing ``_warrants_legacy_warning``'s classification, C-005) and routes the
latter to ``repo_root`` on the caller-resolved ``target_branch`` instead of
``Path.cwd()``. The test below is now an unmarked GREEN assertion; see
``tests/specify_cli/coordination/test_transaction_legacy_topology_routing.py``
for the characterization-first unit-level coverage of the three routing
shapes.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.core.paths import is_worktree_context
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_MISSION_ID = "01KXCWDFIX7M8N0RAB4CDXYZ90"
_MID8 = _MISSION_ID[:8]
_MISSION_SLUG = f"movetask-cwd-fix-{_MID8}"
_LANE_BRANCH = f"kitty/mission-{_MISSION_SLUG}-{_MID8}-lane-c"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _build_mission(repo_root: Path) -> Path:
    """A real, flat (no-coord) mission with WP01 already ``in_progress``.

    Mirrors the shared ``_simple_mission`` recipe used by the sibling
    ``test_tasks_cli_contract_coord.py`` golden harness -- the codebase's own
    minimal real-on-disk WP fixture.
    """
    (repo_root / ".kittify").mkdir(parents=True, exist_ok=True)
    (repo_root / ".kittify" / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n", encoding="utf-8"
    )

    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "tasks" / "WP01-fixture.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Fixture WP01\n"
        "execution_mode: code_change\n"
        "agent: testbot\n"
        "subtasks: []\n"
        "owned_files:\n  - src/wp01/**\n"
        "authoritative_surface: src/wp01/\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Work Packages\n\n## WP01 - fixture\n- [x] T001 done already\n",
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text(
        "# Spec\n\nFR-001 do a thing.\n", encoding="utf-8"
    )

    # Canonical event-log lane: planned -> claimed -> in_progress. This is the
    # ONLY authority for "old_lane" (frontmatter `lane` is retired) -- the
    # transition core reads this, not anything derived from the worktree cwd.
    for ordinal, (from_lane, to_lane) in enumerate(
        (("planned", "claimed"), ("claimed", "in_progress")), start=1
    ):
        seed_status_event(
            feature_dir,
            StatusEvent(
                event_id=f"{_MID8}FC00000000000000{ordinal:04d}",
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                from_lane=Lane(from_lane),
                to_lane=Lane(to_lane),
                at=f"2026-01-01T00:00:{ordinal:02d}+00:00",
                actor="test",
                force=True,
                execution_mode="worktree",
            ),
        )

    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "fixture: movetask-cwd mission bootstrap")
    return feature_dir


def _build_repo_with_worktree(root: Path) -> tuple[Path, Path]:
    """Real git repo (main checkout) + a REAL linked lane worktree under ``root``.

    Returns ``(repo_root, worktree_path)``. The worktree is a genuine
    ``git worktree add`` result -- ``.git`` is a real gitdir-pointer file, so
    ``is_worktree_context(cwd)`` is tripped through its actual detection
    logic, not a fabricated marker (WP06 discipline: a mocked cwd would make
    the RED hollow).
    """
    repo_root = root / "repo"
    repo_root.mkdir(parents=True)
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "t@example.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "config", "commit.gpgsign", "false")
    _build_mission(repo_root)

    worktree_path = repo_root / ".worktrees" / f"{_MISSION_SLUG}-lane-c"
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo_root, "worktree", "add", "-b", _LANE_BRANCH, str(worktree_path), "main")
    assert (worktree_path / ".git").is_file(), (
        "git worktree add must produce a real gitdir-pointer file"
    )

    return repo_root, worktree_path


@pytest.fixture()
def mission_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Single real repo + lane-worktree pair (see :func:`_build_repo_with_worktree`)."""
    return _build_repo_with_worktree(tmp_path)


def _invoke_move_task() -> Result:
    """Drive the live ``move-task`` Typer command against ``Path.cwd()``.

    The caller controls the process cwd via ``monkeypatch.chdir`` before
    calling this -- the whole point of the repro is that the command's
    resolvers, not this helper, decide whether cwd matters.
    """
    return runner.invoke(
        app,
        [
            "move-task",
            "WP01",
            "--to",
            "for_review",
            "--mission",
            _MISSION_SLUG,
            "--no-auto-commit",
            "--force",
            "--skip-pre-review-gate",
            "--json",
        ],
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# T028/T030: worktree-cwd invocation succeeds and matches the repo-root result
# (FR-001 no-regression, SC-001).
# ---------------------------------------------------------------------------


def test_move_task_succeeds_from_lane_worktree_cwd(
    mission_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Driving move-task from a REAL lane-worktree cwd must not fail with
    "Illegal transition" -- the status surface must resolve from the
    canonical mission root regardless of where the operator's shell sits.
    """
    repo_root, worktree_path = mission_repo
    monkeypatch.chdir(worktree_path)
    # is_worktree_context(Path.cwd()) must genuinely be True for this repro
    # to mean anything -- assert the precondition before driving the command.
    assert is_worktree_context(Path.cwd()) is True

    result = _invoke_move_task()

    assert "Illegal transition" not in (result.output or ""), (
        "move-task from a lane-worktree cwd regressed to the #2647 "
        f"'Illegal transition' failure:\n{result.output}"
    )
    assert result.exit_code == 0, result.output


def test_move_task_repo_root_cwd_no_regression(
    mission_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The repo-root invocation (the historically-working arm) stays green."""
    repo_root, _worktree_path = mission_repo
    monkeypatch.chdir(repo_root)
    result = _invoke_move_task()

    assert "Illegal transition" not in (result.output or "")
    assert result.exit_code == 0, result.output


def test_worktree_cwd_and_repo_root_cwd_produce_the_identical_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both cwd contexts must resolve WP01's ``in_progress`` from-lane and
    land the SAME successful ``for_review`` transition (SC-001).

    Two INDEPENDENT repo/worktree pairs are built (rather than reusing one
    mission for both invocations) so a real transition happens in each arm --
    the second call must not merely observe an already-moved WP from the
    first.
    """
    repo_root_a, worktree_path_a = _build_repo_with_worktree(tmp_path / "a")
    monkeypatch.chdir(worktree_path_a)
    from_worktree = _invoke_move_task()
    assert from_worktree.exit_code == 0, from_worktree.output
    assert "Illegal transition" not in (from_worktree.output or "")
    # ``.output`` interleaves stderr warnings (e.g. the offline-sync queue
    # notice) ahead of the ``--json`` payload; ``.stdout`` is the clean stream
    # the ``--json`` contract actually promises.
    worktree_payload = json.loads(from_worktree.stdout)

    repo_root_b, _worktree_path_b = _build_repo_with_worktree(tmp_path / "b")
    monkeypatch.chdir(repo_root_b)
    from_repo_root = _invoke_move_task()
    assert from_repo_root.exit_code == 0, from_repo_root.output
    assert "Illegal transition" not in (from_repo_root.output or "")
    repo_root_payload = json.loads(from_repo_root.stdout)

    for payload, label in (
        (worktree_payload, "worktree-cwd"),
        (repo_root_payload, "repo-root-cwd"),
    ):
        assert payload.get("result") == "success", f"{label}: {payload}"
        assert payload.get("task_id") == "WP01", f"{label}: {payload}"
        assert payload.get("new_lane") == "for_review", f"{label}: {payload}"

    # Same semantic transition on both arms (SC-001): only identity metadata
    # (event_id/path/timestamps) may legitimately differ, not the from/to
    # lane shape.
    assert worktree_payload.get("old_lane") == repo_root_payload.get("old_lane")
    assert worktree_payload.get("new_lane") == repo_root_payload.get("new_lane")


# ---------------------------------------------------------------------------
# Live-reproduction finding: the WRITE-side ``from_lane`` re-derivation in
# ``coordination/transaction.py`` (tracked #2453) is the genuine #2647 taint
# for coordination-less (``single_branch``/``lanes``) modern missions -- a
# DIFFERENT mechanism than the read-side classes above, which stay green.
# xfail(strict=True): fixing this lives in ``coordination/transaction.py``,
# out of WP06's scope (see module docstring + design-decisions.md).
# ---------------------------------------------------------------------------

_LEGACY_MISSION_ID = "01KXCWDF3TRANSACTWRITELEG0"
_LEGACY_MID8 = _LEGACY_MISSION_ID[:8]
_LEGACY_MISSION_SLUG = f"movetask-legacy-write-{_LEGACY_MID8}"
_LEGACY_LANE_BRANCH = f"kitty/mission-{_LEGACY_MISSION_SLUG}-{_LEGACY_MID8}-lane-c"
# The mission's own dedicated branch (#2453 fix realism): ``create_mission_core``
# never mints a NEW branch for coordination-less topologies -- ``target_branch``
# is whatever branch was checked out at the primary checkout when the mission
# was created (``planning_branch = target_branch if target_branch else
# current_branch``, ``core/mission_creation.py``), and the primary checkout is
# expected to stay on it for the coordination-less mission's whole lifetime
# (there is no coordination worktree to carry that invariant instead -- see
# CLAUDE.md's "coord/primary partition": SINGLE_BRANCH/LANES route everything
# to primary). Using literally "main" here would be a degenerate edge case
# (a mission created directly off main) that collides with the protected-
# branch guard for an unrelated reason -- not what this fixture exists to pin.
_LEGACY_TARGET_BRANCH = f"mission/{_LEGACY_MISSION_SLUG}"


def _build_stale_worktree_mission(root: Path) -> tuple[Path, Path]:
    """A real, *coordination-less* single_branch mission whose lane worktree
    forks BEFORE later status transitions land on the primary checkout.

    This mirrors production shape exactly (unlike ``_build_mission`` above,
    which omits ``meta.json`` entirely and so never exercises
    ``BookkeepingTransaction``'s "legacy" branch at all):

    * ``meta.json`` carries a real ``mission_id`` and ``topology:
      single_branch`` but -- correctly, by design, per #2218 -- NO
      ``coordination_branch``. ``_is_legacy_mission`` (transaction.py:200)
      classifies this as "legacy" purely on that absence.
    * WP01 starts ``planned`` at the fork point, then advances to
      ``claimed`` -> ``in_progress`` ONLY on the primary checkout, AFTER the
      lane worktree already exists -- so the worktree's own git-tracked
      ``kitty-specs/<slug>/status.events.jsonl`` snapshot is genuinely stale
      relative to the primary's.
    """
    repo_root = root / "repo"
    repo_root.mkdir(parents=True)
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "t@example.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "config", "commit.gpgsign", "false")
    (repo_root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-q", "-m", "seed")
    # Checkout the mission's own branch -- the primary checkout stays on it
    # for the rest of the fixture (see _LEGACY_TARGET_BRANCH's docstring).
    _git(repo_root, "checkout", "-q", "-b", _LEGACY_TARGET_BRANCH)

    (repo_root / ".kittify").mkdir(parents=True, exist_ok=True)
    (repo_root / ".kittify" / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n", encoding="utf-8"
    )

    feature_dir = repo_root / "kitty-specs" / _LEGACY_MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _LEGACY_MISSION_ID,
                "mission_slug": _LEGACY_MISSION_SLUG,
                "mission_type": "research",  # sidesteps the software-dev
                # worktree-currency guard (_validate_worktree_state) so the
                # repro isolates the write-side "Illegal transition" failure
                # rather than an unrelated readiness-gate refusal.
                "target_branch": _LEGACY_TARGET_BRANCH,
                "topology": "single_branch",
                "friendly_name": "movetask legacy-write repro",
            }
        ),
        encoding="utf-8",
    )
    (feature_dir / "tasks" / "WP01-fixture.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Fixture WP01\n"
        "execution_mode: code_change\n"
        "agent: testbot\n"
        "subtasks: []\n"
        "owned_files:\n  - src/wp01/**\n"
        "authoritative_surface: src/wp01/\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Work Packages\n\n## WP01 - fixture\n- [x] T001 done already\n",
        encoding="utf-8",
    )
    (feature_dir / "research.md").write_text("# Research\n", encoding="utf-8")

    # Fork point: WP01 at "planned" only -- this is the snapshot the lane
    # worktree will carry forward, frozen, once created below.
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"{_LEGACY_MID8}FC000000000000001",
            mission_slug=_LEGACY_MISSION_SLUG,
            wp_id="WP01",
            from_lane=Lane.GENESIS,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "fixture: fork point, WP01 planned")

    worktree_path = repo_root / ".worktrees" / f"{_LEGACY_MISSION_SLUG}-lane-c"
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    _git(
        repo_root,
        "worktree",
        "add",
        "-b",
        _LEGACY_LANE_BRANCH,
        str(worktree_path),
        _LEGACY_TARGET_BRANCH,
    )
    assert (worktree_path / ".git").is_file()

    # Advance the PRIMARY checkout past the fork point: planned -> claimed ->
    # in_progress. The lane worktree created above does NOT see these -- its
    # own tracked kitty-specs/ copy stays frozen at the fork-point commit.
    for ordinal, (from_lane, to_lane) in enumerate(
        (("planned", "claimed"), ("claimed", "in_progress")), start=2
    ):
        seed_status_event(
            feature_dir,
            StatusEvent(
                event_id=f"{_LEGACY_MID8}FC00000000000000{ordinal:02d}",
                mission_slug=_LEGACY_MISSION_SLUG,
                wp_id="WP01",
                from_lane=Lane(from_lane),
                to_lane=Lane(to_lane),
                at=f"2026-01-01T01:00:{ordinal:02d}+00:00",
                actor="test",
                force=True,
                execution_mode="worktree",
            ),
        )
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "fixture: advance to in_progress on primary")

    return repo_root, worktree_path


def _invoke_move_task_for_stale_worktree_mission() -> Result:
    return runner.invoke(
        app,
        [
            "move-task",
            "WP01",
            "--to",
            "for_review",
            "--mission",
            _LEGACY_MISSION_SLUG,
            "--no-auto-commit",
            "--skip-pre-review-gate",
            "--json",
        ],
        catch_exceptions=False,
    )


def test_write_side_from_lane_rederivation_no_longer_reproduces_2647(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GREEN (#2453 fixed): the write-side re-derivation taint is closed.

    Was ``xfail(strict=True)`` -- the WP06 cycle-1 characterization pinned
    this as a genuine RED reproduction of #2647 via
    ``coordination/transaction.py``'s write-side ``from_lane`` re-derivation
    (``_is_legacy_mission`` misclassified every modern coordination-less
    ``single_branch``/``lanes`` mission as "legacy" and routed the commit
    through ``_resolve_legacy_lane_destination``'s ``Path.cwd()`` read). The
    #2453 fix (``_acquire_locked``, reusing ``_warrants_legacy_warning``'s
    stored-topology classification) routes a modern coordination-less
    mission's status commit to ``repo_root`` on the caller-resolved
    ``target_branch`` instead -- cwd-independent. FR-001 is now genuinely
    satisfied: this is a real, unmarked GREEN assertion, not an expected
    failure.

    Unlike the flat/no-meta.json fixture used by the tests above (which never
    exercises ``BookkeepingTransaction``'s "legacy" branch at all, since
    ``_transaction_topology_available`` short-circuits to the non-
    transactional path when no meta.json/coord branch exists), this fixture
    matches production shape: a real ``meta.json`` with a ``mission_id`` and
    ``single_branch`` topology, no ``coordination_branch``.
    """
    repo_root, worktree_path = _build_stale_worktree_mission(tmp_path / "worktree-cwd")
    monkeypatch.chdir(worktree_path)
    assert is_worktree_context(Path.cwd()) is True

    result = _invoke_move_task_for_stale_worktree_mission()

    assert result.exit_code == 0, result.output
    assert "Illegal transition" not in (result.output or ""), (
        "move-task from a lane-worktree cwd regressed to the #2647/#2453 "
        f"write-side 'Illegal transition' failure:\n{result.output}"
    )

    # FR-001 no-regression (T030): an INDEPENDENT stale-worktree mission
    # instance, invoked from the historically-working repo-root cwd, must
    # still succeed identically -- the fix must not have traded one cwd
    # sensitivity for another.
    repo_root_b, _worktree_path_b = _build_stale_worktree_mission(tmp_path / "repo-root-cwd")
    monkeypatch.chdir(repo_root_b)
    result_repo_root = _invoke_move_task_for_stale_worktree_mission()

    assert result_repo_root.exit_code == 0, result_repo_root.output
    assert "Illegal transition" not in (result_repo_root.output or "")
