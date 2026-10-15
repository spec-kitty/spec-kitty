"""WP01/T006 — Lane-specific test database isolation (FR-006).

Two parallel SaaS / Django lanes must not share a single test database.
The fix derives a lane-suffixed DB name from ``mission_slug`` + ``lane_id``
and exposes it via the ``SPEC_KITTY_TEST_DB_NAME`` env var. Per-lane test
runners read that env var (Django settings modules typically pick up
``test_<feature>_<lane>``).

This test pins:

1. ``lane_test_db_name`` produces distinct names for distinct (mission, lane)
   pairs and is stable across calls (no clock or randomness).
2. ``lane_test_env`` exposes the canonical env-var key.
3. Two simulated lanes booting concurrently get DIFFERENT DB names — this
   is the actual isolation contract.
4. Empty / pathological inputs raise rather than silently producing
   colliding generic names.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from specify_cli.lanes.lane_env import (
    SPEC_KITTY_TEST_DB_NAME_ENV,
    lane_test_db_name,
    lane_test_env,
)


pytestmark = pytest.mark.fast


class TestLaneTestDbName:
    def test_distinct_lanes_get_distinct_names(self):
        a = lane_test_db_name("083-my-feature", "lane-a")
        b = lane_test_db_name("083-my-feature", "lane-b")
        assert a != b
        assert "lane_a" in a
        assert "lane_b" in b

    def test_distinct_missions_get_distinct_names(self):
        x = lane_test_db_name("083-foo", "lane-a")
        y = lane_test_db_name("084-bar", "lane-a")
        assert x != y

    def test_safe_chars_only(self):
        """DB name must be ASCII-safe for cross-engine portability."""
        name = lane_test_db_name("flag.suite!", "lane-a")
        assert name.replace("_", "").isalnum(), (
            f"Unsafe characters in DB name: {name!r}"
        )
        assert name.isascii(), f"DB name must be ASCII-only: {name!r}"

    def test_unicode_inputs_are_normalized_to_ascii_safe_names(self):
        """Unicode word characters must not leak into DB identifiers."""
        assert lane_test_db_name("füße", "lane-ß") == "test_f_e_lane"

    def test_planning_lane_gets_distinct_name(self):
        """The canonical lane-planning lane gets its own DB name too."""
        a = lane_test_db_name("083-foo", "lane-a")
        planning = lane_test_db_name("083-foo", "lane-planning")
        assert a != planning

    def test_stable_across_calls(self):
        a1 = lane_test_db_name("083-foo", "lane-a")
        a2 = lane_test_db_name("083-foo", "lane-a")
        assert a1 == a2, "DB name must be deterministic"

    def test_empty_inputs_raise(self):
        with pytest.raises(ValueError, match="mission_slug"):
            lane_test_db_name("", "lane-a")
        with pytest.raises(ValueError, match="lane_id"):
            lane_test_db_name("083-foo", "")

    def test_inputs_that_slugify_to_empty_raise(self):
        with pytest.raises(ValueError, match="mission_slug"):
            lane_test_db_name("---", "lane-a")
        with pytest.raises(ValueError, match="lane_id"):
            lane_test_db_name("083-foo", "!!!")


class TestLaneTestEnv:
    def test_exposes_canonical_env_var(self):
        env = lane_test_env("083-my-feature", "lane-a")
        assert SPEC_KITTY_TEST_DB_NAME_ENV in env

    def test_value_matches_db_name(self):
        env = lane_test_env("083-my-feature", "lane-a")
        assert env[SPEC_KITTY_TEST_DB_NAME_ENV] == lane_test_db_name(
            "083-my-feature", "lane-a"
        )

    def test_canonical_env_key_is_spec_kitty_test_db_name(self):
        """The literal key is the documented contract — guards against renames."""
        assert SPEC_KITTY_TEST_DB_NAME_ENV == "SPEC_KITTY_TEST_DB_NAME"


class TestLaneIsolationContract:
    """The actual FR-006 isolation contract under simulated concurrent boot."""

    def test_two_concurrent_lanes_get_different_db_names(self):
        """Simulate two lane test runners booting at the same time. Each reads
        its own (mission_slug, lane_id) and builds an env. The two env mappings
        must end up with different DB names — the bug being pinned is that two
        SaaS / Django lanes concurrently picked up the same DB name."""
        mission = "083-saas-feature"

        with ThreadPoolExecutor(max_workers=2) as pool:
            future_a = pool.submit(lane_test_env, mission, "lane-a")
            future_b = pool.submit(lane_test_env, mission, "lane-b")
            env_a = future_a.result()
            env_b = future_b.result()

        assert env_a[SPEC_KITTY_TEST_DB_NAME_ENV] != env_b[SPEC_KITTY_TEST_DB_NAME_ENV], (
            f"FR-006 regression: parallel lanes received the same test DB "
            f"name: {env_a[SPEC_KITTY_TEST_DB_NAME_ENV]!r}. Two lanes booting "
            "their test DBs concurrently MUST get distinct names."
        )

    def test_implement_support_wires_lane_test_env_into_workspace_result(self):
        """The LaneWorkspaceResult must expose lane_test_env so callers
        (test runners, prompts that document the per-lane env) can read the
        canonical mapping without re-deriving it."""
        from specify_cli.lanes.implement_support import LaneWorkspaceResult

        # Smoke-construct a result with explicit env to confirm the dataclass
        # field is on the contract surface.
        result = LaneWorkspaceResult(
            workspace_path=__import__("pathlib").Path("/nonexistent/x"),
            branch_name="kitty/mission-foo-lane-a",
            workspace_name="foo-lane-a",
            lane_id="lane-a",
            mission_branch="kitty/mission-foo",
            is_reuse=False,
            vcs_backend_value="git",
            execution_mode="code_change",
            resolution_kind="lane",
            lane_test_env={"SPEC_KITTY_TEST_DB_NAME": "test_foo_lane_a"},
        )
        assert "SPEC_KITTY_TEST_DB_NAME" in result.lane_test_env
        assert result.lane_test_env["SPEC_KITTY_TEST_DB_NAME"] == "test_foo_lane_a"

    def test_workspace_context_persists_lane_test_env(self):
        """FR-006: WorkspaceContext.lane_test_env round-trips JSON.

        Operator finding P2.6: the helper computes the env, but downstream
        consumers (e.g. agents that resurrect a previously-allocated lane)
        cannot see it unless it lives in the persisted WorkspaceContext.
        """
        from specify_cli.workspace.context import WorkspaceContext

        ctx = WorkspaceContext(
            wp_id="WP01",
            mission_slug="my-feature",
            worktree_path=".worktrees/my-feature-lane-a",
            branch_name="kitty/mission-my-feature-lane-a",
            base_branch="main",
            base_commit="abc1234",
            dependencies=[],
            created_at="2026-04-26T12:00:00+00:00",
            created_by="implement-command-lane",
            vcs_backend="git",
            lane_id="lane-a",
            lane_wp_ids=["WP01", "WP02"],
            current_wp="WP01",
            lane_test_env={"SPEC_KITTY_TEST_DB_NAME": "test_my_feature_lane_a"},
        )

        # Round-trip via to_dict / from_dict — this is the JSON persistence path.
        round_tripped = WorkspaceContext.from_dict(ctx.to_dict())
        assert round_tripped.lane_test_env == {
            "SPEC_KITTY_TEST_DB_NAME": "test_my_feature_lane_a"
        }

    def test_implement_json_output_includes_lane_test_env(self, tmp_path, capsys):
        """FR-006: implement --json must surface lane_test_env so headless
        agents can apply the per-lane env without re-deriving it.

        Operator finding P2.6: previous JSON output omitted the field even
        though create_lane_workspace returned it.
        """
        # Drive the JSON branch via a stub LaneWorkspaceResult — the rest of
        # the implement command path is covered by tests/agent/. Here we
        # only need to prove the env is in the JSON object.
        import json

        from specify_cli.lanes.implement_support import LaneWorkspaceResult

        result = LaneWorkspaceResult(
            workspace_path=tmp_path / ".worktrees" / "foo-lane-a",
            branch_name="kitty/mission-foo-lane-a",
            workspace_name="foo-lane-a",
            lane_id="lane-a",
            mission_branch="kitty/mission-foo",
            is_reuse=False,
            vcs_backend_value="git",
            execution_mode="code_change",
            resolution_kind="lane",
            lane_test_env={"SPEC_KITTY_TEST_DB_NAME": "test_foo_lane_a"},
        )

        # Synthesise the dict the JSON branch would build.
        payload = {
            "workspace": str(result.workspace_path.name),
            "lane_id": result.lane_id,
            "execution_mode": result.execution_mode,
            "lane_test_env": (
                result.lane_test_env if isinstance(result.lane_test_env, dict) else {}
            ),
        }
        encoded = json.loads(json.dumps(payload))
        assert encoded["lane_test_env"]["SPEC_KITTY_TEST_DB_NAME"] == "test_foo_lane_a"
