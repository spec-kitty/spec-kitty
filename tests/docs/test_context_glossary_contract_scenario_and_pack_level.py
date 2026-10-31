"""Standing guard for the two glossary claims of issue #6439.

Issue #6439 asks core's glossary for two things, and this module pins both so a
later edit cannot quietly undo them:

1. ``docs/context/governance.md``'s **Pack Level** entry and
   ``docs/context/charter.md``'s **Charter Pack** entry describe what a Charter
   Pack declares as a **level**, never a **tier**. The ADR the entry itself cites
   chose ``pack_level`` over ``pack_tier`` and rejected "tier" because it is
   overloaded (see ``docs/adr/4.x/2026-10-11-2-a-pack-declares-its-level-in-pack-yaml.md``,
   "Rejected"). ``kernel.pack_tiers`` is a module name and survives.
2. ``docs/context/charter.md`` defines **Contract Scenario** beside **Charter
   Pack**, with the four required rows, a ``Location`` row naming the scenario
   files' home, a ``Related terms`` row and a ``Do NOT use when`` guard that sends
   a reader to the acceptance scenarios, the conformance corpus and away from
   "BDD scenarios".

**Out of scope, deliberately.** The word "tier" has three other live senses in this
glossary that this guard must never assert against: the **Organization Tier** term
and the *Three-layer DRG* entry's own "tier" prose (``docs/context/charter.md``),
and "tiered rigour" in the charter. Only the pack-level sense is guarded here; do
not widen these probes to other entries.

**Non-vacuity.** Every absence probe below is paired, on the same fixture, with a
presence assertion proving the probe can see the entry at all (the slicer is
exercised against known neighbouring entries, and the Pack Level entry must still
name ``kernel.pack_tiers``). The tier probe strips inline code spans first, so the
authority name cannot red it — which is also why no allowlist exists here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO_ROOT = Path(__file__).resolve().parents[2]
CHARTER_PATH = REPO_ROOT / "docs" / "context" / "charter.md"
GOVERNANCE_PATH = REPO_ROOT / "docs" / "context" / "governance.md"

#: An inline code span. Stripped before the "tier" probe so `kernel.pack_tiers`
#: (the one authority for the three level names) cannot be mistaken for prose.
_CODE_SPAN_RE = re.compile(r"`[^`]*`")

#: The prose word this guard exists to keep out of the pack-level sense.
_TIER_RE = re.compile(r"(?i)\btiers?\b")

#: Required row labels for any context-glossary term
#: (``docs/context/glossary-conventions.md``, "Term Entry Schema").
_REQUIRED_ROWS: tuple[str, ...] = (
    "**Definition**",
    "**Context**",
    "**Status**",
    "**Applicable to**",
)

#: The rows issue #6439 additionally asks the new entry to carry: where the
#: scenario files live, the neighbouring terms, and the disambiguation guard.
_DISAMBIGUATION_ROWS: tuple[str, ...] = (
    "**Location**",
    "**Related terms**",
    "**Do NOT use when**",
)


def _page(path: Path) -> str:
    """Read one glossary page, failing loudly if it is not where we expect."""
    assert path.is_file(), f"glossary page is missing: {path}"
    return path.read_text(encoding="utf-8")


def _entry_body(text: str, heading: str) -> str:
    """Return the body of ``### <heading>`` up to the next rule or heading.

    Context-glossary entries are ``### Term`` headings followed by a table and a
    ``---`` rule. An empty string means the entry is absent (or the heading has no
    body), which the callers assert on explicitly.
    """
    lines = text.splitlines()
    marker = f"### {heading}"
    start: int | None = None
    for index, line in enumerate(lines):
        if line.strip() == marker:
            start = index
            break
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() == "---" or line.startswith("### "):
            break
        body.append(line)
    return "\n".join(body).strip()


def _prose(body: str) -> str:
    """Drop inline code spans, leaving only the prose a reader reads as prose."""
    return _CODE_SPAN_RE.sub("", body)


def _tier_words(body: str) -> list[str]:
    """Every "tier"/"tiers" occurrence left in the entry's prose."""
    return [match.group(0) for match in _TIER_RE.finditer(_prose(body))]


def _row_text(body: str, label: str) -> str:
    """The text of one table row (its label onwards), up to the next row."""
    start = body.find(label)
    if start < 0:
        return ""
    rest = body[start + len(label) :]
    return rest.split("\n| **", 1)[0].strip()


def _entry_titles(text: str) -> list[str]:
    """The ``### `` headings of a context-glossary page, in document order."""
    return [match.group(1).strip() for match in re.finditer(r"(?m)^###[ \t]+(.+?)[ \t]*$", text)]


@pytest.fixture(scope="module")
def charter_text() -> str:
    return _page(CHARTER_PATH)


@pytest.fixture(scope="module")
def governance_text() -> str:
    return _page(GOVERNANCE_PATH)


def test_entry_slicer_sees_known_neighbouring_entries(charter_text: str, governance_text: str) -> None:
    """Positive control: the slicer returns real bodies, so absence means absent.

    Without this, every "no tier" assertion below could pass because the slicer
    returned nothing at all.
    """
    for heading in ("Charter Pack", "Activation preset"):
        body = _entry_body(charter_text, heading)
        assert body, f"{CHARTER_PATH.name}: expected a body for '### {heading}'"
        assert "**Definition**" in body
    for heading in ("Pack Level", "Precedence Rule"):
        body = _entry_body(governance_text, heading)
        assert body, f"{GOVERNANCE_PATH.name}: expected a body for '### {heading}'"
        assert "**Definition**" in body


def test_pack_level_entry_still_names_the_level_authority(governance_text: str) -> None:
    """Positive control for the tier probe: the entry names `kernel.pack_tiers`.

    The authority lives inside an inline code span, so the absence probe below
    must strip code spans rather than the entry dropping the authority.
    """
    body = _entry_body(governance_text, "Pack Level")
    assert "kernel.pack_tiers" in body, f"{GOVERNANCE_PATH}: the Pack Level entry must still name kernel.pack_tiers as the one authority for the three level names"


def test_pack_level_entry_calls_a_pack_level_a_level(governance_text: str) -> None:
    """The Pack Level entry says a pack declares a level, never a tier (#6439).

    The probe is scoped to the entry's **definition**, where the pack-level claim
    lives. The other rows are excluded on purpose: a ``Related terms`` row may name
    the separate **Organization Tier** term, which is a different sense of the word
    and is not this guard's business.
    """
    body = _entry_body(governance_text, "Pack Level")
    assert body, f"{GOVERNANCE_PATH}: the Pack Level entry is missing"
    claim = _row_text(body, "**Definition**")
    assert claim, f"{GOVERNANCE_PATH}: the Pack Level entry has no definition row"
    offenders = _tier_words(claim)
    assert not offenders, (
        f"{GOVERNANCE_PATH}: the Pack Level entry calls a pack's level a {offenders[0]!r}. "
        "A pack declares a level; only the module name kernel.pack_tiers keeps the word."
    )


def test_charter_pack_entry_calls_a_pack_level_a_level(charter_text: str) -> None:
    """The Charter Pack entry restates the same claim; it must not say "tier".

    Scoped to its definition for the same reason as the Pack Level probe: the
    entry's ``Related terms`` row legitimately links **Organization Tier**.
    """
    body = _entry_body(charter_text, "Charter Pack")
    assert body, f"{CHARTER_PATH}: the Charter Pack entry is missing"
    claim = _row_text(body, "**Definition**")
    assert claim, f"{CHARTER_PATH}: the Charter Pack entry has no definition row"
    offenders = _tier_words(claim)
    assert not offenders, (
        f"{CHARTER_PATH}: the Charter Pack entry calls a pack's level a {offenders[0]!r}. It restates the Pack Level entry's claim and must use the same word."
    )


def test_contract_scenario_entry_sits_beside_charter_pack(charter_text: str) -> None:
    """Contract Scenario is defined, between Charter Pack and Activation preset."""
    titles = _entry_titles(charter_text)
    assert "Contract Scenario" in titles, (
        f"{CHARTER_PATH}: no '### Contract Scenario' entry. Issue #6439 asks core's glossary to define the Gherkin behavior half of the charter contract."
    )
    for neighbour in ("Charter Pack", "Activation preset"):
        assert neighbour in titles, f"{CHARTER_PATH}: the '{neighbour}' neighbour of Contract Scenario is missing; this test orders the entry beside it"
    positioned = titles.index("Contract Scenario")
    assert titles.index("Charter Pack") < positioned < titles.index("Activation preset"), (
        f"{CHARTER_PATH}: Contract Scenario must sit beside Charter Pack, between "
        f"'### Charter Pack' and '### Activation preset'; found it at index {positioned} "
        f"of {len(titles)} entries"
    )


def test_contract_scenario_entry_carries_the_required_rows(charter_text: str) -> None:
    """The new entry carries the schema's required rows and its guard rows."""
    body = _entry_body(charter_text, "Contract Scenario")
    assert body, f"{CHARTER_PATH}: the Contract Scenario entry has no body"
    for row in (*_REQUIRED_ROWS, *_DISAMBIGUATION_ROWS):
        # The label alone is not the row: `| **Status** | |` would satisfy a bare
        # membership check, so assert the cell after the label carries content.
        cell = _row_text(body, row).lstrip("|").strip()
        assert cell, f"{CHARTER_PATH}: the Contract Scenario entry is missing the {row} row or leaves it empty"


def test_contract_scenario_definition_states_what_it_names_and_calls(
    charter_text: str,
) -> None:
    """The definition says what a contract scenario names, calls and asserts."""
    body = _entry_body(charter_text, "Contract Scenario")
    for fact in ("Gherkin", "contracts/charter/openapi.yaml", "@contract", "@provisional"):
        assert fact in body, f"{CHARTER_PATH}: the Contract Scenario definition must name {fact!r}; it is the behavior half of the charter contract"
    assert "verifyAll" in body, f"{CHARTER_PATH}: the Contract Scenario definition must say that @contract scenarios run in verifyAll"


def test_contract_scenario_entry_names_its_home(charter_text: str) -> None:
    """The entry says where the scenario files live — the issue's "home" field.

    The files are in ``spec-kitty/spec-kitty-charter``, not in this repository, so
    the entry has to name the path rather than link it.
    """
    body = _entry_body(charter_text, "Contract Scenario")
    location = _row_text(body, "**Location**")
    assert "contracts/charter/scenarios/" in location, (
        f"{CHARTER_PATH}: the Contract Scenario entry must name its home 'contracts/charter/scenarios/' in spec-kitty-charter (found {location!r})"
    )
    for feature_file in ("action_context.feature", "errors.feature", "packs.feature"):
        assert feature_file in location, f"{CHARTER_PATH}: the Contract Scenario home must name {feature_file!r} as the file that carries the scenarios today"


def test_contract_scenario_guard_steers_to_the_neighbouring_terms(
    charter_text: str,
) -> None:
    """The Do NOT use when row sends the reader somewhere, not just away."""
    body = _entry_body(charter_text, "Contract Scenario")
    guard_row = _row_text(body, "**Do NOT use when**")
    assert guard_row, f"{CHARTER_PATH}: the Contract Scenario entry has no guard row"
    for alternate in ("BDD", "acceptance scenario", "conformance corpus"):
        assert alternate.lower() in guard_row.lower(), (
            f"{CHARTER_PATH}: the Contract Scenario guard must name {alternate!r} as the term a reader probably wants instead"
        )


def test_contract_scenario_entry_starts_as_a_candidate(charter_text: str) -> None:
    """A new term enters as `candidate` and is version-scoped like its neighbour.

    ``styleguide:kitty-glossary-writing`` makes the candidate-first rule explicit:
    the Human-in-Charge (HiC) promotes a term, not the author of the entry. The
    version scope matches the Charter Pack entry the term sits beside.
    """
    body = _entry_body(charter_text, "Contract Scenario")
    status = _row_text(body, "**Status**")
    assert "candidate" in status.lower(), (
        f"{CHARTER_PATH}: the Contract Scenario entry must enter as a candidate (found status row {status!r}); only the HiC promotes a term"
    )
    applicable = _row_text(body, "**Applicable to**")
    assert "4.x" in applicable, (
        f"{CHARTER_PATH}: the Contract Scenario entry must be scoped like the Charter Pack entry beside it (found applicable-to row {applicable!r})"
    )
