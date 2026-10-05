"""NFR-003 (T013): the protection decision reads its I/O once, at the ``ProtectionPolicy.resolve`` boundary.

Moved from ``tests/agent/test_implement_command.py``: these cases pin a ``git.protection_policy``
contract, not the implement command. The two I/O helpers are wrapped by counting spies that call
through to the real helpers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# The policy probes the repository's remote default branch with git.
pytestmark = pytest.mark.git_repo


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

    def test_protection_decision_io_confined_to_resolve_boundary(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Drive _protected_branch_status_commit_error and assert single-boundary I/O (T013)."""
        from specify_cli.cli.commands.implement_claim import _protected_branch_status_commit_error
        from specify_cli.git import protection_policy as _pp_module

        # The hatch must be OFF to observe the real protection decision.
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        # Spy: track calls to the two internal I/O helpers inside ProtectionPolicy.resolve
        kittify_read_count: list[int] = [0]
        remote_read_count: list[int] = [0]

        _real_load_kittify_config = _pp_module._load_kittify_config
        _real_remote_default_branch = _pp_module._remote_default_branch

        def _spy_load_kittify_config(repo_root: Path) -> dict[str, Any]:
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
        assert kittify_read_count[0] == 1, f"_load_kittify_config called {kittify_read_count[0]} times; expected exactly 1 (boundary-resolved value, NFR-003)"
        # Remote read happens at most ONCE (only on the absent-key path)
        assert remote_read_count[0] <= 1, f"_remote_default_branch called {remote_read_count[0]} times; expected at most 1 (boundary-resolved value, NFR-003)"
        # The decision itself: "main" is in the default protected set, no hatch active
        assert result is not None, "Expected a refusal message for protected branch 'main'"

    def test_is_protected_makes_no_io_after_resolve(self, tmp_path: Path) -> None:
        """is_protected() is pure after resolve — zero filesystem/env reads (T013)."""
        from specify_cli.git.protection_policy import ProtectionPolicy
        from specify_cli.git import protection_policy as _pp_module

        io_call_count: list[int] = [0]

        def _counting_load(repo_root: Path) -> dict[str, Any]:
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
