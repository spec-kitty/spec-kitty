"""Stable, origin-aware lane identity (WP04, C-4, FR-010; traces #4945 #4969).

Two independent regressions are pinned here with real fixtures:

* **#4945 (re-lettering)** — ``compute_lanes`` assigned ``lane_id`` positionally
  (``lane-a``, ``lane-b``, …) on every finalize. Removing a middle WP and
  re-finalizing shifted the surviving lanes' ids onto a different WP's branch.
  The fix binds a lane's id to its branch at creation and *reads it back* on
  subsequent finalize (PP-F5: read-back, never also-mint), so a surviving lane
  keeps its id across a WP-removal re-finalize.
* **#4969 (origin shadowing)** — lane base resolution cut a fresh branch from
  local ``main`` even when a teammate's approved lane existed as
  ``origin/<lane>``. The fix prefers the origin ref when present and falls back
  to the local base only when the origin ref is genuinely absent (offline / no
  remote / never pushed) — base resolution never fails closed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.compute import compute_lanes
from specify_cli.ownership.models import OwnershipManifest, WorkProductKind
from specify_cli.workspace.context import resolve_lane_base_ref

pytestmark = pytest.mark.fast


def _manifest(owned_files: list[str]) -> OwnershipManifest:
    return OwnershipManifest(
        execution_mode=WorkProductKind("code_change"),
        owned_files=tuple(owned_files),
        authoritative_surface=owned_files[0] if owned_files else "",
    )


# ---------------------------------------------------------------------------
# #4945 — stable lane id across a WP-removal re-finalize (read-back, not mint)
# ---------------------------------------------------------------------------


class TestStableLaneIdentity:
    def test_surviving_lane_keeps_id_after_middle_wp_removed(self) -> None:
        """Removing a middle WP must not re-letter the surviving lanes."""
        graph = {"WP01": [], "WP03": [], "WP05": []}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP03": _manifest(["src/b/**"]),
            "WP05": _manifest(["src/c/**"]),
        }
        first = compute_lanes(graph, manifests, "test-feat")
        lane_of = {lane.wp_ids[0]: lane.lane_id for lane in first.lanes}
        # Sanity: initial positional mint is a/b/c in WP order.
        assert lane_of == {"WP01": "lane-a", "WP03": "lane-b", "WP05": "lane-c"}

        # Remove the middle WP and re-finalize, reading back the prior manifest.
        graph.pop("WP03")
        manifests.pop("WP03")
        second = compute_lanes(graph, manifests, "test-feat", previous_lanes=first)
        lane_of_2 = {lane.wp_ids[0]: lane.lane_id for lane in second.lanes}

        # The surviving lanes keep their ORIGINAL ids — WP05 does NOT slide
        # from lane-c onto lane-b (the #4945 re-lettering harm).
        assert lane_of_2["WP01"] == "lane-a"
        assert lane_of_2["WP05"] == "lane-c"

    def test_surviving_lane_keeps_id_after_first_wp_removed(self) -> None:
        """Removing the FIRST WP is the sharpest re-lettering case."""
        graph = {"WP01": [], "WP03": [], "WP05": []}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP03": _manifest(["src/b/**"]),
            "WP05": _manifest(["src/c/**"]),
        }
        first = compute_lanes(graph, manifests, "test-feat")

        graph.pop("WP01")
        manifests.pop("WP01")
        second = compute_lanes(graph, manifests, "test-feat", previous_lanes=first)
        lane_of = {lane.wp_ids[0]: lane.lane_id for lane in second.lanes}

        # Without read-back WP03 would be re-lettered onto lane-a (WP01's branch).
        assert lane_of["WP03"] == "lane-b"
        assert lane_of["WP05"] == "lane-c"

    def test_read_back_never_overwrites_a_bound_id(self) -> None:
        """A bound id survives a finalize that would otherwise re-letter it.

        No two lanes may ever collide on one id after read-back.
        """
        graph = {"WP01": [], "WP03": [], "WP05": []}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP03": _manifest(["src/b/**"]),
            "WP05": _manifest(["src/c/**"]),
        }
        first = compute_lanes(graph, manifests, "test-feat")
        graph.pop("WP03")
        manifests.pop("WP03")
        second = compute_lanes(graph, manifests, "test-feat", previous_lanes=first)
        ids = [lane.lane_id for lane in second.lanes]
        assert len(ids) == len(set(ids)), f"lane ids collided after read-back: {ids}"

    def test_new_lane_gets_a_fresh_unused_id(self) -> None:
        """A genuinely new lane mints the next free id; existing lanes stay bound."""
        graph = {"WP01": [], "WP03": []}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP03": _manifest(["src/b/**"]),
        }
        first = compute_lanes(graph, manifests, "test-feat")

        graph["WP07"] = []
        manifests["WP07"] = _manifest(["src/z/**"])
        second = compute_lanes(graph, manifests, "test-feat", previous_lanes=first)
        lane_of = {lane.wp_ids[0]: lane.lane_id for lane in second.lanes}

        assert lane_of["WP01"] == "lane-a"
        assert lane_of["WP03"] == "lane-b"
        # The new lane takes the next free positional letter, never a bound id.
        assert lane_of["WP07"] == "lane-c"

    def test_default_no_previous_is_positional_and_unchanged(self) -> None:
        """Without a previous manifest, minting is positional a/b/c (regression guard)."""
        graph = {"WP01": [], "WP02": [], "WP03": []}
        manifests = {
            "WP01": _manifest(["src/a/**"]),
            "WP02": _manifest(["src/b/**"]),
            "WP03": _manifest(["src/c/**"]),
        }
        result = compute_lanes(graph, manifests, "test-feat")
        lane_of = {lane.wp_ids[0]: lane.lane_id for lane in result.lanes}
        assert lane_of == {"WP01": "lane-a", "WP02": "lane-b", "WP03": "lane-c"}


# ---------------------------------------------------------------------------
# #4969 — origin-aware base resolution (prefer origin/<lane>, offline fallback)
# ---------------------------------------------------------------------------


def _make_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main", str(path)], capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    (path / "README.md").write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(path), capture_output=True, check=True)


def _head_sha(path: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.mark.git_repo
class TestOriginAwareBaseResolution:
    def test_prefers_origin_ref_when_present(self, tmp_path: Path) -> None:
        """A pushed lane (origin/<lane>) is the base, not a fresh cut from main."""
        _make_git_repo(tmp_path)
        lane_branch = "kitty/mission-test-feat-lane-a"
        # Simulate a teammate's pushed, fetched lane: a remote-tracking ref.
        subprocess.run(
            ["git", "update-ref", f"refs/remotes/origin/{lane_branch}", _head_sha(tmp_path)],
            cwd=str(tmp_path),
            capture_output=True,
            check=True,
        )

        resolved = resolve_lane_base_ref(tmp_path, lane_branch, fallback_base="main")
        assert resolved == f"refs/remotes/origin/{lane_branch}"

    def test_falls_back_to_local_when_origin_absent(self, tmp_path: Path) -> None:
        """No origin ref (offline / never pushed) -> local fallback, never fail-closed."""
        _make_git_repo(tmp_path)
        lane_branch = "kitty/mission-test-feat-lane-a"

        resolved = resolve_lane_base_ref(tmp_path, lane_branch, fallback_base="main")
        assert resolved == "main"

    def test_falls_back_when_no_remote_configured(self, tmp_path: Path) -> None:
        """A repo with no remote at all still resolves to the fallback base."""
        _make_git_repo(tmp_path)
        resolved = resolve_lane_base_ref(tmp_path, "kitty/mission-other-lane-b", fallback_base="kitty/mission-other")
        assert resolved == "kitty/mission-other"
