"""Permanent guard: ``mission close --discard`` is transactional and honest.

Issue #3716 (FIXED): the ``--discard`` path on a coord-topology mission had two
defects, both surfaced through the REAL ``spec-kitty mission close --discard
--force`` entry point:

Defect 1 — uncommitted ``meta.json`` flatten.
    ``_flatten_discarded_mission`` pops ``coordination_branch`` + ``topology``
    and sets ``flattened: true`` in ``meta.json`` as the LAST write on the path,
    and used to have NO commit leg. A command that reported success left
    ``M kitty-specs/<slug>/meta.json`` in ``git status --porcelain``. The fix
    (``mission_type._commit_flattened_meta``) commits the flatten to the PRIMARY
    surface — the mission's ``target_branch`` — never the coordination branch,
    which the discard already deleted.

Defect 2 — completion provenance on an abandoned mission.
    The retrospective the discard path persisted was stamped
    ``provenance.kind: runtime_post_completion`` because ``ProvenanceKind`` had
    no abandonment member. The fix adds ``runtime_abandoned`` and threads it from
    the discard leg (``_discard_mission`` → ``teardown_coordination_topology`` →
    ``run_retrospective_postcondition`` → the facilitator's ``provenance_kind``),
    so an abandoned mission is no longer tagged as completed.

These are now permanent regression guards against those two defects recurring.
The sibling ``test_mission_close_discard_coord_teardown.py`` drives the same real
CLI entry point and split-brain coord fixture.
"""

from __future__ import annotations

import json
import logging
import re
import shlex
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from specify_cli.cli.commands import mission_type
from specify_cli.coordination import CoordinationWorkspace

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

MISSION_ID = "01J6XW9K000000000000000000"
MID8 = MISSION_ID[:8]
SLUG = f"demo-coord-mission-{MID8}"
COORD_BRANCH = CoordinationWorkspace.branch_name(SLUG, MID8)

# The completion provenance kind that must NOT be stamped on a discarded mission.
_COMPLETION_PROVENANCE_KIND = "runtime_post_completion"
# The abandonment provenance kind the discard leg must stamp instead (#3716).
_ABANDONED_PROVENANCE_KIND = "runtime_abandoned"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def coord_mission(tmp_path: Path) -> Path:
    """A coordination-topology mission in the split-brain surface layout.

    Primary branch carries meta.json (with ``coordination_branch`` +
    ``topology: coord``) + lanes.json; the coordination branch's mission dir is
    status-only; a real coordination worktree is materialised.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".kittify").mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    # A real spec-kitty project gitignores its own sync-state frame (see e.g.
    # ``test_accept_residual_partition.py``); without this, the whole-tree
    # porcelain assertion below would spuriously trip on the offline queue's
    # ambient ``.kittify/sync-state.json`` local write, which is unrelated to
    # the #3716 defect under test.
    (repo / ".gitignore").write_text(".worktrees/\n.kittify/sync-state.json\n", encoding="utf-8")

    fdir = repo / "kitty-specs" / SLUG
    fdir.mkdir(parents=True)
    (fdir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": SLUG,
                "mission_id": MISSION_ID,
                "mid8": MID8,
                "coordination_branch": COORD_BRANCH,
                "mission_branch": COORD_BRANCH,
                "target_branch": "main",
                "topology": "coord",
                "flattened": False,
            }
        ),
        encoding="utf-8",
    )
    (fdir / "lanes.json").write_text(
        json.dumps(
            {
                "version": 1,
                "mission_slug": SLUG,
                "mission_id": MISSION_ID,
                "mission_branch": COORD_BRANCH,
                "target_branch": "main",
                "computed_at": "2026-01-01T00:00:00+00:00",
                "computed_from": "test",
                "lanes": [
                    {
                        "lane_id": "lane-a",
                        "wp_ids": ["WP01"],
                        "write_scope": [],
                        "predicted_surfaces": [],
                        "depends_on_lanes": [],
                        "parallel_group": 0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (fdir / "status.events.jsonl").write_text("", encoding="utf-8")
    (fdir / "status.json").write_text("{}", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed primary mission surface")

    # Coordination branch: status-only mission dir (drop planning artifacts).
    _git(repo, "branch", COORD_BRANCH)
    _git(repo, "checkout", "-q", COORD_BRANCH)
    _git(
        repo,
        "rm",
        "-q",
        f"kitty-specs/{SLUG}/meta.json",
        f"kitty-specs/{SLUG}/lanes.json",
    )
    _git(repo, "commit", "-q", "-m", "coord: status-only mission surface")
    _git(repo, "checkout", "-q", "main")

    # Materialise the real coordination worktree (full checkout of coord branch).
    CoordinationWorkspace.resolve(repo, SLUG, MID8)
    assert CoordinationWorkspace.is_present(repo, SLUG, MID8)
    return repo


def _run_discard(repo: Path) -> None:
    result = runner.invoke(
        mission_type.app,
        ["close", "--mission", SLUG, "--discard", "--force"],
        env={"PWD": str(repo)},
    )
    assert result.exit_code == 0, result.output


def _porcelain_paths(repo: Path) -> list[str]:
    out = _git(repo, "status", "--porcelain").stdout
    return [line[3:] for line in out.splitlines() if line.strip()]


def test_close_discard_commits_meta_flatten(coord_mission: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Defect 1: after ``--discard`` reports success, its own ``meta.json``
    flatten is committed — the WHOLE working tree is clean, not just
    ``meta.json`` in isolation.

    (squad) Strengthened from a ``meta.json``-only check to a whole-tree
    ``git status --porcelain`` empty assertion: the retrospective the discard
    path persists (``retrospective.yaml``, pinned by
    ``test_teardown_seam_persist_before_destroy``) is written to the SAME
    working tree by the SAME command invocation, so a narrower check that
    only inspects ``meta.json`` would miss an uncommitted retrospective write
    landing alongside it. A real spec-kitty project's own ambient
    ``.kittify/sync-state.json`` is gitignored by the fixture above so it
    cannot produce a false positive here.
    """
    repo = coord_mission
    monkeypatch.chdir(repo)

    _run_discard(repo)

    dirty = _porcelain_paths(repo)
    assert dirty == [], (
        "issue #3716 defect 1 (squad-strengthened): `mission close --discard` "
        "reported success but left the working tree dirty — either its own "
        "meta.json flatten, or the retrospective it persists alongside it, is "
        f"uncommitted. git status --porcelain: {dirty!r}"
    )


def test_close_discard_retrospective_provenance_is_abandoned(coord_mission: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Defect 2: the retrospective persisted by ``--discard`` is stamped with
    abandonment provenance, never completion provenance.
    """
    repo = coord_mission
    monkeypatch.chdir(repo)

    _run_discard(repo)

    retro_path = repo / "kitty-specs" / SLUG / "retrospective.yaml"
    assert retro_path.exists(), "the discard path is expected to persist a retrospective (pinned by test_teardown_seam_persist_before_destroy)"
    data = yaml.safe_load(retro_path.read_text(encoding="utf-8"))
    kind = (data.get("provenance") or {}).get("kind")
    assert kind != _COMPLETION_PROVENANCE_KIND, f"issue #3716 defect 2: a discarded/abandoned mission must NOT be stamped with completion provenance ({kind!r})."
    assert kind == _ABANDONED_PROVENANCE_KIND, (
        f"issue #3716 defect 2: the discard leg must stamp the abandonment provenance kind {_ABANDONED_PROVENANCE_KIND!r}; got {kind!r}."
    )


@pytest.mark.regression
def test_close_discard_commit_failure_points_at_the_idempotent_rerun(coord_mission: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The warning names a command that works, never a raw git recipe (#5078).

    When the flatten's bookkeeping commit fails, ``meta.json`` is left
    uncommitted. The re-run of the SAME ``mission close --discard --force``
    heals it (a ``safe-commit`` recipe would be refused on a protected target),
    so that is what the warning must point at -- and the re-run must really
    leave the tree clean.
    """
    repo = coord_mission
    monkeypatch.chdir(repo)

    with patch("specify_cli.git.bookkeeping_commit.commit_merge_bookkeeping", side_effect=RuntimeError("boom")):
        result = runner.invoke(mission_type.app, ["close", "--mission", SLUG, "--discard", "--force"], env={"PWD": str(repo)})
    assert result.exit_code == 0, result.output
    assert f"kitty-specs/{SLUG}/meta.json" in _porcelain_paths(repo)

    flat = " ".join(result.output.split())  # rich wraps long lines
    assert f"`spec-kitty mission close --mission {SLUG} --discard --force`" in flat, flat
    assert "project root" in flat, flat
    for forbidden in ("git -C", "git add", "git commit", "safe-commit", "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"):
        assert forbidden not in flat, (forbidden, flat)

    _run_discard(repo)  # the printed command, run from the project root
    assert _porcelain_paths(repo) == []


_REFUSING_HOOK = "#!/bin/sh\necho 'commit refused by test hook' >&2\nexit 1\n"


def _retarget_to_topic_branch(repo: Path) -> None:
    """Make ``topic`` the Mission's non-protected target; ``main`` stays the primary branch."""
    _git(repo, "update-ref", "refs/remotes/origin/main", "main")
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    _git(repo, "checkout", "-q", "-b", "topic")
    for name in ("meta.json", "lanes.json"):
        path = repo / "kitty-specs" / SLUG / name
        data = json.loads(path.read_text(encoding="utf-8"))
        data["target_branch"] = "topic"
        path.write_text(json.dumps(data), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "target the topic branch")


@pytest.mark.regression
@pytest.mark.parametrize("target", ["main", "topic"], ids=["protected-main", "non-protected-topic"])
def test_printed_close_command_heals_a_failed_retrospective_commit(
    coord_mission: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, target: str
) -> None:
    """The command the retrospective warning prints really commits the leftovers (#2280, #5078).

    Real path, nothing in-repo is mocked: a merged coordination Mission is closed
    while a ``pre-commit`` hook refuses every commit, so the fail-open retrospective
    commit leaves ``retrospective.yaml`` and the event-log append dirty and logs
    its warning. The command is lifted from that warning and run from the project
    root once the hook is gone. If the printed command ever stops healing, this
    fails.
    """
    repo = coord_mission
    if target == "topic":
        _retarget_to_topic_branch(repo)
    meta_path = repo / "kitty-specs" / SLUG / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["merged_at"] = "2026-01-02T00:00:00+00:00"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "mark the mission merged")
    monkeypatch.chdir(repo)

    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(_REFUSING_HOOK, encoding="utf-8")
    hook.chmod(0o755)
    with caplog.at_level(logging.WARNING):
        first = runner.invoke(mission_type.app, ["close", "--mission", SLUG], env={"PWD": str(repo)})
    assert first.exit_code == 0, first.output
    dirty = _porcelain_paths(repo)
    assert f"kitty-specs/{SLUG}/retrospective.yaml" in dirty, dirty

    warning = " ".join(rec.getMessage() for rec in caplog.records if "could NOT be committed" in rec.getMessage())
    assert warning, [rec.getMessage() for rec in caplog.records]
    printed = re.findall(r"`(spec-kitty [^`]+)`", warning)
    assert len(printed) == 1, warning
    guidance = warning.split("From the project root", 1)[1]  # the failure text above it quotes git itself
    for forbidden in ("git -C", "git add", "git commit", "safe-commit", "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"):
        assert forbidden not in guidance, (forbidden, guidance)

    hook.unlink()
    tokens = shlex.split(printed[0])
    assert tokens[:3] == ["spec-kitty", "mission", "close"], printed
    rerun = runner.invoke(mission_type.app, tokens[2:], env={"PWD": str(repo)})
    assert rerun.exit_code == 0, rerun.output

    assert _porcelain_paths(repo) == []
    tracked = _git(repo, "ls-files", f"kitty-specs/{SLUG}/retrospective.yaml").stdout.split()
    assert tracked == [f"kitty-specs/{SLUG}/retrospective.yaml"]
    assert "capture mission retrospective" in _git(repo, "log", "--format=%s", "-3").stdout
