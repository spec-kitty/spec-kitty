"""Owned arms of ``prompt_builder.build_prompt`` (WP12, FR-008/009/010; #7578 WP05 review range).

The fact is minted by the real validator over the shared R/P/S fixture. The
claim and submission events are committed the way ``move-task`` commits them
(event-only) and carry no stamps, so the ``single_branch`` review range is
derived from those event commits, found by event id, never by subject.
"""

from __future__ import annotations

import json
import shlex
import shutil
from dataclasses import replace
from collections.abc import Callable
import subprocess
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import ActionContextError, OwnedCheckout, OwnedRefusalCode
from runtime.next._tmp_namespace import prompt_tmp_dir
from runtime.next.prompt_builder import build_prompt
from specify_cli.core.owned_mission import NEXT_OWNED_TOPOLOGIES, resolve_owned_mission
from specify_cli.status.models import Lane, StatusEvent
from tests._factories import provision_test_charter
from tests._support.status_seed import seed_status_event
from tests.integration.conftest import OwnedCheckouts

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WP = "WP01"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def _spaced_owned_root(checkouts: OwnedCheckouts) -> OwnedCheckouts:
    """Use a real moved worktree, so the validator still mints the owned fact."""
    root = checkouts.owned_root.with_name("owned checkout")
    relative_mission = checkouts.mission_dir.relative_to(checkouts.owned_root)
    _git(checkouts.repository_root, "worktree", "move", str(checkouts.owned_root), str(root))
    return replace(checkouts, owned_root=root, mission_dir=root / relative_mission)


def _completion_argv(text: str, command: str) -> list[list[str]]:
    return [shlex.split("spec-kitty" + line.partition("spec-kitty")[2]) for line in text.splitlines() if f"spec-kitty agent tasks {command} " in line]


def _fact(checkouts: OwnedCheckouts) -> OwnedCheckout:
    fact: OwnedCheckout = resolve_owned_mission(checkouts.repository_root, checkouts.owned_root, checkouts.mission_slug, allowed_topologies=NEXT_OWNED_TOPOLOGIES)
    return fact


def _set_wp_frontmatter(checkouts: OwnedCheckouts, *, owned_files: str, subtasks: str = "[]") -> None:
    wp_file = checkouts.mission_dir / "tasks" / f"{_WP}-owned.md"
    text = wp_file.read_text(encoding="utf-8").replace("owned_files: []", f"owned_files: {owned_files}").replace("subtasks: []", f"subtasks: {subtasks}")
    wp_file.write_text(text, encoding="utf-8")
    _git(checkouts.owned_root, "add", "-A")
    _git(checkouts.owned_root, "commit", "-qm", "set WP frontmatter", "--allow-empty")


def _claim(checkouts: OwnedCheckouts, event_id: str = "01CLAIMAAAAAAAAAAAAAAAAAA1") -> str:
    seed_status_event(
        checkouts.mission_dir,
        StatusEvent(
            event_id=event_id,
            mission_slug=checkouts.mission_slug,
            wp_id=_WP,
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-09-29T00:00:00+00:00",
            actor="tester",
            force=True,
            execution_mode="direct_repo",
        ),
    )
    _git(checkouts.owned_root, "add", "-A")
    _git(checkouts.owned_root, "commit", "-qm", f"status {event_id}")
    return _git(checkouts.owned_root, "rev-parse", "HEAD")


def _seed(checkouts: OwnedCheckouts, event_id: str, from_lane: Lane, to_lane: Lane, policy_metadata: dict[str, Any] | None = None) -> str:
    seed_status_event(
        checkouts.mission_dir,
        StatusEvent(
            event_id=event_id,
            mission_slug=checkouts.mission_slug,
            wp_id=_WP,
            from_lane=from_lane,
            to_lane=to_lane,
            at="2026-09-29T00:00:00+00:00",
            actor="tester",
            force=True,
            execution_mode="direct_repo",
            policy_metadata=policy_metadata,
        ),
    )
    _git(checkouts.owned_root, "add", "-A")
    _git(checkouts.owned_root, "commit", "-qm", f"status {event_id}")
    return _git(checkouts.owned_root, "rev-parse", "HEAD")


def _commit_work(checkouts: OwnedCheckouts, name: str) -> str:
    (checkouts.owned_root / name).write_text(f"# {name}\n", encoding="utf-8")
    _git(checkouts.owned_root, "add", "-A")
    _git(checkouts.owned_root, "commit", "-qm", f"work on {name}")
    return _git(checkouts.owned_root, "rev-parse", "HEAD")


def _submit(checkouts: OwnedCheckouts) -> str:
    """Start and submit the claimed WP (unstamped events); returns the submission event commit."""
    _seed(checkouts, "01PROGAAAAAAAAAAAAAAAAAAA1", Lane.CLAIMED, Lane.IN_PROGRESS)
    return _seed(checkouts, "01REVWAAAAAAAAAAAAAAAAAAA1", Lane.IN_PROGRESS, Lane.FOR_REVIEW)


def _build(checkouts: OwnedCheckouts, action: str, **overrides: Any) -> tuple[str, Path]:
    provision_test_charter(checkouts.owned_root)
    args: dict[str, Any] = {
        "action": action,
        "feature_dir": checkouts.mission_dir,
        "mission_slug": checkouts.mission_slug,
        "wp_id": _WP,
        "agent": "claude",
        "repo_root": checkouts.repository_root,
        "mission_type": "software-dev",
        "owned": _fact(checkouts),
    }
    args.update(overrides)
    return build_prompt(**args)


def test_owned_review_prompt_diffs_the_claim_commit_scoped_to_owned_files(owned_checkouts: OwnedCheckouts) -> None:
    """re-pin (IC-05, DIRECTIVE_041): ``claim..HEAD`` text replaced by the WP review range, still scoped to the owned files."""
    _set_wp_frontmatter(owned_checkouts, owned_files="[wp01.py]")
    claim = _claim(owned_checkouts)
    work = _commit_work(owned_checkouts, "wp01.py")
    _commit_work(owned_checkouts, "wp02.py")
    tip = _submit(owned_checkouts)

    text, path = _build(owned_checkouts, "review")

    assert f"REVIEW RANGE ({_WP}): {claim[:12]}..{tip[:12]}  [derived]" in text
    assert f"  git log --oneline {claim}..{tip} -- wp01.py" in text
    diff_line = f"  git diff {claim}..{tip} -- wp01.py"
    assert diff_line in text
    printed = subprocess.run(["bash", "-c", diff_line.strip()], cwd=owned_checkouts.owned_root, check=True, capture_output=True, text=True).stdout
    assert "wp01.py" in printed and "wp02.py" not in printed
    assert f"  {work[:12]} work on wp01.py" in text
    assert "Workspace contract: owned checkout" in text
    assert "# Work for this WP happens in the owned checkout" in text
    assert f"cd {owned_checkouts.owned_root}" in text
    path.unlink()


def test_owned_prompt_reads_no_resolver_and_no_repository_root_walk(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_wp_frontmatter(owned_checkouts, owned_files="[wp01.py]")
    _claim(owned_checkouts)
    _submit(owned_checkouts)
    fact = _fact(owned_checkouts)

    def _forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("an owned arm consulted a resolver or walked to the repository root")

    monkeypatch.setattr("mission_runtime.mission_context_for", _forbidden)
    monkeypatch.setattr("specify_cli.core.paths.get_main_repo_root", _forbidden)

    for action in ("implement", "review"):
        _text, path = _build(owned_checkouts, action, owned=fact)
        path.unlink()


@pytest.mark.parametrize("reason", ["no_owned_files", "no_claim_event", "ambiguous"])
def test_owned_review_without_a_provable_base_raises_the_typed_refusal(owned_checkouts: OwnedCheckouts, reason: str) -> None:
    _set_wp_frontmatter(owned_checkouts, owned_files="[]" if reason == "no_owned_files" else "[wp01.py]")
    if reason == "no_owned_files":
        _claim(owned_checkouts)
    if reason == "ambiguous":
        _claim(owned_checkouts)
        _submit(owned_checkouts)  # re-pin: only the ambiguous event commits leave the scoped range unavailable
        events = owned_checkouts.mission_dir / "status.events.jsonl"
        original = events.read_text(encoding="utf-8")
        events.write_text("", encoding="utf-8")
        _git(owned_checkouts.owned_root, "commit", "-qam", "remove the claim")
        events.write_text(original, encoding="utf-8")
        _git(owned_checkouts.owned_root, "commit", "-qam", "re-add the claim")

    with pytest.raises(ActionContextError) as raised:
        _build(owned_checkouts, "review")

    assert raised.value.code == OwnedRefusalCode.OWNED_REVIEW_BASE_UNAVAILABLE


def test_owned_implement_completion_commands_carry_the_owned_checkout_flag(owned_checkouts: OwnedCheckouts) -> None:
    checkouts = _spaced_owned_root(owned_checkouts)
    _set_wp_frontmatter(checkouts, owned_files="[wp01.py]", subtasks="[T001]")
    text, path = _build(checkouts, "implement")
    marks, moves = _completion_argv(text, "mark-status"), _completion_argv(text, "move-task")
    assert marks and moves
    for argv in marks:
        assert "T001" in argv
        assert argv[argv.index("--wp") + 1] == _WP
        assert argv[argv.index("--status") + 1] == "done"
    for argv in moves:
        assert argv[4] == _WP
        assert argv[argv.index("--to") + 1] == "for_review"
    for argv in marks + moves:
        assert argv[argv.index("--mission") + 1] == checkouts.mission_slug
        assert argv[argv.index("--owned-checkout") + 1] == str(checkouts.owned_root)
    path.unlink()


def test_owned_review_completion_commands_carry_the_owned_checkout_flag(owned_checkouts: OwnedCheckouts) -> None:
    checkouts = _spaced_owned_root(owned_checkouts)
    _set_wp_frontmatter(checkouts, owned_files="[wp01.py]")
    _claim(checkouts)
    _submit(checkouts)
    text, path = _build(checkouts, "review")
    moves = _completion_argv(text, "move-task")
    assert {argv[argv.index("--to") + 1] for argv in moves} == {"approved", "planned"}
    for argv in moves:
        assert argv[4] == _WP
        assert argv[argv.index("--mission") + 1] == checkouts.mission_slug
        assert argv[argv.index("--owned-checkout") + 1] == str(checkouts.owned_root)
    rejected = next(argv for argv in moves if argv[argv.index("--to") + 1] == "planned")
    assert rejected[rejected.index("--review-feedback-file") + 1] == "<feedback-file>"
    path.unlink()


def test_owned_template_prompt_is_written_under_the_owned_checkout_not_the_repository_root(owned_checkouts: OwnedCheckouts) -> None:
    _text, path = _build(owned_checkouts, "plan", wp_id=None)

    assert path.parent == prompt_tmp_dir(owned_checkouts.owned_root)
    assert path.parent != prompt_tmp_dir(owned_checkouts.repository_root)
    path.unlink()


@pytest.fixture
def owned_checkouts_lanes(make_owned_checkouts: Callable[..., OwnedCheckouts]) -> OwnedCheckouts:
    """An owned coordination-topology mission: its WPs resolve to a lane workspace (lane id set), not the lane-less owned arm."""
    return make_owned_checkouts(topology="lanes_with_coord")


@pytest.fixture
def stale_root_copy_for_lanes(owned_checkouts_lanes: OwnedCheckouts) -> Any:
    def _make() -> Path:
        root_mission = owned_checkouts_lanes.repository_root / "kitty-specs" / owned_checkouts_lanes.mission_slug
        shutil.copytree(owned_checkouts_lanes.mission_dir, root_mission)
        meta = root_mission / "meta.json"
        data = json.loads(meta.read_text(encoding="utf-8"))
        data["target_branch"] = "wrong-repository-root-target"
        meta.write_text(json.dumps(data), encoding="utf-8")
        return root_mission

    return _make


def test_owned_lane_review_base_is_the_facts_target_branch_not_the_repository_roots(owned_checkouts_lanes: OwnedCheckouts, stale_root_copy_for_lanes: Any) -> None:
    """Review cycle 1 MEDIUM-2: the owned lane arm takes its base from ``owned.write_branch``.

    R carries a stale copy of the mission whose ``meta.json`` names a different target
    branch; reading it would silently move the review base off the validated fact.
    """
    checkouts = owned_checkouts_lanes
    _set_wp_frontmatter(checkouts, owned_files="[wp01.py]")
    open_sha = _git(checkouts.owned_root, "rev-parse", "HEAD")
    window = {"lane_head": open_sha, "wp_window": {"schema_version": 1, "open_sha": open_sha}}
    _seed(checkouts, "01CLAIMAAAAAAAAAAAAAAAAAA1", Lane.PLANNED, Lane.CLAIMED, window)
    _seed(checkouts, "01PROGAAAAAAAAAAAAAAAAAAA1", Lane.CLAIMED, Lane.IN_PROGRESS, {"lane_head": open_sha})
    tip = _commit_work(checkouts, "wp01.py")
    _seed(checkouts, "01REVWAAAAAAAAAAAAAAAAAAA1", Lane.IN_PROGRESS, Lane.FOR_REVIEW, {"lane_head": tip})
    stale_root_copy_for_lanes()

    text, path = _build(checkouts, "review")

    # re-pin (IC-05): the base is the WP's recorded window open on the fact's status surface, never a target-branch ref.
    assert f"REVIEW RANGE ({_WP}): {open_sha[:12]}..{tip[:12]}  [recorded]" in text
    assert f"  git diff {open_sha}..{tip} -- wp01.py" in text
    assert f"{checkouts.target_branch}..HEAD" not in text
    assert "wrong-repository-root-target" not in text
    path.unlink()
