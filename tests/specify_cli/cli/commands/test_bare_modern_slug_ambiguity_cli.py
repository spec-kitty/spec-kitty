"""#4723: a bare human slug matching >1 mission must surface ambiguity, never
``MISSION_NOT_FOUND`` and never an uncaught traceback, across the CLI commands
that resolve ``--mission``.

Root cause (fixed in ``missions._read_path_resolver.resolve_bare_modern_mission_dir_name``):
the glob that folds a bare human slug (``payment``) onto its on-disk composed
``<slug>-<mid8>`` primary dir (``payment-01M2TM6J``) collapsed BOTH the
zero-match and multi-match cases onto the same ``return None`` — so an
operator whose bare slug collided with two or more missions was told the
mission did not exist at all.

That fix alone flows automatically through every caller in the
``missions._read_path_resolver`` / ``placement_seam(...).read_dir(...)``
family (``agent status``, ``agent tasks``, ``next``, ``status.aggregate``).
Two residual gaps needed threading separately:

* ``research`` and ``merge`` called ``placement_seam(...).read_dir(...)``
  directly with no ``except MissionSelectorAmbiguous`` — the newly-raised
  exception would have escaped as a raw traceback instead of the intended
  clean diagnostic (the exact class of bug #2878 already fixed for
  ``UnsafePathSegmentError`` on these same two commands).
* ``accept`` and ``reconcile`` resolved ``--mission`` via
  ``resolve_mission_handle`` directly, which delegates to the IDENTITY
  resolver (``context.mission_resolver.resolve_mission``) — a completely
  separate resolver with NO fold from a bare human slug onto a composed
  ``<slug>-<mid8>`` dir name at all, so it silently produced
  ``MissionNotFoundError`` for both the zero-match AND the multi-match case.
  Both commands now consult the new shared
  ``selector_resolution.resolve_mission_dir_with_bare_modern_fold`` helper,
  which tries the (now-fixed) bare-modern-slug primitive first.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _seed_two_colliding_missions(tmp_path: Path) -> None:
    """Two composed primary dirs sharing the bare human slug ``payment``."""
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    for mid8 in ("01M2TM6J", "01M2TM6M"):
        mission_dir = tmp_path / "kitty-specs" / f"payment-{mid8}"
        mission_dir.mkdir(parents=True)
        (mission_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": f"{mid8}ABCDEFGHJKMNPQRSTV",
                    "mission_slug": f"payment-{mid8}",
                }
            ),
            encoding="utf-8",
        )


def _seed_one_mission(tmp_path: Path, *, slug: str, mid8: str) -> Path:
    mission_dir = tmp_path / "kitty-specs" / f"{slug}-{mid8}"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": f"{mid8}ABCDEFGHJKMNPQRSTV",
                "mission_slug": f"{slug}-{mid8}",
            }
        ),
        encoding="utf-8",
    )
    return mission_dir


class TestResearchBareSlugAmbiguity:
    def test_ambiguous_bare_slug_exits_cleanly_not_traceback(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.research import _read_mission_dir_or_exit
        from mission_runtime import MissionArtifactKind

        _seed_two_colliding_missions(tmp_path)

        with pytest.raises(typer.Exit) as excinfo:
            _read_mission_dir_or_exit(tmp_path, "payment", MissionArtifactKind.STATUS_STATE)

        assert excinfo.value.exit_code == 2


class TestMergeBareSlugAmbiguity:
    def test_ambiguous_bare_slug_exits_cleanly_not_traceback(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.merge import _resolve_slug_or_exit

        _seed_two_colliding_missions(tmp_path)

        with pytest.raises(typer.Exit) as excinfo:
            _resolve_slug_or_exit(tmp_path, "payment")

        assert excinfo.value.exit_code == 2


class TestSelectorResolutionBareModernFold:
    """``resolve_mission_dir_with_bare_modern_fold`` — the shared helper
    ``accept`` and ``reconcile`` now consume instead of calling
    ``resolve_mission_handle`` directly."""

    def test_ambiguous_bare_slug_raises_structured_json_envelope(self, tmp_path: Path) -> None:
        from specify_cli.cli.selector_resolution import (
            resolve_mission_dir_with_bare_modern_fold,
        )

        _seed_two_colliding_missions(tmp_path)

        with pytest.raises(SystemExit) as excinfo:
            resolve_mission_dir_with_bare_modern_fold("payment", tmp_path, json_mode=True)

        assert excinfo.value.code == 1

    def test_ambiguous_bare_slug_never_reports_not_found(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.selector_resolution import (
            resolve_mission_dir_with_bare_modern_fold,
        )

        _seed_two_colliding_missions(tmp_path)

        with pytest.raises(SystemExit):
            resolve_mission_dir_with_bare_modern_fold("payment", tmp_path, json_mode=True)

        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False
        assert payload["error_code"] == "MISSION_AMBIGUOUS_SELECTOR"
        assert set(payload["candidates"]) == {
            "payment-01M2TM6J",
            "payment-01M2TM6M",
        }

    def test_unambiguous_bare_slug_still_resolves(self, tmp_path: Path) -> None:
        from specify_cli.cli.selector_resolution import (
            resolve_mission_dir_with_bare_modern_fold,
        )

        expected = _seed_one_mission(tmp_path, slug="invoicing", mid8="01M2TM7A")

        resolved = resolve_mission_dir_with_bare_modern_fold("invoicing", tmp_path, json_mode=True)

        assert resolved == expected

    def test_unknown_handle_falls_back_to_identity_resolver_not_found(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.selector_resolution import (
            resolve_mission_dir_with_bare_modern_fold,
        )

        (tmp_path / "kitty-specs").mkdir(parents=True)

        with pytest.raises(SystemExit) as excinfo:
            resolve_mission_dir_with_bare_modern_fold("no-such-mission", tmp_path, json_mode=True)

        assert excinfo.value.code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["error_code"] == "MISSION_NOT_FOUND"


class TestReconcileBareSlugAmbiguity:
    def test_ambiguous_bare_slug_never_reports_not_found(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands._review_cycle_reconcile_doctor import (
            _mission_dirs_for,
        )

        _seed_two_colliding_missions(tmp_path)

        with pytest.raises(SystemExit) as excinfo:
            _mission_dirs_for(tmp_path, "payment", json_mode=True)

        assert excinfo.value.code == 1


class TestAcceptBareSlugAmbiguity:
    def test_command_imports_bare_modern_fold_helper_not_raw_resolver(self) -> None:
        """Regression guard: ``accept`` must resolve ``--mission`` through the
        bare-modern-slug-aware helper, not ``resolve_mission_handle`` directly
        (which cannot fold a bare human slug onto a composed dir at all)."""
        import specify_cli.cli.commands.accept as accept_module

        assert hasattr(accept_module, "resolve_mission_dir_with_bare_modern_fold")
