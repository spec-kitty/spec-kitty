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
from collections.abc import Callable
from pathlib import Path

import pytest
import typer

from specify_cli.bulk_edit.gate import (
    BULK_EDIT_REVIEW_RANGE_EMPTY,
    BULK_EDIT_REVIEW_RANGE_UNAVAILABLE,
)
from specify_cli.cli.commands.agent import workflow_executor
from specify_cli.cli.commands.agent.tasks import app as tasks_app
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


#: A protected file under ``.kittify/``: the review range counts ``.kittify/`` as bookkeeping, but the
#: gate must still judge an edit there that the occurrence map forbids (#7726 landing fold).
_KITTIFY_PROBE = ".kittify/bulk-edit-probe.yaml"


def _make_bulk_edit(repo: Path, slug: str, occurrence_map: str = _OCCURRENCE_MAP) -> None:
    """Declare the Mission bulk_edit, add its occurrence map and a protected file, before any WP opens."""
    feature_dir = repo / "kitty-specs" / slug
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["change_mode"] = "bulk_edit"
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (feature_dir / "occurrence_map.yaml").write_text(occurrence_map, encoding="utf-8")
    (repo / "config.yaml").write_text("oldName: true\n", encoding="utf-8")
    (repo / _KITTIFY_PROBE).parent.mkdir(parents=True, exist_ok=True)
    (repo / _KITTIFY_PROBE).write_text("oldName: true\n", encoding="utf-8")
    sb.git(repo, "add", "-A")
    sb.git(repo, "add", "-f", _KITTIFY_PROBE)
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


def _submit(m: sb.Mission, *, forbidden_edit: bool, forbidden_path: str = "config.yaml") -> None:
    """alice implements WP01 (optionally also editing a protected file) and hands it to review."""
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    if forbidden_edit:
        sb.commit_file(m, forbidden_path, "oldName: false\n", "feat(WP01): touch a do_not_change key")
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


def test_an_unreadable_status_surface_is_a_named_refusal(
    templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The range resolved but the gate could not read the status surface: a named refusal, never a blank one."""
    from specify_cli.cli.commands.agent import workflow

    m = _checkout(templates, "minted", tmp_path, monkeypatch)
    _submit(m, forbidden_edit=False)
    monkeypatch.setattr(workflow, "_review_gate_topology", lambda *_args: None)

    with pytest.raises(typer.Exit) as excinfo:
        _gate(m)
    assert excinfo.value.exit_code == 1
    output = " ".join(capsys.readouterr().out.split())
    assert BULK_EDIT_REVIEW_RANGE_UNAVAILABLE in output, output
    assert "status surface" in output and f"agent tasks status --mission {m.slug}" in output, output


# --------------------------------------------------------------------------- lanes_with_coord


def _lane_mission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, forbidden_edit: bool, after_submission: bool = False, forbidden_path: str = "config.yaml"
) -> tuple[Path, str]:
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
        _commit_in(tree, forbidden_path, "oldName: false\n", "feat: touch a do_not_change key")
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


@pytest.mark.parametrize("flavour", ["minted", "ctt"])
def test_single_branch_forbidden_kittify_edit_is_refused(
    templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], flavour: str
) -> None:
    """``.kittify/`` is range bookkeeping, not gate bookkeeping: a forbidden edit there is judged."""
    m = _checkout(templates, flavour, tmp_path, monkeypatch)
    _submit(m, forbidden_edit=True, forbidden_path=_KITTIFY_PROBE)
    with pytest.raises(typer.Exit) as excinfo:
        _gate(m)
    assert excinfo.value.exit_code == 1
    output = " ".join(capsys.readouterr().out.split())
    assert "bulk-edit-probe.yaml" in output and BULK_EDIT_REVIEW_RANGE_EMPTY not in output, output


def test_lane_forbidden_kittify_edit_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """lanes_with_coord: the gate judged ``.kittify/`` before #7726 and still does."""
    repo, slug = _lane_mission(tmp_path, monkeypatch, forbidden_edit=True, forbidden_path=_KITTIFY_PROBE)
    with pytest.raises(typer.Exit):
        _gate(sb.Mission(repo, slug, tmp_path))
    output = " ".join(capsys.readouterr().out.split())
    assert "bulk-edit-probe.yaml" in output, output


def test_mission_bookkeeping_never_blocks_its_own_review(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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


# --------------------------------------------------------------------------- the move-task path into review


@pytest.mark.parametrize("flavour", ["minted", "ctt"])
def test_unforced_move_task_into_review_then_the_gate_judges_the_work(
    templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], flavour: str
) -> None:
    """The operator's path: an unforced ``move-task --to for_review`` (every move-task gate runs), then review.

    Red on main: the gate then diffed ``X..X`` and passed. A minted Mission's status is written to
    its Mission branch, so that branch must exist locally for any status move (``DESTINATION_REF_NOT_FOUND``
    otherwise); with it present, the gate now judges the work instead of passing vacuously.
    """
    from specify_cli.lanes.claim_base import record_claim_base

    m = _checkout(templates, flavour, tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    record_claim_base(m.repo, m.repo, m.slug, "WP01")  # what ``implement`` records at the claim
    sb.implement(m, "WP01")
    sb.commit_file(m, "config.yaml", "oldName: false\n", "feat(WP01): touch a do_not_change key")

    sb.move(m, "WP01", "for_review", "alice")

    with pytest.raises(typer.Exit):
        _gate(m)
    output = " ".join(capsys.readouterr().out.split())
    assert "config.yaml" in output and "do_not_change" in output, output


# --------------------------------------------------------------------------- planning lane on lanes_with_coord


@pytest.fixture(scope="module")
def review_templates(tmp_path_factory: pytest.TempPathFactory) -> object:
    from tests.integration.review.review_range_fixtures import ReviewTemplates

    return ReviewTemplates(tmp_path_factory.mktemp("bulk-edit-coord-planning"))


def _merge_foreign_forbidden_edit(repo: Path, branch: str) -> None:
    """Someone else's commit (a do_not_change edit) reaches *branch* through a merge commit (ruling B)."""
    sb.git(repo, "checkout", "-q", "-b", "foreign", f"{branch}~1")
    (repo / "config.yaml").write_text("oldName: false\n", encoding="utf-8")
    sb.git(repo, "commit", "-qam", "foreign: touch a do_not_change key")
    sb.git(repo, "checkout", "-q", branch)
    sb.git(repo, "merge", "-q", "--no-ff", "--no-edit", "foreign")


#: scenario -> what the gate does (``None`` passes, else the text the refusal holds).
_PLANNING_SCENARIOS = {
    "compliant": None,
    "own_forbidden_edit": "config.yaml",
    "foreign_merge": None,
    "no_claim_base": "no claim base is recorded",
    "empty": "BULK_EDIT_REVIEW_RANGE_EMPTY",
}


@pytest.mark.parametrize("scenario", sorted(_PLANNING_SCENARIOS))
def test_coord_planning_lane_wp_is_judged_from_its_claim_base(review_templates: object, tmp_path: Path, capsys: pytest.CaptureFixture[str], scenario: str) -> None:
    """Ruling Q10's case: the range owner records no range (events on the coordination branch).

    Before the fold the gate always refused. The planning-lane window runs from the claim base to
    the planning branch named in ``meta.json`` (never the reviewer's checkout), judging only the
    non-merge first-parent commits (ruling B): a foreign edit merged in is not judged, the work
    package's own edit is. A missing claim base refuses rather than widening to the Mission.
    """
    from specify_cli.lanes.claim_base import record_claim_base
    from tests.integration.review.review_range_fixtures import ReviewTemplates, submitted_coord_planning_lane_wp

    assert isinstance(review_templates, ReviewTemplates)
    fx = review_templates.checkout("lanes_with_coord", tmp_path)
    with fx.environment():
        _make_bulk_edit(fx.repo, fx.mission_slug)
        if scenario not in {"no_claim_base", "empty"}:
            record_claim_base(fx.repo, fx.repo, fx.mission_slug, "WP03")
        submitted = submitted_coord_planning_lane_wp(fx)
        branch = sb.git(fx.repo, "rev-parse", "--abbrev-ref", "HEAD")
        if scenario == "empty":
            record_claim_base(fx.repo, fx.repo, fx.mission_slug, "WP03")  # at the tip: nothing after it
        elif scenario == "own_forbidden_edit":
            (fx.repo / "config.yaml").write_text("oldName: false\n", encoding="utf-8")
            sb.git(fx.repo, "commit", "-qam", "docs(WP03): touch a do_not_change key")
        elif scenario == "foreign_merge":
            _merge_foreign_forbidden_edit(fx.repo, branch)
        sb.git(fx.repo, "checkout", "-q", "--detach")  # the gate reads the planning branch by name, not HEAD

        expected = _PLANNING_SCENARIOS[scenario]
        gate = _bound_gate(fx.feature_dir, fx.repo, fx.mission_slug, submitted.wp_id)
        if expected is None:
            gate()
        else:
            with pytest.raises(typer.Exit):
                gate()
            output = " ".join(capsys.readouterr().out.split())
            assert expected in output, output


def _bound_gate(feature_dir: Path, repo: Path, mission_slug: str, wp_id: str) -> Callable[[], None]:
    def _run() -> None:
        workflow_executor.review_enforce_bulk_edit_gate(feature_dir=feature_dir, main_repo_root=repo, mission_slug=mission_slug, wp_id=wp_id)

    return _run


# --------------------------------------------------------------------------- ruling B on commit-to-target


def test_ctt_foreign_commit_merged_into_the_target_is_not_judged(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruling B: on a commit-to-target Mission only the non-merge first-parent commits' paths are judged.

    A forbidden edit someone else made reaches the target through a merge inside the window: not judged.
    """
    m = _checkout(templates, "ctt", tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    _merge_foreign_forbidden_edit(m.repo, "main")
    sb.emit(m, "WP01", "for_review", "alice", "--force", "--reason", "handed to review")
    _gate(m)


def test_ctt_foreign_commit_rebased_onto_the_target_is_still_judged(
    templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The documented limit of ruling B: a rebased or fast-forwarded foreign commit lands on the
    first-parent chain and is indistinguishable from the work package's own, so it is judged (fail-closed)."""
    m = _checkout(templates, "ctt", tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    sb.git(m.repo, "checkout", "-q", "-b", "foreign", "main~1")
    (m.repo / "config.yaml").write_text("oldName: false\n", encoding="utf-8")
    sb.git(m.repo, "commit", "-qam", "foreign: touch a do_not_change key")
    sb.git(m.repo, "checkout", "-q", "main")
    sb.git(m.repo, "cherry-pick", "foreign")  # what a rebase-pull does to the target
    sb.emit(m, "WP01", "for_review", "alice", "--force", "--reason", "handed to review")
    with pytest.raises(typer.Exit):
        _gate(m)
    assert "config.yaml" in " ".join(capsys.readouterr().out.split())


# --------------------------------------------------------------------------- the absent Mission branch remedy


@pytest.mark.parametrize("force", [False, True])
def test_an_absent_mission_branch_names_the_command_that_restores_it(templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, force: bool) -> None:
    """Operator ruling A (#7726): the local Mission branch stays a precondition for a minted Mission's status moves.

    Both refusals an operator meets without it print the one command that restores it: the
    implementation-evidence gate (unforced) and the status write itself (``--force`` skips the
    evidence gate, so the move reaches ``DESTINATION_REF_NOT_FOUND``).
    """
    m = _checkout(templates, "minted", tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    branch = m.mission_branch
    sb.git(m.repo, "branch", "-m", branch, "pr-head")

    extra = ["--force"] if force else []
    code, out = sb._invoke(
        tasks_app,
        ["move-task", "WP01", "--to", "for_review", "--agent", "alice", "--note", "x", "--mission", m.slug, *extra],
    )
    flat = " ".join(out.split())
    assert code != 0, flat
    assert ("DESTINATION_REF_NOT_FOUND" if force else "implementation window") in flat, flat
    assert f"git branch {branch} <commit holding the work>" in flat, flat


def test_ctt_rename_then_rewrite_keeps_the_old_path_judged(
    templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Renames are split in the first-parent listing, so a moved protected file's old path is still judged."""
    m = _checkout(templates, "ctt", tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    sb.git(m.repo, "mv", "config.yaml", "settings.yaml")
    sb.git(m.repo, "commit", "-qm", "feat(WP01): move config")
    (m.repo / "settings.yaml").write_text("entirely: different\ncontent: here\n", encoding="utf-8")
    sb.git(m.repo, "commit", "-qam", "feat(WP01): rewrite the moved config")
    sb.emit(m, "WP01", "for_review", "alice", "--force", "--reason", "handed to review")
    with pytest.raises(typer.Exit):
        _gate(m)
    assert "config.yaml" in " ".join(capsys.readouterr().out.split())


def test_ctt_work_that_arrives_only_through_a_merge_is_refused_not_passed(
    templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every changed path is behind a merge: nothing the work package committed itself can be judged, so it refuses."""
    m = _checkout(templates, "ctt", tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.git(m.repo, "checkout", "-q", "-b", "side")
    (m.repo / "src" / "m1").mkdir(parents=True, exist_ok=True)
    (m.repo / "src" / "m1" / "real.py").write_text("VALUE = 1\n", encoding="utf-8")
    sb.git(m.repo, "add", "-A", "src")
    sb.git(m.repo, "commit", "-qm", "feat(WP01): work on a side branch")
    sb.git(m.repo, "checkout", "-q", "main")
    sb.git(m.repo, "merge", "-q", "--no-ff", "--no-edit", "side")
    sb.emit(m, "WP01", "for_review", "alice", "--force", "--reason", "handed to review")
    with pytest.raises(typer.Exit):
        _gate(m)
    assert "BULK_EDIT_REVIEW_RANGE_EMPTY" in " ".join(capsys.readouterr().out.split())


def test_ctt_edit_folded_into_the_work_package_merge_is_judged(
    templates: _Templates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A merge on the first-parent chain contributes what its own resolution introduced (remerge diff)."""
    m = _checkout(templates, "ctt", tmp_path, monkeypatch)
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    sb.git(m.repo, "checkout", "-q", "-b", "foreign", "main~1")
    (m.repo / "notes.md").write_text("foreign\n", encoding="utf-8")
    sb.git(m.repo, "add", "notes.md")
    sb.git(m.repo, "commit", "-qm", "foreign: notes")
    sb.git(m.repo, "checkout", "-q", "main")
    sb.git(m.repo, "merge", "-q", "--no-ff", "--no-commit", "foreign")
    (m.repo / "config.yaml").write_text("oldName: false\n", encoding="utf-8")
    sb.git(m.repo, "add", "config.yaml")
    sb.git(m.repo, "commit", "-qm", "merge foreign, folding in a do_not_change edit")
    sb.emit(m, "WP01", "for_review", "alice", "--force", "--reason", "handed to review")
    with pytest.raises(typer.Exit):
        _gate(m)
    output = " ".join(capsys.readouterr().out.split())
    assert "config.yaml" in output and "notes.md" not in output, output
