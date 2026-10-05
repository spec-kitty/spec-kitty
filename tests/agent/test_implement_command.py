"""Unit tests for lane-only implement command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from specify_cli.cli.commands.implement import implement
from tests.specify_cli.cli.commands._implement_fixtures import MISSION_ID, SLUG, activate_repo, build_mission, init_repo

pytestmark = pytest.mark.fast


@pytest.fixture(autouse=True)
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass the charter preflight gate for these implement-flow tests.

    None of these fixtures stage a charter; without the bypass the gate
    returns ``Error: charter_source missing`` before reaching the
    lane-workspace creation / JSON-output paths the tests exercise.
    Patch the hook boundary directly instead of relying on a production
    environment bypass.
    """
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    result = CharterPreflightResult(passed=True, checks=[])
    # Fixtures run implement on a protected ``main`` branch; the documented
    # operator escape hatch is the ONE sanctioned waiver (SPEC_KITTY_TEST_MODE
    # no longer waives the pre-check — PR #1850 guard-bypass fix).
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_args, **_kwargs: result,
    )


class TestImplementCommand:
    """The --json error guard for a missing lanes.json (the end-to-end behaviours moved to
    test_implement_phases.py and test_implement_characterization.py, WP10)."""

    @pytest.mark.git_repo
    def test_implement_json_error_output_is_clean(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        repo = init_repo(tmp_path / "repo")
        activate_repo(repo, monkeypatch, tmp_path)
        build_mission(repo, SLUG, MISSION_ID, write_lanes=False)

        with pytest.raises(typer.Exit):
            implement("WP01", mission=SLUG, json_output=True, recover=False)

        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["status"] == "error"
        assert payload["wp_id"] == "WP01"
        assert payload["error"] != "implement command failed"
        assert "lanes.json is required" in payload["error"]


# ---------------------------------------------------------------------------
# T013 — NFR-003 spy: ProtectionPolicy.resolve reads I/O once at the boundary;
# is_protected() and commit_guard.evaluate() make ZERO further I/O reads.
# ---------------------------------------------------------------------------


class TestNFR003ProtectionPolicySingleBoundaryRead:
    """NFR-003: the protection decision I/O boundary is ProtectionPolicy.resolve (T013).

    Verifies that:
    - ``_load_kittify_config`` is called exactly ONCE (the config read) inside ``resolve``
    - ``_remote_default_branch`` is called at most ONCE inside ``resolve`` (only on absent key path)
    - Neither ``is_protected`` nor ``commit_guard.evaluate`` trigger additional I/O reads
    """

    def test_protection_decision_io_confined_to_resolve_boundary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Drive _protected_branch_status_commit_error and assert single-boundary I/O (T013)."""
        from specify_cli.cli.commands.implement_claim import _protected_branch_status_commit_error
        from specify_cli.git import protection_policy as _pp_module

        # The autouse fixture sets SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1.
        # For this test we need the hatch OFF so we can observe the real protection decision.
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        # Spy: track calls to the two internal I/O helpers inside ProtectionPolicy.resolve
        kittify_read_count: list[int] = [0]
        remote_read_count: list[int] = [0]

        _real_load_kittify_config = _pp_module._load_kittify_config
        _real_remote_default_branch = _pp_module._remote_default_branch

        def _spy_load_kittify_config(repo_root: Path) -> dict:  # type: ignore[type-arg]
            kittify_read_count[0] += 1
            return _real_load_kittify_config(repo_root)

        def _spy_remote_default_branch(repo_root: Path) -> str | None:
            remote_read_count[0] += 1
            return _real_remote_default_branch(repo_root)

        with (
            patch.object(_pp_module, "_load_kittify_config", _spy_load_kittify_config),
            patch.object(_pp_module, "_remote_default_branch", _spy_remote_default_branch),
        ):
            # Call the decision function — "main" should be protected (no .kittify/config.yaml
            # override, so the default set includes "main"; hatch is OFF).
            result = _protected_branch_status_commit_error("main", tmp_path)

        # Config read happens exactly ONCE at the resolve boundary — not per is_protected call
        assert kittify_read_count[0] == 1, (
            f"_load_kittify_config called {kittify_read_count[0]} times; "
            "expected exactly 1 (boundary-resolved value, NFR-003)"
        )
        # Remote read happens at most ONCE (only on the absent-key path)
        assert remote_read_count[0] <= 1, (
            f"_remote_default_branch called {remote_read_count[0]} times; "
            "expected at most 1 (boundary-resolved value, NFR-003)"
        )
        # The decision itself: "main" is in the default protected set, no hatch active
        assert result is not None, "Expected a refusal message for protected branch 'main'"

    def test_is_protected_makes_no_io_after_resolve(
        self, tmp_path: Path
    ) -> None:
        """is_protected() is pure after resolve — zero filesystem/env reads (T013)."""
        from specify_cli.git.protection_policy import ProtectionPolicy
        from specify_cli.git import protection_policy as _pp_module

        io_call_count: list[int] = [0]

        def _counting_load(repo_root: Path) -> dict:  # type: ignore[type-arg]
            io_call_count[0] += 1
            return {}

        with patch.object(_pp_module, "_load_kittify_config", _counting_load):
            policy = ProtectionPolicy.resolve(tmp_path)
            count_after_resolve = io_call_count[0]
            # Call is_protected multiple times — must NOT trigger further I/O
            policy.is_protected("main")
            policy.is_protected("master")
            policy.is_protected("some-branch")

        assert io_call_count[0] == count_after_resolve, (
            f"is_protected triggered {io_call_count[0] - count_after_resolve} additional I/O read(s); "
            "expected zero (NFR-003: value object is I/O-free after resolve)"
        )
