"""Tests for MissionReviewMode and resolve_mode() (T018, FR-005, FR-006, FR-023)."""

from __future__ import annotations

import pytest

from specify_cli.cli.commands.review._diagnostics import MissionReviewDiagnostic
from specify_cli.cli.commands.review._mode import (
    MissionReviewMode,
    ModeMismatchError,
    resolve_mode,
)

pytestmark = [pytest.mark.fast, pytest.mark.non_sandbox]


class TestMissionReviewModeEnum:
    def test_lightweight_value(self) -> None:
        assert MissionReviewMode.LIGHTWEIGHT == "lightweight"

    def test_post_merge_value(self) -> None:
        assert MissionReviewMode.POST_MERGE == "post-merge"

    def test_is_str(self) -> None:
        assert isinstance(MissionReviewMode.LIGHTWEIGHT, str)


class TestResolveModeAutoDetect:
    def test_no_flag_no_bmc_is_lightweight(self) -> None:
        """Pre-merge mission, bare invocation → lightweight."""
        mode, auto = resolve_mode(cli_flag=None, baseline_merge_commit=None)
        assert mode is MissionReviewMode.LIGHTWEIGHT
        assert auto is True

    def test_no_flag_with_bmc_is_post_merge(self) -> None:
        """Post-merge mission, bare invocation → post-merge (auto-detected)."""
        mode, auto = resolve_mode(cli_flag=None, baseline_merge_commit="abc123def")
        assert mode is MissionReviewMode.POST_MERGE
        assert auto is True

    def test_flag_lightweight_overrides_bmc(self) -> None:
        """--mode lightweight on already-merged mission → lightweight, explicit."""
        mode, auto = resolve_mode(
            cli_flag="lightweight", baseline_merge_commit="abc123def"
        )
        assert mode is MissionReviewMode.LIGHTWEIGHT
        assert auto is False

    def test_flag_post_merge_with_bmc(self) -> None:
        """--mode post-merge with baseline_merge_commit → post-merge, explicit."""
        mode, auto = resolve_mode(
            cli_flag="post-merge", baseline_merge_commit="deadbeef"
        )
        assert mode is MissionReviewMode.POST_MERGE
        assert auto is False


class TestResolveModeMismatch:
    def test_post_merge_flag_without_bmc_raises(self) -> None:
        """--mode post-merge without baseline_merge_commit → ModeMismatchError."""
        with pytest.raises(ModeMismatchError) as exc_info:
            resolve_mode(cli_flag="post-merge", baseline_merge_commit=None)

        err = exc_info.value
        assert err.diagnostic_code == MissionReviewDiagnostic.MODE_MISMATCH

    def test_mismatch_error_message_contains_3_remediation_options(self) -> None:
        """FR-023: mode-mismatch diagnostic body must contain 3 remediation options."""
        with pytest.raises(ModeMismatchError) as exc_info:
            resolve_mode(cli_flag="post-merge", baseline_merge_commit=None)

        message = exc_info.value.message
        # Must name the missing signal
        assert "baseline_merge_commit" in message
        # Must contain 3 remediation options
        assert "spec-kitty consolidate" in message
        assert "--mode lightweight" in message
        assert "backfill" in message.lower() or "migrate" in message.lower()

    def test_mismatch_error_what_this_means_present(self) -> None:
        """FR-023: body must contain a 'What this means' paragraph."""
        with pytest.raises(ModeMismatchError) as exc_info:
            resolve_mode(cli_flag="post-merge", baseline_merge_commit=None)

        # The contract says: A "What this means" paragraph naming the missing signal
        assert "What this means" in exc_info.value.message

    def test_lightweight_flag_with_bmc_is_not_mismatch(self) -> None:
        """The reverse case is NOT a mismatch — legitimate quick check on merged mission."""
        # Must not raise
        mode, auto = resolve_mode(
            cli_flag="lightweight", baseline_merge_commit="abc123"
        )
        assert mode is MissionReviewMode.LIGHTWEIGHT

    def test_mismatch_is_value_error_subclass(self) -> None:
        with pytest.raises(ValueError):
            resolve_mode(cli_flag="post-merge", baseline_merge_commit=None)


class TestResolveModeAcceptanceFixtures:
    """Acceptance fixtures from review-mode-resolution.md contract."""

    def test_pre_merge_bare_invocation(self) -> None:
        mode, auto = resolve_mode(cli_flag=None, baseline_merge_commit=None)
        assert mode is MissionReviewMode.LIGHTWEIGHT

    def test_pre_merge_mode_post_merge_raises(self) -> None:
        with pytest.raises(ModeMismatchError):
            resolve_mode(cli_flag="post-merge", baseline_merge_commit=None)

    def test_post_merge_bare_invocation(self) -> None:
        mode, auto = resolve_mode(cli_flag=None, baseline_merge_commit="sha1234")
        assert mode is MissionReviewMode.POST_MERGE
        assert auto is True

    def test_post_merge_mode_lightweight_explicit(self) -> None:
        mode, auto = resolve_mode(
            cli_flag="lightweight", baseline_merge_commit="sha1234"
        )
        assert mode is MissionReviewMode.LIGHTWEIGHT
        assert auto is False
