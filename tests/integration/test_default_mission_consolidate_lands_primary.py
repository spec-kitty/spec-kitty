"""FR-062 / SC-007: ``consolidate`` lands a default Mission's PRIMARY artifacts from its topic branch (#7282, WP20).

A Mission created without ``--topology`` and settled to ``lanes_with_coord`` at its first
``finalize-tasks`` keeps its PRIMARY partition (spec, tasks, WP files, ``lanes.json``,
``meta.json``) on its topic branch, which is also its coordination branch and its
``lanes.json`` ``mission_branch``. Each test drives the real ``spec-kitty`` CLI (a subprocess on
this checkout's ``src``) through implement, review and ``consolidate`` on a real git repository.

Windows (T118, the characterization that decides the design):

* **A** -- a PRIMARY edit committed on the topic branch before ``consolidate``: the landing
  (``integrate_mission_into_target``) carries the topic tip, so it reaches the target.
* **B** -- a PRIMARY commit made on the topic branch after the landing read its tip, before the
  coordination teardown (and the same commit in the resumed late window): the coordination
  projection excludes PRIMARY kinds on purpose (G2), so the teardown used to delete it with the
  branch at exit 0. It must reach the target, with target-authored ``meta.json`` values kept.
* **C** -- the run's PRIMARY anchor (``run.target_feature_dir``): before the landing it is the
  topic holder (the coordination worktree), so the post-landing ``baseline_merge_commit`` stamp
  went there and the post-merge baseline validation rolled the whole run back. After the landing
  the anchor must be the target checkout.

Fixture workarounds for gaps outside this work package, each recorded as tooling friction:
``auto_commit: false`` (the claim commit expects the repository root checkout on the topic
branch, which the coordination worktree holds), a shim that lets the implement planning-commit
probe skip a coordination-worktree PRIMARY directory (``SafeCommitPathPolicyError``), the
coordination worktree committed by hand after each claim, ``--force`` on ``for_review`` (the lane
is cut from the topic branch and carries PRIMARY files), an unprotected target (``work``), and
no approval attestation (the in_review -> approved hop records a review stamp).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    THREE_LANES,
    DefaultMission,
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.slow]

_SRC = str(Path(__file__).resolve().parents[2] / "src")
_TARGET = "work"
_CLI_TIMEOUT_SECONDS = 300
_WINDOW_A_MARK = "WINDOW_A_SPEC"
_WINDOW_B_MARK = "WINDOW_B_SPEC"
_STALE_MISSION_NUMBER = 99
_ANALYSIS = (
    "---\nschema: analysis-findings/v1\nfindings: []\n"
    "counts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n---\n\n"
    "# Specification Analysis Report\n\nNo blocking findings.\n"
)

#: The CLI entry the tests run. It applies the planning-commit workaround (module docstring)
#: and three phase hooks read from the environment: ``WP20_COMMIT_AFTER`` (commit a PRIMARY
#: edit on the topic branch right after that executor phase), ``WP20_FAIL_BEFORE`` (raise
#: before that phase) and ``WP20_FAIL_KIND`` (``exit`` -> ``typer.Exit(1)``, else RuntimeError).
_SHIM = """
import json, os, subprocess, sys
from pathlib import Path
import specify_cli.coordination.planning_commit as pc
_paths = pc.feature_dir_file_paths
def _tolerant(repo_root, feature_dir):
    try:
        return _paths(repo_root, feature_dir)
    except pc.SafeCommitPathPolicyError:
        return []
pc.feature_dir_file_paths = _tolerant

def _commit_primary_edit():
    coord = Path(os.environ["WP20_COORD"])
    mission_dir = coord / "kitty-specs" / os.environ["WP20_SLUG"]
    spec = mission_dir / "spec.md"
    spec.write_text(spec.read_text() + "\\n__WINDOW_B__\\n")
    meta_path = mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text())
    meta["window_b_key"] = "B"
    meta["mission_number"] = __STALE__
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\\n")
    subprocess.run(["git", "-C", str(coord), "-c", "user.name=e", "-c", "user.email=e@x", "commit", "-qam", "late PRIMARY"], check=True)

import specify_cli.consolidation.executor as executor
after = os.environ.get("WP20_COMMIT_AFTER")
before = os.environ.get("WP20_FAIL_BEFORE")
def _wrap(name, post=None, pre=None):
    original = getattr(executor, name)
    def wrapped(*args, **kwargs):
        if pre:
            pre()
        result = original(*args, **kwargs)
        if post:
            post()
        return result
    setattr(executor, name, wrapped)
def _fail():
    os.environ.pop("WP20_FAIL_BEFORE", None)
    if os.environ.get("WP20_FAIL_KIND") == "exit":
        import typer
        raise typer.Exit(1)
    raise RuntimeError("WP20 injected failure")
if after:
    _wrap(after, post=_commit_primary_edit)
if before:
    _wrap(before, pre=_fail)
from specify_cli.__main__ import main
sys.argv = ["spec-kitty", *sys.argv[1:]]
main()
""".replace("__WINDOW_B__", _WINDOW_B_MARK).replace("__STALE__", str(_STALE_MISSION_NUMBER))


@dataclass(frozen=True)
class Built:
    """A settled, implemented and approved Mission ready to consolidate."""

    mission: DefaultMission
    shim: Path

    @property
    def root(self) -> Path:
        return self.mission.root

    @property
    def slug(self) -> str:
        return self.mission.slug

    @property
    def rel(self) -> str:
        return f"kitty-specs/{self.mission.slug}"

    @property
    def coord_worktree(self) -> Path:
        return self.mission.coord_mission_dir.parents[1]


def _commit_all(checkout: Path, message: str) -> None:
    if git(checkout, "status", "--porcelain"):
        git(checkout, "add", "-A")
        git(checkout, "-c", "user.name=e", "-c", "user.email=e@x", "commit", "-qm", message)


def cli(built: Built, *args: str, hooks: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run ``spec-kitty <args>`` through the shim, from the repository root checkout."""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in (_SRC, os.environ.get("PYTHONPATH")) if p), NO_COLOR="1")
    env.update({"WP20_COORD": str(built.coord_worktree), "WP20_SLUG": built.slug, **(hooks or {})})
    return subprocess.run(
        [sys.executable, str(built.shim), *args], cwd=built.root, env=env, capture_output=True, text=True, timeout=_CLI_TIMEOUT_SECONDS, check=False
    )


def _ok(proc: subprocess.CompletedProcess[str]) -> subprocess.CompletedProcess[str]:
    assert proc.returncode == 0, f"exit {proc.returncode}\nSTDOUT:\n{proc.stdout[-3000:]}\nSTDERR:\n{proc.stderr[-2000:]}"
    return proc


def _lane_worktree(built: Built, index: int) -> Path:
    return built.root / ".worktrees" / f"{built.slug}-lane-{'abc'[index - 1]}"


def build(tmp_path: Path, *, explicit: str | None = None) -> Built:
    """Create (default or *explicit* topology), finalize, implement and approve three code WPs."""
    mission = make_default_mission(tmp_path, THREE_LANES, standing_on=_TARGET, explicit=explicit)
    code, payload = run_finalize(mission)
    assert code == 0, payload
    shim = tmp_path / "wp20_shim.py"
    shim.write_text(_SHIM, encoding="utf-8")
    built = Built(mission, shim)
    config = built.root / ".kittify" / "config.yaml"
    config.write_text(config.read_text(encoding="utf-8") + "auto_commit: false\n", encoding="utf-8")
    git(built.root, "add", ".kittify/config.yaml")
    git(built.root, "commit", "-qm", "fixture: no auto-commit")
    planning = built.coord_worktree if explicit is None else built.root
    (planning / built.rel / "plan.md").write_text("# Plan\n", encoding="utf-8")
    _commit_all(planning, "plan")
    analysis = tmp_path / "analysis.md"
    analysis.write_text(_ANALYSIS, encoding="utf-8")
    _ok(cli(built, "agent", "mission", "record-analysis", "--mission", built.slug, "--input-file", str(analysis)))
    for index in (1, 2, 3):
        _ok(cli(built, "agent", "action", "implement", f"WP0{index}", "--agent", "impl", "--mission", built.slug))
        _commit_all(built.coord_worktree, f"claim WP0{index}")
    for index, owned in enumerate(THREE_LANES, start=1):
        lane = _lane_worktree(built, index)
        (lane / owned).parent.mkdir(parents=True, exist_ok=True)
        (lane / owned).write_text(f"X = {index}\n", encoding="utf-8")
        git(lane, "add", owned)
        git(lane, "-c", "user.name=e", "-c", "user.email=e@x", "commit", "-qm", f"feat(WP0{index})")
        for to, agent, force in (("for_review", "impl", ("--force",)), ("in_review", "rev", ()), ("approved", "rev", ("--force",))):
            _ok(cli(built, "agent", "tasks", "move-task", f"WP0{index}", "--to", to, "--mission", built.slug, "--agent", agent, *force, "--note", agent))
    _commit_all(built.coord_worktree, "status")
    _commit_all(built.root, "status")
    return built


#: The fixture's approvals carry a review stamp, so no attestation is needed (or accepted).
_ATTEST: tuple[str, ...] = ()


def consolidate(built: Built, *extra: str, hooks: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return cli(built, "consolidate", "--mission", built.slug, *extra, hooks=hooks)


def target_file(built: Built, name: str) -> str:
    return git(built.root, "show", f"{_TARGET}:{built.rel}/{name}")


def target_meta(built: Built) -> dict[str, object]:
    meta: dict[str, object] = json.loads(target_file(built, "meta.json"))
    return meta


def branch_exists(built: Built, branch: str) -> bool:
    return bool(git(built.root, "branch", "--list", branch))


def _commit_window_a(built: Built) -> None:
    mission_dir = built.mission.coord_mission_dir
    (mission_dir / "spec.md").write_text((mission_dir / "spec.md").read_text(encoding="utf-8") + f"\n{_WINDOW_A_MARK}\n", encoding="utf-8")
    wp01 = next((mission_dir / "tasks").glob("WP01-*.md"))
    wp01.write_text(wp01.read_text(encoding="utf-8") + "\nWINDOW_A_TASK\n", encoding="utf-8")
    meta = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    meta["window_a_key"] = "A"
    (mission_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _commit_all(built.coord_worktree, "window A")


@pytest.fixture(scope="module")
def window_a_run(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Built, subprocess.CompletedProcess[str]]]:
    with pytest.MonkeyPatch.context() as mp:
        _quiet(mp)
        built = build(tmp_path_factory.mktemp("window-a"))
        _commit_window_a(built)
        yield built, consolidate(built, *_ATTEST)


@pytest.fixture(scope="module")
def window_b_run(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Built, subprocess.CompletedProcess[str]]]:
    with pytest.MonkeyPatch.context() as mp:
        _quiet(mp)
        built = build(tmp_path_factory.mktemp("window-b"))
        yield built, consolidate(built, *_ATTEST, hooks={"WP20_COMMIT_AFTER": "_phase_mission_to_target"})


@pytest.fixture(autouse=True)
def _quiet_status_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    _quiet(monkeypatch)


def _quiet(mp: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    mp.chdir(Path(_SRC).parent)
    mp.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


# ---------------------------------------------------------------------------
# T118: characterization (Windows A and C)
# ---------------------------------------------------------------------------


def test_characterize_default_mission_primary_windows(window_a_run: tuple[Built, subprocess.CompletedProcess[str]]) -> None:
    built, proc = window_a_run
    _ok(proc)
    # Window A: the landing carries the topic tip, PRIMARY edits included.
    assert _WINDOW_A_MARK in target_file(built, "spec.md")
    assert "WINDOW_A_TASK" in git(built.root, "show", f"{_TARGET}:{built.rel}/tasks/WP01-work.md")
    meta = target_meta(built)
    assert meta["window_a_key"] == "A"
    # Window C: the post-landing writes found the target checkout, not the topic holder.
    assert meta["mission_number"] == 1
    assert meta.get("baseline_merge_commit")
    for owned in THREE_LANES:
        git(built.root, "cat-file", "-e", f"{_TARGET}:{owned}")


def test_default_mission_consolidate_detects_coord_topology_and_bakes_on_target(window_a_run: tuple[Built, subprocess.CompletedProcess[str]]) -> None:
    built, proc = window_a_run
    _ok(proc)
    meta = target_meta(built)
    assert meta["mission_id"] and meta["mission_number"] == 1
    assert "Cleaned up mission/coordination branch + worktree" in proc.stdout
    assert not branch_exists(built, built.mission.topic)
    assert not built.coord_worktree.exists()
    assert not meta.get("coordination_branch"), "the coordination marker survived the teardown"


# ---------------------------------------------------------------------------
# T119: Window B, G2
# ---------------------------------------------------------------------------


def test_primary_commit_after_landing_before_teardown_reaches_target_or_refuses(window_b_run: tuple[Built, subprocess.CompletedProcess[str]]) -> None:
    built, proc = window_b_run
    if proc.returncode == 0:
        assert _WINDOW_B_MARK in target_file(built, "spec.md"), "the late PRIMARY commit was deleted with the topic branch"
        assert target_meta(built)["window_b_key"] == "B"
        assert not branch_exists(built, built.mission.topic)
    else:
        assert branch_exists(built, built.mission.topic), proc.stdout[-2000:]


def test_target_authored_mission_number_and_baseline_survive(window_b_run: tuple[Built, subprocess.CompletedProcess[str]]) -> None:
    built, proc = window_b_run
    _ok(proc)
    meta = target_meta(built)
    assert meta["mission_number"] == 1, "the topic branch's stale mission_number overwrote the target's bake"
    baseline = meta.get("baseline_merge_commit")
    assert isinstance(baseline, str) and baseline
    git(built.root, "merge-base", "--is-ancestor", baseline, _TARGET)


# ---------------------------------------------------------------------------
# NFR-002: resume and rollback
# ---------------------------------------------------------------------------


def _subdir(base: Path, name: str) -> Path:
    path = base / name
    path.mkdir()
    return path


@pytest.mark.timeout(900)
def test_resume_and_rollback_lose_no_primary_change(tmp_path: Path) -> None:
    # (1) Interrupted after the landing passed its gate, with a PRIMARY commit in the resumed late window.
    built = build(_subdir(tmp_path, "resume"))
    hooks = {"WP20_COMMIT_AFTER": "_phase_reconcile_before_teardown", "WP20_FAIL_BEFORE": "_phase_cleanup_worktrees_and_branches"}
    first = consolidate(built, *_ATTEST, hooks=hooks)
    assert first.returncode != 0
    assert branch_exists(built, built.mission.topic)
    _ok(consolidate(built, "--resume"))
    assert _WINDOW_B_MARK in target_file(built, "spec.md")
    meta = target_meta(built)
    assert meta["window_b_key"] == "B" and meta["mission_number"] == 1
    assert not branch_exists(built, built.mission.topic)

    # (2) A gate FAIL rolls the run back through the one rollback authority; the topic branch keeps every change.
    built = build(_subdir(tmp_path, "rollback"))
    _commit_window_a(built)
    base_tip = git(built.root, "rev-parse", _TARGET)
    failed = consolidate(built, *_ATTEST, hooks={"WP20_FAIL_BEFORE": "_phase_reconcile_before_teardown", "WP20_FAIL_KIND": "exit"})
    assert failed.returncode != 0
    assert git(built.root, "rev-parse", _TARGET) == base_tip, failed.stdout[-2000:]
    assert _WINDOW_A_MARK in git(built.root, "show", f"{built.mission.topic}:{built.rel}/spec.md")
    _ok(consolidate(built))
    assert _WINDOW_A_MARK in target_file(built, "spec.md")
    assert target_meta(built)["window_a_key"] == "A"


# ---------------------------------------------------------------------------
# Control and orchestrator-api parity
# ---------------------------------------------------------------------------


def test_explicit_lanes_with_coord_consolidate_unchanged(tmp_path: Path) -> None:
    built = build(tmp_path, explicit="lanes_with_coord")
    proc = _ok(consolidate(built, *_ATTEST))
    assert "PRIMARY change(s) made on the topic branch" not in proc.stdout
    tree = set(git(built.root, "ls-tree", "-r", "--name-only", _TARGET).splitlines())
    assert {*THREE_LANES, f"{built.rel}/spec.md", f"{built.rel}/meta.json", f"{built.rel}/lanes.json"} <= tree
    meta = target_meta(built)
    assert meta["mission_number"] == 1 and meta.get("baseline_merge_commit")
    assert meta.get("topology_source") == "explicit"


def test_primary_landing_through_orchestrator_api(tmp_path: Path) -> None:
    built = build(tmp_path)
    _commit_window_a(built)
    proc = cli(built, "orchestrator-api", "consolidate-mission", "--mission", built.slug, "--strategy", "squash")
    payload = json.loads(proc.stdout[proc.stdout.find("{") :])
    if payload.get("success"):
        assert _WINDOW_A_MARK in target_file(built, "spec.md")
        assert target_meta(built)["window_a_key"] == "A"
    else:
        # Pinned: no rollback door for this path; it refuses with its existing envelope (C-012).
        assert payload.get("error_code") == "PREFLIGHT_FAILED", payload
