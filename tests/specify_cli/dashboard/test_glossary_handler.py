"""Tests for dashboard GlossaryHandler — /api/glossary-health, /api/glossary-terms, /glossary."""

from __future__ import annotations

import io
import json
from kernel.clock import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from glossary.exceptions import SeedFileValidationError, SeedValidationError
from glossary.models import Provenance, SenseStatus, TermSense, TermSurface

pytestmark = pytest.mark.fast


def _make_term(surface: str, definition: str, status: str, confidence: float) -> TermSense:
    """Build a TermSense for test use."""
    status_enum = {
        "active": SenseStatus.ACTIVE,
        "draft": SenseStatus.DRAFT,
        "deprecated": SenseStatus.DEPRECATED,
    }[status]
    return TermSense(
        surface=TermSurface(surface),
        scope="spec_kitty_core",
        definition=definition,
        provenance=Provenance(
            actor_id="test",
            timestamp=datetime(2026, 1, 1),
            source="test",
        ),
        confidence=confidence,
        status=status_enum,
    )


def _make_handler(tmp_path: Path) -> MagicMock:
    """Build a minimal mock handler that records HTTP method calls."""
    handler = MagicMock()
    handler.project_dir = str(tmp_path)
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.wfile = io.BytesIO()
    return handler


def _read_response(handler: MagicMock) -> object:
    """Decode JSON written to handler.wfile."""
    handler.wfile.seek(0)
    return json.loads(handler.wfile.read().decode("utf-8"))


class TestGlossaryHealth:
    """Tests for handle_glossary_health() → GET /api/glossary-health."""

    def test_health_counts_terms_by_status(self, tmp_path):
        """Returns correct totals when store has 2 active, 1 draft."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        terms = [
            _make_term("alpha", "def a", "active", 1.0),
            _make_term("beta", "def b", "active", 0.9),
            _make_term("gamma", "def g", "draft", 0.7),
        ]

        handler = _make_handler(tmp_path)

        with patch.object(gloss_module, "_collect_all_senses_with_errors", return_value=(terms, [])):
            gloss_module.GlossaryHandler.handle_glossary_health(handler)

        handler.send_response.assert_called_once_with(200)
        data = _read_response(handler)
        assert data["total_terms"] == 3
        assert data["active_count"] == 2
        assert data["draft_count"] == 1
        assert data["deprecated_count"] == 0

    def test_health_returns_zero_counts_on_empty_store(self, tmp_path):
        """Returns zero counts when store is empty (no exception raised)."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        handler = _make_handler(tmp_path)

        with patch.object(gloss_module, "_collect_all_senses_with_errors", return_value=([], [])):
            gloss_module.GlossaryHandler.handle_glossary_health(handler)

        handler.send_response.assert_called_once_with(200)
        data = _read_response(handler)
        assert data["total_terms"] == 0
        assert data["active_count"] == 0
        assert data["draft_count"] == 0
        assert data["deprecated_count"] == 0

    def test_health_returns_zero_counts_on_error(self, tmp_path):
        """Returns safe zero-count payload when _collect_all_senses raises."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        handler = _make_handler(tmp_path)

        with patch.object(gloss_module, "_collect_all_senses_with_errors", side_effect=RuntimeError("boom")):
            gloss_module.GlossaryHandler.handle_glossary_health(handler)

        handler.send_response.assert_called_once_with(200)
        data = _read_response(handler)
        assert data["total_terms"] == 0
        assert data["high_severity_drift_count"] == 0
        assert data["entity_pages_generated"] is False
        assert data["last_conflict_at"] is None

    def test_health_returns_zero_counts_without_project_dir(self, tmp_path):
        """Returns safe zero-count payload when project_dir is not configured."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        handler = _make_handler(tmp_path)
        handler.project_dir = None

        gloss_module.GlossaryHandler.handle_glossary_health(handler)

        handler.send_response.assert_called_once_with(200)
        data = _read_response(handler)
        assert data["total_terms"] == 0
        assert data["high_severity_drift_count"] == 0
        assert data["entity_pages_generated"] is False
        assert data["last_conflict_at"] is None

    def test_health_counts_high_severity_events(self, tmp_path):
        """Reads canonical glossary event logs and counts high/critical findings."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)
        event_log = events_dir / "mission-001.events.jsonl"
        events = [
            {
                "event_type": "SemanticCheckEvaluated",
                "step_id": "step-1",
                "timestamp": "2026-01-01T00:00:00Z",
                "findings": [
                    {
                        "term": {"surface_text": "alpha"},
                        "term_id": "glossary:alpha",
                        "severity": "high",
                        "conflict_type": "ambiguous",
                    }
                ],
            },
            {
                "event_type": "SemanticCheckEvaluated",
                "step_id": "step-2",
                "timestamp": "2026-01-02T00:00:00Z",
                "findings": [
                    {
                        "term": {"surface_text": "beta"},
                        "term_id": "glossary:beta",
                        "severity": "critical",
                        "conflict_type": "inconsistent",
                    },
                    {
                        "term": {"surface_text": "gamma"},
                        "term_id": "glossary:gamma",
                        "severity": "low",
                        "conflict_type": "unknown",
                    },
                ],
            },
            {"event_type": "other_event", "severity": "high", "timestamp": "2026-01-04T00:00:00Z"},
        ]
        event_log.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

        handler = _make_handler(tmp_path)

        with patch.object(gloss_module, "_collect_all_senses_with_errors", return_value=([], [])):
            gloss_module.GlossaryHandler.handle_glossary_health(handler)

        data = _read_response(handler)
        assert data["high_severity_drift_count"] == 2
        assert data["last_conflict_at"] == "2026-01-02T00:00:00Z"

    def test_health_missing_event_log_returns_zero_drift(self, tmp_path):
        """Returns high_severity_drift_count=0 when event log doesn't exist."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        handler = _make_handler(tmp_path)

        with patch.object(gloss_module, "_collect_all_senses_with_errors", return_value=([], [])):
            gloss_module.GlossaryHandler.handle_glossary_health(handler)

        data = _read_response(handler)
        assert data["high_severity_drift_count"] == 0
        assert data["last_conflict_at"] is None

    def test_health_includes_all_required_fields(self, tmp_path):
        """All GlossaryHealthResponse fields are present in the response."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        handler = _make_handler(tmp_path)

        with patch.object(gloss_module, "_collect_all_senses_with_errors", return_value=([], [])):
            gloss_module.GlossaryHandler.handle_glossary_health(handler)

        data = _read_response(handler)
        required_keys = {
            "total_terms", "active_count", "draft_count", "deprecated_count",
            "high_severity_drift_count", "orphaned_term_count",
            "entity_pages_generated", "entity_pages_path", "last_conflict_at",
            "validation_errors",
        }
        assert required_keys.issubset(data.keys())

    def test_health_valid_data_has_null_validation_errors(self, tmp_path):
        """When data is valid, validation_errors is None."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        terms = [_make_term("alpha", "def a", "active", 1.0)]
        handler = _make_handler(tmp_path)

        with patch.object(gloss_module, "_collect_all_senses_with_errors", return_value=(terms, [])):
            gloss_module.GlossaryHandler.handle_glossary_health(handler)

        data = _read_response(handler)
        assert data["validation_errors"] is None
        assert data["total_terms"] == 1

    def test_health_surfaces_validation_errors(self, tmp_path):
        """When SeedFileValidationError is raised, validation_errors contains error details."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        seed_errors = [
            SeedValidationError(
                file_path=Path("/fake/seed.yaml"),
                term_index=2,
                term_surface="badterm",
                field="definition",
                message="Field required",
            ),
            SeedValidationError(
                file_path=Path("/fake/seed.yaml"),
                term_index=None,
                term_surface=None,
                field="terms",
                message="List should have at least 1 item",
            ),
        ]
        exc = SeedFileValidationError(Path("/fake/seed.yaml"), seed_errors)

        handler = _make_handler(tmp_path)

        with patch.object(gloss_module, "_collect_all_senses_with_errors", side_effect=exc):
            gloss_module.GlossaryHandler.handle_glossary_health(handler)

        data = _read_response(handler)
        assert data["total_terms"] == 0
        assert data["validation_errors"] is not None
        assert len(data["validation_errors"]) == 2

        err0 = data["validation_errors"][0]
        assert err0["file"] == "/fake/seed.yaml"
        assert err0["term_index"] == 2
        assert err0["term_surface"] == "badterm"
        assert err0["field"] == "definition"
        assert err0["message"] == "Field required"

        err1 = data["validation_errors"][1]
        assert err1["term_index"] is None
        assert err1["term_surface"] is None

    def test_health_generic_error_has_null_validation_errors(self, tmp_path):
        """Generic Exception path still sets validation_errors to None."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        handler = _make_handler(tmp_path)

        with patch.object(gloss_module, "_collect_all_senses_with_errors", side_effect=RuntimeError("boom")):
            gloss_module.GlossaryHandler.handle_glossary_health(handler)

        data = _read_response(handler)
        assert data["total_terms"] == 0
        assert data["validation_errors"] is None

    def test_health_reports_validation_errors_after_partial_recovery(self, tmp_path):
        """Recovered dashboard terms must not hide seed validation errors."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        seed_dir = tmp_path / ".kittify" / "glossaries"
        seed_dir.mkdir(parents=True)
        (seed_dir / "spec_kitty_core.yaml").write_text(
            "terms:\n"
            "  - surface: alpha\n"
            "    definition: First letter\n"
            "    status: active\n"
            "  - surface: beta\n"
            "    definition: Invalid extra field\n"
            "    status: active\n"
            "    bogus_extra_field: rejected\n"
            "  - surface: gamma\n"
            "    definition: Third letter\n"
            "    status: draft\n",
            encoding="utf-8",
        )
        handler = _make_handler(tmp_path)

        gloss_module.GlossaryHandler.handle_glossary_health(handler)

        data = _read_response(handler)
        assert data["total_terms"] == 2
        assert data["active_count"] == 1
        assert data["draft_count"] == 1
        assert data["validation_errors"] is not None
        assert data["validation_errors"][0]["term_index"] == 1
        assert data["validation_errors"][0]["term_surface"] == "beta"
        assert data["validation_errors"][0]["field"] == "bogus_extra_field"

    def test_health_reports_invalid_scope_even_when_lower_scope_loads(self, tmp_path):
        """A valid lower-precedence scope must not mask an invalid higher scope."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        seed_dir = tmp_path / ".kittify" / "glossaries"
        seed_dir.mkdir(parents=True)
        (seed_dir / "mission_local.yaml").write_text(
            "terms:\n"
            "  - surface: BadTerm\n"
            "    definition: Invalid high-precedence term\n",
            encoding="utf-8",
        )
        (seed_dir / "spec_kitty_core.yaml").write_text(
            "terms:\n"
            "  - surface: alpha\n"
            "    definition: Valid core term\n"
            "    status: active\n",
            encoding="utf-8",
        )
        handler = _make_handler(tmp_path)

        gloss_module.GlossaryHandler.handle_glossary_health(handler)

        data = _read_response(handler)
        assert data["total_terms"] == 1
        assert data["active_count"] == 1
        assert data["validation_errors"] is not None
        assert data["validation_errors"][0]["term_index"] == 0
        assert data["validation_errors"][0]["term_surface"] == "BadTerm"
        assert data["validation_errors"][0]["field"] == "surface"

    def test_health_refuses_recovery_for_root_level_validation_error(self, tmp_path):
        """Root seed schema errors are file-level failures, not per-term recovery."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        seed_dir = tmp_path / ".kittify" / "glossaries"
        seed_dir.mkdir(parents=True)
        (seed_dir / "spec_kitty_core.yaml").write_text(
            "version: 1\n"
            "terms:\n"
            "  - surface: alpha\n"
            "    definition: Valid term in invalid file shape\n"
            "    status: active\n",
            encoding="utf-8",
        )
        handler = _make_handler(tmp_path)

        gloss_module.GlossaryHandler.handle_glossary_health(handler)

        data = _read_response(handler)
        assert data["total_terms"] == 0
        assert data["validation_errors"] is not None
        assert data["validation_errors"][0]["term_index"] is None
        assert data["validation_errors"][0]["field"] == "version"

    def test_health_reports_yaml_parse_error(self, tmp_path):
        """Malformed YAML must not look like an empty healthy glossary."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        seed_dir = tmp_path / ".kittify" / "glossaries"
        seed_dir.mkdir(parents=True)
        (seed_dir / "spec_kitty_core.yaml").write_text(
            "terms:\n"
            "  - surface: alpha\n"
            "    definition: ok\n"
            "    confidence: [unterminated\n",
            encoding="utf-8",
        )
        handler = _make_handler(tmp_path)

        gloss_module.GlossaryHandler.handle_glossary_health(handler)

        data = _read_response(handler)
        assert data["total_terms"] == 0
        assert data["validation_errors"] is not None
        assert data["validation_errors"][0]["term_index"] is None
        assert "YAML parse error" in data["validation_errors"][0]["message"]


class TestGlossaryTerms:
    """Tests for handle_glossary_terms() → GET /api/glossary-terms."""

    def test_terms_returns_list_of_records(self, tmp_path):
        """Returns a list of GlossaryTermRecord-shaped dicts from the store."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        terms = [
            _make_term("lane", "kanban lane", "active", 1.0),
            _make_term("wp", "work package", "draft", 0.8),
        ]

        handler = _make_handler(tmp_path)

        with patch.object(gloss_module, "_collect_all_senses", return_value=terms):
            gloss_module.GlossaryHandler.handle_glossary_terms(handler)

        handler.send_response.assert_called_once_with(200)
        records = _read_response(handler)
        assert isinstance(records, list)
        assert len(records) == 2

        lane_rec = next(r for r in records if r["surface"] == "lane")
        assert lane_rec["definition"] == "kanban lane"
        assert lane_rec["status"] == "active"
        assert lane_rec["confidence"] == 1.0

        wp_rec = next(r for r in records if r["surface"] == "wp")
        assert wp_rec["status"] == "draft"
        assert abs(wp_rec["confidence"] - 0.8) < 1e-9

    def test_terms_returns_empty_list_on_store_error(self, tmp_path):
        """Returns [] without raising when _collect_all_senses raises."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        handler = _make_handler(tmp_path)

        with patch.object(gloss_module, "_collect_all_senses", side_effect=RuntimeError("oops")):
            gloss_module.GlossaryHandler.handle_glossary_terms(handler)

        handler.send_response.assert_called_once_with(200)
        records = _read_response(handler)
        assert records == []

    def test_terms_returns_empty_list_without_project_dir(self, tmp_path):
        """Returns [] without raising when project_dir is not configured."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        handler = _make_handler(tmp_path)
        handler.project_dir = None

        gloss_module.GlossaryHandler.handle_glossary_terms(handler)

        handler.send_response.assert_called_once_with(200)
        records = _read_response(handler)
        assert records == []

    def test_terms_record_shape(self, tmp_path):
        """Each record has exactly the expected keys."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        terms = [_make_term("mission", "workflow machine", "active", 0.95)]
        handler = _make_handler(tmp_path)

        with patch.object(gloss_module, "_collect_all_senses", return_value=terms):
            gloss_module.GlossaryHandler.handle_glossary_terms(handler)

        records = _read_response(handler)
        assert len(records) == 1
        rec = records[0]
        assert set(rec.keys()) == {"surface", "definition", "status", "confidence"}

    def test_terms_returns_empty_on_validation_error(self, tmp_path):
        """Returns [] and logs warning when SeedFileValidationError is raised."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        exc = SeedFileValidationError(
            Path("/fake/seed.yaml"),
            [SeedValidationError(
                file_path=Path("/fake/seed.yaml"),
                term_index=0,
                term_surface="bad",
                field="status",
                message="Invalid enum value",
            )],
        )
        handler = _make_handler(tmp_path)

        with patch.object(gloss_module, "_collect_all_senses", side_effect=exc):
            gloss_module.GlossaryHandler.handle_glossary_terms(handler)

        handler.send_response.assert_called_once_with(200)
        records = _read_response(handler)
        assert records == []


class TestCollectAllSenses:
    """Tests for _collect_all_senses propagation behavior."""

    def test_propagates_seed_file_validation_error(self, tmp_path):
        """SeedFileValidationError from load_seed_file propagates out of _collect_all_senses."""
        from specify_cli.dashboard.handlers.glossary import _collect_all_senses

        exc = SeedFileValidationError(
            Path("/fake/seed.yaml"),
            [SeedValidationError(
                file_path=Path("/fake/seed.yaml"),
                term_index=0,
                term_surface="x",
                field="surface",
                message="bad",
            )],
        )

        with (
            patch("specify_cli.dashboard.handlers.glossary.SeedFileValidationError", SeedFileValidationError),
            patch("glossary.scope.load_seed_file", side_effect=exc),
            pytest.raises(SeedFileValidationError),
        ):
            _collect_all_senses(tmp_path)

    def test_other_exceptions_are_swallowed(self, tmp_path):
        """Non-validation exceptions are caught, returning empty list."""
        from specify_cli.dashboard.handlers.glossary import _collect_all_senses

        with patch("glossary.scope.load_seed_file", side_effect=RuntimeError("oops")):
            result = _collect_all_senses(tmp_path)

        assert result == []

    def test_recovers_valid_terms_when_file_validation_fails(self, tmp_path):
        """Per-term recovery returns valid terms even when one entry is malformed."""
        from specify_cli.dashboard.handlers.glossary import _collect_all_senses

        # Write a seed file w/ two valid terms and one term with an
        # extra-forbidden field, simulating the upstream schema drift
        # that prompted this regression test.
        seed_dir = tmp_path / ".kittify" / "glossaries"
        seed_dir.mkdir(parents=True)
        (seed_dir / "spec_kitty_core.yaml").write_text(
            "terms:\n"
            "  - surface: alpha\n"
            "    definition: First letter\n"
            "    confidence: 0.9\n"
            "    status: active\n"
            "  - surface: beta\n"
            "    definition: Second letter\n"
            "    confidence: 0.9\n"
            "    status: active\n"
            "    bogus_extra_field: rejected\n"
            "  - surface: gamma\n"
            "    definition: Third letter\n"
            "    confidence: 0.9\n"
            "    status: active\n",
            encoding="utf-8",
        )

        result = _collect_all_senses(tmp_path)

        surfaces = sorted(t.surface.surface_text for t in result)
        assert surfaces == ["alpha", "gamma"], (
            f"recovery should keep alpha + gamma and skip beta; got {surfaces}"
        )

    def test_recovered_term_provenance_timestamp_is_aware_utc(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-011 (kernel-clock-single-door, WP13c): per-term recovery stamps
        ``Provenance.timestamp`` via the door's aware-UTC ``now_utc()``, not
        a naive local ``datetime.now()``.

        A naive ``datetime.now()`` here has no UTC offset once serialized by
        any downstream ``Provenance`` renderer (e.g. an ``.isoformat()``
        call) --
        this pins ``tzinfo``/the exact frozen instant so a reversion to the
        naive form is caught even though this handler's own JSON response
        does not itself render the timestamp.

        C-009 mutation verified: reverting the site to a naive
        ``datetime.now()`` makes ``provenance.timestamp.tzinfo`` ``None``,
        failing the assertion below.
        """
        import kernel.clock as clock_module
        from kernel.clock import UTC, FrozenClock
        from specify_cli.dashboard.handlers.glossary import _collect_all_senses

        frozen_instant = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
        monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=frozen_instant))

        seed_dir = tmp_path / ".kittify" / "glossaries"
        seed_dir.mkdir(parents=True)
        (seed_dir / "spec_kitty_core.yaml").write_text(
            "terms:\n"
            "  - surface: alpha\n"
            "    definition: First letter\n"
            "    confidence: 0.9\n"
            "    status: active\n"
            "  - surface: beta\n"
            "    definition: Second letter\n"
            "    confidence: 0.9\n"
            "    status: active\n"
            "    bogus_extra_field: rejected\n",
            encoding="utf-8",
        )

        result = _collect_all_senses(tmp_path)

        recovered = next(t for t in result if t.surface.surface_text == "alpha")
        assert recovered.provenance.timestamp.tzinfo is not None
        assert recovered.provenance.timestamp == frozen_instant


class TestGlossaryPage:
    """Tests for handle_glossary_page() → GET /glossary."""

    def test_glossary_page_returns_200_with_html(self, tmp_path):
        """Serves the glossary browser HTML with status 200 and correct content-type."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        handler = _make_handler(tmp_path)

        gloss_module.GlossaryHandler.handle_glossary_page(handler)

        handler.send_response.assert_called_once_with(200)
        # Verify content-type header was set to text/html
        ct_calls = [
            call for call in handler.send_header.call_args_list
            if call.args[0] == "Content-type"
        ]
        assert len(ct_calls) == 1
        assert "text/html" in ct_calls[0].args[1]

        handler.wfile.seek(0)
        body = handler.wfile.read()
        assert body  # non-empty
        assert b"<!DOCTYPE html>" in body or b"<html" in body
        text = body.decode("utf-8")
        assert 'id="validation-banner"' in text
        # The glossary JS (which performs the /api/glossary-health fetch) is
        # served same-origin from static/dashboard/glossary.js — the dashboard
        # CSP (style-src/script-src 'self') blocks an inline block (#71).
        assert '<script src="/static/dashboard/glossary.js"></script>' in text
        assert '<link rel="stylesheet" href="/static/dashboard/glossary.css">' in text
        assert '<label for="search" class="sr-only">Search glossary terms</label>' in text

    def test_glossary_page_uses_cached_bytes(self, tmp_path):
        """Module-level _GLOSSARY_HTML_BYTES is reused for each request."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        handler1 = _make_handler(tmp_path)
        handler2 = _make_handler(tmp_path)

        gloss_module.GlossaryHandler.handle_glossary_page(handler1)
        gloss_module.GlossaryHandler.handle_glossary_page(handler2)

        handler1.wfile.seek(0)
        handler2.wfile.seek(0)
        assert handler1.wfile.read() == handler2.wfile.read()

    def test_glossary_page_uses_dashboard_shell_and_light_theme(self, tmp_path):
        """Glossary page keeps dashboard navigation and does not leak dark mode."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        handler = _make_handler(tmp_path)

        gloss_module.GlossaryHandler.handle_glossary_page(handler)

        handler.wfile.seek(0)
        body = handler.wfile.read().decode("utf-8")
        assert 'class="sidebar"' in body
        assert 'href="/" title="Dashboard Overview"' in body
        assert 'class="sidebar-item active" href="/glossary"' in body
        assert 'id="validation-banner"' in body
        # Styles/behaviour are same-origin assets now (#71) — see
        # test_glossary_page_returns_200_with_html above.
        assert '<script src="/static/dashboard/glossary.js"></script>' in body
        assert '<link rel="stylesheet" href="/static/dashboard/glossary.css">' in body
        assert '<label for="search" class="sr-only">Search glossary terms</label>' in body
        assert "prefers-color-scheme: dark" not in body


class TestGlossaryHelpers:
    """Exercise helper paths that feed the glossary dashboard endpoints."""

    def test_count_orphaned_terms_counts_uncovered_glossary_nodes(self, tmp_path):
        """Glossary nodes without an incoming vocabulary edge count as orphans."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        doctrine_dir = tmp_path / ".kittify" / "doctrine"
        doctrine_dir.mkdir(parents=True)
        (doctrine_dir / "graph.yaml").write_text(
            """
nodes:
  - urn: glossary:alpha
  - urn: glossary:beta
  - urn: mission:mission-1
edges:
  - relation: vocabulary
    target: glossary:alpha
  - relation: ownership
    target: glossary:beta
""".strip(),
            encoding="utf-8",
        )

        assert gloss_module._count_orphaned_terms(tmp_path) == 1

    def test_count_orphaned_terms_returns_zero_for_non_mapping_graph(self, tmp_path):
        """Non-dict graph payloads are treated as unavailable."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        doctrine_dir = tmp_path / ".kittify" / "doctrine"
        doctrine_dir.mkdir(parents=True)
        (doctrine_dir / "graph.yaml").write_text("- not-a-dict\n", encoding="utf-8")

        assert gloss_module._count_orphaned_terms(tmp_path) == 0

    def test_count_orphaned_terms_returns_zero_when_no_glossary_nodes_exist(self, tmp_path):
        """A DRG without glossary nodes reports no orphans."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        doctrine_dir = tmp_path / ".kittify" / "doctrine"
        doctrine_dir.mkdir(parents=True)
        (doctrine_dir / "graph.yaml").write_text(
            """
nodes:
  - urn: mission:mission-1
edges:
  - relation: ownership
    target: mission:mission-1
""".strip(),
            encoding="utf-8",
        )

        assert gloss_module._count_orphaned_terms(tmp_path) == 0

    def test_count_orphaned_terms_returns_zero_on_yaml_error(self, tmp_path):
        """Unreadable YAML does not break the dashboard helper."""
        from specify_cli.dashboard.handlers import glossary as gloss_module

        doctrine_dir = tmp_path / ".kittify" / "doctrine"
        doctrine_dir.mkdir(parents=True)
        (doctrine_dir / "graph.yaml").write_text("nodes: [\n", encoding="utf-8")

        assert gloss_module._count_orphaned_terms(tmp_path) == 0

    def test_collect_all_senses_skips_scopes_that_fail(self, monkeypatch, tmp_path):
        """A single broken seed file does not prevent collecting other scopes."""
        from glossary.scope import GlossaryScope
        from specify_cli.dashboard.handlers import glossary as gloss_module

        first_scope = list(GlossaryScope)[0]
        expected = _make_term("alpha", "definition", "active", 0.9)

        def fake_load_seed_file(scope, repo_root):
            assert repo_root == tmp_path
            if scope is first_scope:
                return [expected]
            raise RuntimeError(f"missing seed for {scope.value}")

        monkeypatch.setattr("glossary.scope.load_seed_file", fake_load_seed_file)

        assert gloss_module._collect_all_senses(tmp_path) == [expected]

    def test_collect_all_senses_returns_empty_list_when_scope_module_fails(
        self, monkeypatch, tmp_path
    ):
        """Import failures degrade to an empty response payload."""
        import builtins

        from specify_cli.dashboard.handlers import glossary as gloss_module

        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "glossary.scope":
                raise ImportError("boom")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr("builtins.__import__", fake_import)

        assert gloss_module._collect_all_senses(tmp_path) == []

    def test_collect_all_senses_raises_when_root_level_recovery_refused(self, tmp_path):
        """The compatibility helper still raises when no safe recovery exists."""
        from glossary.exceptions import SeedFileValidationError
        from specify_cli.dashboard.handlers import glossary as gloss_module

        seed_dir = tmp_path / ".kittify" / "glossaries"
        seed_dir.mkdir(parents=True)
        (seed_dir / "spec_kitty_core.yaml").write_text(
            "version: 1\n"
            "terms:\n"
            "  - surface: alpha\n"
            "    definition: Valid term in invalid file shape\n",
            encoding="utf-8",
        )

        with pytest.raises(SeedFileValidationError):
            gloss_module._collect_all_senses(tmp_path)


class TestRouterRegistration:
    """Verify the routes are wired in DashboardRouter."""

    def test_glossary_handler_in_mro(self):
        """GlossaryHandler must appear in DashboardRouter's MRO before StaticHandler."""
        from specify_cli.dashboard.handlers.router import DashboardRouter
        from specify_cli.dashboard.handlers.glossary import GlossaryHandler
        from specify_cli.dashboard.handlers.static import StaticHandler

        mro = DashboardRouter.__mro__
        glossary_idx = mro.index(GlossaryHandler)
        static_idx = mro.index(StaticHandler)
        assert glossary_idx < static_idx, "GlossaryHandler must precede StaticHandler in MRO"

    def test_router_has_glossary_methods(self):
        """DashboardRouter exposes all three glossary handler methods."""
        from specify_cli.dashboard.handlers.router import DashboardRouter

        assert hasattr(DashboardRouter, "handle_glossary_health")
        assert hasattr(DashboardRouter, "handle_glossary_terms")
        assert hasattr(DashboardRouter, "handle_glossary_page")
