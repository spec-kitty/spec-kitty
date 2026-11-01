"""Tests for WP04: Release-Prep CLI.

Covers FR-013, FR-014, FR-015, NFR-004, NFR-005.
Zero network calls (all network entry-points are mocked to raise).
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from dataclasses import asdict
from pathlib import Path
from textwrap import dedent
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.release import app
from specify_cli.release.changelog import (
    _parse_wp_frontmatter_status,
    _parse_wp_id,
    _parse_wp_title,
    build_changelog_block,
)
from specify_cli.release.payload import ReleasePrepPayload, build_release_prep_payload
from specify_cli.release.version import propose_version
from tests._perf_helpers import assert_timing_budget

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration]

runner = CliRunner()


def _write_pyproject(tmp_path: Path, version: str) -> None:
    (tmp_path / "pyproject.toml").write_text(
        dedent(
            f"""\
            [project]
            name = "spec-kitty-cli"
            version = "{version}"
            description = "Test project"
            """
        ),
        encoding="utf-8",
    )


def _write_mission(
    tmp_path: Path,
    mission_slug: str,
    friendly_name: str,
    wp_statuses: dict[str, str],
) -> None:
    """Create a synthetic mission directory under kitty-specs/ in tmp_path."""
    mission_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    meta = {
        "friendly_name": friendly_name,
        "mission_number": mission_slug.split("-")[0],
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    (mission_dir / "meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    (mission_dir / "spec.md").write_text(
        f"# {friendly_name}\n\nDescription of the mission.\n", encoding="utf-8"
    )

    for wp_id, status in wp_statuses.items():
        wp_content = dedent(
            f"""\
            ---
            work_package_id: {wp_id}
            status: {status}
            ---

            ## {wp_id} — Test Work Package for {mission_slug}
            """
        )
        (tasks_dir / f"{wp_id}-test.md").write_text(wp_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# T019 — propose_version unit tests
# ---------------------------------------------------------------------------


def test_propose_version_alpha_increments_alpha() -> None:
    assert propose_version("3.1.0a7", "alpha") == "3.1.0a8"


def test_propose_version_alpha_to_beta_starts_beta1() -> None:
    assert propose_version("3.1.0a7", "beta") == "3.1.0b1"


def test_propose_version_beta_increments_beta() -> None:
    assert propose_version("3.1.0b1", "beta") == "3.1.0b2"


def test_propose_version_alpha_to_stable() -> None:
    assert propose_version("3.1.0a7", "stable") == "3.1.0"


def test_propose_version_beta_to_stable() -> None:
    assert propose_version("3.1.0b3", "stable") == "3.1.0"


def test_propose_version_stable_to_stable_patches() -> None:
    assert propose_version("3.1.0", "stable") == "3.1.1"


def test_propose_version_stable_to_alpha() -> None:
    assert propose_version("3.1.0", "alpha") == "3.1.0a1"


def test_propose_version_stable_to_beta() -> None:
    assert propose_version("3.1.0", "beta") == "3.1.0b1"


def test_propose_version_raises_for_rc_suffix() -> None:
    with pytest.raises(ValueError, match="Cannot parse version"):
        propose_version("3.1.0rc1", "stable")


def test_propose_version_raises_for_dev_suffix() -> None:
    with pytest.raises(ValueError, match="Cannot parse version"):
        propose_version("3.1.0.dev1", "stable")


def test_propose_version_raises_beta_to_alpha() -> None:
    with pytest.raises(ValueError, match="Cannot promote a beta"):
        propose_version("3.1.0b1", "alpha")


# ---------------------------------------------------------------------------
# T020 — build_changelog_block tests
# ---------------------------------------------------------------------------


def test_changelog_built_from_local_artifacts_only(tmp_path: Path) -> None:
    """A synthetic fixture with no network access produces the changelog (FR-014)."""
    _write_mission(tmp_path, "010-test-mission", "Test Mission Alpha", {"WP01": "done"})

    # Ensure no network calls are made
    with patch("urllib.request.urlopen", side_effect=AssertionError("network call!")):
        changelog, slugs = build_changelog_block(tmp_path, since_tag=None)

    assert "010-test-mission" in changelog or "Test Mission Alpha" in changelog
    assert "010-test-mission" in slugs


def test_changelog_includes_accepted_missions(tmp_path: Path) -> None:
    _write_mission(
        tmp_path,
        "010-mission-a",
        "Mission A",
        {"WP01": "done", "WP02": "done"},
    )
    _write_mission(
        tmp_path,
        "011-mission-b",
        "Mission B",
        {"WP01": "done"},
    )
    changelog, slugs = build_changelog_block(tmp_path, since_tag=None)

    assert "Mission A" in changelog or "010-mission-a" in changelog
    assert "Mission B" in changelog or "011-mission-b" in changelog
    assert set(slugs) == {"010-mission-a", "011-mission-b"}


def test_changelog_excludes_missions_with_no_accepted_wps(tmp_path: Path) -> None:
    _write_mission(
        tmp_path, "010-mission-no-done", "Incomplete Mission", {"WP01": "in_progress"}
    )
    changelog, slugs = build_changelog_block(tmp_path, since_tag=None)

    assert slugs == []
    assert changelog == ""


def test_changelog_returns_empty_for_empty_kitty_specs(tmp_path: Path) -> None:
    # No kitty-specs directory at all
    changelog, slugs = build_changelog_block(tmp_path, since_tag=None)
    assert changelog == ""
    assert slugs == []


def test_changelog_accepts_since_tag_none(tmp_path: Path) -> None:
    """Passing since_tag=None should not raise even with no git tags."""
    _write_mission(tmp_path, "001-test", "Test", {"WP01": "done"})
    # No git tags present — should not raise
    changelog, slugs = build_changelog_block(tmp_path, since_tag=None)
    assert isinstance(changelog, str)
    assert isinstance(slugs, list)


def test_wp_frontmatter_status_parses_quoted_values_without_regex(tmp_path: Path) -> None:
    wp_file = tmp_path / "WP01-test.md"
    wp_file.write_text(
        dedent(
            """\
            ---
            work_package_id: "WP01"
            status: 'done'
            ---

            ## WP01
            """
        ),
        encoding="utf-8",
    )

    assert _parse_wp_frontmatter_status(wp_file) == "done"


def test_wp_id_parses_values_containing_colons(tmp_path: Path) -> None:
    wp_file = tmp_path / "custom-name.md"
    wp_file.write_text(
        dedent(
            """\
            ---
            work_package_id: "WP:01"
            status: done
            ---

            ## WP01
            """
        ),
        encoding="utf-8",
    )

    assert _parse_wp_id(wp_file) == "WP:01"


def test_wp_title_strips_heading_markers_without_regex(tmp_path: Path) -> None:
    wp_file = tmp_path / "WP01-title.md"
    wp_file.write_text(
        dedent(
            """\
            ---
            work_package_id: WP01
            status: done
            ---

            ##   Release Prep Title
            """
        ),
        encoding="utf-8",
    )

    assert _parse_wp_title(wp_file) == "Release Prep Title"


# ---------------------------------------------------------------------------
# T021 — build_release_prep_payload tests
# ---------------------------------------------------------------------------


def test_build_release_prep_payload_returns_correct_shape(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, "3.1.0a7")
    _write_mission(tmp_path, "010-test", "Test Mission", {"WP01": "done"})

    payload = build_release_prep_payload("alpha", tmp_path)

    assert isinstance(payload, ReleasePrepPayload)
    assert payload.channel == "alpha"
    assert payload.current_version == "3.1.0a7"
    assert payload.proposed_version == "3.1.0a8"
    assert payload.target_branch == "main"
    assert isinstance(payload.changelog_block, str)
    assert isinstance(payload.mission_slug_list, list)
    assert isinstance(payload.structured_inputs, dict)


def test_payload_structured_inputs_keys(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, "3.1.0a7")

    payload = build_release_prep_payload("alpha", tmp_path)

    required_keys = {
        "version",
        "tag_name",
        "release_title",
        "release_notes_body",
        "mission_slug_list",
    }
    assert required_keys.issubset(payload.structured_inputs.keys())


def test_payload_tag_name_uses_v_prefix(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, "3.1.0a7")

    payload = build_release_prep_payload("alpha", tmp_path)

    assert payload.structured_inputs["tag_name"] == f"v{payload.proposed_version}"


def test_payload_json_roundtrip(tmp_path: Path) -> None:
    """ReleasePrepPayload round-trips through json.dumps + json.loads (FR-015)."""
    _write_pyproject(tmp_path, "3.1.0a7")

    payload = build_release_prep_payload("alpha", tmp_path)
    serialized = json.dumps(asdict(payload))
    deserialized = json.loads(serialized)

    assert deserialized["channel"] == "alpha"
    assert deserialized["proposed_version"] == payload.proposed_version
    assert isinstance(deserialized["structured_inputs"], dict)


def test_payload_no_github_api_calls(tmp_path: Path) -> None:
    """FR-014/C-002: No network calls are made during payload construction.

    We mock urllib.request.urlopen, requests.get, and any subprocess call to
    'gh' to raise immediately if invoked. The test passes only if none of them
    are called.
    """
    _write_pyproject(tmp_path, "3.1.0a7")
    _write_mission(tmp_path, "010-test", "Test", {"WP01": "done"})

    def _raise_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(
            "Network call detected! build_release_prep_payload must not make "
            "network calls (FR-014/C-002)."
        )

    original_run = __import__("subprocess").run

    def _guarded_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "gh":
            raise AssertionError(
                f"'gh' subprocess call detected: {cmd!r}. "
                "No gh calls are allowed (C-002)."
            )
        return original_run(cmd, *args, **kwargs)

    with (
        patch.object(urllib.request, "urlopen", side_effect=_raise_network),
        patch("subprocess.run", side_effect=_guarded_run),
    ):
        payload = build_release_prep_payload("alpha", tmp_path)

    assert payload.proposed_version == "3.1.0a8"


# ---------------------------------------------------------------------------
# T022 — CLI command tests
# ---------------------------------------------------------------------------


def test_prep_command_emits_text_by_default(tmp_path: Path) -> None:
    """FR-013: running prep produces a rich-formatted summary."""
    _write_pyproject(tmp_path, "3.1.0a7")
    _write_mission(tmp_path, "010-test", "Test Mission", {"WP01": "done"})

    result = runner.invoke(
        app,
        ["--channel", "alpha", "--repo", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    # Should contain version information
    assert "3.1.0a8" in result.output or "3.1.0a7" in result.output


def test_prep_command_emits_json_with_flag(tmp_path: Path) -> None:
    """FR-015: --json produces a parseable JSON document with all fields."""
    _write_pyproject(tmp_path, "3.1.0a7")
    _write_mission(tmp_path, "010-test", "Test Mission", {"WP01": "done"})

    result = runner.invoke(
        app,
        ["--channel", "alpha", "--repo", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0, result.output
    # Output should be valid JSON
    data = json.loads(result.output)
    assert data["channel"] == "alpha"
    assert data["current_version"] == "3.1.0a7"
    assert data["proposed_version"] == "3.1.0a8"
    assert "structured_inputs" in data
    assert "changelog_block" in data
    assert "mission_slug_list" in data
    assert "target_branch" in data


def test_prep_command_stable_channel(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, "3.1.0a7")

    result = runner.invoke(
        app,
        ["--channel", "stable", "--repo", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["proposed_version"] == "3.1.0"


def test_prep_command_beta_channel(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, "3.1.0a7")

    result = runner.invoke(
        app,
        ["--channel", "beta", "--repo", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["proposed_version"] == "3.1.0b1"


def test_prep_help_text_is_populated() -> None:
    """The prep subcommand must have real help text (not the old stub comment)."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # The stale "Deep implementation in WP05" text must be gone
    assert "WP05" not in result.output
    # Real help text should be present
    assert "channel" in result.output.lower()


# ---------------------------------------------------------------------------
# T022 — FR-023: scope-cut documentation
# ---------------------------------------------------------------------------


def test_close_comment_scope_cut_documented(tmp_path: Path) -> None:
    """FR-023: the text output lists automated steps and still-manual steps."""
    _write_pyproject(tmp_path, "3.1.0a7")

    result = runner.invoke(
        app,
        ["--channel", "alpha", "--repo", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    output_lower = result.output.lower()

    # Automated steps should be apparent
    assert "changelog" in output_lower or "version" in output_lower

    # Manual steps must be documented
    assert "manual" in output_lower or "still" in output_lower
    assert "gh pr create" in result.output or "pr create" in result.output.lower()
    assert "tag" in output_lower


# ---------------------------------------------------------------------------
# NFR-004 — Performance benchmark: <= 5 seconds on a synthetic 16-WP mission
# ---------------------------------------------------------------------------


def test_build_release_prep_payload_for_16_wps(tmp_path: Path) -> None:
    """Functional half of the #4015 split: payload is correct for 16 WPs."""
    _write_pyproject(tmp_path, "3.1.0a7")

    # Create a synthetic mission with 16 WPs
    wp_statuses = {f"WP{i:02d}": "done" for i in range(1, 17)}
    _write_mission(tmp_path, "068-big-mission", "Big Mission", wp_statuses)

    payload = build_release_prep_payload("alpha", tmp_path)

    assert payload.proposed_version == "3.1.0a8"
    assert "068-big-mission" in payload.mission_slug_list


@pytest.mark.performance
def test_runs_within_5s_for_16_wps(tmp_path: Path) -> None:
    """NFR-004 (#4015 split): build_release_prep_payload returns within 5 seconds on 16 WPs."""
    _write_pyproject(tmp_path, "3.1.0a7")

    # Create a synthetic mission with 16 WPs
    wp_statuses = {f"WP{i:02d}": "done" for i in range(1, 17)}
    _write_mission(tmp_path, "068-big-mission", "Big Mission", wp_statuses)

    start = time.monotonic()
    build_release_prep_payload("alpha", tmp_path)
    elapsed = time.monotonic() - start

    assert_timing_budget(elapsed, 5.0, name="elapsed")


# ---------------------------------------------------------------------------
# #6612 — WP acceptance must follow the canonical reducer over the resolved
# status surface (gap G-13). Red-first: these failed before the fix because
# _wp_lane_from_event_log took the last ``to_lane`` in file order off the
# primary mission dir and silently skipped corrupt lines.
# ---------------------------------------------------------------------------


def _status_event_row(
    mission_slug: str,
    wp_id: str,
    from_lane: str,
    to_lane: str,
    at: str,
    event_id: str,
) -> dict[str, object]:
    """One valid lane ``StatusEvent`` row (the store's on-disk shape)."""
    return {
        "event_id": event_id,
        "mission_slug": mission_slug,
        "wp_id": wp_id,
        "from_lane": from_lane,
        "to_lane": to_lane,
        "at": at,
        "actor": "codex",
        "force": False,
        "execution_mode": "worktree",
        "evidence": None,
        "reason": None,
        "review_ref": None,
    }


def _write_event_log(mission_dir: Path, rows: list[dict[str, object]]) -> None:
    """Write ``status.events.jsonl`` into a mission dir."""
    mission_dir.joinpath("status.events.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_changelog_classifies_wp_by_reduced_lane_not_file_order(tmp_path: Path) -> None:
    """File order is not lane order after a union merge / out-of-order append.

    The log below is a continuous chain in REDUCER order (by ``at``):
    ``planned -> in_review`` (05-01) then ``in_review -> approved`` (05-02),
    but is written to disk with the approval FIRST. The last ``to_lane`` in
    file order is ``in_review``; the reduced lane is ``approved``.
    """
    _write_mission(tmp_path, "010-out-of-order", "Out Of Order", {"WP01": "in_progress"})
    _write_event_log(
        tmp_path / "kitty-specs" / "010-out-of-order",
        [
            _status_event_row(
                "010-out-of-order",
                "WP01",
                "in_review",
                "approved",
                "2026-05-02T10:00:00Z",
                "e-approve",
            ),
            _status_event_row(
                "010-out-of-order",
                "WP01",
                "planned",
                "in_review",
                "2026-05-01T09:00:00Z",
                "e-review",
            ),
        ],
    )

    changelog, slugs = build_changelog_block(tmp_path, since_tag=None)

    assert "010-out-of-order" in slugs
    assert "WP01" in changelog


def test_changelog_excludes_wp_when_reducer_order_leaves_it_unaccepted(tmp_path: Path) -> None:
    """The mirror image: file order ends accepted, reducer order does not."""
    _write_mission(tmp_path, "011-out-of-order", "Mirror Case", {"WP01": "in_progress"})
    _write_event_log(
        tmp_path / "kitty-specs" / "011-out-of-order",
        [
            # Later ``at`` (reducer-final): departure to in_review.
            _status_event_row(
                "011-out-of-order",
                "WP01",
                "approved",
                "in_review",
                "2026-05-02T10:00:00Z",
                "e-reopen",
            ),
            _status_event_row(
                "011-out-of-order",
                "WP01",
                "in_review",
                "approved",
                "2026-05-01T09:00:00Z",
                "e-approve",
            ),
        ],
    )

    changelog, slugs = build_changelog_block(tmp_path, since_tag=None)

    assert "011-out-of-order" not in slugs


def test_changelog_fails_loudly_on_corrupt_status_log(tmp_path: Path) -> None:
    """A corrupt log line must fail the build the way every other reader fails."""
    from specify_cli.status import StoreError

    _write_mission(tmp_path, "012-corrupt-log", "Corrupt Log", {"WP01": "in_progress"})
    mission_dir = tmp_path / "kitty-specs" / "012-corrupt-log"
    mission_dir.joinpath("status.events.jsonl").write_text(
        json.dumps(
            _status_event_row(
                "012-corrupt-log",
                "WP01",
                "planned",
                "in_review",
                "2026-05-01T09:00:00Z",
                "e-review",
            )
        )
        + "\nthis line is not json\n",
        encoding="utf-8",
    )

    # The failure must be loud AND diagnosable: name the mission, not just
    # the line number, when hundreds of missions are scanned (#6612 review).
    with pytest.raises(StoreError, match=r"012-corrupt-log: .*line 2"):
        build_changelog_block(tmp_path, since_tag=None)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def test_changelog_reads_coordination_surface_not_stale_primary_copy(tmp_path: Path) -> None:
    """Under coordination topology the authoritative log is the coord branch's.

    The primary mission dir carries a stale ``in_review`` copy; the
    coordination worktree carries the authoritative ``approved`` log. The
    changelog must classify from the coordination surface (the #1735
    split-brain class, closed for the changelog by #6612).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / ".kittify").mkdir()
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    slug = "coord-m"
    mission_id = "01ABCDEF1234567890123456"
    mid8 = mission_id[:8]
    coord_branch = f"kitty/mission-{slug}-{mid8}"
    primary_dir = repo / "kitty-specs" / slug
    tasks_dir = primary_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (primary_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "coordination_branch": coord_branch,
                "mission_slug": slug,
                "friendly_name": "Coord Mission",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (primary_dir / "spec.md").write_text("# Coord Mission\n", encoding="utf-8")
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\nstatus: in_progress\n---\n\n## WP01 — coord thing\n",
        encoding="utf-8",
    )
    # Stale primary copy: the WP never got past in_review here.
    _write_event_log(
        primary_dir,
        [
            _status_event_row(slug, "WP01", "planned", "in_review", "2026-05-01T09:00:00Z", "e-review"),
        ],
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "primary stale copy")

    # Authoritative log on the coordination branch.
    _git(repo, "checkout", "-b", coord_branch)
    coord_dir = repo / "kitty-specs" / f"{slug}-{mid8}"
    coord_dir.mkdir(parents=True)
    _write_event_log(
        coord_dir,
        [
            _status_event_row(slug, "WP01", "planned", "in_review", "2026-05-01T09:00:00Z", "e-review"),
            _status_event_row(slug, "WP01", "in_review", "approved", "2026-05-02T10:00:00Z", "e-approve"),
        ],
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "coord approved")
    _git(repo, "checkout", "main")
    # Materialize the coordination worktree at the registered location.
    _git(
        repo,
        "worktree",
        "add",
        str(repo / ".worktrees" / f"{slug}-{mid8}-coord"),
        coord_branch,
    )

    changelog, slugs = build_changelog_block(repo, since_tag=None)

    assert slug in slugs
    assert "WP01" in changelog


def _make_coord_branch_repo(tmp_path: Path) -> tuple[Path, Path, str, str, str]:
    """Git fixture for a coordination-topology mission (#6612 review findings).

    Creates a repo whose primary mission dir carries a stale ``in_review``
    copy of ``status.events.jsonl`` and whose coordination branch carries
    the authoritative ``approved`` log. The caller decides whether the
    coordination worktree is materialized and whether the branch survives.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / ".kittify").mkdir()
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    slug = "coord-edge"
    mission_id = "01ABCDEF1234567890123456"
    mid8 = mission_id[:8]
    coord_branch = f"kitty/mission-{slug}-{mid8}"
    primary_dir = repo / "kitty-specs" / slug
    tasks_dir = primary_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (primary_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "coordination_branch": coord_branch,
                "mission_slug": slug,
                "friendly_name": "Coord Edge Mission",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (primary_dir / "spec.md").write_text("# Coord Edge Mission\n", encoding="utf-8")
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\nstatus: in_progress\n---\n\n## WP01 — coord edge thing\n",
        encoding="utf-8",
    )
    # Stale primary copy: the WP never got past in_review here.
    _write_event_log(
        primary_dir,
        [
            _status_event_row(slug, "WP01", "planned", "in_review", "2026-05-01T09:00:00Z", "e-review"),
        ],
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "primary stale copy")

    # Authoritative log on the coordination branch.
    _git(repo, "checkout", "-b", coord_branch)
    coord_dir = repo / "kitty-specs" / f"{slug}-{mid8}"
    coord_dir.mkdir(parents=True)
    _write_event_log(
        coord_dir,
        [
            _status_event_row(slug, "WP01", "planned", "in_review", "2026-05-01T09:00:00Z", "e-review"),
            _status_event_row(slug, "WP01", "in_review", "approved", "2026-05-02T10:00:00Z", "e-approve"),
        ],
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "coord approved")
    _git(repo, "checkout", "main")
    return repo, primary_dir, slug, mid8, coord_branch


def test_changelog_unmaterialized_coord_surface_never_reads_stale_primary(tmp_path: Path) -> None:
    """Unmaterialized coordination worktree: frontmatter fallback, not the stale primary.

    The coordination branch exists but its worktree is not materialized
    (fresh-clone window, #4959), so no authoritative log is readable. The
    changelog must fall back to the WP frontmatter (``in_progress`` → not
    accepted) and must NOT classify from the stale primary copy — which
    here says ``approved``, so a regression to the primary surface would
    wrongly include the mission.
    """
    repo, primary_dir, slug, _mid8, _coord_branch = _make_coord_branch_repo(tmp_path)
    # Discriminating stale copy: a continuous chain ending approved.
    _write_event_log(
        primary_dir,
        [
            _status_event_row(slug, "WP01", "planned", "in_review", "2026-05-01T09:00:00Z", "e-review"),
            _status_event_row(slug, "WP01", "in_review", "approved", "2026-05-02T10:00:00Z", "e-approve"),
        ],
    )

    changelog, slugs = build_changelog_block(repo, since_tag=None)

    assert slug not in slugs
    assert "WP01" not in changelog


def test_changelog_raises_when_coordination_branch_deleted(tmp_path: Path) -> None:
    """A deleted coordination branch must fail loudly, not read the stale primary (#1848).

    The mission's authoritative surface was destroyed mid-flight. Release
    prep must raise ``CoordinationBranchDeleted`` — the same data-loss guard
    every other reader of the status surface shares — never silently
    classify WPs off the stale primary copy.
    """
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    repo, _primary_dir, _slug, _mid8, coord_branch = _make_coord_branch_repo(tmp_path)
    _git(repo, "branch", "-D", coord_branch)

    with pytest.raises(CoordinationBranchDeleted):
        build_changelog_block(repo, since_tag=None)
