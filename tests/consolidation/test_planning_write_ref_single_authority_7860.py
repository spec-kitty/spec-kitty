"""#7860 (FR-005, C-001, C-004): every planning write-branch decision reads ONE authority.

The planning lane's write branch is :func:`mission_runtime.planning_write_ref` (the Mission branch
of a default Mission that has not landed, else the target), and the checkout holding it is
:func:`specify_cli.coordination.planning_commit.planning_lane_target`. Two pins:

* **Follow the authority (a).** A real-git explicit-topology Mission whose true answer is the
  target branch in the repository root checkout. With the reader replaced by a sentinel branch held
  by a sentinel worktree, every planning surface must report the sentinel: the planning lane target,
  the workspace (``implement``), the claim base, the ``for_review`` gate, the orchestrator API's
  repo-root lane branch, the evidence window (``consolidate`` / ``accept``) and ``move-task``'s
  evidence leg. A surface that decides on its own keeps reporting the target and fails here. The
  control test proves the same surfaces report the target without the patch (non-vacuity).
* **No second copy of the rule (b).** An AST scan of ``src/``: only ``mission_runtime/resolution.py``
  calls ``default_mission_primary_ref``, and no function outside it compares ``topology_source``
  with ``"default"`` while reading a landing signal (re-deriving the rule instead of reading the one
  predicate, ``mission_runtime.default_mission_rule_applies``). One priced
  exception: ``specify_cli/review/wp_range.py`` reads ``default_mission_primary_ref`` directly (C-001,
  operator ruling: fold it onto the shared reader after #5604 lands; exit: #5604). The review-range
  ratchet below pins that its answer agrees with the authority for a default, not-landed Mission.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import mission_runtime
from mission_runtime import resolution
from specify_cli.cli.commands.agent import tasks_move_task as move_task_module
from specify_cli.consolidation import wp_evidence
from specify_cli.coordination import planning_commit
from specify_cli.lanes import for_review_gate
from specify_cli.lanes.claim_base import read_claim_base
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.implement_support import guard_repo_root_claim
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.orchestrator_api import wp_lifecycle
from specify_cli.status import read_events
from specify_cli.status.models import Lane
from specify_cli.workspace.context import MISSION_BRANCH_CHECKOUT_KIND, clear_workspace_resolution_caches, resolve_workspace_for_wp
from tests._support.git_cli import git_out

pytestmark = [pytest.mark.git_repo]

_SLUG = "pin-01M8CCCC"
_MISSION_ID = "01M8CCCCCCCCCCCCCCCCCCCCCC"
_TARGET = "main"
_WP = "WP01"
_SENTINEL = "sentinel/planning-write-ref"
_OWNED = f"kitty-specs/{_SLUG}/research/notes.md"
_SRC = Path(__file__).resolve().parents[2] / "src"
_AUTHORITY = Path("mission_runtime/resolution.py")
#: The one priced exception (Standing Order #5): the review range keeps its own read until #5604 lands.
_REVIEW_RANGE_EXCEPTION = Path("specify_cli/review/wp_range.py")
#: Calls that decide a write branch on their own. The pure predicate ``default_mission_rule_applies``
#: is the one rule itself, so reading it (the topic-holder locator does) is reuse, not a copy.
_RULE_FUNCTIONS = frozenset({"default_mission_primary_ref"})
_LANDING_SIGNALS = frozenset({"merged_at", "mission_has_landed", "landed"})


@pytest.fixture(autouse=True)
def _reset_caches() -> Iterator[None]:
    clear_workspace_resolution_caches()
    yield
    clear_workspace_resolution_caches()


def _git(repo: Path, *args: str) -> str:
    return git_out(repo, *args).strip()


def _manifest(pin: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch=_TARGET,
        lanes=[
            ExecutionLane(PLANNING_LANE_ID, (_WP,), (_OWNED,), ("planning",), (), 0),
            ExecutionLane("lane-a", ("WP02",), ("src/**",), ("core",), (), 0),
        ],
        computed_at="2026-11-26T00:00:00+00:00",
        computed_from="test",
        planning_artifact_wps=[_WP],
        planning_commit_sha=pin,
    )


def _claim_event() -> dict[str, Any]:
    return {
        "actor": "claude:sonnet:implementer",
        "at": "2026-11-26T00:00:01+00:00",
        "event_id": "01M8CCCC00000000000000000001",
        "evidence": None,
        "execution_mode": "direct_repo",
        "mission_slug": _SLUG,
        "force": False,
        "from_lane": "planned",
        "reason": None,
        "review_ref": None,
        "to_lane": "claimed",
        "wp_id": _WP,
    }


def _explicit_mission(tmp_path: Path) -> tuple[Path, Path]:
    """An explicit-topology Mission on ``main`` in the repository root checkout, plus a sentinel worktree.

    The true planning write branch is ``main`` (repository root checkout). The sentinel worktree
    holds ``sentinel/planning-write-ref``, cut from the Mission, with WP01's claim event committed
    there (so a window starting on it is provable).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    pin = _git(repo, "rev-parse", "HEAD")
    mission = repo / "kitty-specs" / _SLUG
    (mission / "tasks").mkdir(parents=True)
    meta = {
        "mission_id": _MISSION_ID,
        "mission_slug": _SLUG,
        "mission_type": "software-dev",
        "friendly_name": _SLUG,
        "target_branch": _TARGET,
        "topology": "lanes_with_coord",
        "topology_source": "explicit",
        "created_at": "2026-11-26T00:00:00+00:00",
    }
    (mission / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    for wp_id, mode, owned in ((_WP, "planning_artifact", _OWNED), ("WP02", "code_change", "src/**")):
        (mission / "tasks" / f"{wp_id}-work.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\ndependencies: []\nexecution_mode: {mode}\nowned_files:\n- {owned}\n---\n# {wp_id}\n",
            encoding="utf-8",
        )
    write_lanes_json(mission, _manifest(pin))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "mission")
    sentinel = repo / ".worktrees" / "sentinel"
    _git(repo, "worktree", "add", "-q", "-b", _SENTINEL, str(sentinel))
    (sentinel / "kitty-specs" / _SLUG / "status.events.jsonl").write_text(json.dumps(_claim_event()) + "\n", encoding="utf-8")
    _git(sentinel, "add", "-A")
    _git(sentinel, "commit", "-qm", "chore: claim WP01 on the sentinel branch")
    return repo, sentinel


def _state(repo: Path) -> move_task_module._MoveTaskState:
    return move_task_module._MoveTaskState(
        task_id=_WP,
        to=Lane.FOR_REVIEW.value,
        mission=_SLUG,
        agent="claude",
        assignee=None,
        shell_pid=None,
        note=None,
        review_feedback_file=None,
        approval_ref=None,
        reviewer=None,
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=False,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=None,
        json_output=True,
        target_lane=Lane.FOR_REVIEW,
        feature_dir=repo / "kitty-specs" / _SLUG,
        old_lane=Lane.IN_PROGRESS,
        mission_slug=_SLUG,
        main_repo_root=repo,
    )


def _surfaces(repo: Path, sentinel: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """What every planning surface reports for WP01's write branch / checkout."""
    manifest = _manifest(_git(repo, "rev-parse", _TARGET))
    planning_lane = manifest.lanes[0]
    sentinel_events = sentinel / "kitty-specs" / _SLUG
    monkeypatch.setattr(move_task_module, "_mt_status_events", lambda _st: read_events(sentinel_events))
    target = planning_commit.planning_lane_target(repo, _SLUG, _TARGET)
    workspace = resolve_workspace_for_wp(repo, _SLUG, _WP)
    guard_repo_root_claim(repo, _SLUG, _WP, workspace)
    gate = for_review_gate._evaluate_repo_root_lane_gate(repo, _SLUG, _WP, PLANNING_LANE_ID, _TARGET)
    window = wp_evidence.planning_evidence_window(repo, manifest, planning_lane, _WP, lambda: read_events(sentinel_events))
    move_window = move_task_module._mt_planning_window(_state(repo), manifest, planning_lane)
    return {
        "planning_lane_target.branch": target.branch,
        "planning_lane_target.checkout": target.checkout.resolve(),
        "workspace.branch_name": workspace.branch_name,
        "workspace.worktree_path": Path(workspace.worktree_path).resolve(),
        "claim_base": read_claim_base(repo, _SLUG, _WP),
        "for_review_gate.lane_branch": gate.lane_branch,
        "orchestrator._repo_root_lane_branch": wp_lifecycle._repo_root_lane_branch(repo, _SLUG, manifest),
        "planning_evidence_window.end": window[1] if window is not None else _TARGET,
        "move_task.window.end": move_window[1] if move_window is not None else _TARGET,
    }


def test_without_the_patch_every_surface_reports_the_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control (non-vacuity): the true answer for this explicit-topology Mission is the target in the root checkout."""
    repo, sentinel = _explicit_mission(tmp_path)

    reported = _surfaces(repo, sentinel, monkeypatch)

    assert reported == {
        "planning_lane_target.branch": _TARGET,
        "planning_lane_target.checkout": repo.resolve(),
        # The repository root arm of a lanes Mission records no branch name (its pre-#7860 value).
        "workspace.branch_name": None,
        "workspace.worktree_path": repo.resolve(),
        "claim_base": _git(repo, "rev-parse", "HEAD"),
        "for_review_gate.lane_branch": _TARGET,
        "orchestrator._repo_root_lane_branch": _TARGET,
        "planning_evidence_window.end": _TARGET,
        "move_task.window.end": _TARGET,
    }


def test_every_planning_surface_follows_the_one_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the reader: every surface reports the sentinel branch and its checkout."""
    repo, sentinel = _explicit_mission(tmp_path)
    sentinel_ref = mission_runtime.PlanningWriteRef(branch=_SENTINEL, on_mission_branch=True, landed=False)

    def _reader(*_args: object, **_kwargs: object) -> mission_runtime.PlanningWriteRef:
        return sentinel_ref

    # Consumers look the reader up at call time on the package (WP01's rule); the module binding is patched too.
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader)
    monkeypatch.setattr(resolution, "planning_write_ref", _reader)
    monkeypatch.setattr(planning_commit, "primary_partition_checkout", lambda _repo, _slug: sentinel)

    reported = _surfaces(repo, sentinel, monkeypatch)

    assert reported == {
        "planning_lane_target.branch": _SENTINEL,
        "planning_lane_target.checkout": sentinel.resolve(),
        "workspace.branch_name": _SENTINEL,
        "workspace.worktree_path": sentinel.resolve(),
        "claim_base": _git(sentinel, "rev-parse", "HEAD"),
        "for_review_gate.lane_branch": _SENTINEL,
        "orchestrator._repo_root_lane_branch": _SENTINEL,
        "planning_evidence_window.end": _SENTINEL,
        "move_task.window.end": _SENTINEL,
    }
    assert resolve_workspace_for_wp(repo, _SLUG, _WP).resolution_kind == MISSION_BRANCH_CHECKOUT_KIND


# ---------------------------------------------------------------- (b) no second copy of the rule


def _called_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _names_in(node: ast.AST) -> set[str]:
    """Every identifier, attribute and string constant inside *node*."""
    found: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            found.add(child.id)
        elif isinstance(child, ast.Attribute):
            found.add(child.attr)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            found.add(child.value)
    return found


def _compares_topology_source_with_default(function: ast.AST) -> bool:
    for node in ast.walk(function):
        if isinstance(node, ast.Compare):
            names = _names_in(node)
            if "topology_source" in names and "default" in names:
                return True
    return False


def rule_copies(source: str) -> list[str]:
    """``<line>: <what>`` for each use of the default-Mission rule in *source* (a module outside the authority)."""
    tree = ast.parse(source)
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _called_name(node) in _RULE_FUNCTIONS:
            hits.append(f"{node.lineno}: calls {_called_name(node)}")
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _compares_topology_source_with_default(node) and _names_in(node) & _LANDING_SIGNALS:
            hits.append(f"{node.lineno}: {node.name} re-derives the default-Mission rule (topology_source == 'default' with a landing signal)")
    return hits


def _scan_src() -> dict[Path, list[str]]:
    found: dict[Path, list[str]] = {}
    for path in sorted(_SRC.rglob("*.py")):
        relative = path.relative_to(_SRC)
        if relative == _AUTHORITY:
            continue
        hits = rule_copies(path.read_text(encoding="utf-8"))
        if hits:
            found[relative] = hits
    return found


def test_the_default_mission_rule_has_one_home() -> None:
    """Only ``mission_runtime/resolution.py`` decides the rule; the review range is the one priced exception (#5604)."""
    found = _scan_src()

    assert set(found) <= {_REVIEW_RANGE_EXCEPTION}, f"a second copy of the default-Mission write-branch rule: {found}"
    assert _REVIEW_RANGE_EXCEPTION in found, "the review-range exception is gone: drop it from this test (its exit, #5604, has landed)"
    assert all("default_mission_primary_ref" in hit for hit in found[_REVIEW_RANGE_EXCEPTION]), found[_REVIEW_RANGE_EXCEPTION]


@pytest.mark.parametrize(
    "snippet",
    [
        "from mission_runtime import default_mission_primary_ref\nx = default_mission_primary_ref('default', 'b', False, 'main')\n",
        "import mission_runtime\nx = mission_runtime.default_mission_primary_ref('default', 'b', False, 'main')\n",
        "def f(meta):\n    return meta.get('topology_source') == 'default' and not meta.get('merged_at')\n",
    ],
)
def test_the_scan_catches_a_second_copy(snippet: str) -> None:
    """Self-mutation: each way of copying the rule is detected."""
    assert rule_copies(snippet)


def test_the_scan_accepts_a_reader_of_the_one_predicate() -> None:
    """Reading ``default_mission_rule_applies`` is reuse of the rule, not a copy of it."""
    reader = (
        "import mission_runtime\n"
        "def f(meta, landed):\n"
        "    return mission_runtime.default_mission_rule_applies(meta.get('topology_source'), meta.get('mission_branch'), landed)\n"
    )
    assert not rule_copies(reader)


def test_the_scan_ignores_the_settlement_rule() -> None:
    """``topology_source == 'default'`` with ``topology_settled`` (the settlement, not the landing) is a different rule."""
    assert not rule_copies("def f(meta):\n    return meta.get('topology_source') == 'default' and meta.get('topology_settled') is False\n")
