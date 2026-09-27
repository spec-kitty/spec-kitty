"""Tests for ``scripts/docs/check_slash_command_freshness.py``.

Covers the two rule IDs (``SLASH-MISSING`` / ``SLASH-EXTRA``), the heading
extractor, and the CLI entry-point exit codes (0/1/2). The negative tests
mutate fixture docs in both drift directions so the gate is non-vacuous
(NFR-001): it fails when a registry command is undocumented AND when a
documented command is not in the registry.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.docs import check_slash_command_freshness as freshness

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.fixture(autouse=True)
def _pin_no_upgrade_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the upgrade-check opt-out set for every test (was a module-level ``setdefault``)."""
    monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", os.environ.get("SPEC_KITTY_NO_UPGRADE_CHECK", "1"))


# ---------------------------------------------------------------------------
# Heading extractor
# ---------------------------------------------------------------------------


class TestExtractDocumentedCommands:
    def test_extracts_slash_dot_headings(self) -> None:
        text = "## /spec-kitty.specify\n\nprose\n\n## /spec-kitty.tasks-outline\n"
        assert freshness.extract_documented_commands(text) == {
            "specify",
            "tasks-outline",
        }

    def test_ignores_prose_headings(self) -> None:
        text = "## Getting Started\n\n## /spec-kitty.plan\n\n## Practical Usage\n"
        assert freshness.extract_documented_commands(text) == {"plan"}

    def test_does_not_match_space_form(self) -> None:
        # The sibling CLI-reference form `## spec-kitty foo` must NOT match.
        text = "## spec-kitty foo\n\n## spec-kitty bar baz\n"
        assert freshness.extract_documented_commands(text) == set()

    def test_extracts_nothing_from_empty(self) -> None:
        assert freshness.extract_documented_commands("") == set()

    def test_requires_top_level_heading(self) -> None:
        # A deeper heading (###) is not a documented section.
        text = "### /spec-kitty.specify\n"
        assert freshness.extract_documented_commands(text) == set()


# ---------------------------------------------------------------------------
# Rule engine (bidirectional set-diff)
# ---------------------------------------------------------------------------


class TestEvaluate:
    _REGISTRY = frozenset({"specify", "plan", "tasks"})

    def test_no_findings_when_mirrored(self) -> None:
        findings = freshness.evaluate(
            documented={"specify", "plan", "tasks"},
            registry=self._REGISTRY,
        )
        assert findings == []

    def test_missing_direction(self) -> None:
        findings = freshness.evaluate(
            documented={"specify", "plan"},
            registry=self._REGISTRY,
        )
        assert [(f.rule_id, f.command) for f in findings] == [("SLASH-MISSING", "tasks")]

    def test_extra_direction(self) -> None:
        findings = freshness.evaluate(
            documented={"specify", "plan", "tasks", "retired-cmd"},
            registry=self._REGISTRY,
        )
        assert [(f.rule_id, f.command) for f in findings] == [("SLASH-EXTRA", "retired-cmd")]

    def test_both_directions_at_once(self) -> None:
        findings = freshness.evaluate(
            documented={"specify", "retired-cmd"},
            registry=self._REGISTRY,
        )
        by_rule = {(f.rule_id, f.command) for f in findings}
        assert ("SLASH-MISSING", "plan") in by_rule
        assert ("SLASH-MISSING", "tasks") in by_rule
        assert ("SLASH-EXTRA", "retired-cmd") in by_rule


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


_REAL_REFERENCE = Path(__file__).resolve().parents[2] / "docs" / "api" / "slash-commands.md"


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


class TestCli:
    def test_missing_reference_returns_2(self, tmp_path: Path) -> None:
        rc = freshness.main(["--reference", str(tmp_path / "absent.md")])
        assert rc == 2

    def test_missing_command_returns_1(self, tmp_path: Path) -> None:
        # Drop one real command from the backfilled doc -> SLASH-MISSING.
        from specify_cli.shims.registry import CONSUMER_SKILLS

        victim = next(iter(sorted(CONSUMER_SKILLS)))
        documented = sorted(CONSUMER_SKILLS - {victim})
        body = "\n".join(f"## /spec-kitty.{name}\n" for name in documented)
        ref = _write(tmp_path / "ref.md", body)
        rc = freshness.main(["--reference", str(ref)])
        assert rc == 1

    def test_extra_command_returns_1(self, tmp_path: Path) -> None:
        # Document every real command plus a retired one -> SLASH-EXTRA.
        from specify_cli.shims.registry import CONSUMER_SKILLS

        documented = sorted(CONSUMER_SKILLS | {"retired-cmd"})
        body = "\n".join(f"## /spec-kitty.{name}\n" for name in documented)
        ref = _write(tmp_path / "ref.md", body)
        rc = freshness.main(["--reference", str(ref)])
        assert rc == 1

    def test_extra_command_ci_writes_stdout(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.shims.registry import CONSUMER_SKILLS

        documented = sorted(CONSUMER_SKILLS | {"retired-cmd"})
        body = "\n".join(f"## /spec-kitty.{name}\n" for name in documented)
        ref = _write(tmp_path / "ref.md", body)
        rc = freshness.main(["--reference", str(ref), "--ci"])
        assert rc == 1
        out = capsys.readouterr().out
        assert "SLASH-EXTRA retired-cmd" in out

    def test_real_backfilled_doc_returns_0(self) -> None:
        # The committed, backfilled reference must mirror the registry exactly.
        rc = freshness.main(["--reference", str(_REAL_REFERENCE)])
        assert rc == 0
