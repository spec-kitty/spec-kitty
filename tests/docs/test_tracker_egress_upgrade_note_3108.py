"""FR-013's anchor check: the tracker-egress-refusal upgrade note must keep saying what it says.

Mission `tracker-egress-refusal-3108-01KYWF1R`, WP08. Every existing `beads`/`fp` tracker binding
stops working on upgrade unless its project records a decision at one of the two consent channels
(mission `#3108`). SC-018 requires the upgrade note carrying every remediation path to be "pinned
by an anchor check that fails in CI if the section is removed or renamed" -- the `#3030` FR-018
pattern already used by :mod:`tests.docs.test_env_var_scope_warning`.

That sibling test's own docstring states the design constraint this file follows too: assertions
run against the *substance* (the load-bearing sentences), never only a heading, because a heading
anchor passes happily against an emptied section. :func:`check_note_substance` takes the note's
*text*, never a path, precisely so this module can point it at the real file (must pass) and at
two synthetic mutants held only in this file's own strings -- a renamed heading and an emptied
section (both must fail) -- without ever touching the shipped note during a verification run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_NOTE_PATH: Final[Path] = _REPO_ROOT / "docs" / "migrations" / "tracker-egress-refusal.md"
_INDEX_PATH: Final[Path] = _REPO_ROOT / "docs" / "migrations" / "index.md"

#: Every stable heading FR-013 pins. A rename of any one of these must be caught -- this is the
#: "removed or renamed" half of the anchor check; :data:`_SUBSTANCE_PHRASES` below is the other
#: half, catching a heading kept in place over an emptied body.
_HEADINGS: Final[tuple[str, ...]] = (
    "## What Changed and Why It Breaks You",
    "## The Two Consent Channels, and What Absence Means at Each",
    "## How to Tell Which Channel Is Refusing You",
    "## The Three Channel-1 States and Their Remedies",
    "## The Identity-less Checkout",
    "## What `permitted` Does and Does Not Do",
    "## The `map list` Split",
    "## A Typo Refuses",
    "## Which Commands Are Gated",
    "## A Recorded Decision Outlives Its Binding",
)

#: (label, phrase) -- one pair per load-bearing claim named in the WP08 prompt's T045 assertion
#: list. Checked against *normalized* text (runs of whitespace collapsed to one space) so a
#: markdown source reflow -- the paragraph rewrapping at a different column -- cannot make an
#: otherwise-present sentence invisible to a plain substring check. This is deliberately not the
#: same axis as the heading check above: a section can keep its exact heading and still have this
#: axis fail if its body is hollowed out.
_SUBSTANCE_PHRASES: Final[tuple[tuple[str, str], ...]] = (
    (
        "Channel-2 key path (`tracker.egress`) and both legal values",
        "tracker: egress: permitted # or: refused",
    ),
    (
        "absence of both channels denies",
        "Absence of **both** channels denies.",
    ),
    (
        "`spec-kitty init` as the not-consentable remedy",
        "The remedy is **`spec-kitty init`**, run in this checkout, which mints that identity.",
    ),
    (
        "hand-authoring `sync.enabled: true` still denies without identity",
        "you hand-author `sync.enabled: true` and the binding **still** denies",
    ),
    (
        "the Channel-2 grant is the only remedy needing no project identity",
        "Record `tracker.egress: permitted` is the only remedy that works in every "
        "one of these three states without a project identity.",
    ),
    (
        "C-016: `permitted` grants nothing at the hosted destination",
        "`permitted` **grants nothing**.",
    ),
    (
        "C-016: hosted-sync consent remains a hard prerequisite at the hosted destination",
        "Hosted-sync consent (Channel 1) remains a hard prerequisite there",
    ),
    (
        "the `map list` split -- the unqualified form",
        "`spec-kitty tracker map list` (no `--provider`)",
    ),
    (
        "the `map list` split -- the provider-qualified form",
        "`spec-kitty tracker map list --provider jira`",
    ),
    (
        "the `map list` split -- the reason (destination, not subcommand name)",
        "the gate follows the destination, not the subcommand name.",
    ),
    (
        "fault-refuses -- at least one named near-miss value",
        "not `Refused`, not `REFUSED`, not `refuse`, not `deny`",
    ),
    (
        "fault-refuses -- refuses at both destinations",
        "is a fault, and a fault refuses tracker egress at both destinations.",
    ),
    # Review LOW-6: T045's enumerated substance list did not name these four
    # sections, but leaving them heading-only pinned means the breaking-change
    # headline (and three others) could have its body emptied with the gate
    # green -- exactly the vacuity shape this Mission exists to eliminate.
    (
        "What Changed -- the breaking-change sentence itself",
        "a local tracker binding now requires a **recorded decision at one of "
        "two consent channels**, and **absence of both channels denies**.",
    ),
    (
        "How to Tell -- why sync doctor, not a tracker-side command",
        "the `spec-kitty tracker` command group is **conditionally registered** "
        "and does not exist at all unless hosted SaaS sync is armed on the machine",
    ),
    (
        "Which Commands Are Gated -- the four non-gated commands construct no connector",
        "construct no connector, run no subprocess, and reach no transport at all",
    ),
    (
        "A Recorded Decision Outlives Its Binding -- both values survive unbind alike",
        "both survive an `unbind` exactly the same way, so re-binding later does "
        "not silently reset your decision back to absence.",
    ),
)


def _normalize(text: str) -> str:
    """Collapse whitespace runs to single spaces so a markdown reflow cannot hide a phrase."""
    return " ".join(text.split())


def check_note_substance(text: str) -> None:
    """Assert every FR-013 load-bearing claim is present in *text*.

    Takes *text*, never a path, so this same checker can run against the real note, a synthetic
    renamed-heading copy, and a synthetic emptied-section copy. Collects every failure rather
    than stopping at the first, so a single failing run names everything that broke.
    """
    failures: list[str] = []

    for heading in _HEADINGS:
        if heading not in text:
            failures.append(f"missing or renamed heading: {heading!r}")

    normalized = _normalize(text)
    for label, phrase in _SUBSTANCE_PHRASES:
        if _normalize(phrase) not in normalized:
            failures.append(f"missing substance ({label}): {phrase!r}")

    assert not failures, "tracker-egress-refusal.md substance check failed:\n- " + "\n- ".join(failures)


# --------------------------------------------------------------------------- #
# T045.1 -- the note exists, and the index links it from both frontmatter and body
# --------------------------------------------------------------------------- #


def test_note_exists_at_its_pinned_path() -> None:
    assert _NOTE_PATH.is_file(), f"upgrade note not found at {_NOTE_PATH}"


def test_index_links_note_in_frontmatter_related_and_in_body() -> None:
    index_text = _INDEX_PATH.read_text(encoding="utf-8")
    parts = index_text.split("---", 2)
    assert len(parts) == 3, "docs/migrations/index.md must have a frontmatter block"
    frontmatter, body = parts[1], parts[2]

    assert "docs/migrations/tracker-egress-refusal.md" in frontmatter, (
        "index.md frontmatter `related:` list must list the upgrade note "
        "(docs/migrations/tracker-egress-refusal.md)"
    )
    # Review LOW-7: a bare-filename substring is satisfied by prose that merely
    # *names* the file with no markdown link around it, and the repo-wide
    # relative-link-fixer gate only catches *dead* links, never *missing* ones.
    # Assert the markdown link form itself, `](tracker-egress-refusal.md)`.
    assert "](tracker-egress-refusal.md)" in body, (
        "index.md body (Current 3.2 migrations) must link the upgrade note as a "
        "markdown link, not merely mention its filename"
    )


# --------------------------------------------------------------------------- #
# T045.2-4 -- substance + heading, against the real note. MUST PASS.
# --------------------------------------------------------------------------- #


def test_real_note_passes_the_full_substance_and_heading_check() -> None:
    text = _NOTE_PATH.read_text(encoding="utf-8")
    byte_count = len(text.encode("utf-8"))
    assertion_count = len(_HEADINGS) + len(_SUBSTANCE_PHRASES)
    print(
        f"INPUT COUNT: note is {byte_count} bytes; "
        f"{len(_HEADINGS)} heading checks + {len(_SUBSTANCE_PHRASES)} substance checks "
        f"= {assertion_count} assertions run"
    )
    assert byte_count > 0, "note file is empty -- a check against it would pass vacuously"
    assert assertion_count > 0, "no assertions configured -- a check against zero is vacuous"

    check_note_substance(text)


# --------------------------------------------------------------------------- #
# T045 red-first demonstration -- synthetic mutants, held only as strings here.
# Neither mutant ever touches the shipped note; both are built in-memory from
# the real file's own text.
# --------------------------------------------------------------------------- #


def test_check_reds_when_a_heading_is_renamed() -> None:
    """Renaming one stable heading must fail the check, even though every
    substance phrase in the body is completely untouched -- the "renamed" half
    of FR-013's "removed or renamed" requirement."""
    real = _NOTE_PATH.read_text(encoding="utf-8")
    target = "## The `map list` Split"
    assert target in real, "fixture precondition: heading must exist in the real note"

    mutated = real.replace(target, "## Provider-Scoped Command Behavior", 1)
    assert target not in mutated, "fixture did not actually rename the heading"

    with pytest.raises(AssertionError, match="missing or renamed heading") as excinfo:
        check_note_substance(mutated)

    # Review LOW-5: matching on the heading-axis message alone does not prove the
    # substance axis stayed silent -- this mutant would still pass that `match=`
    # if the substance axis had *also* fired. Assert independence by measurement:
    # renaming a heading must not touch the body, so zero substance failures.
    assert "missing substance" not in str(excinfo.value), (
        "renaming a heading must not also trip a substance failure -- the two "
        "axes are supposed to be independent"
    )


def test_check_reds_when_a_section_is_emptied() -> None:
    """Emptying a section's body while leaving its heading in place must also
    fail -- this is the whole point of the `#3030` FR-018 pattern: a check that
    only looks for the heading passes happily against an emptied section."""
    real = _NOTE_PATH.read_text(encoding="utf-8")
    heading = "## The `map list` Split"
    next_heading = "## A Typo Refuses"
    start = real.index(heading) + len(heading)
    end = real.index(next_heading)
    assert start < end, "fixture precondition: a non-empty section body must sit between the headings"

    mutated = real[:start] + "\n\nNothing to see here.\n\n" + real[end:]
    assert heading in mutated, "fixture must leave the heading itself untouched"
    assert "the gate follows the destination, not the subcommand name" not in mutated, (
        "fixture did not actually remove the section's load-bearing sentence"
    )

    with pytest.raises(AssertionError, match="missing substance") as excinfo:
        check_note_substance(mutated)

    # Review LOW-5: the mirror of the assertion above. Emptying a section's body
    # leaves every heading -- including this one -- untouched, so the heading
    # axis must report zero failures even though the substance axis reports
    # several (the three map-list phrases living in this section's body).
    assert "missing or renamed heading" not in str(excinfo.value), (
        "emptying a section's body must not also trip a heading failure -- its "
        "own heading, and every other heading, is left in place"
    )
