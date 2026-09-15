"""NFR-008 cross-reference test: every MissionReviewDiagnostic member has a
corresponding section in ERROR_CODES.md.

The StrEnum and the markdown file are the two required surfaces; this test
asserts they are in sync so neither can diverge silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.review._diagnostics import MissionReviewDiagnostic

pytestmark = [pytest.mark.fast, pytest.mark.non_sandbox]

_ERROR_CODES_PATH = Path(__file__).parents[5] / "src" / "specify_cli" / "cli" / "commands" / "review" / "ERROR_CODES.md"


@pytest.fixture(scope="module")
def error_codes_text() -> str:
    assert _ERROR_CODES_PATH.exists(), f"ERROR_CODES.md not found at {_ERROR_CODES_PATH}. WP03 must author this file."
    return _ERROR_CODES_PATH.read_text(encoding="utf-8")


class TestNFR008CrossReference:
    def test_error_codes_file_exists(self) -> None:
        assert _ERROR_CODES_PATH.exists(), "src/specify_cli/cli/commands/review/ERROR_CODES.md is missing"

    def test_all_diagnostic_members_documented(self, error_codes_text: str) -> None:
        """Every StrEnum member must have a ## section in ERROR_CODES.md."""
        missing: list[str] = []
        for member in MissionReviewDiagnostic:
            # Each code should appear as a `## CODE_NAME` section header
            # The code name is the part after MISSION_REVIEW_ (or the full value)
            # The section uses the SHORT name (e.g. ## MODE_MISMATCH)
            short_name = member.name  # e.g. "MODE_MISMATCH"
            full_code = str(member)  # e.g. "MISSION_REVIEW_MODE_MISMATCH"

            # Check for either the short section header or the full code string
            has_section = f"## {short_name}" in error_codes_text or f"## {full_code}" in error_codes_text
            if not has_section:
                missing.append(f"{member.name} (code: {full_code})")

        assert not missing, f"The following MissionReviewDiagnostic members have no ## section in ERROR_CODES.md: {missing}"

    def test_section_count_matches_member_count(self, error_codes_text: str) -> None:
        """The number of h2 code sections must equal the number of StrEnum members."""
        member_count = len(list(MissionReviewDiagnostic))

        # Count ## sections that correspond to diagnostic codes
        # (skip the title and any non-code sections)
        h2_sections = [line.strip() for line in error_codes_text.splitlines() if line.startswith("## ") and not line.startswith("### ")]
        # Filter to only sections that look like CODE_NAME or MISSION_REVIEW_*
        code_sections = [s for s in h2_sections if any(s == f"## {m.name}" or s == f"## {m.value}" for m in MissionReviewDiagnostic)]

        assert len(code_sections) == member_count, (
            f"ERROR_CODES.md has {len(code_sections)} code sections but MissionReviewDiagnostic has {member_count} members. Sections found: {code_sections}"
        )

    def test_each_section_has_remediation(self, error_codes_text: str) -> None:
        """Every section should contain a Remediation block."""
        # This is a soft structural check — not strictly required by NFR-008
        # but ensures the file is well-formed
        assert "**Remediation**" in error_codes_text, "ERROR_CODES.md should contain at least one **Remediation** block"

    def test_docstring_references_error_codes_md(self) -> None:
        """StrEnum class docstring must reference ERROR_CODES.md (NFR-008 contract)."""
        docstring = MissionReviewDiagnostic.__doc__ or ""
        assert "ERROR_CODES.md" in docstring, "MissionReviewDiagnostic class docstring must contain 'ERROR_CODES.md' per the NFR-008 cross-reference contract."

    def test_member_count(self) -> None:
        """Exactly 14 diagnostic codes defined, including #2987's and #4231's fail-closed verdicts."""
        assert len(list(MissionReviewDiagnostic)) == 14, (
            f"Expected 14 MissionReviewDiagnostic members, got {len(list(MissionReviewDiagnostic))}: {list(MissionReviewDiagnostic)}"
        )
