"""#3471: consecutive ``--no-auto-commit`` claims need no commit between them.

With auto-commit off, a claim leaves its own writes uncommitted: the allocator's WP frontmatter stamp
(``base_branch`` / ``base_commit`` / ``created_at``) and, on a topology without a coordination branch,
its status-log append and the snapshot materialized from it. The next claim's planning-artifact guard
used to read those self-writes as uncommitted planning edits and refuse. The guard now treats exactly
those self-writes as non-blocking; a genuine operator edit still blocks.

Every test drives the real command against a real git fixture; nothing is patched.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import Result

from specify_cli.charter_runtime.preflight.ambient_warning import _reset_surfaced_for_testing
from specify_cli.cli.commands.implement_cores import (
    _is_runtime_frontmatter_only_wp_diff,
    _is_self_write_only_diff,
    resolve_planning_artifact_staging,
)
from tests.specify_cli.cli.commands.test_implement_characterization import (
    MISSION_ID,
    SLUG,
    Mission,
    activate_repo,
    build_mission,
    flat,
    git,
    implement_cli,
    init_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

WPS = ("WP01", "WP02", "WP03")
NOT_COMMITTED = "Planning artifacts not committed:"


@pytest.fixture(autouse=True)
def _fresh_charter_warning() -> Iterator[None]:
    _reset_surfaced_for_testing()
    yield
    _reset_surfaced_for_testing()


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = init_repo(tmp_path / "repo")
    activate_repo(root, monkeypatch, tmp_path)
    return root


def _independent_lanes_mission(repo: Path) -> Mission:
    """Three independent code WPs, one lane each, on the ``lanes`` topology (status on PRIMARY)."""
    return build_mission(
        repo,
        SLUG,
        MISSION_ID,
        wps={wp_id: ("code_change", []) for wp_id in WPS},
        layout=tuple((f"lane-{wp_id[-1]}", (wp_id,), ()) for wp_id in WPS),
        spec_text="# Spec\n",
    )


def _claim(wp_id: str) -> Result:
    return implement_cli(wp_id, "--mission", SLUG, "--actor", "tester", "--no-auto-commit")


def _wp_file(mission: Mission, wp_id: str) -> Path:
    return mission.feature_dir / "tasks" / f"{wp_id}-test.md"


def test_n_consecutive_no_auto_commit_claims_need_no_commit_between_them(repo: Path) -> None:
    """The "no inter-allocation commit needed" contract, for real (no mocked status write).

    Planted break (proven red): drop the claim status self-write exemption from the planning guard.
    """
    mission = _independent_lanes_mission(repo)
    head_before = git(repo, "rev-parse", "HEAD")

    for wp_id in WPS:
        result = _claim(wp_id)
        assert result.exit_code == 0, result.output
        assert NOT_COMMITTED not in flat(result.output)

    assert git(repo, "rev-parse", "HEAD") == head_before
    lanes: dict[str, list[tuple[str, str]]] = {wp_id: [] for wp_id in WPS}
    for line in mission.events_path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("actor") == "tester":
            lanes[event["wp_id"]].append((event["from_lane"], event["to_lane"]))
    assert all(transitions == [("planned", "claimed"), ("claimed", "in_progress")] for transitions in lanes.values()), lanes
    for wp_id in WPS:
        assert (repo / ".worktrees" / f"{SLUG}-lane-{wp_id[-1]}").is_dir()


def test_the_claims_own_writes_are_staged_as_the_message_says(repo: Path) -> None:
    """ "changes staged only" is true: the claim's own writes are in the index, nothing is left unstaged.

    Planted break (proven red): drop the staging step from the ``--no-auto-commit`` branch of the claim commit.
    """
    mission = _independent_lanes_mission(repo)

    result = _claim("WP01")

    assert result.exit_code == 0, result.output
    assert "→ WP01 moved to 'doing' (auto-commit disabled, changes staged only)" in flat(result.output)
    rel = f"kitty-specs/{SLUG}"
    staged = set(git(repo, "diff", "--cached", "--name-only").splitlines())
    assert {f"{rel}/tasks/WP01-test.md", f"{rel}/status.events.jsonl", f"{rel}/status.json", f"{rel}/meta.json"} <= staged
    assert git(repo, "diff", "--name-only") == ""
    assert _wp_file(mission, "WP01").read_text(encoding="utf-8").count("created_at:") == 1


def test_a_failed_staging_is_reported_and_the_message_says_unstaged(repo: Path) -> None:
    """A held index lock makes ``git add`` fail: the claim still lands, and says so truthfully."""
    _independent_lanes_mission(repo)
    lock = repo / ".git" / "index.lock"
    lock.write_text("", encoding="utf-8")
    try:
        result = _claim("WP01")
    finally:
        lock.unlink()

    assert result.exit_code == 0, result.output
    text = flat(result.output)
    assert "Warning: Could not stage the claim's changes: git add --force -- " in text
    assert "→ WP01 moved to 'doing' (auto-commit disabled, changes left unstaged)" in text
    assert "changes staged only" not in text
    assert git(repo, "diff", "--cached", "--name-only") == ""


def test_an_ignored_claim_file_is_staged_with_the_rest_like_the_auto_commit_would_commit_it(repo: Path) -> None:
    """A consumer repository that ignores the status snapshot: the claim stages it with ``--force``,
    exactly as ``safe_commit`` would commit it, and never leaves the rest half-staged behind a warning.

    Planted break (proven red): stage with plain ``git add`` (git then stages the other paths and
    refuses the ignored one, and the claim reports "changes left unstaged").
    """
    mission = _independent_lanes_mission(repo)
    rel = f"kitty-specs/{SLUG}"
    (repo / ".gitignore").write_text(f"{rel}/status.json\n", encoding="utf-8")
    git(repo, "rm", "-q", "--cached", f"{rel}/status.json")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-q", "-m", "ignore the status snapshot")
    assert (mission.feature_dir / "status.json").exists()

    result = _claim("WP01")

    assert result.exit_code == 0, result.output
    text = flat(result.output)
    assert "→ WP01 moved to 'doing' (auto-commit disabled, changes staged only)" in text
    assert "Could not stage" not in text
    staged = set(git(repo, "diff", "--cached", "--name-only").splitlines())
    assert {f"{rel}/tasks/WP01-test.md", f"{rel}/status.events.jsonl", f"{rel}/status.json", f"{rel}/meta.json"} <= staged
    assert git(repo, "diff", "--name-only") == ""


def test_a_hand_edit_to_the_spec_between_claims_still_blocks(repo: Path) -> None:
    mission = _independent_lanes_mission(repo)
    assert _claim("WP01").exit_code == 0
    (mission.feature_dir / "spec.md").write_text("# Spec\nEdited by hand.\n", encoding="utf-8")

    result = _claim("WP02")

    assert result.exit_code == 1, result.output
    text = flat(result.output)
    assert NOT_COMMITTED in text
    assert f"kitty-specs/{SLUG}/spec.md" in text
    assert not (repo / ".worktrees" / f"{SLUG}-lane-2").exists()


def test_a_hand_edit_to_a_non_runtime_frontmatter_field_between_claims_still_blocks(repo: Path) -> None:
    mission = _independent_lanes_mission(repo)
    assert _claim("WP01").exit_code == 0
    wp01 = _wp_file(mission, "WP01")
    wp01.write_text(wp01.read_text(encoding="utf-8").replace("title: WP01 code_change", "title: WP01 renamed by hand"), encoding="utf-8")

    result = _claim("WP02")

    assert result.exit_code == 1, result.output
    text = flat(result.output)
    assert NOT_COMMITTED in text
    assert f"kitty-specs/{SLUG}/tasks/WP01-test.md" in text


def test_a_hand_edit_to_the_status_snapshot_between_claims_still_blocks(repo: Path) -> None:
    """The snapshot counts as the claim's own write only while it is exactly what the event log materializes to."""
    mission = _independent_lanes_mission(repo)
    assert _claim("WP01").exit_code == 0
    snapshot_path = mission.feature_dir / "status.json"
    snapshot_path.write_text(snapshot_path.read_text(encoding="utf-8").replace('"in_progress"', '"approved"', 1), encoding="utf-8")

    result = _claim("WP02")

    assert result.exit_code == 1, result.output
    assert f"kitty-specs/{SLUG}/status.json" in flat(result.output)


def test_an_appended_non_claim_status_event_between_claims_still_blocks(repo: Path) -> None:
    """Only claim transitions (planned -> claimed -> in_progress) count as the claim's own status appends."""
    mission = _independent_lanes_mission(repo)
    assert _claim("WP01").exit_code == 0
    last = json.loads(mission.events_path.read_text(encoding="utf-8").splitlines()[-1])
    foreign = {**last, "event_id": "01FOREIGNEVENT0000000000ZZ", "from_lane": "in_progress", "to_lane": "for_review", "actor": "someone"}
    with mission.events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(foreign, sort_keys=True) + "\n")

    result = _claim("WP02")

    assert result.exit_code == 1, result.output
    assert f"kitty-specs/{SLUG}/status.events.jsonl" in flat(result.output)


def test_a_corrupt_status_log_between_claims_still_reads_as_not_committed(repo: Path) -> None:
    """A corrupt event log keeps both status files in the "not committed" set; it never raises.

    The command's own claim preflight reads the log first and refuses a corrupt one, so this drives
    the planning guard's staging core directly, on the state a real claim left behind.

    Planted break (proven red): restore the pre-fix snapshot leg, which rebuilt the snapshot before
    judging the event log and so raised ``StoreError`` from the corrupt log.
    """
    mission = _independent_lanes_mission(repo)
    assert _claim("WP01").exit_code == 0
    with mission.events_path.open("a", encoding="utf-8") as handle:
        handle.write('{"truncated": \n')
    rel = f"kitty-specs/{SLUG}"

    plan = resolve_planning_artifact_staging(repo, mission.feature_dir, None, [], auto_commit=False)

    assert {f"{rel}/status.events.jsonl", f"{rel}/status.json"} <= set(plan.files_to_commit)
    assert _is_self_write_only_diff(repo, f"{rel}/status.json", None) is False


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        ({"base_branch": "b", "base_commit": "c", "created_at": "t"}, True),
        ({"base_commit": "c", "created_at": "t"}, True),
        ({"created_at": "t"}, False),
        ({"base_commit": "c", "created_at": "t", "title": "x"}, False),
    ],
    ids=["allocator-stamp", "re-stamp", "created-at-alone", "stamp-plus-operator-edit"],
)
def test_created_at_counts_as_runtime_only_inside_the_allocator_stamp(changed: dict[str, str], expected: bool) -> None:
    """``created_at`` is the allocator's stamp only together with ``base_commit``; alone it is an operator edit.

    Planted break (proven red): add ``created_at`` to the runtime-field set unconditionally.
    """
    committed = {"work_package_id": "WP01", "title": "t0"}
    working = {**committed, **changed}

    assert _is_runtime_frontmatter_only_wp_diff(committed, working, "body", "body") is expected
