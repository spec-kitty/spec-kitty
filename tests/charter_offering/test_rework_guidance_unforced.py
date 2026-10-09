"""Guard: shipped review-loop guidance never teaches a forced ordinary rework.

The ordinary reject / rework / re-review loop needs no ``--force``. Forced
moves are legitimate only for the arbiter override, the self-review fallback,
the done override and a genuine takeover.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.charter_offering.conftest import OFFERING_SOURCE_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = OFFERING_SOURCE_ROOT.parent.parent.parent
_IMPL_REVIEW = OFFERING_SOURCE_ROOT / "skills" / "spec-kitty-implement-review" / "SKILL.md"
_GUIDANCE_FILES = (
    _IMPL_REVIEW,
    OFFERING_SOURCE_ROOT / "skills" / "spec-kitty-runtime-review" / "SKILL.md",
    OFFERING_SOURCE_ROOT / "skills" / "spec-kitty-runtime-review" / "references" / "review-checklist.md",
    _REPO_ROOT / "docs" / "guides" / "how-to" / "missions" / "review-work-package.md",
)

_ALLOWED_MARKERS = ("--self-review-fallback", "--done-override-reason")
_ARBITER_LANES = ("--to approved", "--to done")
_SPACED_FORCE = re.compile(r"(?<![\w-])--force(?![\w-])")


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Return (first physical line number, text) with backslash continuations joined."""
    joined: list[tuple[int, str]] = []
    buffer = ""
    start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        if not buffer:
            start = number
        stripped = raw.rstrip()
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
            continue
        joined.append((start, buffer + raw))
        buffer = ""
    if buffer:
        joined.append((start, buffer))
    return joined


def classify_forced_move(line: str) -> str | None:
    """Return 'forbidden' / 'allowed' for a forced move-task line, else None."""
    if "move-task" not in line or not _SPACED_FORCE.search(line):
        return None
    if any(marker in line for marker in _ALLOWED_MARKERS):
        return "allowed"
    if "--to blocked" in line:
        return "allowed"
    if any(lane in line for lane in _ARBITER_LANES) and "arbiter" in line.lower():
        return "allowed"
    return "forbidden"


def _forbidden_hits(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [f"{path.name}:{number}: {line.strip()}" for number, line in _logical_lines(text) if classify_forced_move(line) == "forbidden"]


@pytest.mark.parametrize("path", _GUIDANCE_FILES, ids=lambda p: p.name)
def test_guidance_file_exists(path: Path) -> None:
    assert path.is_file(), f"guidance file missing: {path}"


def test_ordinary_loop_guidance_never_forces_a_move() -> None:
    hits = [hit for path in _GUIDANCE_FILES for hit in _forbidden_hits(path)]
    assert not hits, "Ordinary review-loop guidance must not use --force:\n" + "\n".join(hits)


def test_implement_review_troubleshooting_does_not_recommend_force() -> None:
    text = _IMPL_REVIEW.read_text(encoding="utf-8")
    assert "may need `--force`" not in text


def test_classifier_flags_synthetic_forbidden_lines() -> None:
    ordinary_reject = "spec-kitty agent tasks move-task WP01 --to planned --force --review-feedback-file f.md"
    inline_code = "1. The reviewer runs `move-task WP## --to planned --force --review-feedback-file <path>`"
    resubmit = "spec-kitty agent tasks move-task WP01 --to for_review --force"
    assert classify_forced_move(ordinary_reject) == "forbidden"
    assert classify_forced_move(inline_code) == "forbidden"
    assert classify_forced_move(resubmit) == "forbidden"
    continued = _logical_lines("spec-kitty agent tasks move-task WP01 --to planned --force \\\n  --review-feedback-file f.md\n")
    assert classify_forced_move(continued[0][1]) == "forbidden"


def test_classifier_passes_synthetic_legitimate_lines() -> None:
    arbiter = 'spec-kitty agent tasks move-task WP01 --to approved --force --note "Arbiter decision: ok"'
    fallback = "spec-kitty agent tasks move-task WP01 --to approved --force --self-review-fallback"
    override = "spec-kitty agent tasks move-task WP01 --to done --force --done-override-reason x"
    escalate = "spec-kitty agent tasks move-task WP01 --to blocked --force --note x"
    unforced = "spec-kitty agent tasks move-task WP01 --to planned --review-feedback-file f.md"
    for line in (arbiter, fallback, override, escalate):
        assert classify_forced_move(line) == "allowed"
    assert classify_forced_move(unforced) is None
