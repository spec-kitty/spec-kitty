"""FR-005/FR-006 read-surface presence-gate retarget: charter.yaml authority.

WP03 (charter-pack-usage-journey-01KYWWTF): the presence gates on
``charter context`` / ``charter status`` retargeted from the display-only
``charter.md`` onto the authoritative ``charter.yaml`` (FR-005), and the
``charter context --json`` ``project_charter.present`` signal flipped to key
on ``charter.yaml`` as the primary source of truth (FR-006). This module pins
the two remaining journeys from ``notes/research-synthesis.md``
("Journey acceptance tests" #4/#5) plus a dedicated FR-006 JSON contract-flip
test (SC-002: presence must survive ``charter.md`` deletion).

C-003 guard: these tests exercise the *presence* gate only. They never assert
that the ``charter.md`` prose/section readers (``context.py``'s bootstrap
"Source:" line, ``_extract_policy_summary``, the ``--include section:<id>``
selector) were retargeted -- those legitimately stay on ``charter.md`` and
are covered by ``tests/charter/test_context.py``.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from charter.activation.context import build_charter_context, build_charter_context_json
from specify_cli.cli.commands.charter import app
from specify_cli.cli.commands.charter._status_collectors import (
    _collect_charter_sync_status,
)
from tests.charter.test_context import _MINIMAL_GRAPH_YAML, _setup_fixture_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Journey 4 (#3105): context -- bundle authority. Renders the activated
# doctrine bundle; deleting charter.md must not stop it rendering.
# ---------------------------------------------------------------------------


class TestJourney4ContextBundleAuthority:
    def test_context_renders_activated_bundle_and_survives_charter_md_deletion(
        self, tmp_path: Path
    ) -> None:
        _setup_fixture_repo(tmp_path)

        from charter.offering.drg.models import DRGGraph
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        graph_data = yaml.load(StringIO(_MINIMAL_GRAPH_YAML))
        mock_graph = DRGGraph.model_validate(graph_data)

        with (
            patch("charter.activation._drg_helpers.load_validated_graph", return_value=mock_graph),
            patch("charter.activation.catalog.resolve_offering_root", return_value=tmp_path),
            patch("charter.offering.drg.validator.assert_valid"),
        ):
            before = build_charter_context(
                tmp_path, action="implement", depth=2, mission_type="software-dev"
            )

        assert before.mode == "bootstrap"
        assert "Charter file not found" not in before.text
        assert "DIRECTIVE_001" in before.text

        (tmp_path / ".kittify" / "charter" / "charter.md").unlink()

        with (
            patch("charter.activation._drg_helpers.load_validated_graph", return_value=mock_graph),
            patch("charter.activation.catalog.resolve_offering_root", return_value=tmp_path),
            patch("charter.offering.drg.validator.assert_valid"),
        ):
            after = build_charter_context(
                tmp_path, action="implement", depth=2, mission_type="software-dev"
            )

        # Bundle authority proven: the same activated directive still
        # renders -- this is NOT the "not found" dead-end the mission
        # closes (#3105), and mode never regresses to "missing".
        assert after.mode == "bootstrap"
        assert after.mode != "missing"
        assert "Charter file not found" not in after.text
        assert "DIRECTIVE_001" in after.text


# ---------------------------------------------------------------------------
# Journey 5 (#3105): status -- SYNCED on charter.yaml authority, survives
# charter.md deletion.
# ---------------------------------------------------------------------------


class TestJourney5StatusBundleAuthority:
    def test_status_reports_synced_on_charter_yaml_and_survives_charter_md_deletion(
        self, tmp_path: Path
    ) -> None:
        charter_dir = tmp_path / ".kittify" / "charter"
        charter_dir.mkdir(parents=True)
        (charter_dir / "charter.yaml").write_text(
            textwrap.dedent("""\
                schema_version: "2.0.0"
                metadata:
                  bundle_schema_version: 2
            """),
            encoding="utf-8",
        )
        (charter_dir / "charter.md").write_text("# Curated Charter\n", encoding="utf-8")

        before = _collect_charter_sync_status(tmp_path)
        assert before["available"] is True
        assert before["status"] == "synced"
        assert before["charter_path"] == ".kittify/charter/charter.md"

        (charter_dir / "charter.md").unlink()

        after = _collect_charter_sync_status(tmp_path)
        assert after["available"] is True
        assert after["status"] == "synced"
        # Header-authority regression pin (squad fold A): once charter.md is
        # gone, the header must name the file that actually exists
        # (charter.yaml, the authoritative bundle) -- not a stale reference
        # to a charter.md that no longer exists on disk.
        assert after["charter_path"] == ".kittify/charter/charter.yaml"
        assert not (charter_dir / "charter.md").exists()


# ---------------------------------------------------------------------------
# FR-006 -- dedicated JSON present-signal contract-flip test. NOT covered by
# the human-facing journeys 4/5 above: this pins the machine ``--json``
# surface specifically, the assertion that would fail against the pre-flip
# producer (which keyed ``present`` on charter.md).
# ---------------------------------------------------------------------------


def _git_init(repo_root: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(repo_root)], check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)


class TestFR006JsonPresentSignalFlip:
    def test_build_charter_context_json_present_keys_on_charter_yaml(
        self, tmp_path: Path
    ) -> None:
        """Direct producer-level pin: charter.yaml present, charter.md absent."""
        charter_dir = tmp_path / ".kittify" / "charter"
        charter_dir.mkdir(parents=True)
        (charter_dir / "charter.yaml").write_text("schema_version: '2.0.0'\n", encoding="utf-8")
        # ``mission_type_activations`` is unrelated to the FR-006 present-signal
        # flip this test pins, but WP04 (C-A1) made it a hard construction
        # precondition for ``PackContext.from_config`` (invoked internally by
        # ``build_charter_context_json``'s action-bundle resolution).
        (tmp_path / ".kittify" / "config.yaml").write_text(
            "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
        )

        from charter.activation.sync import SyncResult

        sync_result = SyncResult(
            synced=False,
            stale_before=False,
            files_written=[],
            extraction_mode="",
            canonical_root=tmp_path,
        )
        with patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=sync_result):
            payload = build_charter_context_json(tmp_path, action="plan", depth=1)

        # The FR-006 flip: charter.md was NEVER written in this fixture. A
        # pre-flip producer (keyed on charter.md) would report False here --
        # this is the assertion that proves the authority moved.
        assert payload["project_charter"]["present"] is True
        assert payload["project_charter"]["charter_md_present"] is False

        # Survives charter.md deletion when it later appears then disappears
        # again (SC-002), not just "never existed".
        (charter_dir / "charter.md").write_text("# Charter\n", encoding="utf-8")
        with patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=sync_result):
            with_md = build_charter_context_json(tmp_path, action="plan", depth=1)
        assert with_md["project_charter"]["present"] is True
        assert with_md["project_charter"]["charter_md_present"] is True

        (charter_dir / "charter.md").unlink()
        with patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=sync_result):
            after_delete = build_charter_context_json(tmp_path, action="plan", depth=1)
        assert after_delete["project_charter"]["present"] is True
        assert after_delete["project_charter"]["charter_md_present"] is False

    @pytest.mark.integration
    @pytest.mark.git_repo
    def test_cli_context_json_present_survives_charter_md_deletion(
        self, tmp_path: Path, charter_cwd_isolation: Callable[..., Path]
    ) -> None:
        """End-to-end pin through the real ``charter context --json`` CLI surface.

        Exercises both FR-006 sites at once: the producer
        (``context_json._project_charter_json_block``) and the CLI fallback
        default (``cli/commands/charter/context.py:158``) that must stay
        consistent with it.
        """
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        _git_init(repo_root)
        charter_dir = repo_root / ".kittify" / "charter"
        charter_dir.mkdir(parents=True)
        # ``generate --no-from-interview`` extracts from a seeded charter.md
        # to produce charter.yaml (the sync pipeline reads charter.md as its
        # source); once charter.yaml exists we delete charter.md to prove
        # the read surface no longer depends on it (SC-002).
        (charter_dir / "charter.md").write_text("# Curated Charter\n", encoding="utf-8")
        # ``mission_type_activations`` is unrelated to the FR-006 present-signal
        # flip this test pins, but WP04 (C-A1) made it a hard construction
        # precondition for ``PackContext.from_config`` -- provision it so both
        # the ``generate`` and ``context`` CLI invocations below can construct.
        (repo_root / ".kittify" / "config.yaml").write_text(
            "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
        )

        charter_cwd_isolation(repo_root)
        with patch("specify_cli.cli.commands.charter.find_repo_root", return_value=repo_root):
            generate_result = runner.invoke(app, ["generate", "--json", "--no-from-interview"])
            assert generate_result.exit_code == 0, generate_result.output
            assert (charter_dir / "charter.yaml").exists()

            (charter_dir / "charter.md").unlink()

            result = runner.invoke(app, ["context", "--action", "specify", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["project_charter"]["present"] is True


# ---------------------------------------------------------------------------
# Squad fold C (landing PR #3146) -- pin the intentional present-flip
# consumer-cell divergence.
#
# The ``--json`` ``project_charter.present`` signal keys SOLELY on
# ``charter.yaml`` (FR-006 above); the text renderer's ``mode`` gate
# (``build_charter_context`` in ``charter/context.py``) is deliberately an
# OR over BOTH files -- ``mode`` is only ``"missing"`` when NEITHER file
# exists (see that function's own "FR-005" comment block). This divergence
# is intentional: charter.yaml is the governance-read authority for the
# machine JSON signal, while a legacy project's curated charter.md alone is
# still enough to render bootstrap text for a human. The risky, previously
# UNTESTED cell is the legacy layout the OR-gate exists to keep serving:
# charter.md present, charter.yaml ABSENT. No product code changes here --
# this is a regression pin on already-shipped, deliberate behaviour, not a
# fix.
# ---------------------------------------------------------------------------


class TestFoldCLegacyCharterMdOnlyPresentFlipCell:
    def test_charter_md_present_yaml_absent_json_present_is_false(
        self, tmp_path: Path
    ) -> None:
        """Direct producer-level pin: charter.md present, charter.yaml
        ABSENT ⇒ ``project_charter.present`` is ``False``. A pre-FR-006
        (or a future "aligned to the text renderer") producer that ORs in
        ``charter.md`` presence would report ``True`` here instead -- that
        is the exact assertion this test exists to catch.
        """
        charter_dir = tmp_path / ".kittify" / "charter"
        charter_dir.mkdir(parents=True)
        (charter_dir / "charter.md").write_text(
            "# Legacy Curated Charter\n", encoding="utf-8"
        )
        assert not (charter_dir / "charter.yaml").exists()
        # ``mission_type_activations`` is unrelated to the present-signal
        # divergence this test pins, but WP04 (C-A1) made it a hard
        # construction precondition for ``PackContext.from_config``. A
        # separate file from ``charter.yaml`` (whose absence is the fixture
        # precondition under test), so this does not disturb that assertion.
        (tmp_path / ".kittify" / "config.yaml").write_text(
            "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
        )

        from charter.activation.sync import SyncResult

        # ``build_charter_context_json`` -> ``_project_charter_json_block``
        # resolves its bundle root via ``ensure_charter_bundle_fresh``,
        # which -- because ``charter.md`` exists here -- would otherwise
        # auto-sync and WRITE ``charter.yaml`` as a side effect, silently
        # flipping the very fixture precondition ("charter.yaml absent")
        # this test depends on. Stubbed to a no-op ``SyncResult`` exactly
        # like the FR-006 producer test above, for the same reason.
        sync_result = SyncResult(
            synced=False,
            stale_before=False,
            files_written=[],
            extraction_mode="",
            canonical_root=tmp_path,
        )
        with patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=sync_result):
            payload = build_charter_context_json(tmp_path, action="plan", depth=1)

        # Sanity: the stub must not have let anything else mutate the
        # fixture out from under the assertion below.
        assert not (charter_dir / "charter.yaml").exists()

        project_charter = payload["project_charter"]
        assert project_charter["present"] is False
        assert project_charter["charter_md_present"] is True

    def test_text_renderer_still_renders_for_the_same_charter_md_only_project(
        self, tmp_path: Path
    ) -> None:
        """Documents the intended divergence for the SAME legacy layout: the
        text renderer's ``mode`` never regresses to ``"missing"`` for a
        charter.md-only project, even though the JSON producer above
        reports ``present: False`` for it. If a future change makes the two
        surfaces agree by also gating the TEXT renderer on ``charter.yaml``
        alone, this is the test that should catch it.
        """
        charter_dir = tmp_path / ".kittify" / "charter"
        charter_dir.mkdir(parents=True)
        (charter_dir / "charter.md").write_text(
            "# Legacy Curated Charter\n", encoding="utf-8"
        )
        assert not (charter_dir / "charter.yaml").exists()
        # ``mission_type_activations`` is unrelated to the text-renderer
        # divergence this test pins, but WP04 (C-A1) made it a hard
        # construction precondition for ``PackContext.from_config``.
        (tmp_path / ".kittify" / "config.yaml").write_text(
            "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
        )

        from charter.offering.drg.models import DRGGraph
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        graph_data = yaml.load(StringIO(_MINIMAL_GRAPH_YAML))
        mock_graph = DRGGraph.model_validate(graph_data)

        with (
            patch("charter.activation._drg_helpers.load_validated_graph", return_value=mock_graph),
            patch("charter.activation.catalog.resolve_offering_root", return_value=tmp_path),
            patch("charter.offering.drg.validator.assert_valid"),
        ):
            result = build_charter_context(
                tmp_path, action="implement", depth=2, mission_type="software-dev"
            )

        assert result.mode != "missing"
        assert "Charter file not found" not in result.text
