"""#7726: the bulk-edit review gate judges the work package's own review range on ``single_branch``.

Before #7726 the gate diffed ``lanes.json mission_branch .. review workspace branch``. On a
``single_branch`` Mission both name the same branch (the minted ``kitty/mission-*`` branch, or the
target branch on a commit-to-target Mission), so the gate diffed ``X..X`` and passed having
checked nothing. When that branch was absent locally it refused with a ``rev-parse`` failure
instead, and the workaround (a local branch at the work's head) made it pass vacuously.

The gate now takes its range from :func:`specify_cli.review.wp_range.resolve_wp_review_range`
(window open .. ``for_review`` submission, recorded as SHAs), so:

* a work package that edits a path the occurrence map forbids is refused, minted and
  commit-to-target alike (red on main: both passed);
* a compliant work package still passes;
* with the local ``kitty/mission-*`` ref deleted the range still resolves from the recorded window;
* an empty or unavailable range is a named refusal, never a pass.

The Missions are built through the real CLI (``tests/integration/single_branch_window_support``).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import typer

from specify_cli.bulk_edit.gate import (
    BULK_EDIT_REVIEW_RANGE_EMPTY,
    BULK_EDIT_REVIEW_RANGE_UNAVAILABLE,
)
from specify_cli.cli.commands.agent import workflow_executor
from tests.integration import single_branch_window_support as sb

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_HARNESS_VARIABLES = ("SPEC_KITTY_NO_NAG", "SPEC_KITTY_NON_INTERACTIVE", "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS")

# serialized_keys is do_not_change: an edit of the existing ``config.yaml`` (which carries the
# term) is a violation; the WP's own ``src/m1/real.py`` is created, so it never violates.
_OCCURRENCE_MAP = """\
target:
  term: oldName
  operation: rename
categories:
  code_symbols:
    action: rename
  import_paths:
    action: rename
  filesystem_paths:
    action: rename
  serialized_keys:
    action: do_not_change
  cli_commands:
    action: rename
  user_facing_strings:
    action: rename
  tests_fixtures:
    action: rename
  logs_telemetry:
    action: rename
"""


#: A map that also protects user-facing text: the Mission's own ``tasks.md`` and task files are
#: classified there by path, so a gate that read Mission bookkeeping would block its own review.
_DOCS_PROTECTED_MAP = _OCCURRENCE_MAP.replace("  user_facing_strings:\n    action: rename", "  user_facing_strings:\n    action: do_not_change")


def _make_bulk_edit(repo: Path, slug: str, occurrence_map: str = _OCCURRENCE_MAP) -> None:
    """Declare the Mission bulk_edit, add its occurrence map and a protected file, before any WP opens."""
    feature_dir = repo / "kitty-specs" / slug
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["change_mode"] = "bulk_edit"
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (feature_dir / "occurrence_map.yaml").write_text(occurrence_map, encoding="utf-8")
    (repo / "config.yaml").write_text("oldName: true\n", encoding="utf-8")
    sb.git(repo, "add", "-A")
    sb.git(repo, "commit", "-qm", "test: declare the Mission bulk_edit")


class _Templates:
    """One built Mission per flavour (minted / commit-to-target), copied per test."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._built: dict[str, tuple[Path, str]] = {}

    def get(self, flavour: str) -> tuple[Path, str]:
        if flavour not in self._built:
            base = self._root / flavour
            with pytest.MonkeyPatch.context() as patch:
                for key in _HARNESS_VARIABLES:
                    patch.delenv(key, raising=False)
                repo, slug = sb.build_template(base, commit_to_target=flavour == "ctt")
                _make_bulk_edit(repo, slug, _DOCS_PROTECTED_MAP if flavour == "docs" else _OCCURRENCE_MAP)
            self._built[flavour] = (repo, slug)
        return self._built[flavour]


@pytest.fixture(scope="module")
def templates(tmp_path_factory: pytest.TempPathFactory) -> _Templates:
    return _Templates(tmp_path_factory.mktemp("bulk-edit-sb"))


def _checkout(templates: _Templates, flavour: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sb.Mission:
    source, slug = templates.get(flavour)
    repo = tmp_path / "repo"
    shutil.copytree(source, repo, symlinks=True)
    monkeypatch.chdir(repo)
    for key, value in sb.cli_env(tmp_path).items():
        if key.startswith(("HOME", "XDG_", "SPEC_KITTY_")):
            monkeypatch.setenv(key, value)
    for key in _HARNESS_VARIABLES:
        monkeypatch.delenv(key, raising=False)
    return sb.Mission(repo, slug, tmp_path)


def _submit(m: sb.Mission, *, forbidden_edit: bool) -> None:
    """alice implements WP01 (optionally also editing the protected ``config.yaml``) and hands it to review."""
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    if forbidden_edit:
        sb.commit_file(m, "config.yaml", "oldName: false\n", "feat(WP01): touch a do_not_change key")
    sb.emit(m, "WP01", "for_review", "alice", "--force", "--reason", "handed to review")


def _gate(m: sb.Mission) -> None:
    workflow_executor.review_enforce_bulk_edit_gate(
        feature_dir=m.repo / "kitty-specs" / m.slug,
        main_repo_root=m.repo,
        mission_slug=m.slug,
        wp_id="WP01",
    )


@pytest.mark.parametrize("flavour", ["minted", "ctt"])
def test_agent_action_review_refuses_a_forbidden_edit_on_single_branch(
    templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flavour: str
) -> None:
    """Red on main: the gate diffed ``X..X`` and ``agent action review`` went on to claim the WP."""
    m = _checkout(templates, flavour, tmp_path, monkeypatch)
    _submit(m, forbidden_edit=True)

    proc = subprocess.run(
        [*sb._CLI, "agent", "action", "review", "WP01", "--agent", "bob", "--mission", m.slug],
        cwd=m.repo,
        env=m.env,
        capture_output=True,
        text=True,
        timeout=400,
    )
    output = " ".join((proc.stdout + "\n" + proc.stderr).split())

    assert proc.returncode != 0, output
    assert "config.yaml" in output, output
    assert "do_not_change" in output, output


@pytest.mark.parametrize("flavour", ["minted", "ctt"])
def test_gate_refuses_a_forbidden_edit_and_passes_a_compliant_one(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flavour: str) -> None:
    compliant = _checkout(templates, flavour, tmp_path / "ok", monkeypatch)
    _submit(compliant, forbidden_edit=False)
    _gate(compliant)  # no Exit: the WP only created its own owned file

    violating = _checkout(templates, flavour, tmp_path / "bad", monkeypatch)
    _submit(violating, forbidden_edit=True)
    with pytest.raises(typer.Exit) as excinfo:
        _gate(violating)
    assert excinfo.value.exit_code == 1


def test_gate_resolves_the_recorded_window_without_the_local_mission_ref(
    templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fresh clone or cloud session may never have the unpushed ``kitty/mission-*`` ref: the range is SHAs."""
    m = _checkout(templates, "minted", tmp_path, monkeypatch)
    _submit(m, forbidden_edit=True)
    branch = m.mission_branch
    sb.git(m.repo, "checkout", "-q", "--detach")
    sb.git(m.repo, "branch", "-D", branch)

    with pytest.raises(typer.Exit):
        _gate(m)
    output = " ".join(capsys.readouterr().out.split())
    assert "config.yaml" in output, output
    assert BULK_EDIT_REVIEW_RANGE_UNAVAILABLE not in output
    assert "rev-parse" not in output and branch not in output, output


def test_an_empty_range_is_refused_not_passed(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A WP submitted with no commit in its window: the gate has nothing to judge, so it refuses."""
    m = _checkout(templates, "minted", tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.emit(m, "WP01", "for_review", "alice", "--force", "--reason", "handed to review")

    with pytest.raises(typer.Exit) as excinfo:
        _gate(m)
    assert excinfo.value.exit_code == 1
    output = " ".join(capsys.readouterr().out.split())
    assert BULK_EDIT_REVIEW_RANGE_EMPTY in output, output
    assert "move-task WP01" in output, output


def test_an_unavailable_range_is_a_named_refusal(
    templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No ``for_review`` submission: the range is unavailable, the gate names why and how to fix it."""
    m = _checkout(templates, "minted", tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")

    with pytest.raises(typer.Exit) as excinfo:
        _gate(m)
    assert excinfo.value.exit_code == 1
    output = " ".join(capsys.readouterr().out.split())
    assert BULK_EDIT_REVIEW_RANGE_UNAVAILABLE in output, output
    assert "no_submission" in output, output
    assert "--to for_review" in output, output


# --------------------------------------------------------------------------- lanes_with_coord


def _lane_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, forbidden_edit: bool, after_submission: bool = False) -> tuple[Path, str]:
    """A one-lane coordination Mission (bulk_edit), WP01 worked on its lane and handed to review."""
    from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
    from tests.consolidation import characterization_support as cs
    from tests.terminus.canceled_dependency_support import ACTOR, _commit_in
    from tests.terminus.conftest import CoordMission, _write_meta
    from tests.terminus.mixed_lane_support import transition

    for key in _HARNESS_VARIABLES:
        monkeypatch.delenv(key, raising=False)

    def _bulk_edit_meta(mission: CoordMission) -> None:
        _write_meta(mission)
        _make_bulk_edit(mission.repo, mission.slug)

    monkeypatch.setattr(cs, "_write_meta", _bulk_edit_meta)
    mission, manifest = cs._bootstrap_one_lane_coord(tmp_path, mid8="01M7726A", wps=("WP01",))
    tree, _branch = allocate_lane_worktree(mission.repo, mission.slug, "WP01", manifest)
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP01", lane, actor=ACTOR)
    _commit_in(tree, "src/pkg/wp01.py", "def wp01() -> int:\n    return 1\n", "feat: WP01 work")
    if forbidden_edit and not after_submission:
        _commit_in(tree, "config.yaml", "oldName: false\n", "feat: touch a do_not_change key")
    transition(mission, "WP01", "for_review", actor=ACTOR, subtasks_complete=True)
    if forbidden_edit and after_submission:
        _commit_in(tree, "config.yaml", "oldName: false\n", "feat: touch a do_not_change key after submission")
    monkeypatch.chdir(mission.repo)
    return mission.repo, mission.slug


@pytest.mark.parametrize("forbidden_edit", [False, True])
def test_lane_gate_judges_the_lane_work_through_the_shared_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], forbidden_edit: bool
) -> None:
    """lanes_with_coord: the gate keeps judging the lane's work, now from the recorded window."""
    repo, slug = _lane_mission(tmp_path, monkeypatch, forbidden_edit=forbidden_edit)
    m = sb.Mission(repo, slug, tmp_path)
    if forbidden_edit:
        with pytest.raises(typer.Exit) as excinfo:
            _gate(m)
        assert excinfo.value.exit_code == 1
        output = " ".join(capsys.readouterr().out.split())
        assert "config.yaml" in output and BULK_EDIT_REVIEW_RANGE_UNAVAILABLE not in output, output
    else:
        _gate(m)


def test_lane_commit_after_the_submission_is_still_judged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A lane topology keeps judging up to the live lane head: a later forbidden commit is refused."""
    repo, slug = _lane_mission(tmp_path, monkeypatch, forbidden_edit=True, after_submission=True)
    with pytest.raises(typer.Exit):
        _gate(sb.Mission(repo, slug, tmp_path))
    output = " ".join(capsys.readouterr().out.split())
    assert "config.yaml" in output, output


def test_mission_bookkeeping_never_blocks_its_own_review(
    templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """single_branch: the window holds Mission bookkeeping (a ticked task file); the gate leaves it out.

    The map protects user-facing text, where the task file is classified by path, so a gate that
    read the bookkeeping the review range excludes would block the Mission's own review.
    """
    m = _checkout(templates, "docs", tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    task_file = m.repo / "kitty-specs" / m.slug / "tasks" / "WP01-m1.md"
    task_file.write_text(task_file.read_text(encoding="utf-8").replace("- [ ] T1", "- [x] T1"), encoding="utf-8")
    sb.git(m.repo, "commit", "-qam", "chore: tick WP01 subtask")
    sb.emit(m, "WP01", "for_review", "alice", "--force", "--reason", "handed to review")
    _gate(m)
