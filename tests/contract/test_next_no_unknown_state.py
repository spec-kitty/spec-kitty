"""Contract test: ``unknown`` mission state and the legacy
``[QUERY - no result provided]`` placeholder must never surface in shipped
templates or runtime decision JSON for a valid run (FR-020, WP04/T019).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast


_PLACEHOLDER = "[QUERY - no result provided]"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES_ROOT = _REPO_ROOT / "src" / "specify_cli" / "missions"
_RUNTIME_SOURCE_ROOT = _REPO_ROOT / "src" / "runtime" / "next"
# Planning-base count of ``.py`` files under ``_RUNTIME_SOURCE_ROOT`` (NFR-002
# floor). A deliberate shrink of the runtime tree is a one-line edit here.
# 31 -> 27: the dead-code sweep (6bb119d0d0) deleted four runtime modules (#5506).
_RUNTIME_SOURCE_FILE_FLOOR = 27


def _placeholder_offenders(root: Path) -> tuple[int, list[tuple[Path, int]]]:
    """Return ``(files_inspected, [(path, line)])`` for placeholder hits under ``root``.

    Fails loudly on a missing or empty target: a scan that inspects nothing
    must never pass (SC-005).
    """
    assert root.is_dir(), f"placeholder scan: missing target {root} (0 files inspected)"
    files = sorted(root.rglob("*.py"))
    assert files, f"placeholder scan: empty target {root} (0 files inspected)"
    offenders: list[tuple[Path, int]] = []
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        offenders.extend((path, idx) for idx, line in enumerate(lines, start=1) if _PLACEHOLDER in line)
    return len(files), offenders


def test_runtime_placeholder_scan_inspects_live_source() -> None:
    """The placeholder scan targets the live runtime tree, not a vanished path."""
    files_inspected, _ = _placeholder_offenders(_RUNTIME_SOURCE_ROOT)
    assert files_inspected >= _RUNTIME_SOURCE_FILE_FLOOR, (
        f"placeholder scan inspected {files_inspected} files under {_RUNTIME_SOURCE_ROOT}; expected >= {_RUNTIME_SOURCE_FILE_FLOOR}"
    )


def test_runtime_placeholder_scan_flags_planted_placeholder(tmp_path: Path) -> None:
    """A planted placeholder is named ``(path, line)`` by the helper the ban calls."""
    planted = tmp_path / "emitter.py"
    planted.write_text(f"x = 1\nmsg = {_PLACEHOLDER!r}\n", encoding="utf-8")
    (tmp_path / "clean.py").write_text("msg = 'query result'\n", encoding="utf-8")
    files_inspected, offenders = _placeholder_offenders(tmp_path)
    assert files_inspected == 2
    assert offenders == [(planted, 2)]


class TestNoLegacyQueryPlaceholderInTemplates:
    """The literal placeholder must not appear in any shipped command template."""

    def test_placeholder_is_absent_from_command_templates(self) -> None:
        offenders: list[Path] = []
        for path in _TEMPLATES_ROOT.rglob("*.md"):
            if "command-templates" not in path.parts and "templates" not in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if _PLACEHOLDER in text:
                offenders.append(path)
        assert not offenders, f"Found legacy placeholder '{_PLACEHOLDER}' in shipped templates: {offenders}"

    def test_placeholder_is_absent_from_runtime_source(self) -> None:
        files_inspected, offenders = _placeholder_offenders(_RUNTIME_SOURCE_ROOT)
        assert files_inspected >= _RUNTIME_SOURCE_FILE_FLOOR, (
            f"placeholder scan inspected {files_inspected} files under {_RUNTIME_SOURCE_ROOT}; expected >= {_RUNTIME_SOURCE_FILE_FLOOR}"
        )
        assert not offenders, f"Runtime source must not emit the legacy placeholder. Offenders: {offenders}"


class TestQueryModeDoesNotReturnUnknownForValidMission:
    """For a populated mission run, mission_state must not be 'unknown'."""

    def test_query_decision_for_valid_run_has_real_state(self, tmp_path: Path) -> None:
        """When the mission has a runtime snapshot, mission_state is real."""
        from runtime.next.decision import Decision, DecisionKind

        decision = Decision(
            kind=DecisionKind.query,
            agent="claude",
            mission_slug="fixture-mission",
            mission="software-dev",
            mission_state="implementing",
            timestamp="2026-04-26T00:00:00+00:00",
            is_query=True,
            mission_type="software-dev",
        )

        # The contract: a mission with a real state must not produce
        # mission_state == "unknown" in the JSON envelope.
        payload = decision.to_dict()
        assert payload["mission_state"] != "unknown"
        assert payload["mission_state"] == "implementing"

        # The decision body must not contain the placeholder.
        rendered = repr(payload)
        assert _PLACEHOLDER not in rendered

    def test_query_decision_for_missing_feature_dir_is_structured(self, tmp_path: Path) -> None:
        """A missing feature dir raises MissionNotFoundError (FR-004 / WP03).

        After WP03, ``query_current_state`` raises ``MissionNotFoundError``
        (fail-closed) instead of returning a silent ``Decision`` with
        ``mission_state="unknown"``. The exception must carry the attempted
        handle so callers can emit structured JSON errors.
        """
        from runtime.next.runtime_bridge import (
            MissionNotFoundError,
            query_current_state,
        )

        repo_root = tmp_path
        # No kitty-specs/<slug> dir created, so feature_dir is missing.
        with pytest.raises(MissionNotFoundError) as exc_info:
            query_current_state(
                agent="claude",
                mission_slug="nonexistent-mission",
                repo_root=repo_root,
            )

        err = exc_info.value
        assert err.handle == "nonexistent-mission"
        assert err.error_code == "MISSION_NOT_FOUND"
        assert _PLACEHOLDER not in str(err)


class TestRuntimeBridgeBlockedReasonIsConcrete:
    """A blocked decision must carry a concrete reason, not boilerplate."""

    def test_runtime_engine_error_reason_is_specific(self) -> None:
        """Sanity check: the runtime bridge surfaces concrete error
        reasons rather than stringified placeholders.

        We grep for the legacy placeholder in the function body — it is a
        regression guard for future edits.
        """
        runtime_bridge_path = _REPO_ROOT / "src" / "runtime" / "next" / "runtime_bridge.py"
        text = runtime_bridge_path.read_text(encoding="utf-8")
        # Acceptable: "no result provided" appearing inside human-readable
        # query mode banner. We forbid only the bracket form that historically
        # leaked into prompt files.
        assert _PLACEHOLDER not in text, f"runtime_bridge.py must not emit the legacy placeholder {_PLACEHOLDER}"
