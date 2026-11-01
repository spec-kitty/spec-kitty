"""Regression tests for stale back-compat symlink / architecture/ prose on the ADR era landing pages.

The era landing pages are ``docs/adr/<era>/index.md``. The ``README.md`` redirect stubs
these tests first guarded were deleted in #6928 (one index file per folder); the claim
they pin still applies to the surviving landing pages.

SC-006 backstop (WP07, doc-quality-hardening-2245-01KW9AKV):
The Common Docs structural move (PR #2225) removed the `architecture/` tree and dropped
the 71 back-compat symlinks that some README files claimed would exist.  These tests pin
the fix so future edits cannot silently re-introduce the false present-tense symlink claim.

Note: `tests/docs/test_adr_readme_prose.py` is outside the WP07 `owned_files` list
(`docs/adr/{1,2,3}.x/README.md`) but is a sanctioned small addition required by the WP's
DoD (Review Guidance item 8).  The no-overlap rule with other lanes is the real guard.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]

_ADR_README_2X = REPO_ROOT / "docs" / "adr" / "2.x" / "index.md"
_OWNED_READMES = [
    REPO_ROOT / "docs" / "adr" / "1.x" / "index.md",
    REPO_ROOT / "docs" / "adr" / "2.x" / "index.md",
    REPO_ROOT / "docs" / "adr" / "3.x" / "index.md",
]

# Matches the dropped-symlink pattern: "symlink" (case-insensitive) within 5 lines of
# "architecture/2.x/adr" or "architecture/adrs" in a present-tense context.
_SYMLINK_NEAR_ARCH_RE = re.compile(
    r"(?:"
    r"symlink[^\n]*architecture/[^\n]*adr"
    r"|"
    r"architecture/[^\n]*adr[^\n]*symlink"
    r")",
    re.IGNORECASE,
)

# Matches any present-tense claim that symlinks exist at an architecture/ path.
# We look for "back-compat symlinks at" or "symlinks at the old" near "architecture/".
_BACCOMPAT_SYMLINK_CLAIM_RE = re.compile(
    r"back.compat symlinks? at[^\n]*architecture/"
    r"|"
    r"symlinks? at the old[^\n]*architecture/",
    re.IGNORECASE,
)


def test_adr_2x_readme_no_false_symlink_claim() -> None:
    """docs/adr/2.x/index.md must not contain a present-tense dropped-symlink claim.

    The back-compat symlinks at the old `architecture/2.x/adr/<filename>` paths
    were NOT retained when PR #2225 moved the files — the `architecture/` tree no
    longer exists.  Any prose claiming they resolve is factually false.
    """
    text = _ADR_README_2X.read_text(encoding="utf-8")
    match = _BACCOMPAT_SYMLINK_CLAIM_RE.search(text)
    assert match is None, (
        f"docs/adr/2.x/index.md still contains a present-tense dropped-symlink claim "
        f"(SC-006 regression).  Offending text near char {match.start()}: "
        f"{text[max(0, match.start() - 40):match.end() + 40]!r}"
    )


def test_owned_readmes_no_present_tense_architecture_symlink_claims() -> None:
    """None of the three ADR era landing pages may claim that architecture/ symlinks exist.

    Counts present-tense architecture/... symlink claims across all three era landing pages;
    the expected count is 0.  The `architecture/` tree was removed in PR #2225 and the
    back-compat symlinks were dropped — any such claim is factually incorrect.
    """
    offences: list[str] = []
    for readme in _OWNED_READMES:
        text = readme.read_text(encoding="utf-8")
        for match in _BACCOMPAT_SYMLINK_CLAIM_RE.finditer(text):
            offences.append(
                f"{readme.relative_to(REPO_ROOT)}: {text[max(0, match.start() - 20):match.end() + 40]!r}"
            )

    assert len(offences) == 0, (
        f"Found {len(offences)} present-tense architecture/ symlink claim(s) in owned "
        f"ADR READMEs (SC-006 regression):\n"
        + "\n".join(f"  - {o}" for o in offences)
    )
