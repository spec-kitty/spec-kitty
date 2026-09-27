"""Tests for the ADR header converter (Mission B WP05).

Proves the three header parsers (markdown-table, bold-inline, dash-bullet) each
extract ``title``/``status``/``date`` and leave the decision body verbatim, that
the emitter writes **bare** ``status`` (MADR vocabulary, never ``doc_status``),
and that the content-invariance check is **false-green-proof**: a one-byte body
mutation drives it RED.

Fixtures are realistic ADR-shaped documents with real dated filenames and real
header bytes. The dash-bullet fixture is shaped from the canonical real file
``docs/adr/3.x/2026-04-15-2-explicit-empty-charter-selections-remain-empty.md``
(the ``2.x/adr/`` path is a back-compat symlink into 3.x — never the fixture
source).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs import _inventory
from scripts.docs.adr_converter import (
    AdrParseError,
    body_minus_frontmatter,
    convert,
    invariant,
    parse_bold_inline_header,
    parse_dash_bullet_header,
    parse_header,
    parse_table_header,
    render_frontmatter,
)
from scripts.docs.adr_converter import _status_root

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Pure converter unit tests (no git/subprocess) — fast developer-loop shard.
pytestmark = pytest.mark.fast

# ---------------------------------------------------------------------------
# Realistic ADR-shaped fixtures — one per dialect.
# ---------------------------------------------------------------------------

# 46 of 117 ADRs use the markdown-table dialect.
# Shaped from docs/adr/3.x/2026-04-19-1-cli-auth-uses-...md
TABLE_ADR = """\
# CLI Auth Uses Browser-Mediated OAuth With Encrypted File-Only Session Storage

| Field | Value |
|---|---|
| Filename | `2026-04-19-1-cli-auth-uses-encrypted-file-only-session-storage.md` |
| Status | Accepted |
| Date | 2026-04-19 |
| Deciders | Spec Kitty Architecture Team |
| Supersedes | `2026-04-09-2-cli-saas-auth-is-browser-mediated-oauth-not-password.md` |

---

## Context and Problem Statement

The April 9 auth ADR made the correct high-level product call and the wrong
local persistence call.

## Decision

Encrypt the session file at rest; never persist tokens to the OS keyring.
"""

# 70 of 117 ADRs use the bold-inline dialect (the dominant format).
# Shaped from docs/adr/3.x/2026-06-02-2-letta-agent-skill-only-support.md
BOLD_ADR = """\
# Letta agent is skill-only: no slash-command templates

**Filename:** `2026-06-02-2-letta-agent-skill-only-support.md`

**Status:** Accepted

**Date:** 2026-06-02

**Deciders:** Spec Kitty core team

**Technical Story:** [GitHub #1054](https://github.com/Priivacy-ai/spec-kitty/issues/1054)

---

## Context and Problem Statement

Letta Code (`letta`) is a memory-first coding agent supporting headless
automation. The design spike (#1054) raised two questions.

## Decision

Letta is skill-only; no `.letta/commands/` slash-command templates are shipped.
"""

# 1 of 117 ADRs uses the dash-bullet dialect — the dialect the spec missed.
# Verbatim bytes from the canonical real file
# docs/adr/3.x/2026-04-15-2-explicit-empty-charter-selections-remain-empty.md
DASH_BULLET_ADR = """\
# ADR 2026-04-15-2: Explicit Empty Charter Selections Remain Empty

- Status: Accepted
- Date: 2026-04-15
- Decision Makers: Spec Kitty maintainers
- Supersedes: None
- Related: `/spec-kitty.charter`, charter interview/generation flow, doctrine selection

## Context

`spec-kitty charter generate` compiles a project charter from
`.kittify/charter/interview/answers.yaml`.

That interview schema includes explicit selection lists for:

- `selected_paradigms`
- `selected_directives`
- `available_tools`

## Decision

Explicit empty charter selections remain empty.
"""


# ---------------------------------------------------------------------------
# T027 — markdown-table parser.
# ---------------------------------------------------------------------------
def test_table_parser_extracts_fields_and_body() -> None:
    header = parse_table_header(TABLE_ADR)

    assert header.title == ("CLI Auth Uses Browser-Mediated OAuth With Encrypted File-Only Session Storage")
    assert header.status == "Accepted"
    assert header.date == "2026-04-19"
    # The table rows, the `---` rule, and surrounding blanks are header, not body.
    assert header.body.startswith("## Context and Problem Statement")
    assert "| Status | Accepted |" not in header.body


# ---------------------------------------------------------------------------
# T028 — bold-inline parser.
# ---------------------------------------------------------------------------
def test_bold_inline_parser_extracts_fields_and_body() -> None:
    header = parse_bold_inline_header(BOLD_ADR)

    assert header.title == "Letta agent is skill-only: no slash-command templates"
    assert header.status == "Accepted"
    assert header.date == "2026-06-02"
    assert header.body.startswith("## Context and Problem Statement")
    assert "**Status:**" not in header.body


# ---------------------------------------------------------------------------
# T029 — dash-bullet parser (the missed dialect) + its boundary rule.
# ---------------------------------------------------------------------------
def test_dash_bullet_parser_extracts_fields_and_body() -> None:
    header = parse_dash_bullet_header(DASH_BULLET_ADR)

    assert header.title == ("ADR 2026-04-15-2: Explicit Empty Charter Selections Remain Empty")
    assert header.status == "Accepted"
    assert header.date == "2026-04-15"
    # Boundary rule: top bullets are header; the body begins at `## Context`.
    assert header.body.startswith("## Context")
    assert "- Status: Accepted" not in header.body


def test_dash_bullet_body_bullets_are_body_not_header() -> None:
    # Bullets *inside* the body (after the heading) must survive in the body —
    # the boundary is the first non-bullet, non-blank line after the top block.
    header = parse_dash_bullet_header(DASH_BULLET_ADR)

    assert "- `selected_paradigms`" in header.body
    assert "- `available_tools`" in header.body


# ---------------------------------------------------------------------------
# T030 — frontmatter emitter (bare `status`, MADR vocabulary, never doc_status).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("adr", [TABLE_ADR, BOLD_ADR, DASH_BULLET_ADR])
def test_emitter_writes_bare_status_not_doc_status(adr: str) -> None:
    converted = convert(adr)

    assert converted.startswith("---\n")
    parsed = _inventory.parse_frontmatter(converted)
    # Bare `status` is the sanctioned ADR exception; `doc_status` is for pages.
    assert "status" in parsed
    assert "doc_status" not in parsed
    assert parsed["status"] == "Accepted"
    assert "title" in parsed
    assert "date" in parsed


def test_emitter_satisfies_ratchet_required_keys() -> None:
    # The anti-sprawl ratchet requires exactly these keys via the same parser.
    converted = convert(BOLD_ADR)
    parsed = _inventory.parse_frontmatter(converted)

    for key in ("title", "status", "date"):
        assert key in parsed


def test_render_frontmatter_emits_fenced_ordered_block() -> None:
    header = parse_bold_inline_header(BOLD_ADR)
    block = render_frontmatter(header)

    assert block.startswith("---\n")
    assert block.endswith("---\n")
    # title → status → date order, bare `status` key.
    assert block.index("title:") < block.index("status:") < block.index("date:")
    assert "doc_status" not in block


def test_emitter_canonicalises_madr_status_case() -> None:
    lowercase = BOLD_ADR.replace("**Status:** Accepted", "**Status:** accepted")
    parsed = _inventory.parse_frontmatter(convert(lowercase))

    assert parsed["status"] == "Accepted"


# ---------------------------------------------------------------------------
# T031 + T032 — content-invariance: green per dialect, RED on body mutation.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("name", "adr"),
    [("table", TABLE_ADR), ("bold", BOLD_ADR), ("dash-bullet", DASH_BULLET_ADR)],
)
def test_conversion_preserves_body_invariance(name: str, adr: str) -> None:
    converted = convert(adr)

    assert invariant(adr, converted), f"{name} dialect broke body invariance"


def test_mutation_fixture_drives_invariance_red() -> None:
    # Simulate a converter that altered one decision-body byte: invariance MUST
    # catch it. This is the false-green-proof — a re-render comparison would
    # pass on whitespace and miss this.
    converted = convert(BOLD_ADR)
    mutated = converted.replace("Letta is skill-only", "Letta is slash-command-only")

    assert mutated != converted  # the mutation actually landed
    assert not invariant(BOLD_ADR, mutated)


def test_whitespace_only_mutation_drives_invariance_red() -> None:
    # Locks the *raw-byte* (non-normalised) contract per NFR-001 / spec T031
    # ("A re-render comparison is a false-green — assert raw bytes"). A word-swap
    # mutation alone cannot distinguish a raw-byte ``==`` from a whitespace-
    # normalised compare. This fixture differs from the converted output by
    # whitespace ONLY (a doubled space in the Decision body), so it is caught by
    # raw-byte ``==`` (RED) but MISSED by a ``.split()``/normalised compare
    # (GREEN). It therefore fails if someone weakens ``invariant()`` to normalise.
    converted = convert(BOLD_ADR)
    mutated = converted.replace("skill-only; no", "skill-only;  no")

    assert mutated != converted  # the whitespace-only mutation actually landed
    # Same non-whitespace tokens — only the spacing differs. A normalised compare
    # would treat these as equal; raw-byte invariance must not.
    assert mutated.split() == converted.split()
    assert not invariant(BOLD_ADR, mutated)


def test_invariance_reuses_inventory_parse_frontmatter() -> None:
    # The post-image strip delegates the "is this frontmatter?" judgment to the
    # canonical inventory parser: a post-image whose frontmatter that parser
    # rejects (empty mapping) must raise, not silently treat the page as body.
    not_frontmatter = "## Context\n\nNo frontmatter fence here.\n"
    assert _inventory.parse_frontmatter(not_frontmatter) == {}

    with pytest.raises(AdrParseError):
        body_minus_frontmatter(not_frontmatter)


# ---------------------------------------------------------------------------
# T032 — malformed input surfaces a clear error (no silent status-less emit).
# ---------------------------------------------------------------------------
def test_status_less_header_raises_clear_error() -> None:
    status_less = """\
# Some ADR Without A Status

**Date:** 2026-06-02

## Context

Body text.
"""
    with pytest.raises(AdrParseError, match="Status"):
        parse_header(status_less)


def test_non_madr_status_raises_clear_error() -> None:
    bogus = BOLD_ADR.replace("**Status:** Accepted", "**Status:** Ratified")

    with pytest.raises(AdrParseError, match="MADR"):
        parse_header(bogus)


def test_titleless_input_raises_clear_error() -> None:
    titleless = "**Status:** Accepted\n\n**Date:** 2026-06-02\n\n## Context\n"

    with pytest.raises(AdrParseError, match="title"):
        parse_header(titleless)


# ===========================================================================
# WP05 CYCLE 3 — two more live dialects + status aliases + Date-from-filename.
#
# Real-data execution (WP06) hard-failed on 32/117 ADRs the cycle-2 census
# missed: 26 colon-OUTSIDE-bold, 1 dash+bold hybrid, several qualified MADR
# status values, and 2 era-less files with a broken/absent Date header. These
# fixtures are shaped from those real ADR header bytes.
# ===========================================================================

# 26 of 117 ADRs use the colon-OUTSIDE-bold dialect (``**Status**: X``). The
# cycle-2 bold parser only matched the colon-INSIDE form (``**Status:** X``).
# Shaped from docs/adr/3.x/2026-06-03-2-executioncontext-owner-and-committarget.md
BOLD_OUTSIDE_ADR = """\
# ADR 2026-06-03-2: ExecutionContext Owner and CommitTarget Atomicity

**Date**: 2026-06-03
**Status**: Accepted
**Mission**: `execution-state-domain-remediation-01KT6HVH`
**Issues**: [#1619](https://github.com/Priivacy-ai/spec-kitty/issues/1619)

## Context

Two related structural decisions are needed before implementation WPs can begin.

## Decision

`ExecutionContext` owns the commit target; `CommitTarget` is the final step.
"""

# 1 of 117 ADRs uses the dash+bold hybrid (``- **Status:** X``). The dash-bullet
# line wraps the field in bold.
# Shaped from docs/adr/3.x/2026-05-18-1-monorepo-charter-scope.md
DASH_BOLD_ADR = """\
# ADR-8: Monorepo charter scope via `CharterScope` abstraction

- **Status:** Accepted
- **Date:** 2026-05-18
- **Mission:** `slice-f-multi-context-extensibility-01KRX5C8` / WP09 (axis 2)
- **Issue:** [#522](https://github.com/Priivacy-ai/spec-kitty/issues/522)

---

## Context

Slice F lifts spec-kitty's governance surface beyond a single repository.

## Decision

A monorepo ships multiple charters scoped by the mission's filesystem location.
"""

# Broken-Date era-less ADR: the ``**Date:**`` header sits AFTER a revision-log
# block, so field consumption stops at the ``- rev 1`` bullet before reaching it.
# The status value is double-bold-wrapped and em-dash-qualified.
# Shaped from docs/adr/3.x/2026-05-12-1-wp03-review-mode-contract-PROPOSED.md
BROKEN_DATE_ADR = """\
# PROPOSAL: `spec-kitty review` lightweight vs post-merge mode contract (WP03)

**Filename:** `2026-05-12-1-wp03-review-mode-contract-PROPOSED.md`

**Status:** **Proposed — awaiting HiC review (revision 2: 2026-05-12).** Do not implement until HiC approves all open sub-questions.

**Revision log:**
- rev 1 (2026-05-12 AM): initial proposal, three open sub-questions.
- rev 2 (2026-05-12 PM): HiC resolved Q1 and Q3. Q2 remains open.

**Date:** 2026-05-12

**Deciders:** Architect Alphonso (proposer), HiC (final decision)

## Context

The review command needs a clear lightweight-vs-post-merge mode contract.
"""

# Absent-Date ADR: no ``Date`` header at all (only a ``<DATE> (to be filled)``
# body placeholder); the status carries a parenthetical deferral qualifier.
# Shaped from docs/adr/3.x/2026-05-18-2-delete-specify-cli-auth-transport.md
ABSENT_DATE_ADR = """\
# ADR 2026-05-18-2 — DELETE specify_cli.auth.transport (deferred to Robert)

**Status:** Accepted (DELETE recommended; deferred for execution to lead maintainer Robert)
**Decision driver:** Post-Mission-B architectural review, HIGH-3 finding
**HiC adjudication:** 2026-05-18 §5a.3 (verbatim binding via C-005)

---

## Context

`src/specify_cli/auth/transport.py` ships but has zero non-test callers.

## Decision

Delete the module. Decided on `<DATE> (to be filled)` pending Robert.
"""


# ---------------------------------------------------------------------------
# Cycle 3 — colon-OUTSIDE-bold dialect.
# ---------------------------------------------------------------------------
def test_bold_outside_parser_extracts_fields_and_body() -> None:
    header = parse_bold_inline_header(BOLD_OUTSIDE_ADR)

    assert header.title == ("ADR 2026-06-03-2: ExecutionContext Owner and CommitTarget Atomicity")
    assert header.status == "Accepted"
    assert header.date == "2026-06-03"
    assert header.body.startswith("## Context")
    assert "**Status**: Accepted" not in header.body


def test_bold_outside_dialect_autodetects_and_converts() -> None:
    converted = convert(BOLD_OUTSIDE_ADR)
    parsed = _inventory.parse_frontmatter(converted)

    assert parsed["status"] == "Accepted"
    assert parsed["date"] == "2026-06-03"
    assert invariant(BOLD_OUTSIDE_ADR, converted)


def test_bold_outside_body_status_line_is_not_consumed_as_header() -> None:
    # A ``**Status**:`` line deep in the body (after a heading) is prose, not the
    # header field: consumption stops at ``## Context`` long before it.
    adr = BOLD_OUTSIDE_ADR.replace(
        "the final step.",
        "the final step.\n\n**Status**: `CommitTarget` is Strangler step 7.",
    )
    header = parse_header(adr)

    assert header.status == "Accepted"  # the real header, not the body line
    assert "**Status**: `CommitTarget`" in header.body


# ---------------------------------------------------------------------------
# Cycle 3 — dash+bold hybrid dialect.
# ---------------------------------------------------------------------------
def test_dash_bold_parser_extracts_fields_and_body() -> None:
    header = parse_dash_bullet_header(DASH_BOLD_ADR)

    assert header.title == ("ADR-8: Monorepo charter scope via `CharterScope` abstraction")
    assert header.status == "Accepted"
    assert header.date == "2026-05-18"
    assert header.body.startswith("## Context")
    assert "- **Status:** Accepted" not in header.body


def test_dash_bold_dialect_autodetects_and_converts() -> None:
    converted = convert(DASH_BOLD_ADR)
    parsed = _inventory.parse_frontmatter(converted)

    assert parsed["status"] == "Accepted"
    assert parsed["date"] == "2026-05-18"
    assert invariant(DASH_BOLD_ADR, converted)


# ---------------------------------------------------------------------------
# Cycle 3 — status-normalization alias table (explicit + auditable).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Accepted, qualifier-stripped to the MADR root (sanctioned derivation).
        ("Accepted (amended 2026-02-18)", "Accepted"),
        ("Accepted (DELETE recommended; deferred for execution)", "Accepted"),
        ("Accepted (design) — implementation tracked under mission X", "Accepted"),
        ("Accepted — implemented by mission `write-surface-coherence`", "Accepted"),
        # Proposed, qualifier-stripped to the MADR root.
        ("Proposed (mission `retrospective-durable-home-01KVYM1W`, #2119)", "Proposed"),
        ("Proposed — awaiting HiC review (revision 2: 2026-05-12).", "Proposed"),
        ("**Proposed — awaiting HiC review (revision 2: 2026-05-12).**", "Proposed"),
    ],
)
def test_alias_table_strips_qualifiers_to_madr_root(raw: str, expected: str) -> None:
    adr = BOLD_ADR.replace("**Status:** Accepted", f"**Status:** {raw}")
    parsed = _inventory.parse_frontmatter(convert(adr))

    assert parsed["status"] == expected


def test_alias_amended_superseded_is_explicit_superseded() -> None:
    # OPERATOR-ADJUDICATED: "Amended — the original … is superseded by …" → the
    # MADR terminal state is Superseded. The stripped root ("Amended") is NOT an
    # MADR word, so this is an EXPLICIT alias-table entry, never a silent guess.
    raw = "Amended — the original *hard-fail* decision is **superseded** by the fallback policy below"
    adr = BOLD_OUTSIDE_ADR.replace("**Status**: Accepted", f"**Status**: {raw}")
    parsed = _inventory.parse_frontmatter(convert(adr))

    assert parsed["status"] == "Superseded"
    # C-002: the "amended" provenance prose is preserved verbatim in the body —
    # the alias only touches the frontmatter status value.
    assert invariant(adr, convert(adr))


def test_alias_partially_superseded_is_explicit_superseded() -> None:
    # OPERATOR-ADJUDICATED: MADR has no "partial" state; "Partially superseded"
    # → Superseded, with the partial-scope nuance preserved verbatim in the body.
    adr = TABLE_ADR.replace("| Status | Accepted |", "| Status | Partially superseded |")
    parsed = _inventory.parse_frontmatter(convert(adr))

    assert parsed["status"] == "Superseded"
    assert invariant(adr, convert(adr))


def test_status_root_recovers_madr_word() -> None:
    # The derivation helper is auditable in isolation.
    assert _status_root("Accepted (amended 2026-02-18)") == "Accepted"
    assert _status_root("Accepted (design) — tracked under mission X") == "Accepted"
    assert _status_root("Proposed — awaiting review (rev 2)") == "Proposed"
    assert _status_root("**Proposed — awaiting review.**") == "Proposed"
    # Non-MADR roots survive intact so the alias table / fail-closed can decide.
    assert _status_root("Amended — superseded by Y") == "Amended"
    assert _status_root("Partially superseded") == "Partially superseded"


def test_unmappable_qualified_status_still_hard_errors() -> None:
    # Fail-closed preserved: a qualified value whose root is neither MADR nor a
    # reviewed alias still raises — the alias table is not a silent catch-all.
    adr = BOLD_OUTSIDE_ADR.replace("**Status**: Accepted", "**Status**: Ratified (board vote 2026-06-01)")
    with pytest.raises(AdrParseError, match="MADR"):
        convert(adr)


# ---------------------------------------------------------------------------
# Cycle 3 — Date-from-filename fallback (broken header + absent Date).
# ---------------------------------------------------------------------------
def test_date_derived_from_filename_when_header_broken() -> None:
    # The ``**Date:**`` header sits after the revision-log block, so it is never
    # consumed as a field. The filename's date prefix is the fallback.
    filename = "docs/adr/3.x/2026-05-12-1-wp03-review-mode-contract-PROPOSED.md"
    converted = convert(BROKEN_DATE_ADR, filename=filename)
    parsed = _inventory.parse_frontmatter(converted)

    assert parsed["date"] == "2026-05-12"
    assert parsed["status"] == "Proposed"
    assert invariant(BROKEN_DATE_ADR, converted, filename=filename)


def test_date_derived_from_filename_when_header_absent() -> None:
    # No ``Date`` header at all — only a ``<DATE> (to be filled)`` body
    # placeholder. The filename prefix supplies the date.
    filename = "docs/adr/3.x/2026-05-18-2-delete-specify-cli-auth-transport.md"
    converted = convert(ABSENT_DATE_ADR, filename=filename)
    parsed = _inventory.parse_frontmatter(converted)

    assert parsed["date"] == "2026-05-18"
    assert parsed["status"] == "Accepted"  # alias-stripped from the deferral note
    assert invariant(ABSENT_DATE_ADR, converted, filename=filename)


def test_real_date_header_wins_over_filename() -> None:
    # The fallback is a fallback: a present ``Date`` header is authoritative even
    # when the filename carries a (different) date prefix.
    filename = "docs/adr/3.x/2099-01-01-1-some-slug.md"
    header = parse_header(BOLD_ADR, filename=filename)

    assert header.date == "2026-06-02"  # from the header, not the 2099 filename


def test_absent_date_without_filename_hard_errors() -> None:
    # No header Date and no filename → fail-closed, never a status-less / dateless
    # silent emit.
    with pytest.raises(AdrParseError, match="Date"):
        convert(ABSENT_DATE_ADR)
