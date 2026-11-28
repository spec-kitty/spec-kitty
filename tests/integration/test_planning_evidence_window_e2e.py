"""#7860 acceptance suite: a default Mission's planning lane is written, reviewed and evidenced on its Mission branch.

Background (#7860, P1). A Mission created without ``--topology`` mints one topic branch and settles
its topology at the first ``finalize-tasks`` by size; with more than one code lane it settles
``lanes_with_coord``, the topic branch becoming the coordination branch (ADR ``2026-11-06-3``).
Until the Mission lands, its PRIMARY partition, and with it every planning-artifact work package's
work, is written to that topic branch, the Mission branch (FR-061). The #6715 evidence axis
nevertheless ended a planning lane's window at the TARGET branch and ``implement`` named the
repository root checkout (on the target) as the workspace, so ``move-task --to for_review``
refused every planning work package with ``IMPLEMENTATION_MISSING`` (reproduced in
spec-kitty-open-packs, Mission ``pack-doctor-alignment``).

Operator ruling A' (2026-11-25, recorded on #7860) is in force: before the landing, ``implement``
places such a planning work package in the coordination worktree (the checkout holding the
Mission branch), and its evidence window runs from the commit that introduced its claim to the
Mission branch. Work committed on the target only (the old guidance) is refused with the in-flight
remedy (ruling "guidance only": no migration).

* :func:`test_planning_work_on_the_topic_branch_moves_into_review` (SC-001, SC-005) -- the
  reproduction: ``implement`` names the coordination worktree and the Mission branch; the owned
  file committed there moves into review unforced.
* :func:`test_a_removed_coordination_worktree_fails_closed` (NFR-002, residual 8a) -- with the
  coordination worktree gone, both claim verbs refuse at Mission lookup; nothing falls back.

The finer cases (hollow, sibling, pre-existing, target-only, explicit topology) are pinned on the
evidence window itself in ``tests/consolidation/test_wp_evidence_planning_window.py``.

Drives the REAL CLI end to end in an isolated HOME. The bookkeeping helper stages only the files
the CLI writes (never an owned file), so a status-residue commit can never fake the evidence.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

# Each case drives a dozen real CLI calls on a fresh repository; the default budget is too tight
# on a loaded runner, so the cases carry their own (pytest.ini: mark, never raise the default).
pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(900)]

_CLI = [sys.executable, "-m", "specify_cli"]
_PLANNING_OWNED = "kitty-specs/{slug}/research/notes.md"
_SIBLING_OWNED = "kitty-specs/{slug}/research/other.md"
_MISSING = "IMPLEMENTATION_MISSING"
#: The files the CLI itself writes in the Mission directory (status, metadata, manifests,
#: subtask checkboxes). Owned planning files (``research/``) are never in this list.
_TOOL_WRITTEN = (
    "status.events.jsonl",
    "status.json",
    "meta.json",
    "lanes.json",
    "analysis-report.md",
    "acceptance-matrix.json",
    "issue-matrix.json",
    "decisions",
    "tasks.md",
    "tasks",
)
_WORKSPACE_LINE = re.compile(r"Workspace:\s+(?:cd\s+)?(\S+)")


@dataclass(frozen=True)
class _Mission:
    repo: Path
    env: dict[str, str]
    slug: str
    topic_branch: str
    topic_checkout: Path

    @property
    def feature_dir(self) -> Path:
        """The Mission directory in the checkout holding its PRIMARY partition."""
        return self.topic_checkout / "kitty-specs" / self.slug

    @property
    def owned(self) -> str:
        return _PLANNING_OWNED.format(slug=self.slug)


def _env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        HOME=str(home / "home"),
        XDG_CONFIG_HOME=str(home / "xc"),
        XDG_CACHE_HOME=str(home / "xcache"),
        XDG_DATA_HOME=str(home / "xd"),
        SPEC_KITTY_NO_UPGRADE_CHECK="1",
        SPEC_KITTY_WORKTREE_REMOVAL_DELAY="0",
        SPEC_KITTY_ENABLE_SAAS_SYNC="0",
        # Wide enough that rich never wraps a SHA, a branch or a phrase the assertions read.
        COLUMNS="500",
    )
    for key in ("home", "xc", "xcache", "xd"):
        (home / key).mkdir(parents=True, exist_ok=True)
    return env


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _sk(mission: _Mission | tuple[Path, dict[str, str]], *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    repo, env = (mission.repo, mission.env) if isinstance(mission, _Mission) else mission
    proc = subprocess.run([*_CLI, *args], cwd=repo, env=env, capture_output=True, text=True, timeout=400)
    if check and proc.returncode != 0:
        raise AssertionError(f"fixture setup step failed: spec-kitty {' '.join(args)}\nrc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc


def _wp_file(wp: str, subtask: str, owned: str, *, planning: bool = False) -> str:
    surface = owned.split("*")[0]
    extra = "execution_mode: planning_artifact\n" if planning else ""
    return (
        f"---\nwork_package_id: {wp}\ntitle: {wp}\ndependencies: []\nrequirement_refs: [FR-001]\n{extra}"
        f"authoritative_surface: {surface}\nowned_files:\n  - {owned}\ncreate_intent:\n  - {owned}\nsubtasks:\n  - {subtask}\n---\n# {wp}\n\n- [ ] {subtask} do\n"
    )


_WPS = (
    ("WP01", "T1", "src/m1/**", False),
    ("WP02", "T2", _PLANNING_OWNED, True),
    ("WP03", "T3", "src/m3/**", False),
    ("WP04", "T4", "src/m4/**", False),
    ("WP05", "T5", _SIBLING_OWNED, True),
)


def setup_default_mission(tmp_path: Path, *, topology: str | None = None) -> _Mission:
    """Three code WPs (three lanes) and two planning WPs sharing ``lane-planning``.

    WP02 owns ``kitty-specs/<slug>/research/notes.md``; its sibling WP05 owns ``research/other.md``.

    Without *topology* the Mission is a default Mission: ``finalize-tasks`` settles it
    ``lanes_with_coord`` by size, its topic branch becoming the coordination branch, checked out
    in the coordination worktree. With *topology* it is an explicit-topology Mission (FR-006).
    """
    env = _env(tmp_path)
    if topology is not None:
        env["SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"] = "1"
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    _sk((repo, env), "init", "--ai", "claude", "--non-interactive", check=True)
    (repo / "README.md").write_text("# fixture\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    explicit = ("--topology", topology) if topology is not None else ()
    created = _sk(
        (repo, env),
        *("agent", "mission", "create", "fx", "--mission-type", "software-dev", *explicit),
        *("--branch-strategy", "already-confirmed", "--target-branch", "main", "--friendly-name", "fx"),
        *("--purpose-tldr", "fx", "--purpose-context", "QA fixture.", "--json"),
        check=True,
    )
    slug = json.loads(created.stdout)["mission_slug"]
    fd = repo / "kitty-specs" / slug
    (fd / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: things work.\n", encoding="utf-8")
    (fd / "plan.md").write_text("# Plan\n\nModules.\n", encoding="utf-8")
    (fd / "tasks").mkdir(exist_ok=True)
    sections = "".join(f"## Work Package {wp}: {wp}\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] {t} do\n\n" for wp, t, _o, _p in _WPS)
    (fd / "tasks.md").write_text(f"# Tasks\n\n{sections}", encoding="utf-8")
    for wp, subtask, owned, planning in _WPS:
        (fd / "tasks" / f"{wp}-work.md").write_text(_wp_file(wp, subtask, owned.format(slug=slug), planning=planning), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "planning")
    planning_branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    _sk((repo, env), "agent", "mission", "finalize-tasks", "--mission", slug, "--json", check=True)
    mission = _Mission(repo, env, slug, planning_branch, _checkout_of(repo, planning_branch))
    (tmp_path / "analysis.md").write_text("# Analysis\n\nNo blocking findings.\n", encoding="utf-8")
    _sk(mission, "agent", "mission", "record-analysis", "--mission", slug, "--input-file", str(tmp_path / "analysis.md"), check=True)
    _commit_bookkeeping(mission)
    return mission


def _checkout_of(repo: Path, branch: str) -> Path:
    """The worktree that has *branch* checked out (the settlement moves the topic branch into the coordination worktree)."""
    current: Path | None = None
    for line in _git(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            current = Path(line.removeprefix("worktree "))
        elif line == f"branch refs/heads/{branch}" and current is not None:
            return current
    raise AssertionError(f"fixture: no checkout of {branch}")


def _commit_bookkeeping(mission: _Mission) -> None:
    """Commit only the files the CLI writes in the Mission directory; an owned file is never staged here."""
    checkout = mission.topic_checkout
    paths = [f"kitty-specs/{mission.slug}/{name}" for name in _TOOL_WRITTEN if (checkout / "kitty-specs" / mission.slug / name).exists()]
    if paths:
        _git(checkout, "add", "--", *paths)
    staged = _git(checkout, "diff", "--cached", "--name-only")
    owned = {mission.owned, _SIBLING_OWNED.format(slug=mission.slug)}
    assert not owned.intersection(staged.splitlines()), f"fixture: the bookkeeping helper must never stage the owned file; staged={staged}"
    if staged:
        _git(checkout, "commit", "-qm", "status residue")


def _meta(mission: _Mission) -> dict[str, object]:
    loaded: dict[str, object] = json.loads((mission.feature_dir / "meta.json").read_text(encoding="utf-8"))
    return loaded


def _implement_planning_wp(mission: _Mission, wp: str = "WP02") -> tuple[Path, str]:
    """Claim *wp* through ``agent action implement``; return the workspace it names and its full output."""
    implemented = _sk(mission, "agent", "action", "implement", wp, "--agent", "alice", "--mission", mission.slug, check=True)
    output = implemented.stdout + implemented.stderr
    found = _WORKSPACE_LINE.search(output)
    assert found is not None, f"implement must name the workspace. output:\n{output[-3000:]}"
    _commit_bookkeeping(mission)
    return Path(found.group(1)), output


def _assert_default_mission(mission: _Mission) -> None:
    meta = _meta(mission)
    assert meta.get("topology") == "lanes_with_coord", f"fixture: the size rule must settle lanes_with_coord; meta={meta}"
    assert meta.get("topology_source") == "default", f"fixture: a Mission created without --topology; meta={meta}"
    assert meta.get("coordination_branch") == mission.topic_branch, f"fixture: the topic branch is the coordination branch; meta={meta}"
    assert mission.topic_checkout != mission.repo, "fixture: the settlement moves the Mission branch into the coordination worktree"


def _write_and_commit(checkout: Path, relpath: str, text: str, message: str) -> str:
    target = checkout / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    _git(checkout, "add", "--", relpath)
    _git(checkout, "commit", "-qm", message)
    return _git(checkout, "rev-parse", "HEAD")


def _claim_planning_wp(mission: _Mission) -> str:
    """Claim WP02 of a settled default Mission and return its owned path (kept for ``tests/lanes/test_planning_claim_base.py``)."""
    _assert_default_mission(mission)
    _implement_planning_wp(mission)
    return mission.owned


def _commit_owned(checkout: Path, relpath: str) -> None:
    """Commit WP02's owned file in *checkout* (kept for ``tests/lanes/test_planning_claim_base.py``)."""
    _write_and_commit(checkout, relpath, "# WP02 research\n", "feat(WP02): research notes")


def _move_into_review(mission: _Mission, wp: str = "WP02", subtask: str = "T2") -> subprocess.CompletedProcess[str]:
    _sk(mission, "agent", "tasks", "mark-status", subtask, "--status", "done", "--mission", mission.slug)
    _commit_bookkeeping(mission)
    return _sk(mission, "agent", "tasks", "move-task", wp, "--to", "for_review", "--agent", "alice", "--note", "done", "--mission", mission.slug)


def _flat(proc: subprocess.CompletedProcess[str]) -> str:
    """The command's whole output with every run of whitespace collapsed (a wrapped line still matches)."""
    return " ".join((proc.stdout + proc.stderr).split())


def _on_branch(mission: _Mission, branch: str, relpath: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{branch}:{relpath}"], cwd=mission.repo, capture_output=True).returncode == 0


def test_planning_work_on_the_topic_branch_moves_into_review(tmp_path: Path) -> None:
    """SC-001 / SC-005: implement names the coordination worktree; work committed there moves into review unforced."""
    mission = setup_default_mission(tmp_path)
    _assert_default_mission(mission)

    workspace, implement_output = _implement_planning_wp(mission)

    assert workspace.resolve() == mission.topic_checkout.resolve(), f"implement must name the coordination worktree. output:\n{implement_output[-3000:]}"
    assert mission.topic_branch in implement_output, f"implement must name the Mission branch. output:\n{implement_output[-3000:]}"
    owned_sha = _write_and_commit(workspace, mission.owned, "# WP02 research\n", "feat(WP02): research notes")
    assert not _on_branch(mission, "main", mission.owned), "fixture: the target branch must not carry the planning work before the landing"

    moved = _move_into_review(mission)
    output = _flat(moved)

    assert _MISSING not in output, f"planning work on the Mission branch is the work package's evidence. output:\n{output[-3000:]}"
    assert moved.returncode == 0, f"the unforced move into review must pass. output:\n{output[-3000:]}"
    _assert_review_range_holds(mission, owned_sha)


def _assert_review_range_holds(mission: _Mission, owned_sha: str) -> None:
    """C-001 ratchet: the review range (not folded onto the shared reader until #5604) agrees with the one authority.

    ``review/wp_range.py`` reads ``default_mission_primary_ref`` on its own (it assumes "not
    landed"); this pins that, for the reproduction, its range is available, not withheld as
    bookkeeping-only, and lists the owned commit, which sits only on the branch
    :func:`mission_runtime.planning_write_ref` names. Read only.
    """
    import mission_runtime
    from specify_cli.review.wp_range import RangeGap, RangeStatus, resolve_wp_review_range

    assert mission_runtime.planning_write_ref(mission.repo, mission.slug, "main").branch == mission.topic_branch
    review = resolve_wp_review_range(mission.repo, mission.slug, "WP02", owned_files=[mission.owned])

    assert review.status is not RangeStatus.UNAVAILABLE, f"the review range must be available; gap={review.gap}"
    assert review.gap != RangeGap.PLANNING_RANGE_BOOKKEEPING_ONLY, review
    assert owned_sha in {commit.sha for commit in review.commits}, f"the review range must list the owned commit {owned_sha}; range={review}"


_POLICY = json.dumps(
    {
        "orchestrator_id": "qa-orch",
        "orchestrator_version": "0.1.0",
        "agent_family": "claude",
        "approval_mode": "supervised",
        "sandbox_mode": "sandbox",
        "network_mode": "restricted",
        "dangerous_flags": [],
    }
)


def test_a_removed_coordination_worktree_fails_closed(tmp_path: Path) -> None:
    """Residual 8a (pinned, not fixed): with the coordination worktree gone, both claim verbs refuse at Mission lookup.

    ``lanes.json`` and the Mission directory exist only on the Mission branch, so the Mission
    lookup refuses before the workspace resolver can say ``PLANNING_CHECKOUT_MISSING``: the
    orchestrator API answers a lookup code (``WP_NOT_FOUND`` here, ``MISSION_NOT_FOUND`` when no
    Mission directory is found at all) and ``agent action implement`` refuses with "Error locating
    work package: ... has no tasks directory".
    Both fail closed: no claim is recorded, no workspace is named and nothing falls back to the
    repository root checkout. The lookup refusal does not yet name contract C1's remedy
    (``spec-kitty doctor coordination --mission <slug> --fix``); recorded as a residual in
    ``docs/migrations/planning-lane-write-branch.md``. When the lookup learns that remedy, update
    this pin.
    """
    mission = setup_default_mission(tmp_path)
    _git(mission.repo, "worktree", "remove", "--force", str(mission.topic_checkout))

    implemented = _sk(mission, "agent", "action", "implement", "WP02", "--agent", "alice", "--mission", mission.slug)
    started = _sk(mission, "orchestrator-api", "start-implementation", "--mission", mission.slug, "--wp", "WP02", "--actor", "alice", "--policy", _POLICY)
    implement_output = _flat(implemented)

    assert implemented.returncode != 0, f"implement must refuse without the Mission branch checkout. output:\n{implement_output[-3000:]}"
    # Today's order: the work package lookup refuses first ("no tasks directory"), not the resolver.
    assert "Error locating work package" in implement_output, implement_output[-3000:]
    assert f"Workspace: {mission.repo}" not in implement_output and f"Workspace: cd {mission.repo} " not in implement_output, implement_output[-3000:]
    assert started.returncode != 0, started.stdout[-3000:]
    # A lookup refusal, never a workspace: WP_NOT_FOUND on this real-CLI shape (the repository root
    # checkout no longer carries the Mission's work packages); MISSION_NOT_FOUND where no Mission
    # directory is found at all (WP03 review, residual 8a).
    assert json.loads(started.stdout)["error_code"] in {"WP_NOT_FOUND", "MISSION_NOT_FOUND"}, started.stdout[-3000:]
    claim_refs = _git(mission.repo, "for-each-ref", "--format=%(refname)", "refs/spec-kitty/")
    assert "WP02" not in claim_refs, f"no claim base may be recorded; refs={claim_refs}"
