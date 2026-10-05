"""Target-owned conflict resolution at the git-merge sites (#5457, WP04).

``resolve_target_owned_conflicts`` keeps stage 2 ("ours", the receiving side)
for an unmerged target-owned path, or removes the path when ours deleted it.
Every other unmerged path stays unmerged (#4892: no ``-X ours``/``-X theirs``).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from specify_cli import __version__ as CURRENT_CLI_VERSION
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.lanes.consolidation import (
    _complete_merge_after_target_owned_resolution,
    _make_merge_env,
    _merge_branch_into,
    _run_squash_merge,
    _SquashMergeConflict,
    _unmerged_paths,
    resolve_target_owned_conflicts,
)
from specify_cli.migration.schema_version import REQUIRED_SCHEMA_VERSION

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

METADATA = ".kittify/metadata.yaml"
SOURCE = "src/x.py"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=check)


def _write(repo: Path, files: Mapping[str, str | None]) -> None:
    for rel, content in files.items():
        path = repo / rel
        if content is None:
            _git(repo, "rm", "-q", "--", rel)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        _git(repo, "add", "--", rel)


def _commit(repo: Path, files: Mapping[str, str | None], message: str) -> None:
    _write(repo, files)
    _git(repo, "commit", "-qm", message)


def _conflicted_repo(tmp_path: Path, ours: Mapping[str, str | None], theirs: Mapping[str, str | None]) -> Path:
    """A repo on ``ours`` with a failed ``git merge theirs`` in progress."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-qb", "ours")
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    _commit(repo, {METADATA: "version: base\n", SOURCE: "x = 0\n"}, "base")
    _git(repo, "branch", "theirs")
    _commit(repo, ours, "ours")
    _git(repo, "checkout", "-q", "theirs")
    _commit(repo, theirs, "theirs")
    _git(repo, "checkout", "-q", "ours")
    merge = _git(repo, "merge", "--no-edit", "-m", "Merge theirs into ours", "theirs", check=False)
    assert merge.returncode != 0, merge.stdout
    return repo


def _index_blob(repo: Path, rel: str) -> str | None:
    shown = _git(repo, "show", f":{rel}", check=False)
    return shown.stdout if shown.returncode == 0 else None


def _fail_git_probes(monkeypatch: pytest.MonkeyPatch, *subcommands: str) -> None:
    """Make every ``git <subcommand>`` fail with a spurious exit 128 (all other git calls run for real)."""
    real_run = subprocess.run

    def fake_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, (list, tuple)) and any(sub in cmd for sub in subcommands):
            empty = "" if kwargs.get("text") else b""
            return subprocess.CompletedProcess(cmd, 128, stdout=empty, stderr=empty)
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)


@pytest.mark.parametrize("probe_fails", [False, True], ids=["resolves-to-ours", "spurious-git-probe-failure-deletes-nothing"])
def test_both_modified_resolves_to_ours(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe_fails: bool) -> None:
    repo = _conflicted_repo(tmp_path, {METADATA: "version: ours\n"}, {METADATA: "version: theirs\n"})
    env = _make_merge_env()
    if probe_fails:
        # A stage probe failing for a reason other than "the stage is absent"
        # must leave the path unresolved, never be read as "ours deleted it".
        with monkeypatch.context() as probe_failure:
            _fail_git_probes(probe_failure, "cat-file", "ls-files")
            assert resolve_target_owned_conflicts(repo, env) == []
        assert _unmerged_paths(repo, env) == (METADATA,)
        assert (repo / METADATA).exists()
        return

    assert resolve_target_owned_conflicts(repo, env) == [METADATA]

    assert _unmerged_paths(repo, env) == ()
    assert _index_blob(repo, METADATA) == "version: ours\n"
    assert (repo / METADATA).read_text(encoding="utf-8") == "version: ours\n"


def test_modify_delete_with_ours_deleted_removes_the_path(tmp_path: Path) -> None:
    repo = _conflicted_repo(tmp_path, {METADATA: None}, {METADATA: "version: theirs\n"})
    env = _make_merge_env()

    assert resolve_target_owned_conflicts(repo, env) == [METADATA]

    assert _unmerged_paths(repo, env) == ()
    assert _index_blob(repo, METADATA) is None
    assert not (repo / METADATA).exists()


def test_delete_modify_with_ours_modified_keeps_ours(tmp_path: Path) -> None:
    repo = _conflicted_repo(tmp_path, {METADATA: "version: ours\n"}, {METADATA: None})
    env = _make_merge_env()

    assert resolve_target_owned_conflicts(repo, env) == [METADATA]

    assert _unmerged_paths(repo, env) == ()
    assert _index_blob(repo, METADATA) == "version: ours\n"


def test_mixed_set_resolves_only_the_target_owned_path(tmp_path: Path) -> None:
    repo = _conflicted_repo(
        tmp_path,
        {METADATA: "version: ours\n", SOURCE: "x = 1\n"},
        {METADATA: "version: theirs\n", SOURCE: "x = 2\n"},
    )
    env = _make_merge_env()

    assert resolve_target_owned_conflicts(repo, env) == [METADATA]

    assert _unmerged_paths(repo, env) == (SOURCE,)
    assert _index_blob(repo, METADATA) == "version: ours\n"
    assert "<<<<<<<" in (repo / SOURCE).read_text(encoding="utf-8")


def test_lookalike_paths_are_not_target_owned(tmp_path: Path) -> None:
    nested = "sub/.kittify/metadata.yaml"
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-qb", "ours")
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    _commit(repo, {nested: "base\n"}, "base")
    _git(repo, "branch", "theirs")
    _commit(repo, {nested: "ours\n"}, "ours")
    _git(repo, "checkout", "-q", "theirs")
    _commit(repo, {nested: "theirs\n"}, "theirs")
    _git(repo, "checkout", "-q", "ours")
    assert _git(repo, "merge", "--no-edit", "theirs", check=False).returncode != 0
    env = _make_merge_env()

    assert resolve_target_owned_conflicts(repo, env) == []
    assert _unmerged_paths(repo, env) == (nested,)


def test_non_conflicted_tree_is_a_no_op(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-qb", "ours")
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    _commit(repo, {METADATA: "version: base\n"}, "base")
    head = _git(repo, "rev-parse", "HEAD").stdout

    assert resolve_target_owned_conflicts(repo, _make_merge_env()) == []
    assert _git(repo, "rev-parse", "HEAD").stdout == head
    assert _git(repo, "status", "--porcelain").stdout == ""


def test_resolution_is_idempotent_and_deterministic(tmp_path: Path) -> None:
    """NFR-004: the same inputs give byte-identical content, without markers."""
    contents = []
    for run in ("a", "b"):
        repo = _conflicted_repo(tmp_path / run, {METADATA: "version: ours\n"}, {METADATA: "version: theirs\n"})
        env = _make_merge_env()
        assert resolve_target_owned_conflicts(repo, env) == [METADATA]
        assert resolve_target_owned_conflicts(repo, env) == []
        contents.append((repo / METADATA).read_bytes())
    assert contents[0] == contents[1] == b"version: ours\n"


# ---------------------------------------------------------------------------
# _complete_merge_after_target_owned_resolution: the resolve-and-commit step
# ---------------------------------------------------------------------------


def test_complete_merge_commits_when_only_target_owned_paths_conflicted(tmp_path: Path) -> None:
    repo = _conflicted_repo(tmp_path, {METADATA: "version: ours\n"}, {METADATA: "version: theirs\n", SOURCE: "x = 2\n"})

    assert _complete_merge_after_target_owned_resolution(repo, _make_merge_env()) is True

    parents = _git(repo, "rev-list", "--parents", "-n", "1", "HEAD").stdout.split()
    assert len(parents) == 3, "a real merge commit with both parents"
    assert _git(repo, "log", "-1", "--format=%s").stdout.strip() == "Merge theirs into ours"
    assert _git(repo, "show", f"HEAD:{METADATA}").stdout == "version: ours\n"
    assert _git(repo, "show", f"HEAD:{SOURCE}").stdout == "x = 2\n"
    assert _git(repo, "status", "--porcelain").stdout == ""


def test_complete_merge_leaves_a_genuine_conflict_uncommitted(tmp_path: Path) -> None:
    repo = _conflicted_repo(
        tmp_path,
        {METADATA: "version: ours\n", SOURCE: "x = 1\n"},
        {METADATA: "version: theirs\n", SOURCE: "x = 2\n"},
    )
    head = _git(repo, "rev-parse", "HEAD").stdout
    env = _make_merge_env()

    assert _complete_merge_after_target_owned_resolution(repo, env) is False

    assert _git(repo, "rev-parse", "HEAD").stdout == head
    assert _unmerged_paths(repo, env) == (SOURCE,)


def test_complete_merge_without_target_owned_conflicts_does_nothing(tmp_path: Path) -> None:
    repo = _conflicted_repo(tmp_path, {SOURCE: "x = 1\n"}, {SOURCE: "x = 2\n"})
    head = _git(repo, "rev-parse", "HEAD").stdout
    env = _make_merge_env()

    assert _complete_merge_after_target_owned_resolution(repo, env) is False

    assert _git(repo, "rev-parse", "HEAD").stdout == head
    assert _unmerged_paths(repo, env) == (SOURCE,)


# ---------------------------------------------------------------------------
# _merge_branch_into: the MERGE branch (lane -> mission and --strategy merge
# mission -> target) and the default squash
# ---------------------------------------------------------------------------

TARGET = "work"
MISSION = "kitty/mission-demo-01M5457A"
LANE_CODE = "src/lane_a/m.py"


def _integration_repo(tmp_path: Path, *, source_conflict: bool = False, lane_work: bool = True) -> Path:
    """``work`` (checked out) and a mission branch, each with its own upgrade-written metadata."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-qb", TARGET)
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    _commit(repo, {METADATA: "version: base\n", SOURCE: "x = 0\n"}, "base")
    _git(repo, "branch", MISSION)
    target_files: dict[str, str | None] = {METADATA: "version: target\n"}
    if source_conflict:
        target_files[SOURCE] = "x = target\n"
    _commit(repo, target_files, "chore: upgrade (target)")
    _git(repo, "checkout", "-q", MISSION)
    mission_files: dict[str, str | None] = {METADATA: "version: mission\n"}
    if lane_work:
        mission_files[LANE_CODE] = "def wp01() -> int:\n    return 1\n"
    if source_conflict:
        mission_files[SOURCE] = "x = mission\n"
    _commit(repo, mission_files, "feat: lane work + upgrade (mission)")
    _git(repo, "checkout", "-q", TARGET)
    return repo


def _tip(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def test_merge_strategy_mission_to_target_keeps_target_metadata(tmp_path: Path) -> None:
    """FR-007, ``--strategy merge`` leg: the target's metadata survives, the lane code lands."""
    repo = _integration_repo(tmp_path)
    before = _tip(repo, TARGET)

    assert _merge_branch_into(repo, MISSION, TARGET, strategy=MergeStrategy.MERGE) is True

    assert _git(repo, "show", f"{TARGET}:{METADATA}").stdout == "version: target\n"
    assert _git(repo, "show", f"{TARGET}:{LANE_CODE}").returncode == 0
    parents = _git(repo, "rev-list", "--parents", "-n", "1", TARGET).stdout.split()
    assert parents[1:] == [before, _tip(repo, MISSION)]
    assert _git(repo, "log", "-1", "--format=%s", TARGET).stdout.strip() == f"Merge {MISSION} into {TARGET}"


def test_merge_strategy_lane_to_mission_keeps_mission_metadata(tmp_path: Path) -> None:
    """FR-012: the lane -> mission merge resolves to the mission (receiving) side."""
    repo = _integration_repo(tmp_path)

    assert _merge_branch_into(repo, TARGET, MISSION) is True

    assert _git(repo, "show", f"{MISSION}:{METADATA}").stdout == "version: mission\n"


def test_merge_strategy_source_conflict_still_raises(tmp_path: Path) -> None:
    """MERGE-branch control (FR-009): a genuine source conflict aborts and raises as today."""
    repo = _integration_repo(tmp_path, source_conflict=True)
    before = _tip(repo, TARGET)

    with pytest.raises(RuntimeError, match=rf"(?s)^Merge of {MISSION} into {TARGET} failed: .*CONFLICT \(content\): Merge conflict in {SOURCE}"):
        _merge_branch_into(repo, MISSION, TARGET, strategy=MergeStrategy.MERGE)

    assert _tip(repo, TARGET) == before


def test_squash_keeps_target_metadata(tmp_path: Path) -> None:
    repo = _integration_repo(tmp_path)

    assert _merge_branch_into(repo, MISSION, TARGET, strategy=MergeStrategy.SQUASH) is True

    assert _git(repo, "show", f"{TARGET}:{METADATA}").stdout == "version: target\n"
    assert _git(repo, "show", f"{TARGET}:{LANE_CODE}").returncode == 0


def test_squash_source_conflict_names_only_the_source_path(tmp_path: Path) -> None:
    """Squash control: the refusal names exactly the genuine conflict."""
    repo = _integration_repo(tmp_path, source_conflict=True)
    before = _tip(repo, TARGET)

    with pytest.raises(_SquashMergeConflict) as raised:
        _merge_branch_into(repo, MISSION, TARGET, strategy=MergeStrategy.SQUASH)

    assert raised.value.conflicting_paths == (SOURCE,)
    assert str(raised.value) == f"Squash merge of {MISSION} into {TARGET} failed: unresolved content conflict(s): {SOURCE}"
    assert _tip(repo, TARGET) == before


def test_squash_conflict_of_only_target_owned_paths_reports_reconciliation_with_nothing_staged(tmp_path: Path) -> None:
    """P2: a metadata-only conflict resolves to the target copy; True = a reconciliation was needed.

    The mission carries nothing but its own upgrade-written metadata, so after the
    stage-2 resolution the index equals the target tree: nothing is staged.
    """
    repo = _integration_repo(tmp_path, lane_work=False)
    env = _make_merge_env()

    assert _run_squash_merge(repo, repo, MISSION, TARGET, env) is True

    assert _unmerged_paths(repo, env) == ()
    assert _git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0
    assert _index_blob(repo, METADATA) == "version: target\n"


def test_squash_of_only_target_owned_conflicts_is_an_honest_noop(tmp_path: Path) -> None:
    """P2: nothing staged after a target-owned-only reconciliation is a no-op, never an empty commit.

    ``_merge_branch_into`` treats the reconciliation flag like a planning
    reconciliation: it returns ``False`` (no change) for the executor's zero-diff
    guard to adjudicate, and the target ref does not move.
    """
    repo = _integration_repo(tmp_path, lane_work=False)
    before = _tip(repo, TARGET)

    assert _merge_branch_into(repo, MISSION, TARGET, strategy=MergeStrategy.SQUASH) is False

    assert _tip(repo, TARGET) == before
    assert _git(repo, "show", f"{TARGET}:{METADATA}").stdout == "version: target\n"


# ---------------------------------------------------------------------------
# FR-007 "whatever other derived paths conflict": the MERGE branch reconciles a
# derived status.json snapshot left after the target-owned resolution, in the
# same order as the squash and dependency-lane sites.
# ---------------------------------------------------------------------------

STATUS_SLUG = "status-demo"
STATUS_DIR = f"kitty-specs/{STATUS_SLUG}"
STATUS_JSON = f"{STATUS_DIR}/status.json"
STATUS_EVENTS = f"{STATUS_DIR}/status.events.jsonl"


def _current_metadata(side: str) -> str:
    """A ``metadata.yaml`` the CLI's migration gate accepts (the event-log driver shells out to it)."""
    return (
        "spec_kitty:\n"
        f"  version: {CURRENT_CLI_VERSION}\n"
        "  initialized_at: '2026-01-01T00:00:00'\n"
        f"  last_upgraded_at: '{side}'\n"
        f"  schema_version: {REQUIRED_SCHEMA_VERSION}\n"
    )


def _status_event_line(event_id: str, wp_id: str, at: str) -> str:
    return (
        json.dumps(
            {
                "event_id": event_id,
                "mission_slug": STATUS_SLUG,
                "wp_id": wp_id,
                "from_lane": "genesis",
                "to_lane": "planned",
                "at": at,
                "actor": "seed",
                "force": False,
                "execution_mode": "worktree",
                "reason": None,
                "review_ref": None,
                "evidence": None,
            }
        )
        + "\n"
    )


def _status_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, source_conflict: bool = False) -> Path:
    """Both branches diverge on metadata.yaml AND add a divergent status.json + a union-able event log."""
    # The event-log merge driver shells out to this interpreter's spec-kitty.
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""))
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-qb", TARGET)
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    _commit(repo, {METADATA: _current_metadata("base"), SOURCE: "x = 0\n"}, "base")
    _git(repo, "branch", MISSION)
    target_files: dict[str, str | None] = {
        METADATA: _current_metadata("target"),
        STATUS_EVENTS: _status_event_line("01EVTTARGET0000000000000BB", "WP02", "2026-08-22T08:00:00Z"),
        STATUS_JSON: json.dumps({"stale_side": "target"}) + "\n",
    }
    if source_conflict:
        target_files[SOURCE] = "x = target\n"
    _commit(repo, target_files, "chore: upgrade + status (target)")
    _git(repo, "checkout", "-q", MISSION)
    mission_files: dict[str, str | None] = {
        METADATA: _current_metadata("mission"),
        LANE_CODE: "def wp01() -> int:\n    return 1\n",
        STATUS_EVENTS: _status_event_line("01EVTSOURCE0000000000000AA", "WP01", "2026-08-22T09:00:00Z"),
        STATUS_JSON: json.dumps({"stale_side": "mission"}) + "\n",
    }
    if source_conflict:
        mission_files[SOURCE] = "x = mission\n"
    _commit(repo, mission_files, "feat: lane work + upgrade + status (mission)")
    _git(repo, "checkout", "-q", TARGET)
    return repo


def _assert_status_regenerated(repo: Path, ref: str) -> None:
    snapshot = _git(repo, "show", f"{ref}:{STATUS_JSON}").stdout
    assert "stale_side" not in snapshot, "status.json must be regenerated, not either side's stale copy"
    assert "<<<<<<<" not in snapshot
    assert "WP01" in snapshot and "WP02" in snapshot, "regenerated from the union-merged event log"


def test_merge_strategy_mission_to_target_reconciles_derived_status_after_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-007, ``--strategy merge``: metadata keeps the target copy, status.json is regenerated."""
    repo = _status_repo(tmp_path, monkeypatch)
    before = _tip(repo, TARGET)

    assert _merge_branch_into(repo, MISSION, TARGET, strategy=MergeStrategy.MERGE) is True

    assert _git(repo, "show", f"{TARGET}:{METADATA}").stdout == _current_metadata("target")
    assert _git(repo, "show", f"{TARGET}:{LANE_CODE}").returncode == 0
    _assert_status_regenerated(repo, TARGET)
    parents = _git(repo, "rev-list", "--parents", "-n", "1", TARGET).stdout.split()
    assert parents[1:] == [before, _tip(repo, MISSION)]


def test_merge_strategy_lane_to_mission_reconciles_derived_status_after_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-012 + FR-007: the lane -> mission merge keeps the mission's metadata and regenerates status.json."""
    repo = _status_repo(tmp_path, monkeypatch)

    assert _merge_branch_into(repo, TARGET, MISSION) is True

    assert _git(repo, "show", f"{MISSION}:{METADATA}").stdout == _current_metadata("mission")
    _assert_status_regenerated(repo, MISSION)


def test_merge_strategy_source_conflict_beside_metadata_and_status_still_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control (FR-009): a genuine source conflict next to both still refuses with the original text."""
    repo = _status_repo(tmp_path, monkeypatch, source_conflict=True)
    before = _tip(repo, TARGET)

    with pytest.raises(RuntimeError, match=rf"(?s)^Merge of {MISSION} into {TARGET} failed: .*CONFLICT \(content\): Merge conflict in {SOURCE}"):
        _merge_branch_into(repo, MISSION, TARGET, strategy=MergeStrategy.MERGE)

    assert _tip(repo, TARGET) == before


def test_merge_strategy_unreadable_conflict_set_aborts_and_raises_the_merge_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown conflict set fails closed through the existing abort + raise (allocator parity)."""
    import specify_cli.lanes.consolidation as consolidation

    repo = _integration_repo(tmp_path)
    before = _tip(repo, TARGET)

    def _unreadable(worktree: Path, env: dict[str, str]) -> tuple[str, ...]:
        raise RuntimeError("Could not inspect squash merge conflicts: boom")

    calls: list[list[str]] = []
    real_run = subprocess.run

    def _recording_run(args: list[str], *a: Any, **kw: Any) -> Any:
        calls.append(list(args))
        return real_run(args, *a, **kw)

    monkeypatch.setattr(consolidation, "_unmerged_paths", _unreadable)
    monkeypatch.setattr(subprocess, "run", _recording_run)

    with pytest.raises(RuntimeError, match=rf"^Merge of {MISSION} into {TARGET} failed: "):
        _merge_branch_into(repo, MISSION, TARGET, strategy=MergeStrategy.MERGE)

    assert ["git", "merge", "--abort"] in calls
    assert _tip(repo, TARGET) == before
