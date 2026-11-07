"""S8 (#7283): per-WP approval windows bound a ``single_branch`` Mission at consolidate.

ADR ``2026-10-04-5`` Amendment 2026-11-06. A ``single_branch`` Mission with a minted Mission
branch is bounded like a code lane:

* tier 1 -- content committed after the newest approval stamp refuses ``LANE_MOVED_AFTER_APPROVAL``;
* tier 2 -- every content commit in ``claim_base..mission_branch`` lies in some approved work
  package's window ``(O_k, S_k]``, else ``LANE_MOVED_AFTER_APPROVAL`` naming the commit and the
  work package approved before it;
* an unstamped approval refuses ``APPROVAL_STAMP_MISSING`` until it is attested, a rebased Mission
  branch refuses ``APPROVAL_STAMP_NOT_ON_LANE``;
* the gate re-check reads the Mission branch (never ``lane-planning``'s alias, which resolves to
  the target) and a refusal there restores every branch through the one rollback authority.

The Mission is built once through the real CLI (``init``, ``agent mission create --topology
single_branch`` on protected ``main``, ``finalize-tasks``) and copied per test. Lifecycle moves run
in-process (so the unstamped case can break the best-effort stamp probe); ``consolidate`` runs as
a real subprocess through the production entry point.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.status import app as status_app
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.status import lane_head
from tests._support.ansi import strip_ansi

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

TARGET = "main"
_CLI = [sys.executable, "-m", "specify_cli"]
_MOVED = "LANE_MOVED_AFTER_APPROVAL"
_MISSING = "APPROVAL_STAMP_MISSING"
_NOT_ON_LANE = "APPROVAL_STAMP_NOT_ON_LANE"
_BANNER = "Reconciliation verified"
_REVIEW = json.dumps({"reviewer": "bob", "verdict": "approved", "reference": "PR#1"})
_NO_HOOKS = ("-c", "core.hooksPath=/dev/null")
_MARKER = re.compile(r"INJECTED_SHA=([0-9a-f]{40})")

_runner = CliRunner()

# Runs in the subprocess: commit on the Mission branch right after the claim was captured (the first
# mutating phase), then start the real CLI.
_LAUNCHER = """\
import os
import subprocess
import sys

from specify_cli import main
from specify_cli.consolidation import executor

REPO, LATE_PATH = sys.argv[1:3]
REAL = executor._phase_merge_lanes


def _git(*args):
    return subprocess.run(["git", "-C", REPO, "-c", "core.hooksPath=/dev/null", *args], capture_output=True, text=True, check=True).stdout.strip()


def _inject_then_merge(run):
    late_file = os.path.join(REPO, LATE_PATH)
    os.makedirs(os.path.dirname(late_file), exist_ok=True)
    with open(late_file, "w", encoding="utf-8") as handle:
        handle.write("LATE = True\\n")
    _git("add", LATE_PATH)
    _git("commit", "-qm", "feat: unreviewed change added during consolidate")
    print(f"INJECTED_SHA={_git('rev-parse', 'HEAD')}", flush=True)
    REAL(run)


executor._phase_merge_lanes = _inject_then_merge
sys.argv = ["spec-kitty", *sys.argv[3:]]
main()
"""


# --------------------------------------------------------------------------- fixture


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *_NO_HOOKS, *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def cli_env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        HOME=str(home / "home"),
        XDG_CONFIG_HOME=str(home / "xc"),
        XDG_CACHE_HOME=str(home / "xcache"),
        XDG_DATA_HOME=str(home / "xd"),
        SPEC_KITTY_NO_UPGRADE_CHECK="1",
        SPEC_KITTY_WORKTREE_REMOVAL_DELAY="0",
        SPEC_KITTY_ORIGIN_CHECK="off",
    )
    # A protected-branch override would make create skip the Mission-branch mint.
    env.pop("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", None)
    for key in ("home", "xc", "xcache", "xd"):
        (home / key).mkdir(parents=True, exist_ok=True)
    return env


def _sk(repo: Path, env: dict[str, str], *args: str) -> str:
    proc = subprocess.run([*_CLI, *args], cwd=repo, env=env, capture_output=True, text=True, timeout=400)
    if proc.returncode != 0:
        raise AssertionError(f"spec-kitty {' '.join(args)} failed rc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc.stdout


def _wp_file(wp: str, module: str, subtask: str) -> str:
    return (
        f"---\nwork_package_id: {wp}\ntitle: {wp} {module}\ndependencies: []\nrequirement_refs: [FR-001]\n"
        f"authoritative_surface: src/{module}/\nowned_files:\n  - src/{module}/**\nsubtasks:\n  - {subtask}\n---\n"
        f"# {wp} {module}\n\n- [ ] {subtask} do {module}\n"
    )


def build_template(base: Path, *, commit_to_target: bool) -> tuple[Path, str]:
    """A ``single_branch`` Mission on protected ``main`` with two code work packages (WP01 owns src/m1, WP02 src/m2)."""
    env = cli_env(base)
    repo = base / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", TARGET)
    git(repo, "config", "user.name", "QA")
    git(repo, "config", "user.email", "qa@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    _sk(repo, env, "init", "--ai", "claude", "--non-interactive")
    (repo / "src").mkdir()
    (repo / "src" / "shared.py").write_text("A = 1\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "init")
    extra = ("--commit-to-target",) if commit_to_target else ()
    created = _sk(
        repo,
        env,
        *("agent", "mission", "create", "fx", "--mission-type", "software-dev", "--topology", "single_branch", *extra),
        *("--branch-strategy", "already-confirmed", "--target-branch", TARGET, "--friendly-name", "fx"),
        *("--purpose-tldr", "fx", "--purpose-context", "QA fixture.", "--json"),
    )
    slug = str(json.loads(created)["mission_slug"])
    fd = repo / "kitty-specs" / slug
    (fd / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: things work.\n", encoding="utf-8")
    (fd / "plan.md").write_text("# Plan\n\nModules.\n", encoding="utf-8")
    (fd / "tasks").mkdir(exist_ok=True)
    (fd / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01: m1\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] T1 do m1\n\n"
        "## Work Package WP02: m2\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] T2 do m2\n",
        encoding="utf-8",
    )
    (fd / "tasks" / "WP01-m1.md").write_text(_wp_file("WP01", "m1", "T1"), encoding="utf-8")
    (fd / "tasks" / "WP02-m2.md").write_text(_wp_file("WP02", "m2", "T2"), encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "planning")
    _sk(repo, env, "agent", "mission", "finalize-tasks", "--mission", slug, "--json")
    (base / "analysis.md").write_text("# Analysis\n\nNo blocking findings.\n", encoding="utf-8")
    _sk(repo, env, "agent", "mission", "record-analysis", "--mission", slug, "--input-file", str(base / "analysis.md"))
    settle(repo)
    return repo, slug


class Mission:
    """One copied Mission checkout: the repository, its slug and the CLI environment."""

    def __init__(self, repo: Path, slug: str, home: Path) -> None:
        self.repo = repo
        self.slug = slug
        self.env = cli_env(home)

    @property
    def mission_branch(self) -> str:
        meta = json.loads((self.repo / "kitty-specs" / self.slug / "meta.json").read_text(encoding="utf-8"))
        return str(meta["mission_branch"])


@pytest.fixture(scope="module")
def minted_template(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    repo, slug = build_template(tmp_path_factory.mktemp("minted"), commit_to_target=False)
    meta = json.loads((repo / "kitty-specs" / slug / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("mission_branch") not in (None, TARGET), "fixture: create must mint a Mission branch on protected main"
    return repo, slug


def checkout(template: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Mission:
    source, slug = template
    repo = tmp_path / "repo"
    shutil.copytree(source, repo, symlinks=True)
    monkeypatch.chdir(repo)
    for key, value in cli_env(tmp_path).items():
        if key.startswith(("HOME", "XDG_", "SPEC_KITTY_")):
            monkeypatch.setenv(key, value)
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    return Mission(repo, slug, tmp_path)


@pytest.fixture
def mission(minted_template: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Mission:
    return checkout(minted_template, tmp_path, monkeypatch)


# --------------------------------------------------------------------------- lifecycle steps


def settle(repo: Path) -> None:
    """Commit whatever the CLI left in ``kitty-specs`` (status rows, ticked subtasks): Mission bookkeeping."""
    if git(repo, "status", "--porcelain", "--", "kitty-specs"):
        git(repo, "add", "-A", "kitty-specs")
        git(repo, "commit", "-qm", "chore: status bookkeeping")


def _invoke(app: typer.Typer, args: list[str]) -> tuple[int, str]:
    result = _runner.invoke(app, args)
    return result.exit_code, strip_ansi(result.output + (result.stderr if result.stderr_bytes is not None else ""))


def move(m: Mission, wp: str, to: str, agent: str, *extra: str) -> None:
    code, out = _invoke(tasks_app, ["move-task", wp, "--to", to, "--agent", agent, "--note", f"{to} by {agent}", "--mission", m.slug, *extra])
    assert code == 0, out
    settle(m.repo)


def emit(m: Mission, wp: str, to: str, actor: str, *extra: str) -> None:
    code, out = _invoke(status_app, ["emit", wp, "--to", to, "--actor", actor, "--mission", m.slug, *extra])
    assert code == 0, out
    settle(m.repo)


def commit_file(m: Mission, rel: str, content: str, message: str) -> str:
    path = m.repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    git(m.repo, "add", rel)
    git(m.repo, "commit", "-qm", message)
    return git(m.repo, "rev-parse", "HEAD")


_MODULE = {"WP01": ("m1", "T1"), "WP02": ("m2", "T2")}


def claim(m: Mission, wp: str) -> None:
    move(m, wp, "in_progress", "alice")


def implement(m: Mission, wp: str, *, revision: int = 1) -> str:
    """alice commits real work in *wp*'s owned files and ticks its subtask."""
    module, subtask = _MODULE[wp]
    sha = commit_file(m, f"src/{module}/real.py", f"VALUE = {wp!r}\nREVISION = {revision}\n", f"feat({wp}): implement {module} r{revision}")
    code, out = _invoke(tasks_app, ["mark-status", subtask, "--status", "done", "--mission", m.slug])
    assert code == 0, out
    settle(m.repo)
    return sha


def submit(m: Mission, wp: str) -> None:
    """Hand *wp* to review: a forced ``for_review`` (the commit gate is not under test), then bob's unforced review claim."""
    emit(m, wp, "for_review", "alice", "--force", "--reason", "handed to review")
    emit(m, wp, "in_review", "bob")


def approve(m: Mission, wp: str) -> None:
    emit(m, wp, "approved", "bob", "--review-result-json", _REVIEW)


def send_back(m: Mission, wp: str) -> None:
    move(m, wp, "in_progress", "alice", "--force")


def build_and_approve(m: Mission, wp: str) -> None:
    claim(m, wp)
    implement(m, wp)
    submit(m, wp)
    approve(m, wp)


# --------------------------------------------------------------------------- consolidate


def consolidate(m: Mission, *extra: str) -> tuple[int, str]:
    proc = subprocess.run(
        [*_CLI, "consolidate", "--mission", m.slug, "--yes", *extra],
        cwd=m.repo,
        env=m.env,
        capture_output=True,
        text=True,
        timeout=400,
    )
    return proc.returncode, " ".join((proc.stdout + "\n" + proc.stderr).split())


def tip(m: Mission, ref: str) -> str:
    return git(m.repo, "rev-parse", ref)


def on_target(m: Mission, rel: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{TARGET}:{rel}"], cwd=m.repo, capture_output=True, check=False).returncode == 0


def assert_refused(m: Mission, rc: int, out: str, target_before: str, code: str) -> None:
    assert rc == 1, f"expected exit 1 ({code}), got {rc}:\n{out}"
    assert code in out, f"expected {code}:\n{out}"
    assert _BANNER not in out
    assert tip(m, TARGET) == target_before, "a claim-time refusal must not move the target"


def assert_landed(m: Mission, rc: int, out: str) -> None:
    assert rc == 0, f"expected the Mission to consolidate, got {rc}:\n{out}"
    assert _MOVED not in out and _MISSING not in out and _NOT_ON_LANE not in out, out
    assert on_target(m, "src/m1/real.py")


# --------------------------------------------------------------------------- T067: claim scenarios


def test_late_commit_after_last_approval_refuses(mission: Mission) -> None:
    """Scenario 1 (tier 1): WP01 approved, then content X on the Mission branch."""
    build_and_approve(mission, "WP01")
    build_and_approve(mission, "WP02")
    late = commit_file(mission, "src/m1/late.py", "LATE = 1\n", "feat: unreviewed change after the last approval")
    before = tip(mission, TARGET)

    rc, out = consolidate(mission)

    assert_refused(mission, rc, out, before, _MOVED)
    assert late[:7] in out, f"the refusal must name the late commit:\n{out}"
    assert mission.slug in out, "the printed recovery commands carry the Mission slug"
    assert not on_target(mission, "src/m1/late.py")


def test_commit_between_two_approvals_refuses_naming_preceding_wp(mission: Mission) -> None:
    """Scenario 2 (tier 2): WP01 approved, X, WP02 claimed after X and approved: X is in no window."""
    build_and_approve(mission, "WP01")
    late = commit_file(mission, "src/m1/late.py", "LATE = 1\n", "feat: unreviewed change between two approvals")
    build_and_approve(mission, "WP02")
    before = tip(mission, TARGET)

    rc, out = consolidate(mission)

    assert_refused(mission, rc, out, before, _MOVED)
    assert late[:7] in out, f"the refusal must name the commit outside every window:\n{out}"
    assert "WP01" in out, f"the refusal must name the work package approved before the commit:\n{out}"
    assert "Send WP01 back for review and approve it again, or revert the commit" in out, out


def test_overlapping_review_passes(mission: Mission) -> None:
    """Scenario 3: WP02 committed while WP01 was under review; both approved. No false refusal."""
    claim(mission, "WP01")
    implement(mission, "WP01")
    submit(mission, "WP01")
    claim(mission, "WP02")
    implement(mission, "WP02")
    approve(mission, "WP01")
    submit(mission, "WP02")
    approve(mission, "WP02")

    rc, out = consolidate(mission)

    assert_landed(mission, rc, out)


def test_rework_after_later_approval_passes(mission: Mission) -> None:
    """WP01 approved, WP02 approved, then WP01 reworked and approved again: the rework is in WP01's window."""
    build_and_approve(mission, "WP01")
    build_and_approve(mission, "WP02")
    send_back(mission, "WP01")
    implement(mission, "WP01", revision=2)
    submit(mission, "WP01")
    approve(mission, "WP01")

    rc, out = consolidate(mission)

    assert_landed(mission, rc, out)


def test_reapproval_lifts_refusal(mission: Mission) -> None:
    """Scenario 4: the scenario-2 refusal, then WP01 sent back and approved again: the next run passes."""
    build_and_approve(mission, "WP01")
    commit_file(mission, "src/m1/late.py", "LATE = 1\n", "feat: unreviewed change between two approvals")
    build_and_approve(mission, "WP02")
    before = tip(mission, TARGET)
    rc, out = consolidate(mission)
    assert_refused(mission, rc, out, before, _MOVED)

    send_back(mission, "WP01")
    submit(mission, "WP01")
    approve(mission, "WP01")
    rc, out = consolidate(mission)

    assert_landed(mission, rc, out)
    assert on_target(mission, "src/m1/late.py"), "the re-reviewed commit lands"


# --------------------------------------------------------------------------- T068: legacy, gate and residuals


@pytest.fixture
def broken_stamp(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """While active, the best-effort stamp probe finds nothing: a transition is persisted unstamped (a pre-upgrade approval)."""
    real = lane_head._resolve_lane_head
    monkeypatch.setattr(lane_head, "_resolve_lane_head", lambda **_kwargs: None)
    yield
    monkeypatch.setattr(lane_head, "_resolve_lane_head", real)


def test_unstamped_approval_refuses_then_attest_lifts(mission: Mission, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 5: an unstamped approval refuses APPROVAL_STAMP_MISSING; the per-WP attestation lifts it."""
    build_and_approve(mission, "WP02")
    claim(mission, "WP01")
    implement(mission, "WP01")
    submit(mission, "WP01")
    with monkeypatch.context() as patch:
        patch.setattr(lane_head, "_resolve_lane_head", lambda **_kwargs: None)
        approve(mission, "WP01")
    before = tip(mission, TARGET)

    rc, out = consolidate(mission)

    assert_refused(mission, rc, out, before, _MISSING)
    assert "WP01" in out and "--attest-approved-reviewed WP01" in out, out

    rc, out = consolidate(mission, "--attest-approved-reviewed", "WP01", "--attest-reason", "reviewed in PR #123")

    assert_landed(mission, rc, out)


def test_rebased_mission_branch_refuses_stamp_not_on_lane(mission: Mission) -> None:
    """A Mission branch rewritten after approval refuses APPROVAL_STAMP_NOT_ON_LANE."""
    build_and_approve(mission, "WP01")
    build_and_approve(mission, "WP02")
    branch = mission.mission_branch
    git(mission.repo, "checkout", "-q", TARGET)
    commit_file(mission, "docs/unrelated.md", "unrelated\n", "docs: an unrelated change on the target")
    git(mission.repo, "checkout", "-q", branch)
    git(mission.repo, "rebase", "-q", TARGET)
    before = tip(mission, TARGET)

    rc, out = consolidate(mission)

    assert_refused(mission, rc, out, before, _NOT_ON_LANE)


def test_gate_recheck_mid_run_commit_rolls_back(mission: Mission) -> None:
    """Scenario 6: a commit lands on the Mission branch between claim and gate; the gate refuses and every branch is restored."""
    build_and_approve(mission, "WP01")
    build_and_approve(mission, "WP02")
    branch = mission.mission_branch
    before = {ref: tip(mission, ref) for ref in (TARGET, branch)}
    launcher = mission.repo.parent / "inject_during_consolidate.py"
    launcher.write_text(_LAUNCHER, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(launcher), str(mission.repo), "src/m2/late.py", "consolidate", "--mission", mission.slug, "--yes"],
        cwd=mission.repo,
        env=mission.env,
        capture_output=True,
        text=True,
        timeout=400,
    )
    out = " ".join((proc.stdout + "\n" + proc.stderr).split())

    marker = _MARKER.search(out)
    assert marker is not None, f"the launcher did not report the injection:\n{out}"
    assert proc.returncode != 0, f"a commit added during the run must be refused at the gate:\n{out}"
    assert _MOVED in out and marker.group(1)[:7] in out, f"the gate must name the mid-run commit:\n{out}"
    assert _BANNER not in out
    assert tip(mission, TARGET) == before[TARGET], "the rollback authority must restore the target"
    assert not on_target(mission, "src/m2/late.py")


def test_own_bookkeeping_commits_never_refuse(mission: Mission) -> None:
    """Status bookkeeping committed after the last approval, and the run's own bookkeeping, never refuse."""
    build_and_approve(mission, "WP01")
    build_and_approve(mission, "WP02")
    commit_file(mission, f"kitty-specs/{mission.slug}/notes.md", "notes\n", "chore: Mission notes after approval")

    rc, out = consolidate(mission)

    assert_landed(mission, rc, out)
    assert _BANNER in out


def test_target_merge_into_mission_branch_never_refuses(mission: Mission) -> None:
    """A merge of the target into the Mission branch after the approvals is tool-made movement, never content."""
    build_and_approve(mission, "WP01")
    build_and_approve(mission, "WP02")
    branch = mission.mission_branch
    git(mission.repo, "checkout", "-q", TARGET)
    commit_file(mission, "docs/unrelated.md", "unrelated\n", "docs: an unrelated change on the target")
    git(mission.repo, "checkout", "-q", branch)
    git(mission.repo, "merge", "-q", "--no-ff", "--no-edit", TARGET)

    rc, out = consolidate(mission)

    assert_landed(mission, rc, out)


@pytest.fixture(scope="module")
def commit_to_target_template(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    return build_template(tmp_path_factory.mktemp("ctt"), commit_to_target=True)


@pytest.mark.xfail(strict=True, reason="FR-078 residual: commit-to-target single_branch is unbounded")
def test_commit_to_target_unbounded_residual(commit_to_target_template: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The same late commit as scenario 1 on a commit-to-target Mission is NOT refused: the residual stays visible."""
    m = checkout(commit_to_target_template, tmp_path, monkeypatch)
    build_and_approve(m, "WP01")
    build_and_approve(m, "WP02")
    commit_file(m, "src/m1/late.py", "LATE = 1\n", "feat: unreviewed change after the last approval")

    rc, out = consolidate(m)

    assert rc == 1 and _MOVED in out, out
