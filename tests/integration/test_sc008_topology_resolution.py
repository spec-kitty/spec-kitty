"""SC-008 — cross-package emit sites resolve from stored topology, never cwd.

WP08 (``wp-runtime-state-eviction-01KXWN13``, FR-012 / C-003, #2647): the
``orchestrator_api`` ``append-history`` writer (T031) and the
``map-requirements`` ``tracker_refs`` emit (T030) are carved out as their own
WP precisely because they are the highest #2647 re-open risk -- they can run
from an arbitrary process cwd (a lane worktree, or, for ``orchestrator_api``,
any external-automation cwd). A ``Path.cwd()``-derived write destination would
silently reopen #2647. This is a **net-new owned test** (homeless in the
original task slice; WP08's prompt promotes it to a dedicated ``owned_files``
+ ``create_intent`` entry) -- the dedicated SC-008 acceptance evidence for
both emit sites.

Reproduces the established real-git-worktree pattern from
``tests/specify_cli/cli/commands/test_tasks_move_task_cwd.py`` (#2647): a
genuine ``git worktree add`` so cwd-dependence is exercised through actual
gitdir-pointer topology, not a fabricated marker, and NO
``locate_project_root``/``_get_main_repo_root`` mocking in the "real"
resolution tests -- the whole point is that those resolvers, not this test,
decide whether cwd matters. ``_get_main_repo_root()`` reading ``Path.cwd()``
for *repo-root discovery* is legitimate (T032 edge case) -- the invariant
under test is that the emit **destination** derives from stored topology, not
that cwd is never read anywhere.

Two-sided per T032's validation contract ("the test is red against a
``Path.cwd()``-derived resolution and green against the stored-topology
resolution"): ``TestTwoSidedProof`` below patches ``_get_main_repo_root`` to
return the WORKTREE path -- exactly what a naive cwd-rooted implementation
would resolve to -- and shows the annotation DOES leak into the worktree-local
copy under that (bad) root. That proves the destination assertions in
``TestAppendHistoryTopologyResolution``/``TestMapRequirementsTopologyResolution``
are genuine invariant guards, not tautologies that would pass no matter what.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.core.paths import is_worktree_context
from specify_cli.orchestrator_api.commands import app as orch_app
from specify_cli.status.store import read_event_stream

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_MISSION_SLUG = "sc008-topology-repro"
_LANE_BRANCH = f"kitty/mission-{_MISSION_SLUG}-lane-c"

_SPEC_CONTENT = """\
# Spec
## Functional Requirements
| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | First requirement | Done | proposed |
"""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )


def _build_repo_with_worktree(root: Path) -> tuple[Path, Path]:
    """Real git repo (main checkout) + a REAL linked lane worktree under ``root``.

    Returns ``(repo_root, worktree_path)``. The worktree is a genuine
    ``git worktree add`` result -- ``.git`` is a real gitdir-pointer file, so
    ``is_worktree_context(cwd)`` is tripped through its actual detection
    logic (mirrors the #2647 ``move-task`` repro discipline: a mocked cwd
    would make the invariant hollow).

    A flat (no ``meta.json``, no coordination topology) mission -- the
    simplest shape whose STATUS-partition directory is just
    ``repo_root/kitty-specs/<slug>``, so the "correct" vs. "decoy" write
    locations are unambiguous.
    """
    repo_root = root / "repo"
    repo_root.mkdir(parents=True)
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "t@example.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "config", "commit.gpgsign", "false")

    (repo_root / ".kittify").mkdir(parents=True, exist_ok=True)
    (repo_root / ".kittify" / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n", encoding="utf-8"
    )

    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(_SPEC_CONTENT, encoding="utf-8")
    (tasks_dir / "WP01-fixture.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Fixture WP01\n"
        "execution_mode: code_change\n"
        "agent: testbot\n"
        "owned_files:\n  - src/wp01/**\n"
        "authoritative_surface: src/wp01/\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Work Packages\n\n## WP01 - fixture\n", encoding="utf-8"
    )

    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "fixture: sc008 mission bootstrap")

    worktree_path = repo_root / ".worktrees" / f"{_MISSION_SLUG}-lane-c"
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo_root, "worktree", "add", "-b", _LANE_BRANCH, str(worktree_path), "main")
    assert (worktree_path / ".git").is_file(), (
        "git worktree add must produce a real gitdir-pointer file"
    )

    return repo_root, worktree_path


@pytest.fixture()
def mission_repo(tmp_path: Path) -> tuple[Path, Path]:
    return _build_repo_with_worktree(tmp_path)


def _events_path(feature_dir: Path) -> Path:
    return feature_dir / "status.events.jsonl"


def _invoke_append_history(note: str = "off-axis note") -> object:
    return runner.invoke(
        orch_app,
        [
            "append-history",
            "--mission",
            _MISSION_SLUG,
            "--wp",
            "WP01",
            "--actor",
            "claude",
            "--note",
            note,
        ],
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# T031 -- orchestrator_api ``append-history`` (mandatory SC-008 evidence)
# ---------------------------------------------------------------------------


class TestAppendHistoryTopologyResolution:
    """The ``note`` annotation lands on stored topology, never a cwd join."""

    def test_lands_under_stored_topology_not_worktree_cwd(
        self, mission_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo_root, worktree_path = mission_repo
        monkeypatch.chdir(worktree_path)
        assert is_worktree_context(Path.cwd()) is True

        result = _invoke_append_history()
        assert result.exit_code == 0, result.output

        # Correct destination: the mission's stored-topology feature dir under
        # the MAIN repo root -- resolved via the coord-aware
        # ``_resolve_mission_dir_or_fail`` seam, NOT a Path.cwd()-derived join.
        correct_feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
        stream = read_event_stream(correct_feature_dir)
        notes = [a for a in stream.annotations if a.wp_id == "WP01"]
        assert len(notes) == 1, "expected exactly one note annotation on the stored-topology surface"
        assert notes[0].delta.note is not None
        assert "off-axis note" in notes[0].delta.note
        assert notes[0].actor == "claude"

        # Negative control (proof-of-drive, not proof-of-absence, per the T032
        # edge case): kitty-specs/ is git-tracked, so the decoy worktree
        # carries a checked-out copy with NO events file at all pre-run. If
        # the emit had used a Path.cwd()-derived destination, THIS file would
        # exist instead of (or in addition to) the correct one above.
        decoy_events_path = _events_path(worktree_path / "kitty-specs" / _MISSION_SLUG)
        assert not decoy_events_path.exists(), (
            "InnerStateChanged annotation leaked into the worktree-cwd-derived "
            "kitty-specs/ copy -- destination_ref was NOT topology-resolved "
            "(#2647 regression)."
        )

    def test_repo_root_cwd_still_works(
        self, mission_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No-regression sibling: the historically-working repo-root cwd stays green."""
        repo_root, _worktree_path = mission_repo
        monkeypatch.chdir(repo_root)

        result = _invoke_append_history("repo-root-cwd note")
        assert result.exit_code == 0, result.output

        stream = read_event_stream(repo_root / "kitty-specs" / _MISSION_SLUG)
        notes = [a for a in stream.annotations if a.wp_id == "WP01"]
        assert len(notes) == 1
        assert notes[0].delta.note is not None
        assert "repo-root-cwd note" in notes[0].delta.note


# ---------------------------------------------------------------------------
# T030 -- ``map-requirements`` ``tracker_refs`` emit ("where reachable" per
# the WP08 prompt's T032 steps -- exercised here alongside the mandatory T031
# evidence, using the SAME off-axis-cwd fixture).
# ---------------------------------------------------------------------------


class TestMapRequirementsTopologyResolution:
    """``tracker_refs`` emits land on stored topology; union/replace hold."""

    def test_tracker_refs_union_lands_under_stored_topology_from_worktree_cwd(
        self, mission_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo_root, worktree_path = mission_repo
        monkeypatch.chdir(worktree_path)
        assert is_worktree_context(Path.cwd()) is True

        with (
            patch(
                "specify_cli.cli.commands.agent.tasks.locate_project_root",
                return_value=repo_root,
            ),
            patch(
                "specify_cli.cli.commands.agent.tasks._find_mission_slug",
                return_value=_MISSION_SLUG,
            ),
            patch(
                "specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out",
                return_value=(repo_root, "main"),
            ),
        ):
            result_first = runner.invoke(
                tasks_app,
                ["map-requirements", "--wp", "WP01", "--refs", "FR-001", "--tracker-ref", "#100", "--no-auto-commit", "--json"],
            )
            assert result_first.exit_code == 0, result_first.output

            result_second = runner.invoke(
                tasks_app,
                ["map-requirements", "--wp", "WP01", "--tracker-ref", "#200", "--no-auto-commit", "--json"],
            )
            assert result_second.exit_code == 0, result_second.output

        # Correct destination: the stored-topology feature dir under the MAIN
        # repo root (the same directory ``map-requirements`` reads WP files
        # from via ``_map_requirements_feature_dir``), never the worktree cwd.
        correct_feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
        stream = read_event_stream(correct_feature_dir)
        tracker_events = [a for a in stream.annotations if a.wp_id == "WP01" and a.delta.tracker_refs is not None]
        assert len(tracker_events) == 2

        from specify_cli.status.reducer import reduce

        snapshot = reduce(stream.transitions, stream.annotations)
        wp01 = snapshot.work_packages["WP01"]
        # Union semantics: both tracker refs accumulate (T030 default path).
        assert set(wp01["tracker_refs"]) == {"#100", "#200"}

        # The WP file's frontmatter tracker_refs slot is never MERGED into --
        # union semantics moved entirely onto the reducer (T030 DoD). The
        # ``tracker_refs`` frontmatter key itself may still round-trip at its
        # untouched default (the model-dump schema field isn't struck until
        # WP07); what must never happen is #100/#200 appearing there.
        from specify_cli.status import read_wp_frontmatter

        wp_file = correct_feature_dir / "tasks" / "WP01-fixture.md"
        wp_meta, _ = read_wp_frontmatter(wp_file)
        assert not wp_meta.tracker_refs, (
            "map-requirements must not write the union-merged tracker_refs "
            "into frontmatter any more -- the reducer owns the merge"
        )

        # Negative control: no events file was created under the decoy
        # worktree-cwd-derived kitty-specs/ copy.
        decoy_events_path = _events_path(worktree_path / "kitty-specs" / _MISSION_SLUG)
        assert not decoy_events_path.exists(), (
            "tracker_refs annotation leaked into the worktree-cwd-derived "
            "kitty-specs/ copy -- destination_ref was NOT topology-resolved "
            "(#2647 regression)."
        )

    def test_tracker_refs_replace_never_degrades_to_union(
        self, mission_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--replace`` routes through WP01's dedicated ``tracker_refs_replace``
        channel (set-replace) -- it must never resurrect a stale ref via union.
        """
        repo_root, worktree_path = mission_repo
        monkeypatch.chdir(worktree_path)

        with (
            patch(
                "specify_cli.cli.commands.agent.tasks.locate_project_root",
                return_value=repo_root,
            ),
            patch(
                "specify_cli.cli.commands.agent.tasks._find_mission_slug",
                return_value=_MISSION_SLUG,
            ),
            patch(
                "specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out",
                return_value=(repo_root, "main"),
            ),
        ):
            seed = runner.invoke(
                tasks_app,
                ["map-requirements", "--wp", "WP01", "--refs", "FR-001", "--tracker-ref", "#100", "--no-auto-commit", "--json"],
            )
            assert seed.exit_code == 0, seed.output

            replaced = runner.invoke(
                tasks_app,
                ["map-requirements", "--wp", "WP01", "--tracker-ref", "#999", "--replace", "--no-auto-commit", "--json"],
            )
            assert replaced.exit_code == 0, replaced.output

        correct_feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
        stream = read_event_stream(correct_feature_dir)
        tracker_events = [a for a in stream.annotations if a.wp_id == "WP01" and (a.delta.tracker_refs is not None or a.delta.tracker_refs_replace is not None)]
        assert len(tracker_events) == 2
        assert tracker_events[0].delta.tracker_refs == ["#100"]
        assert tracker_events[0].delta.tracker_refs_replace is None
        assert tracker_events[1].delta.tracker_refs_replace == ["#999"]
        assert tracker_events[1].delta.tracker_refs is None

        from specify_cli.status.reducer import reduce

        snapshot = reduce(stream.transitions, stream.annotations)
        wp01 = snapshot.work_packages["WP01"]
        assert wp01["tracker_refs"] == ["#999"], (
            "--replace must wholesale-replace via tracker_refs_replace, "
            "never degrade to a union that resurrects the stale #100 ref"
        )


# ---------------------------------------------------------------------------
# Two-sided proof (T032): demonstrate the destination assertions above are a
# genuine invariant guard, not a tautology that would pass no matter what.
#
# Simulating the historical #2647 bug shape by merely feeding
# ``_get_main_repo_root`` the WORKTREE path (what a naive ``Path.cwd()``-rooted
# implementation would compute) turns out NOT to reproduce a leak on its own:
# WP01's ``emit_inner_state_changed`` already runs every ``feature_dir`` through
# ``canonicalize_feature_dir``, which independently detects a worktree-rooted
# ``.../kitty-specs/<slug>`` path (via the gitdir-pointer walk-up) and redirects
# it back to the canonical main-repo copy -- a second, load-bearing line of
# defense on top of T031's own topology-aware resolution. That is a GOOD
# discovery (defense in depth), but it means the bad-root patch alone cannot
# characterize what T031's own resolution contributes.
#
# So the two-sided proof disables BOTH layers together (bad root AND a
# no-op-stubbed ``canonicalize_feature_dir``) to show the leak DOES occur
# once neither safety net is present, and then shows each layer holding the
# line independently -- proving the destination assertions above discriminate
# a real regression from a non-regression, on both fronts.
# ---------------------------------------------------------------------------


class TestTwoSidedProof:
    def test_bad_root_alone_is_caught_by_emits_own_canonicalization(
        self, mission_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Defense-in-depth check: WP01's ``canonicalize_feature_dir`` alone
        already heals a worktree-rooted ``main_repo_root`` mistake.
        """
        repo_root, worktree_path = mission_repo
        monkeypatch.chdir(worktree_path)

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=worktree_path,
        ):
            result = _invoke_append_history("bad-root note (healed)")

        assert result.exit_code == 0, result.output
        decoy_events_path = _events_path(worktree_path / "kitty-specs" / _MISSION_SLUG)
        assert not decoy_events_path.exists(), (
            "canonicalize_feature_dir should have redirected the worktree-"
            "rooted path back to the main repo copy"
        )
        stream = read_event_stream(repo_root / "kitty-specs" / _MISSION_SLUG)
        assert any(
            a.wp_id == "WP01" and a.delta.note is not None and "bad-root note (healed)" in a.delta.note
            for a in stream.annotations
        )

    def test_bad_root_without_canonicalization_would_leak_into_the_worktree(
        self, mission_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With BOTH safety nets removed (bad root + stubbed canonicalization),
        the annotation genuinely leaks into the worktree-cwd-derived copy --
        proving the "no write under the decoy cwd" assertions in the classes
        above are capable of failing, not vacuously true.
        """
        repo_root, worktree_path = mission_repo
        monkeypatch.chdir(worktree_path)

        with (
            patch(
                "specify_cli.orchestrator_api._common._get_main_repo_root",
                return_value=worktree_path,
            ),
            patch(
                "specify_cli.status.emit.canonicalize_feature_dir",
                side_effect=lambda feature_dir: feature_dir,
            ),
        ):
            result = _invoke_append_history("bad-root note (unhealed)")

        assert result.exit_code == 0, result.output
        decoy_events_path = _events_path(worktree_path / "kitty-specs" / _MISSION_SLUG)
        assert decoy_events_path.exists(), (
            "sanity check: with both the caller-side topology resolution AND "
            "WP01's own canonicalization bypassed, a cwd-derived root MUST "
            "reproduce the #2647 leak -- otherwise the destination guard "
            "tests above would pass regardless of implementation."
        )
        stream = read_event_stream(worktree_path / "kitty-specs" / _MISSION_SLUG)
        assert any(
            a.wp_id == "WP01" and a.delta.note is not None and "bad-root note (unhealed)" in a.delta.note
            for a in stream.annotations
        )
