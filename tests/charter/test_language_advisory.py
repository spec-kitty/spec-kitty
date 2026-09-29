"""WP02 (#5284): the consumer-facing charter-extension advisory is one neutral line."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.neutrality import run_neutrality_lint

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_HOWTO_TITLE = "Extend your charter for an unsupported language"


def _advisory() -> str:
    # Function-local import: the module does not exist on the planning base,
    # so the test module must still collect there (red for an assertion, not ImportError).
    from charter.activation.language_advisory import CHARTER_EXTENSION_ADVISORY

    return CHARTER_EXTENSION_ADVISORY


def test_advisory_is_a_single_short_line() -> None:
    """RED (pins the fix): one line, at most 200 characters."""
    text = _advisory()
    assert "\n" not in text.strip()
    assert 0 < len(text) <= 200


def test_advisory_points_at_local_charter_and_howto() -> None:
    """RED (pins the fix): names the local charter and the how-to title."""
    text = _advisory()
    assert "local charter" in text
    assert _HOWTO_TITLE in text


@pytest.mark.parametrize("banned", ["python", "pytest", ".py", "src/"])
def test_advisory_has_no_tech_specific_terms(banned: str) -> None:
    """RED (pins the fix): substring second-check for tech neutrality."""
    assert banned not in _advisory().lower()


def test_advisory_passes_neutrality_lint(tmp_path: Path) -> None:
    """RED (pins the fix): the neutrality lint's banned-term matcher finds nothing."""
    root = tmp_path / "src" / "charter" / "offering" / "advisory"
    root.mkdir(parents=True)
    (root / "advisory.md").write_text(_advisory() + "\n", encoding="utf-8")
    allowlist = tmp_path / "allow.yaml"
    allowlist.write_text("schema_version: '1'\npaths: []\n", encoding="utf-8")

    result = run_neutrality_lint(
        repo_root=tmp_path,
        scan_roots=[tmp_path / "src" / "charter" / "offering"],
        allowlist_path=allowlist,
    )

    assert result.scanned_file_count == 1
    assert result.passed, result.hits


def test_neutrality_lint_flags_a_banned_term(tmp_path: Path) -> None:
    """GREEN control (pins unchanged behaviour): the same lint reports a hit on tech-specific text (non-vacuity floor)."""
    root = tmp_path / "src" / "charter" / "offering" / "advisory"
    root.mkdir(parents=True)
    (root / "advisory.md").write_text("Run pytest to check your project.\n", encoding="utf-8")
    allowlist = tmp_path / "allow.yaml"
    allowlist.write_text("schema_version: '1'\npaths: []\n", encoding="utf-8")

    result = run_neutrality_lint(
        repo_root=tmp_path,
        scan_roots=[tmp_path / "src" / "charter" / "offering"],
        allowlist_path=allowlist,
    )

    assert result.scanned_file_count == 1
    assert not result.passed
    assert result.hits
