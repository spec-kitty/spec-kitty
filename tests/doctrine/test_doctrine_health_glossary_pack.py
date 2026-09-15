"""Glossary-pack health in ``spec-kitty doctor doctrine --json`` (WP05, T024-T026).

FR-012 / NFR-005 / SC-001: ``doctor doctrine --json`` must surface glossary-pack
counts + health, an invalid member pack must degrade the aggregate to
**unhealthy** (never silently healthy — the exact anti-pattern SC-001
forbids), and the command must stay fast.

This is a three-layer seam (squad finding F1/M1/M2 on the WP05 prompt):

* **MODEL** (``_doctrine_health.py``) — :class:`GlossaryPackHealth` /
  :class:`SkippedGlossaryPack`, nested inside
  :class:`DoctrineHealthReport` and folded into its ``healthy`` property.
* **COLLECT** (``_doctrine_collect.py``) — :func:`_collect_glossary_pack_health`
  sources loaded packs from ``DoctrineService.glossary_packs`` (the real
  production repository, WP02) and attaches the result to the report built by
  ``_collect_profile_health``. Without this layer the MODEL type would exist
  but the ``--json`` payload would stay silent (the squad's HIGH finding).
* **RENDER** (``_profile_health_render.py``) — untouched: nesting the new
  health dimension inside ``DoctrineHealthReport.to_dict()`` means
  ``_emit_doctrine_json``'s existing ``report.to_dict()`` passthrough already
  carries it, with no render-layer edit required.

Each class of test below exercises one layer, plus an end-to-end CLI test
proving the JSON payload actually carries the health (not just the MODEL
type in isolation — the squad's non-vacuity concern).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.offering.glossary_packs import GlossaryPackRepository
from specify_cli.cli.commands._doctrine_collect import (
    _collect_glossary_pack_health,
    _parse_skipped_glossary_pack_warning,
)
from specify_cli.cli.commands._doctrine_health import (
    DoctrineHealthReport,
    GlossaryPackHealth,
    PackHealth,
    SkippedGlossaryPack,
)
from specify_cli.cli.commands.doctor import app as doctor_app
from tests._perf_helpers import assert_timing_budget

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _write_glossary_pack(directory: Path, filename: str, data: dict[str, object]) -> None:
    """Author a synthetic ``*.glossary-pack.yaml`` file for a load test."""
    directory.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with (directory / filename).open("w") as f:
        yaml.dump(data, f)


@pytest.fixture
def bare_repo_root(tmp_path: Path) -> Path:
    """A minimal spec-kitty project root — no org packs, no project doctrine.

    Mirrors the ``kittify_project`` fixture in
    ``tests/specify_cli/cli/commands/test_doctor_doctrine_integrity.py``: just
    enough for ``locate_project_root``/``DoctrineService`` to resolve without
    a real git checkout.
    """
    project_root = tmp_path / "project"
    kittify = project_root / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n", encoding="utf-8"
    )
    return project_root


@pytest.fixture
def expected_builtin_term_count() -> int:
    """The real shipped ``spec-kitty-core`` pack's term count.

    Loaded fresh from ``GlossaryPackRepository`` (no ``built_in_dir=``
    override) so this test tracks the shipped pack content rather than
    pinning a magic number that would silently drift.
    """
    pack = GlossaryPackRepository().get("spec-kitty-core")
    assert pack is not None, "shipped spec-kitty-core glossary pack is missing"
    return len(pack.terms)


# ---------------------------------------------------------------------------
# MODEL — GlossaryPackHealth / SkippedGlossaryPack / DoctrineHealthReport nesting
# ---------------------------------------------------------------------------


class TestGlossaryPackHealthModel:
    def test_healthy_with_no_invalid_packs(self) -> None:
        health = GlossaryPackHealth(pack_count=1, term_count=104)

        assert health.healthy is True
        assert health.to_dict() == {
            "pack_count": 1,
            "term_count": 104,
            "healthy": True,
            "invalid_packs": [],
        }

    def test_unhealthy_with_one_invalid_pack(self) -> None:
        skipped = SkippedGlossaryPack(
            layer="project", path="broken.glossary-pack.yaml", error_summary="boom"
        )
        health = GlossaryPackHealth(pack_count=1, term_count=104, invalid_packs=[skipped])

        assert health.healthy is False
        payload = health.to_dict()
        assert payload["healthy"] is False
        assert payload["invalid_packs"] == [
            {
                "layer": "project",
                "path": "broken.glossary-pack.yaml",
                "error_summary": "boom",
            }
        ]

    def test_report_nests_glossary_pack_health_and_folds_into_healthy(self) -> None:
        agent_pack = PackHealth(
            pack_id="builtin", layer="builtin", discovered_count=1, valid_count=1
        )

        healthy_report = DoctrineHealthReport(
            packs=[agent_pack],
            glossary_packs=GlossaryPackHealth(pack_count=1, term_count=104),
        )
        assert healthy_report.healthy is True
        report_dict = healthy_report.to_dict()
        assert "glossary_packs" in report_dict
        assert report_dict["glossary_packs"]["healthy"] is True

        unhealthy_report = DoctrineHealthReport(
            packs=[agent_pack],
            glossary_packs=GlossaryPackHealth(
                pack_count=1,
                term_count=104,
                invalid_packs=[
                    SkippedGlossaryPack(
                        layer="project", path="bad.glossary-pack.yaml", error_summary="x"
                    )
                ],
            ),
        )
        # An invalid glossary pack degrades the AGGREGATE report — not just
        # its own nested health block (SC-001 / T025 non-vacuity).
        assert unhealthy_report.healthy is False

    def test_report_default_glossary_pack_health_is_vacuously_healthy(self) -> None:
        """A report built with no glossary-pack data attached stays healthy.

        Existing call sites (e.g. tests exercising other report dimensions)
        must not spuriously flip unhealthy just because they never attached
        glossary-pack health.
        """
        report = DoctrineHealthReport(
            packs=[
                PackHealth(
                    pack_id="builtin", layer="builtin", discovered_count=1, valid_count=1
                )
            ]
        )
        assert report.healthy is True
        assert report.to_dict()["glossary_packs"]["pack_count"] == 0


# ---------------------------------------------------------------------------
# COLLECT — _collect_glossary_pack_health (the load-bearing layer, F1/M1)
# ---------------------------------------------------------------------------


class TestParseSkippedGlossaryPackWarning:
    def test_parses_the_pinned_base_repository_warning_shape(self) -> None:
        skipped = _parse_skipped_glossary_pack_warning(
            "Skipping invalid project glossarypack broken.glossary-pack.yaml: "
            "1 validation error for GlossaryPack\nterms.0.definition\n  Field required"
        )

        assert skipped.layer == "project"
        assert skipped.path == "broken.glossary-pack.yaml"
        assert "Field required" in skipped.error_summary

    def test_unrecognised_message_shape_degrades_to_unknown(self) -> None:
        """Defensive fallback (production emitter shape is pinned): a message
        that doesn't match still surfaces a diagnostic instead of raising.
        """
        skipped = _parse_skipped_glossary_pack_warning("a completely different warning")

        assert skipped.layer == "unknown"
        assert skipped.path == "unknown"
        assert skipped.error_summary == "a completely different warning"


class TestCollectGlossaryPackHealth:
    def test_valid_builtin_pack_reports_healthy_with_term_count(
        self, bare_repo_root: Path, expected_builtin_term_count: int
    ) -> None:
        health = _collect_glossary_pack_health(bare_repo_root)

        assert health.healthy is True
        assert health.pack_count == 1
        assert health.term_count == expected_builtin_term_count
        assert health.invalid_packs == []

    def test_synthetic_missing_definition_pack_degrades_to_unhealthy(
        self, bare_repo_root: Path
    ) -> None:
        """INVALID arm (T024): a term missing ``definition`` fails schema validation."""
        project_glossary_dir = bare_repo_root / ".kittify" / "doctrine" / "glossary_packs"
        _write_glossary_pack(
            project_glossary_dir,
            "broken.glossary-pack.yaml",
            {
                "id": "broken-pack",
                "provenance": "project",
                "terms": [
                    {"surface": "broken term", "confidence": 0.9, "status": "active"}
                ],
            },
        )

        health = _collect_glossary_pack_health(bare_repo_root)

        assert health.healthy is False
        # The valid built-in pack still loads — only the broken one is skipped.
        assert health.pack_count == 1
        assert len(health.invalid_packs) == 1
        invalid = health.invalid_packs[0]
        assert invalid.layer == "project"
        assert "broken.glossary-pack.yaml" in invalid.path
        assert "definition" in invalid.error_summary

    def test_synthetic_duplicate_surface_pack_degrades_to_unhealthy(
        self, bare_repo_root: Path
    ) -> None:
        """INVALID arm (T024): a duplicate ``surface`` fails the pack's own validator."""
        term = {
            "surface": "dup term",
            "definition": "d",
            "confidence": 0.9,
            "status": "active",
        }
        project_glossary_dir = bare_repo_root / ".kittify" / "doctrine" / "glossary_packs"
        _write_glossary_pack(
            project_glossary_dir,
            "dup.glossary-pack.yaml",
            {"id": "dup-pack", "provenance": "project", "terms": [term, dict(term)]},
        )

        health = _collect_glossary_pack_health(bare_repo_root)

        assert health.healthy is False
        assert any("dup.glossary-pack.yaml" in p.path for p in health.invalid_packs)


# ---------------------------------------------------------------------------
# End-to-end CLI — proves the JSON payload actually surfaces the health
# (through COLLECT, not just the MODEL type in isolation).
# ---------------------------------------------------------------------------


def _invoke_doctrine_json(project_root: Path) -> tuple[int, dict[str, object]]:
    with patch(
        "specify_cli.cli.commands.doctor.locate_project_root",
        return_value=project_root,
    ):
        result = runner.invoke(doctor_app, ["doctrine", "--json"])
    payload = json.loads(result.output)
    return result.exit_code, payload


class TestDoctorDoctrineGlossaryPackJson:
    def test_builtin_pack_loaded_healthy_with_term_count(
        self, bare_repo_root: Path, expected_builtin_term_count: int
    ) -> None:
        """VALID arm (T024): built-in spec-kitty-core pack loads healthy."""
        exit_code, payload = _invoke_doctrine_json(bare_repo_root)

        glossary_health = payload["profile_health"]["glossary_packs"]
        assert glossary_health["healthy"] is True
        assert glossary_health["pack_count"] == 1
        assert glossary_health["term_count"] == expected_builtin_term_count
        assert exit_code == 0

    def test_synthetic_invalid_pack_flips_doctor_unhealthy(
        self, bare_repo_root: Path
    ) -> None:
        """INVALID arm (T024): a malformed pack flips RC=1, never silently healthy."""
        project_glossary_dir = bare_repo_root / ".kittify" / "doctrine" / "glossary_packs"
        _write_glossary_pack(
            project_glossary_dir,
            "broken.glossary-pack.yaml",
            {
                "id": "broken-pack",
                "provenance": "project",
                "terms": [{"surface": "x", "confidence": 0.9, "status": "active"}],
            },
        )

        exit_code, payload = _invoke_doctrine_json(bare_repo_root)

        glossary_health = payload["profile_health"]["glossary_packs"]
        assert glossary_health["healthy"] is False
        assert glossary_health["invalid_packs"], glossary_health
        # The invalid glossary pack degrades the AGGREGATE report, not just
        # its own nested block.
        assert payload["profile_health"]["healthy"] is False
        assert exit_code == 1


# ---------------------------------------------------------------------------
# Performance — NFR-005 (T026): a generous, non-flaky single threshold.
# ---------------------------------------------------------------------------


class TestDoctorDoctrineFunctional:
    """Functional companion to TestDoctorDoctrinePerformance (split, #4015):
    the exit-code check must run on the per-PR path, not only nightly."""

    def test_doctor_doctrine_json_succeeds(self, bare_repo_root: Path) -> None:
        exit_code, _payload = _invoke_doctrine_json(bare_repo_root)

        assert exit_code == 0


@pytest.mark.performance
class TestDoctorDoctrinePerformance:
    """NFR-005 wall-clock gate (T026), held out of normal PR runs.

    A single-shot wall-clock budget is cold-start/shared-runner bound, so
    ``@pytest.mark.performance`` keeps it out of normal runs; set
    ``SPEC_KITTY_RUN_PERFORMANCE=1`` for an explicit local run. The out-of-band
    statistical harness is tracked in #3595.

    NFR-005 timing budget only (split, #4015): functional coverage moved to
    TestDoctorDoctrineFunctional, above.
    """

    def test_doctor_doctrine_json_completes_under_two_seconds(
        self, bare_repo_root: Path
    ) -> None:
        start = time.perf_counter()
        _invoke_doctrine_json(bare_repo_root)
        elapsed = time.perf_counter() - start

        assert_timing_budget(elapsed, 2.0, name="doctor_doctrine_json")
