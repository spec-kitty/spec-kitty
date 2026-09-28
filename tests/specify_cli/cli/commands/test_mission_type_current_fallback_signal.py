"""FR-005/NFR-002 -> fail-closed (#3831, ``7a9c35728``): ``mission current`` on
an unresolvable mission type.

The warn-and-substitute-to-``software-dev`` fallback this module originally
pinned was removed on purpose. ``get_mission_for_feature``
(``src/specify_cli/mission.py``) no longer emits a ``warnings.warn`` signal for
a typed-but-unresolvable ``mission_type``; instead ``get_mission_by_name``
raises ``MissionNotFoundError``, which propagates to ``current_cmd`` unchanged
-- a visible, diagnosable failure (exit 1, printed to stdout) rather than a
silent substitution an operator could miss under default warning filters.

These tests drive the real, pre-existing entry point end-to-end
(``spec-kitty mission-type current`` / ``current_cmd``) through
:class:`typer.testing.CliRunner`, capturing real stdout the way an operator
would see it. ``get_mission_for_feature`` itself is NOT mocked: the failure is
produced for real, via a genuinely-unresolvable ``mission_type`` in a real
``meta.json``.

Both directions are proven (SC-004 / NFR-005 non-vacuity):
* the fail-closed error IS present, deterministically across repeats, when
  resolution fails (T001/T003a), and
* it is ABSENT when mission-type resolution succeeds normally, including the
  pinned legacy no-mission-field path (T003b/T004) and a resolvable type
  through which an unrelated warning is still re-emitted (T005, #3831 fold).
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.mission_type import app as mission_type_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _write_meta(feature_dir: Path, *, mission_type: str | None) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "feature_number": "999",
        "slug": feature_dir.name,
        "friendly_name": "Fallback Signal Test Feature",
    }
    if mission_type is not None:
        meta["mission_type"] = mission_type
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _invoke_current(tmp_path: Path, mission_slug: str):
    with patch(
        "specify_cli.cli.commands.mission_type.get_project_root_or_exit",
        return_value=tmp_path,
    ):
        return runner.invoke(mission_type_app, ["current", "--mission", mission_slug])


class TestFallbackSignalPresent:
    """T001/T003a/R15 (re-pinned to fail-closed, #3831 / ``7a9c35728``): an
    unresolvable mission type is now a loud, deterministic ERROR -- never a
    silent software-dev substitution."""

    def test_unresolvable_mission_type_fails_closed_with_loud_error(self, tmp_path: Path) -> None:
        mission_slug = "999-unresolvable-mission-type"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        _write_meta(feature_dir, mission_type="totally-nonexistent-mission-type-xyz")

        # Invoke twice and assert the identical outcome both times: fail-closed
        # must be deterministic across repeats. (The retired warn-and-substitute
        # path was the opposite -- a bare module-level `warnings.warn` fires only
        # once per (message, category, lineno) under default filters, so a
        # second invocation used to go silent; that flakiness is gone with the
        # fallback itself.)
        for _ in range(2):
            result = _invoke_current(tmp_path, mission_slug)
            assert result.exit_code == 1, result.output
            assert "Error" in result.output
            assert "not found" in result.output
            assert "totally-nonexistent-mission-type-xyz" in result.output
            # No silent substitution: the panel that would name the
            # substituted mission is never reached.
            assert "Active Mission" not in result.output


class TestFallbackSignalAbsent:
    """T003b: the loud signal is ABSENT when resolution succeeds normally.

    Non-vacuity: a check that always fires regardless of input is not a real
    signal. Proving the negative direction is required alongside the positive.
    """

    def test_resolvable_mission_type_prints_no_warning(self, tmp_path: Path) -> None:
        mission_slug = "999-resolvable-mission-type"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        _write_meta(feature_dir, mission_type="software-dev")

        result = _invoke_current(tmp_path, mission_slug)

        assert result.exit_code == 0, result.output
        assert "Active Mission" in result.output
        assert "Warning" not in result.output

    def test_legacy_no_mission_field_prints_no_warning(self, tmp_path: Path) -> None:
        """FR-003a: a typeless legacy feature degrades to software-dev with no
        mission-type mismatch, so it is not a "fallback" in the FR-005 sense
        (mission.py itself does not warn for this path either — see
        ``test_legacy_feature_no_warning`` in
        ``tests/missions/test_mission_schema_unit.py``) and must stay silent.
        """
        mission_slug = "999-legacy-no-mission-field"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        _write_meta(feature_dir, mission_type=None)

        result = _invoke_current(tmp_path, mission_slug)

        assert result.exit_code == 0, result.output
        assert "Active Mission" in result.output
        assert "Warning" not in result.output


class TestNonFallbackWarningsReemitted:
    """#3831 fold: ``catch_warnings(record=True)`` captures EVERY warning
    raised inside the block -- an unrelated warning raised anywhere in the
    ``get_mission_for_feature`` call path must not be dropped on the floor
    with no trace. It is re-emitted through the normal ``warnings`` machinery
    (so a caller's own filter/handler still sees it) on a RESOLVABLE mission
    type, so the re-emit loop actually runs (the retired fallback-print
    branch it used to share a code path with is gone -- see R16)."""

    def test_unrelated_warning_is_reemitted_on_resolvable_mission_type(self, tmp_path: Path) -> None:
        from specify_cli.mission import get_mission_for_feature as real_get_mission_for_feature

        mission_slug = "999-unrelated-warning"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        _write_meta(feature_dir, mission_type="software-dev")

        def _wrapped(feature_dir_arg: Path, project_root_arg: Path | None = None):
            warnings.warn("unrelated diagnostic warning xyz123", UserWarning, stacklevel=2)
            return real_get_mission_for_feature(feature_dir_arg, project_root_arg)

        with (
            patch("specify_cli.cli.commands.mission_type.get_mission_for_feature", _wrapped),
            pytest.warns(UserWarning, match="unrelated diagnostic warning xyz123"),
        ):
            result = _invoke_current(tmp_path, mission_slug)

        assert result.exit_code == 0, result.output
        assert "Active Mission" in result.output
        # The retired fallback-print branch is gone (R16): a resolvable
        # mission type prints no CLI "Warning" line even though an unrelated
        # warning was re-emitted through the `warnings` machinery above.
        assert "Warning" not in result.output
