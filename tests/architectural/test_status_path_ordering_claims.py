"""Guard: the CLI status path is described as wall-clock ordered, never as Lamport.

Issue #6604. Since #4941 (PR #6261, ``spec-kitty-events`` 10.5.1) every CLI status
read reaches ONE fold, ``spec_kitty_events.diary.reduce_parsed``, which orders lane
transitions by the writer's ``at`` and then ``event_id``, with the approved-departure
lift. CLI lane rows carry no Lamport clock, and
``spec_kitty_events.status.reduce_status_events`` (the Lamport reducer) is not on the
CLI path.

Before #6604 a number of living pages, the agent guidelines and one docstring still
claimed the status path was Lamport-ordered (some of them also claimed two reducers
were in play, one Lamport and one wall clock). Those sentences were corrected, ADR
``2026-10-01-2`` was amended factually, and this module keeps the correction honest:
it fails if the retired wording returns to a covered living surface, and it fails if
the ADR amendment that records the current ordering is removed.

What it deliberately does NOT do:

* It does not ban the word ``Lamport``. Other event logs legitimately carry a Lamport
  value (``retrospective/lifecycle_events.py`` ticks a counter; ``decisions/emit.py``
  uses a line count as a proxy; ``kernel/clock.py`` explains how it differs). The
  corpus is bounded and the pattern targets the *status-path claim* only.
* It does not police ADR bodies. An ADR is a record: its original decision text stays
  as written and is superseded by a dated amendment. ADR ``2026-10-01-2`` therefore
  keeps "moves them onto the Lamport reducer" **and** must carry the amendment that
  says what the code does now. Both halves are asserted below.
* It does not scan historical trees (``docs/archive/``, ``docs/reports/``,
  ``research/``, ``kitty-specs/**``) - those are records, not claims about today.
* It does not scan ``docs/architecture/event-ledger-writers-and-readers.md`` either.
  That page is frozen in core (ADR 2026-10-29-1 D-9,
  ``tests/architectural/test_events_import_frozen.py``): it moves to
  ``spec-kitty/spec-kitty-events`` with its history, so its gap-table G-3 row has to
  be updated there, or here under the freeze's operator-approved re-pin route. A
  sweep of this page has to land through one of those two doors, not through a guard
  exception.

Non-vacuity is asserted too: the detector is fed a synthetic stale sentence (must
report exactly one violation) and a synthetic negated sentence (must report none), so
a detector that stops working cannot pass silently.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ``docs_scoped``: this test reads ``docs/`` content, so a docs-only PR could newly red
# it and it must run on the arch pole's docs-only trim (same rule as
# ``test_no_legacy_terminology``). No git subprocess, so no ``git_repo`` marker.
pytestmark = [pytest.mark.architectural, pytest.mark.docs_scoped]

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Living surfaces that describe today's read path. Every entry must exist: a covered
#: file that disappears or is renamed is a failure, never a silent skip - otherwise the
#: guard drains itself by attrition.
COVERED_PATHS: tuple[str, ...] = (
    "AGENTS.md",
    "docs/architecture/diagrams/01_context/README.md",
    "docs/architecture/diagrams/02_containers/README.md",
    "docs/architecture/status-model.md",
    "docs/plans/domains/api-dashboard-domain-plan.md",
    "src/specify_cli/consolidation/preflight.py",
)

#: The affirmative claim #6604 removed. A sentence containing this must also carry a
#: negation ("is not", "carry no", "never"), or it is asserting the retired fact.
AFFIRMATIVE_RE = re.compile(r"Lamport[\s_-]+(reducer|reduction|wrapper)", re.IGNORECASE)

#: Markers that make a sentence a *negation* of the claim rather than the claim. The
#: corrected ``status-model.md`` legitimately says "CLI lane rows carry no Lamport
#: clock, and the Lamport reducer ``reduce_status_events`` is not on the CLI path".
NEGATION_MARKERS: tuple[str, ...] = (
    "no ",
    "not ",
    "not\n",
    "never",
    "n't ",
    "NOT ",
    "None ",
)

#: Exact strings this mission removed, with the file each one lived in. They cannot
#: legitimately reappear anywhere in the corpus, so their absence is safe to pin. (Do
#: not add ADR-body sentences here: an ADR keeps its original wording.)
RETIRED_PHRASES: tuple[tuple[str, str], ...] = (
    (
        "owns the event ledger and the Lamport reducer",
        "01_context/README.md prose: the core owns the wall-clock status reducer",
    ),
    (
        "owns event ledger + Lamport reducer",
        "01_context/README.md mermaid node label",
    ),
    (
        "<b>Lamport reducer</b>",
        "02_containers/README.md mermaid node label",
    ),
    (
        "the Lamport reducer, the",
        "02_containers/README.md alt-text",
    ),
    (
        "The dashboard uses the Lamport reducer",
        "api-dashboard-domain-plan.md: both read surfaces reach the same fold",
    ),
    (
        "So two read surfaces can disagree today",
        "api-dashboard-domain-plan.md: one fold, so they cannot disagree about ordering",
    ),
    (
        "still call this the Lamport wrapper",
        "AGENTS.md: the consolidation docstrings were corrected in #6213",
    ),
    (
        "`#6213` tracks correcting them",
        "AGENTS.md: #6213 is closed; nothing is pending on the docstrings",
    ),
)

#: The ADR that owns the read API. Its body is history; its amendment is the claim.
READ_API_ADR_GLOB = "docs/adr/4.x/2026-10-01-2-*.md"
ADR_HISTORICAL_SENTENCE = "moves them onto the Lamport reducer"
ADR_AMENDMENT_HEADING = "## Amendment 2026-10-30 (Accepted)"
ADR_AMENDMENT_MARKERS: tuple[str, ...] = ("(at, event_id)", "lift", "#6609")

#: Where the surviving, narrower residual must stay visible.
RESIDUAL_PATH = "AGENTS.md"
RESIDUAL_MARKERS: tuple[str, ...] = ("non-approval", "clock be")
REMEDY = (
    "State the current fact instead: the status path is ordered by wall clock "
    "`(at, event_id)` with the approved-departure lift; `status.reducer.reduce` and "
    "`materialize_snapshot` both reach `spec_kitty_events.diary.reduce_parsed`; CLI lane "
    "rows carry no Lamport clock (ADR 2026-02-09-3 Amendment 2026-10-22)."
)

_SENTENCE_RE = re.compile(r"[^.!?\n]*(?:[.!?]+|$)")


def _normalize(text: str) -> str:
    """Collapse whitespace so a hard-wrapped sentence still matches a phrase."""
    return " ".join(text.split())


def _read(relative: str) -> str:
    path = REPO_ROOT / relative
    assert path.is_file(), (
        f"covered path is missing: {relative}. The guard's corpus shrank (or the file "
        "moved); update COVERED_PATHS deliberately instead of letting the guard pass on "
        "fewer files."
    )
    return path.read_text(encoding="utf-8")


def _violations(text: str) -> list[tuple[int, str]]:
    """Return ``(line_number, sentence)`` for every affirmative Lamport claim."""
    found: list[tuple[int, str]] = []
    for match in _SENTENCE_RE.finditer(text):
        sentence = match.group(0)
        if not AFFIRMATIVE_RE.search(sentence):
            continue
        if any(marker in sentence for marker in NEGATION_MARKERS):
            continue
        line_number = text.count("\n", 0, match.start()) + 1
        found.append((line_number, " ".join(sentence.split())))
    return found


def test_detector_flags_a_stale_sentence() -> None:
    """Non-vacuity: the detector must SEE the retired phrasing."""
    stale = "Spec Kitty Core owns the event ledger and the Lamport reducer for status."
    assert len(_violations(stale)) == 1


def test_detector_accepts_a_negated_sentence() -> None:
    """Non-vacuity: the corrected, negated phrasing must not trip the detector."""
    corrected = "CLI lane rows carry no Lamport clock, and the Lamport reducer `reduce_status_events` is not on the CLI path."
    assert _violations(corrected) == []


def test_detector_handles_line_wrapped_sentences() -> None:
    """A hard-wrapped paragraph is one sentence; wrapping must not hide the claim."""
    wrapped = "Spec Kitty Core owns the event ledger and the\nLamport reducer for status."
    assert len(_violations(wrapped)) == 1


def test_covered_corpus_is_not_empty() -> None:
    assert len(COVERED_PATHS) >= 5, "the guard must cover the living surfaces #6604 lists"
    for relative in COVERED_PATHS:  # every one must exist (assert inside _read)
        _read(relative)


def test_no_affirmative_lamport_status_path_claim() -> None:
    problems: list[str] = []
    for relative in COVERED_PATHS:
        for line_number, sentence in _violations(_read(relative)):
            problems.append(f"{relative}:{line_number}: {sentence}")
    assert not problems, "the CLI status path is described as Lamport-ordered again:\n  " + "\n  ".join(problems) + "\n" + REMEDY


def test_retired_phrases_are_gone() -> None:
    problems: list[str] = []
    for relative in COVERED_PATHS:
        text = _normalize(_read(relative))
        for phrase, why in RETIRED_PHRASES:
            if phrase in text:
                problems.append(f"{relative}: {phrase!r} is back ({why})")
    assert not problems, "\n".join(problems) + "\n" + REMEDY


def test_read_api_adr_keeps_history_and_records_the_amendment() -> None:
    matches = sorted(REPO_ROOT.glob(READ_API_ADR_GLOB))
    assert len(matches) == 1, f"expected exactly one read-API ADR, found {matches}"
    text = _normalize(matches[0].read_text(encoding="utf-8"))

    assert ADR_HISTORICAL_SENTENCE in text, (
        "the ADR's original D-5 sentence was rewritten. This record is corrected by a dated amendment, not by editing its history."
    )
    assert ADR_AMENDMENT_HEADING in text, (
        f"ADR {matches[0].name} is missing '{ADR_AMENDMENT_HEADING}'; the accepted current ordering (wall clock) is recorded there."
    )
    amendment = _normalize(text.split(ADR_AMENDMENT_HEADING, 1)[1])
    missing = [marker for marker in ADR_AMENDMENT_MARKERS if marker not in amendment]
    assert not missing, f"the ADR amendment does not record: {missing}"


def test_residual_stays_visible() -> None:
    residual = _normalize(_read(RESIDUAL_PATH))
    missing = [marker for marker in RESIDUAL_MARKERS if marker not in residual]
    assert not missing, (
        "AGENTS.md must keep the narrower, surviving residual (a non-approval transition "
        f"minted on a clock behind the event it follows sorts before it); missing {missing}. "
        "Deleting the caveat is not a fix for the retired claim."
    )
