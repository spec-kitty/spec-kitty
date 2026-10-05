"""Shared real-git fixtures for the primary-owned bookkeeping mission (#5457).

WP02 to WP05 drive their red tests off the two builders here, so no work
package hand-rolls its own drifting copy of the broken state:

* :func:`build_older_version_lanes_project` -- a real git project whose
  committed ``.kittify/metadata.yaml`` records an OLDER Spec Kitty version,
  with live lane worktrees (and, for ``lanes_with_coord``, a coordination
  worktree materialised by product code) so that real registered migrations
  apply on ``spec-kitty upgrade``.
* :func:`commit_broken_upgrade_state` -- reproduces what a PRE-FIX upgrade left
  behind: a per-branch divergent ``.kittify/metadata.yaml`` plus an identical
  ``.gitattributes`` addition, committed on every lane / coordination branch
  and on the target (grounding Appendix A).

Construction is direct git (no CLI driving) for speed; the stand-ins are:

====================================  =========================================
Builder step                          CLI step it stands in for
====================================  =========================================
git init + older ``metadata.yaml``    ``spec-kitty init`` (then a CLI downgrade)
meta.json / lanes.json / WP files     ``agent mission create`` + ``finalize-tasks``
``allocate_lane_worktree`` (product)  ``spec-kitty implement WP##``
``CoordinationWorkspace.resolve``     the coordination worktree materialisation
====================================  =========================================

The fixture reuses the terminus harness (``tests/terminus/conftest.py``) for
the isolated HOME, the CLI runner and the git primitives, so a rename there
breaks exactly the adapter block below.

Target branch
-------------
The default target is the NON-protected branch ``work``. A ``lanes`` mission
recorded against protected ``main`` is refused by ``consolidate`` with
``PROTECTED_BRANCH_REFUSED`` before any branch moves, so ``target_branch="main"``
hits that preflight instead of the defect under test.

Lane file layout
----------------
Lane ``lane-a`` carries one committed file ``src/lane_a/m.py`` (the lane id with
``-`` replaced by ``_`` so the path is a valid package directory).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from specify_cli import __version__ as CURRENT_CLI_VERSION
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.branch_naming import mission_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.migration.schema_version import REQUIRED_SCHEMA_VERSION
from specify_cli.status.reducer import materialize
from tests.terminus import conftest as _harness
from tests.terminus.conftest import CoordMission

# --- single adapter over the terminus harness privates (one edit on a rename) ---
_run = _harness._run
_git = _harness._git
_git_out = _harness._git_out
_event = _harness._event
_APPROVE_CHAIN = _harness._APPROVE_CHAIN
_now_iso = _harness._now_iso
_STATUS_EVENTS_FILENAME = _harness._STATUS_EVENTS_FILENAME
_cli_env = _harness._cli_env
_bootstrapped_home_template = _harness._bootstrapped_home_template
# ---------------------------------------------------------------------------------

Topology = Literal["lanes", "lanes_with_coord"]

#: Project metadata path. The selftest pins it against the state contract's
#: primary-owned declaration (the single authority for the production rule).
METADATA_PATH = ".kittify/metadata.yaml"
GITATTRIBUTES_PATH = ".gitattributes"
DECISION_INDEX_GITATTRIBUTES_LINE = "kitty-specs/**/decisions/index.json merge=spec-kitty-decision-index\n"
UPGRADE_COMMIT_SUBJECT_PREFIX = "chore: apply spec-kitty upgrade changes"

DEFAULT_TARGET_BRANCH = "work"

#: Recorded version of the older-version fixture. It sits below the target of
#: the worktree-running 4.0.0rc5 migrations (asserted by the self-test against
#: the live registry, not assumed here), so those evaluate on every worktree.
OLDER_VERSION = "4.0.0rc4"
WORKTREE_MIGRATION_ID = "4.0.0rc5_decision_index_merge_driver"
#: Migration records a pre-fix lane / coordination upgrade commit carried
#: (only the migrations that run in worktrees); the target recorded more.
_LANE_RECORDED_MIGRATIONS = (
    "4.0.0rc5_decision_index_merge_driver",
    "4.0.0rc5_heal_run_index_paths",
)
_TARGET_ONLY_MIGRATIONS = (
    "4.0.0rc5_retire_bundled_dashboard",
    "4.0.0rc5_install_lane_tip_recorder",
)

_INITIALIZED_AT = "2026-01-01T00:00:00"
_FIXED_BASE_TIME = "2026-10-04T12:00:{second:02d}.000000"
_MISSION_MID8 = "01M5457A"
_FIXED_COMPUTED_AT = "2026-10-04T12:00:00+00:00"
_STATUS_JSON = "status.json"
#: ``spec_kitty.schema_version`` a real upgrade stamps into ``metadata.yaml``
#: (``runner._stamp_schema_version(..., REQUIRED_SCHEMA_VERSION)``).
_STAMPED_SCHEMA_VERSION = REQUIRED_SCHEMA_VERSION
#: The ``spec_kitty.schema_version`` of the OLDER-version fixture's initial
#: metadata, which every lane and coordination worktree forks from. Upgrade
#: skips those worktrees, so each keeps this value: a lane command that gated
#: on the lane's own schema version would refuse.
_OLDER_SCHEMA_VERSION = (REQUIRED_SCHEMA_VERSION or 0) - 1


@dataclass
class LanesProject:
    """A real on-disk lanes (or lanes-with-coordination) mission project."""

    mission: CoordMission
    topology: Topology
    target_branch: str
    #: lane_id -> lane branch (real names from ``lanes/branch_naming.py``).
    lane_branches: dict[str, str] = field(default_factory=dict)
    #: lane_id -> lane worktree path (emptied by :meth:`remove_lane_worktrees`).
    lane_worktrees: dict[str, Path] = field(default_factory=dict)
    #: lane_id -> the single WP the lane carries.
    lane_wps: dict[str, str] = field(default_factory=dict)
    coord_branch: str | None = None
    coord_worktree: Path | None = None
    extra_worktrees: list[Path] = field(default_factory=list)

    # -- convenience --------------------------------------------------------

    @property
    def repo(self) -> Path:
        return self.mission.repo

    @property
    def slug(self) -> str:
        return self.mission.slug

    @property
    def feature_dir(self) -> Path:
        return self.mission.feature_dir

    @property
    def mission_branch(self) -> str:
        """The mission integration branch (coordination branch when present)."""
        return self.mission.coord_branch

    @property
    def lane_ids(self) -> list[str]:
        return list(self.lane_branches)

    def branches(self, *, include_target: bool = False) -> list[str]:
        """Every branch the pre-fix upgrade committed on (lanes + coordination)."""
        out = list(self.lane_branches.values())
        if self.coord_branch:
            out.append(self.coord_branch)
        if include_target:
            out.append(self.target_branch)
        return out

    def run(self, *args: str, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """Run the REAL CLI from the repository root checkout (isolated HOME)."""
        return _harness.run_terminus(self.mission, list(args), env=env)

    def upgrade(self) -> subprocess.CompletedProcess[str]:
        """Run today's ``spec-kitty upgrade --yes`` in the project."""
        return self.run("upgrade", "--yes")

    def remove_lane_worktrees(self) -> None:
        """Remove every lane worktree but keep the lane branches (WP04 AS-2)."""
        for path in list(self.lane_worktrees.values()):
            _git(self.repo, "worktree", "remove", "--force", str(path))
        _git(self.repo, "worktree", "prune")
        self.lane_worktrees.clear()

    def extra_worktree(self, *, branch: str | None = None, detached: bool = False) -> Path:
        """Add an extra worktree under ``.worktrees/`` (WP02/T005).

        ``detached=True`` checks out the target tip detached; otherwise
        ``branch`` is checked out (created from the target when missing).
        """
        if detached == (branch is not None):
            raise ValueError("pass exactly one of branch=... or detached=True")
        path = self.repo / ".worktrees" / f"extra-{len(self.extra_worktrees) + 1}"
        if detached:
            _git(self.repo, "worktree", "add", "--detach", str(path), self.target_branch)
        else:
            assert branch is not None
            if _branch_tip(self.repo, branch) is None:
                _git(self.repo, "worktree", "add", "-b", branch, str(path), self.target_branch)
            else:
                _git(self.repo, "worktree", "add", str(path), branch)
        self.extra_worktrees.append(path)
        return path


# ---------------------------------------------------------------------------
# Low-level git helpers
# ---------------------------------------------------------------------------


def _branch_tip(repo: Path, ref: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or None


def _commit_paths(repo: Path, paths: Sequence[str], message: str) -> None:
    _git(repo, "add", *paths)
    _git(repo, "commit", "-qm", message)


def _checkout_of(repo: Path, branch: str) -> Path | None:
    """Return the worktree that has ``branch`` checked out, if any."""
    listing = _git_out(repo, "worktree", "list", "--porcelain")
    current: Path | None = None
    for line in listing.splitlines():
        if line.startswith("worktree "):
            current = Path(line.removeprefix("worktree "))
        elif line == f"branch refs/heads/{branch}":
            return current
    return None


def commit_file_on_branch(repo: Path, branch: str, path: str, content: str, message: str) -> str:
    """Commit one file onto ``branch`` (see :func:`commit_files_on_branch`)."""
    return commit_files_on_branch(repo, branch, {path: content}, message)


def _commit_via_private_index(
    repo: Path,
    branch: str,
    message: str,
    stage: Callable[[Callable[..., str]], None],
) -> str:
    """Commit one tree edit onto ``branch`` through a private index; return the new SHA.

    ``stage`` receives a ``git`` runner bound to the private index and applies
    the edit. The index is seeded from the branch tip and removed afterwards;
    the checkout holding ``branch`` (if any) is hard-reset to the new tip.
    """
    old = _branch_tip(repo, branch)
    if old is None:
        raise AssertionError(f"unknown branch {branch}")
    index_file = Path(_git_out(repo, "rev-parse", "--git-path", "pf-index-tmp").strip())
    if not index_file.is_absolute():
        index_file = repo / index_file
    env_prefix = ["env", f"GIT_INDEX_FILE={index_file}"]

    def index_git(*args: str, stdin: str | None = None) -> str:
        return subprocess.run(
            [*env_prefix, "git", "-C", str(repo), *args],
            input=stdin,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    try:
        index_git("read-tree", old)
        stage(index_git)
        tree = index_git("write-tree")
        new = index_git("commit-tree", tree, "-p", old, "-m", message)
    finally:
        index_file.unlink(missing_ok=True)
    checkout = _checkout_of(repo, branch)
    _git(repo, "update-ref", f"refs/heads/{branch}", new, old)
    if checkout is not None:
        _git(checkout, "reset", "-q", "--hard", branch)
    return new


def commit_files_on_branch(repo: Path, branch: str, files: Mapping[str, str], message: str) -> str:
    """Commit ``files`` (``{path: content}``) as ONE commit onto ``branch`` via plumbing.

    Plumbing (a private index) keeps this working for paths a sparse checkout
    excludes (``status.json`` in a lane) and leaves every other checkout alone.
    The checkout holding ``branch`` is hard-reset to the new tip so it stays
    clean. Returns the new commit SHA.
    """

    def stage(index_git: Callable[..., str]) -> None:
        for path, content in files.items():
            blob = subprocess.run(
                ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
                input=content,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            index_git("update-index", "--add", "--cacheinfo", f"100644,{blob},{path}")

    return _commit_via_private_index(repo, branch, message, stage)


def delete_path_on_branch(repo: Path, branch: str, path: str, message: str | None = None) -> str:
    """Commit the deletion of ``path`` onto ``branch`` via plumbing; return the new SHA.

    Like :func:`commit_files_on_branch`, independent of any sparse-checkout
    pattern; the checkout holding ``branch`` is hard-reset to the new tip.
    """

    def stage(index_git: Callable[..., str]) -> None:
        index_git("update-index", "--force-remove", path)

    return _commit_via_private_index(repo, branch, message or f"chore: delete {path}", stage)


def metadata_blob(repo: Path, ref: str) -> str | None:
    """Content of ``.kittify/metadata.yaml`` at ``ref`` (``None`` when absent)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{METADATA_PATH}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def gitattributes_blob(repo: Path, ref: str) -> str | None:
    """Content of ``.gitattributes`` at ``ref`` (``None`` when absent)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{GITATTRIBUTES_PATH}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def upgrade_commits_on(repo: Path, branch: str) -> list[str]:
    """SHAs on ``branch`` whose subject starts with the upgrade auto-commit subject."""
    listing = _git_out(repo, "log", "--format=%H%x09%s", branch)
    shas: list[str] = []
    for line in listing.splitlines():
        sha, _, subject = line.partition("\t")
        if subject.startswith(UPGRADE_COMMIT_SUBJECT_PREFIX):
            shas.append(sha)
    return shas


# ---------------------------------------------------------------------------
# Builder: older-version project with live lanes
# ---------------------------------------------------------------------------


def status_event(
    mission: CoordMission,
    wp_id: str,
    from_lane: str,
    to_lane: str,
    *,
    force: bool = False,
    reason: str | None = None,
) -> dict[str, object]:
    """One status event in today's ``status.events.jsonl`` row shape.

    The terminus harness still writes the legacy ``feature_slug`` key; this
    re-keys it to the canonical ``mission_slug`` + ``mission_id`` identity and
    carries the nullable fields the mission-state normaliser writes, so a fresh
    ``upgrade`` leaves the row untouched.
    """
    event = _event(mission, wp_id, from_lane, to_lane)
    event.pop("feature_slug", None)
    event.update(
        mission_slug=mission.slug,
        mission_id=mission.mission_id,
        force=force,
        reason=reason,
        reason_source=None,
        review_result=None,
        policy_metadata=None,
    )
    return event


def _event_line(event: Mapping[str, object]) -> str:
    return json.dumps(event, sort_keys=True) + "\n"


def append_status_event_on_branch(
    project: LanesProject,
    branch: str,
    wp_id: str,
    from_lane: str,
    to_lane: str,
    *,
    force: bool = False,
    reason: str | None = None,
) -> str:
    """Commit one appended status event onto ``branch``'s mission event log.

    Stands in for a status transition recorded on ``branch`` (for example a
    coordination lifecycle commit) without driving the CLI, which refuses
    status commands on an older-version project. Returns the new commit SHA.
    """
    rel = f"kitty-specs/{project.slug}/{_STATUS_EVENTS_FILENAME}"
    current = subprocess.run(
        ["git", "-C", str(project.repo), "show", f"{branch}:{rel}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if current and not current.endswith("\n"):
        current += "\n"
    event = status_event(project.mission, wp_id, from_lane, to_lane, force=force, reason=reason)
    return commit_file_on_branch(project.repo, branch, rel, current + _event_line(event), f"status: {wp_id} {from_lane} -> {to_lane}")


def _older_metadata_yaml() -> str:
    return (
        "# Spec Kitty Project Metadata\n"
        "# Auto-generated by spec-kitty init/upgrade\n"
        "# DO NOT EDIT MANUALLY\n"
        "\n"
        "spec_kitty:\n"
        f"  version: {OLDER_VERSION}\n"
        f"  initialized_at: '{_INITIALIZED_AT}'\n"
        f"  schema_version: {_OLDER_SCHEMA_VERSION}\n"
        "environment:\n"
        "  python_version: '3.12'\n"
        "  platform: linux\n"
        "  platform_version: ''\n"
        "migrations:\n"
        "  applied: []\n"
    )


def _init_repo(repo: Path, target_branch: str) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", target_branch, str(repo)])
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    metadata = repo / METADATA_PATH
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(_older_metadata_yaml(), encoding="utf-8")
    _git(repo, "add", "README.md", ".gitignore", METADATA_PATH)
    _git(repo, "commit", "-qm", "init")


def _write_meta(mission: CoordMission, topology: Topology) -> None:
    meta: dict[str, object] = {
        "mission_slug": mission.slug,
        "mission_id": mission.mission_id,
        "mid8": mission.mid8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": mission.target_branch,
        "purpose_tldr": "#5457 primary-owned fixture",
        "purpose_context": "older-version project with live lanes",
        # Current mission-state shape (``agent mission create``), so ``upgrade``'s
        # mission-state normaliser has nothing to repair in the root checkout.
        "created_at": _FIXED_COMPUTED_AT,
        "friendly_name": mission.slug,
        "slug": mission.slug,
    }
    if topology == "lanes_with_coord":
        meta["coordination_branch"] = mission.coord_branch
    else:
        meta["topology"] = "lanes"
    (mission.feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _lane_id(index: int) -> str:
    return f"lane-{chr(ord('a') + index)}"


def _build_manifest(
    mission: CoordMission,
    wps: Sequence[str],
    depends_on_lanes: Mapping[str, Sequence[str]],
) -> LanesManifest:
    lanes = [
        ExecutionLane(
            lane_id=_lane_id(idx),
            wp_ids=(wp_id,),
            write_scope=(f"src/{_lane_id(idx).replace('-', '_')}/**",),
            predicted_surfaces=("code",),
            depends_on_lanes=tuple(depends_on_lanes.get(_lane_id(idx), ())),
            parallel_group=1 if depends_on_lanes.get(_lane_id(idx)) else 0,
        )
        for idx, wp_id in enumerate(wps)
    ]
    return LanesManifest(
        version=1,
        mission_slug=mission.slug,
        mission_id=mission.mission_id,
        mission_branch=mission.coord_branch,
        target_branch=mission.target_branch,
        lanes=lanes,
        computed_at=_FIXED_COMPUTED_AT,
        computed_from="primary-owned-fixture",
    )


def _write_analysis_report(mission: CoordMission) -> None:
    from specify_cli.analysis_report import write_analysis_report

    for name, text in (("spec.md", "Spec\n"), ("plan.md", "Plan\n"), ("tasks.md", "## WP01 Work\n\n- [x] T001 Placeholder\n")):
        (mission.feature_dir / name).write_text(text, encoding="utf-8")
    write_analysis_report(
        feature_dir=mission.feature_dir,
        repo_root=mission.repo,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="fixture",
    )


def _new_mission(tmp_path: Path, target_branch: str, topology: Topology) -> CoordMission:
    mid8 = _MISSION_MID8
    mission_id = (mid8 + "0" * 26)[:26]
    slug = f"primary-owned-{mid8}"
    home = tmp_path / "home"
    shutil.copytree(_bootstrapped_home_template(), home, dirs_exist_ok=True)
    branch = CoordinationWorkspace.branch_name(slug, mid8) if topology == "lanes_with_coord" else mission_branch_name(slug, mission_id=mission_id)
    repo = tmp_path / "repo"
    return CoordMission(
        repo=repo,
        home=home,
        feature_dir=repo / "kitty-specs" / slug,
        slug=slug,
        mission_id=mission_id,
        mid8=mid8,
        coord_branch=branch,
        target_branch=target_branch,
    )


def _plant_lane_commit(worktree: Path, lane_id: str, wp_id: str) -> None:
    package = lane_id.replace("-", "_")
    code = worktree / "src" / package / "m.py"
    code.parent.mkdir(parents=True, exist_ok=True)
    code.write_text(f"def {wp_id.lower()}() -> int:\n    return 1\n", encoding="utf-8")
    _git(worktree, "add", f"src/{package}/m.py")
    _git(worktree, "commit", "-qm", f"feat({wp_id}): lane work")


def build_older_version_lanes_project(
    tmp_path: Path,
    *,
    topology: Topology,
    lanes: int,
    target_branch: str = DEFAULT_TARGET_BRANCH,
    depends_on_lanes: Mapping[str, Sequence[str]] | None = None,
    status_json_divergence: bool = False,
    with_analysis_report: bool = False,
) -> LanesProject:
    """Build a project recorded at an OLDER version with ``lanes`` live lanes.

    ``topology`` is ``"lanes"`` (mission branch only) or ``"lanes_with_coord"``
    (adds a coordination branch and a coordination worktree materialised by
    product code, so its sparse checkout is exercised). Every lane has a real
    worktree from the product allocator, one committed file, and an approved WP.

    Knobs for later work packages:

    * ``target_branch`` -- defaults to the non-protected ``work``; ``main`` hits
      ``PROTECTED_BRANCH_REFUSED`` on ``consolidate`` before any branch moves.
    * ``depends_on_lanes`` -- e.g. ``{"lane-b": ("lane-a",)}`` (WP04/T016).
    * ``status_json_divergence`` -- commit a different ``status.json`` on the
      mission/coordination branch and on every lane branch (WP04 AS-3).
    * ``with_analysis_report`` -- persist a fresh analysis report so
      ``implement`` / ``review`` are not blocked by ``analysis_report_required``.

    A recorded acceptance is NOT provided: WPs are approved via the status log,
    which is all the terminus-style ``consolidate`` path reads. A test that needs
    an acceptance records it through the CLI, e.g.
    ``project.run("agent", "mission", "acceptance-verdict", ...)``.
    """
    if lanes < 1:
        raise ValueError("lanes must be >= 1")
    mission = _new_mission(tmp_path, target_branch, topology)
    wps = [f"WP{idx + 1:02d}" for idx in range(lanes)]
    _init_repo(mission.repo, target_branch)

    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission, topology)
    manifest = _build_manifest(mission, wps, depends_on_lanes or {})
    write_lanes_json(mission.feature_dir, manifest)
    events: list[dict[str, object]] = []
    for wp_id in wps:
        (mission.feature_dir / "tasks" / f"{wp_id}-work.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: {wp_id} work\n---\n# {wp_id}\n",
            encoding="utf-8",
        )
        events.extend(status_event(mission, wp_id, frm, to) for frm, to in _APPROVE_CHAIN)
    (mission.feature_dir / _STATUS_EVENTS_FILENAME).write_text("".join(_event_line(event) for event in events), encoding="utf-8")
    # The derived snapshot comes from the product reducer, as every status write does.
    materialize(mission.feature_dir)
    if with_analysis_report:
        _write_analysis_report(mission)
    _commit_paths(mission.repo, [str(mission.feature_dir.relative_to(mission.repo))], f"chore({mission.slug}): bootstrap")
    _git(mission.repo, "branch", mission.coord_branch)

    project = LanesProject(
        mission=mission,
        topology=topology,
        target_branch=target_branch,
        coord_branch=mission.coord_branch if topology == "lanes_with_coord" else None,
    )
    for idx, wp_id in enumerate(wps):
        lane_id = _lane_id(idx)
        worktree, branch = allocate_lane_worktree(mission.repo, mission.slug, wp_id, manifest)
        _plant_lane_commit(worktree, lane_id, wp_id)
        project.lane_branches[lane_id] = branch
        project.lane_worktrees[lane_id] = worktree
        project.lane_wps[lane_id] = wp_id
        mission.lane_branches[wp_id] = branch
    if topology == "lanes_with_coord":
        project.coord_worktree = CoordinationWorkspace.resolve(mission.repo, mission.slug, mission.mid8)
    if status_json_divergence:
        _plant_status_json_divergence(project)
    return project


def _status_json_path(project: LanesProject) -> str:
    return f"kitty-specs/{project.slug}/{_STATUS_JSON}"


def _plant_status_json_divergence(project: LanesProject) -> None:
    path = _status_json_path(project)
    commit_file_on_branch(
        project.repo,
        project.mission_branch,
        path,
        json.dumps({"side": "mission"}, sort_keys=True) + "\n",
        "chore: status snapshot (mission side)",
    )
    for lane_id, branch in project.lane_branches.items():
        commit_file_on_branch(
            project.repo,
            branch,
            path,
            json.dumps({"side": lane_id}, sort_keys=True) + "\n",
            f"chore: status snapshot ({lane_id} side)",
        )


# ---------------------------------------------------------------------------
# Builder: what a pre-fix upgrade left behind
# ---------------------------------------------------------------------------


def _broken_metadata_yaml(index: int, *, migrations: Sequence[str]) -> str:
    stamp = _FIXED_BASE_TIME.format(second=index)
    records = "".join(
        f"  - id: {migration_id}\n    applied_at: '{_FIXED_BASE_TIME.format(second=index)}'\n    result: success\n    notes: fixture\n"
        for migration_id in migrations
    )
    return (
        "# Spec Kitty Project Metadata\n"
        "# Auto-generated by spec-kitty init/upgrade\n"
        "# DO NOT EDIT MANUALLY\n"
        "\n"
        "spec_kitty:\n"
        f"  version: {CURRENT_CLI_VERSION}\n"
        f"  initialized_at: '{_INITIALIZED_AT}'\n"
        f"  last_upgraded_at: '{stamp}'\n"
        f"  schema_version: {_STAMPED_SCHEMA_VERSION}\n"
        "environment:\n"
        "  python_version: '3.12'\n"
        "  platform: linux\n"
        "  platform_version: ''\n"
        "migrations:\n"
        "  applied:\n"
        f"{records}"
    )


def commit_broken_upgrade_state(project: LanesProject, *, branches: Sequence[str] | None = None) -> dict[str, str]:
    """Commit what a pre-fix ``spec-kitty upgrade`` committed on each branch.

    On every lane branch and the coordination branch (or just ``branches``) and
    on the target branch: a ``.kittify/metadata.yaml`` whose content DIFFERS per
    branch (distinct ``last_upgraded_at`` / ``applied_at``; the target records
    more migrations than a lane, as in the field), stamped with the
    ``spec_kitty.schema_version`` a real upgrade writes, and the IDENTICAL
    ``.gitattributes`` line ``kitty-specs/**/decisions/index.json
    merge=spec-kitty-decision-index``. Returns ``{branch: commit sha}``.
    """
    targets = list(branches) if branches is not None else project.branches()
    ordered = [*targets, project.target_branch]
    commits: dict[str, str] = {}
    for index, branch in enumerate(ordered):
        recorded = _LANE_RECORDED_MIGRATIONS if branch != project.target_branch else (*_LANE_RECORDED_MIGRATIONS, *_TARGET_ONLY_MIGRATIONS)
        message = f"{UPGRADE_COMMIT_SUBJECT_PREFIX} ({OLDER_VERSION} -> {CURRENT_CLI_VERSION})"
        commits[branch] = commit_files_on_branch(
            project.repo,
            branch,
            {
                METADATA_PATH: _broken_metadata_yaml(index + 1, migrations=recorded),
                GITATTRIBUTES_PATH: DECISION_INDEX_GITATTRIBUTES_LINE,
            },
            message,
        )
    return commits


# ---------------------------------------------------------------------------
# Observation of today's upgrade (the positive control)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UpgradeObservation:
    """Facts about one ``spec-kitty upgrade --yes`` run (no verdict attached).

    Consumers assert the invariant they care about from these facts, so this
    record states what happened and never whether the defect is present.
    """

    returncode: int
    output: str
    root_metadata: str | None
    #: branch -> ``.kittify/metadata.yaml`` blob after the run (lanes + coordination).
    metadata_by_branch: dict[str, str | None]
    #: branch -> upgrade auto-commits on that branch after the run.
    upgrade_commits_by_branch: dict[str, list[str]]
    target_upgrade_commits: list[str]

    @property
    def branches_with_upgrade_commit(self) -> list[str]:
        return [b for b, shas in self.upgrade_commits_by_branch.items() if shas]


def observe_upgrade_divergence(project: LanesProject) -> UpgradeObservation:
    """Run ``spec-kitty upgrade --yes`` and report what each branch ended up with."""
    result = project.upgrade()
    branches = project.branches()
    return UpgradeObservation(
        returncode=result.returncode,
        output=(result.stdout or "") + (result.stderr or ""),
        root_metadata=metadata_blob(project.repo, project.target_branch),
        metadata_by_branch={branch: metadata_blob(project.repo, branch) for branch in branches},
        upgrade_commits_by_branch={branch: upgrade_commits_on(project.repo, branch) for branch in branches},
        target_upgrade_commits=upgrade_commits_on(project.repo, project.target_branch),
    )


# ---------------------------------------------------------------------------
# Matchers for the defect's exact text (red consolidate / review / implement tests)
# ---------------------------------------------------------------------------


def _combined(result: subprocess.CompletedProcess[str] | str) -> str:
    if isinstance(result, str):
        return result
    return (result.stdout or "") + (result.stderr or "")


def output_names_stale_metadata_refusal(result: subprocess.CompletedProcess[str] | str) -> bool:
    """``Lane <id> is stale: overlapping files [...'.kittify/metadata.yaml'...]``."""
    text = _combined(result)
    return bool(re.search(r"Lane \S+ is stale", text)) and METADATA_PATH in text


def output_names_target_content_conflict(result: subprocess.CompletedProcess[str] | str) -> bool:
    """``TARGET_BRANCH_CONTENT_CONFLICT`` naming ``.kittify/metadata.yaml``."""
    text = _combined(result)
    return "TARGET_BRANCH_CONTENT_CONFLICT" in text and METADATA_PATH in text


def output_names_merge_failed(result: subprocess.CompletedProcess[str] | str) -> bool:
    """``Merge of <src> into <dst> failed`` (lane -> mission or mission -> target)."""
    return bool(re.search(r"Merge of \S+ into \S+ failed", _combined(result)))


def output_names_auto_rebase_failure(result: subprocess.CompletedProcess[str] | str) -> bool:
    """``LANE_AUTO_REBASE_FAILED: no classifier rule matched .../.kittify/metadata.yaml``."""
    text = _combined(result)
    return "LANE_AUTO_REBASE_FAILED" in text and METADATA_PATH in text


def output_shows_primary_owned_defect(result: subprocess.CompletedProcess[str] | str) -> bool:
    """True when the output carries ANY of the defect's exact signatures."""
    return any(
        matcher(result)
        for matcher in (
            output_names_stale_metadata_refusal,
            output_names_target_content_conflict,
            output_names_merge_failed,
            output_names_auto_rebase_failure,
        )
    )
